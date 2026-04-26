"""
INE（上海国际能源交易中心）历史日K线数据导入工具

将 ai/data/ine/ 目录下的 Excel 文件导入到 vnpy 数据库

修复说明：
- 原来按文件逐个保存，导致同一合约的不同日期数据分布在不同文件时互相覆盖
- 现在改为：先汇总所有文件的数据，按 (symbol, date) 去重，再一次性保存

使用方法：
    # 先测试导入3条
    uv run python ai/data_process/import_ine.py --test --limit 3

    # 测试全部导入（前100条）
    uv run python ai/data_process/import_ine.py --test --limit 100

    # 全部导入（覆盖已有数据）
    uv run python ai/data_process/import_ine.py --force

    # 导入指定年份
    uv run python ai/data_process/import_ine.py --year 2026 --force
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData


# INE 交易所代码
INE_EXCHANGE = Exchange.INE


def get_all_excel_files(data_dir: Path, year: int = None) -> list:
    """获取所有 Excel 文件"""
    if year:
        pattern = f"*{year}*.xls*"
        files = list(data_dir.glob(pattern))
    else:
        files = sorted(data_dir.glob("*.xls*"))
    return files


def read_excel_file(filepath: Path, limit: int = None) -> pd.DataFrame:
    """读取 Excel 文件，处理不同年份的列名差异"""
    df = pd.read_excel(filepath, header=2)
    
    # 跳过英文标题行
    df = df[df['合约'].astype(str) != 'Contract']
    
    # 处理列名差异
    # 2022/2023: 日期, 成交金额
    # 2024+: 交易日期, 成交金额(万元)
    column_mapping = {}
    for col in df.columns:
        if col == '日期':
            column_mapping[col] = '交易日期'
        elif col == '成交金额' and '成交金额(万元)' not in df.columns:
            column_mapping[col] = '成交金额(万元)'
    
    df = df.rename(columns=column_mapping)
    
    # 限制行数
    if limit:
        df = df.head(limit)
    
    return df


def parse_date(date_val) -> datetime:
    """解析日期"""
    if isinstance(date_val, str):
        return datetime.strptime(date_val.strip(), "%Y%m%d")
    elif isinstance(date_val, (int, float)):
        return datetime.strptime(str(int(date_val)), "%Y%m%d")
    elif hasattr(date_val, 'strftime'):
        return date_val
    else:
        return None


def df_to_bars(df: pd.DataFrame) -> list:
    """将 DataFrame 转换为 BarData 列表"""
    bars = []
    current_symbol = None
    
    for _, row in df.iterrows():
        try:
            symbol = str(row['合约']).strip()
            if not symbol or symbol == 'nan':
                symbol = current_symbol  # 使用前一个合约代码
            else:
                current_symbol = symbol
            
            if not symbol or symbol == 'nan':
                continue
            
            # 解析日期
            trade_date = parse_date(row['交易日期'])
            if not trade_date:
                continue
            
            # 解析价格数据
            open_price = pd.to_numeric(row['开盘价'], errors='coerce')
            high_price = pd.to_numeric(row['最高价'], errors='coerce')
            low_price = pd.to_numeric(row['最低价'], errors='coerce')
            close_price = pd.to_numeric(row['收盘价'], errors='coerce')
            volume = pd.to_numeric(row['成交量'], errors='coerce')
            turnover = pd.to_numeric(row['成交金额(万元)'], errors='coerce')
            open_interest = pd.to_numeric(row['持仓量'], errors='coerce')
            
            # 处理 NaN 值
            if pd.isna(open_price):
                open_price = close_price if not pd.isna(close_price) else 0
            if pd.isna(high_price):
                high_price = max(open_price, close_price) if close_price else open_price
            if pd.isna(low_price):
                low_price = min(open_price, close_price) if close_price else open_price
            if pd.isna(close_price):
                continue  # 收盘价必须有效
            
            if pd.isna(volume):
                volume = 0
            if pd.isna(turnover):
                turnover = 0
            else:
                turnover = turnover * 10000  # 万元转元
            if pd.isna(open_interest):
                open_interest = 0
            
            bar = BarData(
                symbol=symbol,
                exchange=INE_EXCHANGE,
                interval=Interval.DAILY,
                datetime=trade_date,
                open_price=float(open_price),
                high_price=float(high_price),
                low_price=float(low_price),
                close_price=float(close_price),
                volume=float(volume),
                turnover=float(turnover),
                open_interest=float(open_interest),
                gateway_name="DB",
            )
            bars.append(bar)
        except Exception as e:
            continue
    
    return bars


def deduplicate_bars(bars: list) -> list:
    """
    按 (symbol, date) 去重，保留每组第一条记录
    """
    seen = {}  # (symbol, date) -> bar
    
    for bar in bars:
        key = (bar.symbol, bar.datetime.date())
        if key not in seen:
            seen[key] = bar
    
    return list(seen.values())


def import_ine_data(
    test: bool = False,
    limit: int = None,
    force: bool = False,
    year: int = None,
) -> dict:
    """
    导入 INE 数据
    """
    data_dir = Path(__file__).parent.parent / "data" / "ine"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return {}
    
    files = get_all_excel_files(data_dir, year)
    if not files:
        print(f"❌ 未找到 Excel 文件")
        return {}
    
    print(f"📂 找到 {len(files)} 个 Excel 文件")
    for f in files:
        print(f"   - {f.name}")
    print()
    
    db = get_database()
    stats = {"total": 0, "success": 0, "error": 0}
    all_bars = []
    
    for excel_file in files:
        print(f"📖 读取 {excel_file.name}...")
        
        try:
            df = read_excel_file(excel_file, limit)
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
            stats["error"] += 1
            continue
        
        print(f"   读取到 {len(df)} 行")
        
        bars = df_to_bars(df)
        print(f"   转换得到 {len(bars)} 根K线")
        
        if test:
            print(f"   🧪 测试模式，只显示前3条:")
            for bar in bars[:3]:
                print(f"      {bar.symbol}: {bar.datetime.date()} O={bar.open_price:.2f} H={bar.high_price:.2f} L={bar.low_price:.2f} C={bar.close_price:.2f} V={bar.volume:.0f}")
            print()
            continue
        
        all_bars.extend(bars)
        stats["total"] += len(bars)
    
    if test:
        return stats
    
    # ==========================================================
    # 关键修复：去重后再保存
    # ==========================================================
    print(f"\n📊 汇总完成，开始去重...")
    original_count = len(all_bars)
    all_bars = deduplicate_bars(all_bars)
    stats["total"] = len(all_bars)
    print(f"   去重前: {original_count} 条, 去重后: {len(all_bars)} 条")
    
    print(f"\n📊 开始写入数据库...")
    saved = save_bars(db, all_bars, force)
    stats["success"] = saved
    
    return stats


def save_bars(db, bars: list, force: bool = False) -> int:
    """保存 K 线数据"""
    if not bars:
        return 0
    
    try:
        # 按合约分组
        bars_by_symbol = defaultdict(list)
        for bar in bars:
            bars_by_symbol[bar.symbol].append(bar)
        
        total_saved = 0
        for symbol, symbol_bars in sorted(bars_by_symbol.items()):
            if force:
                # 查询已有数据
                existing = db.load_bar_data(
                    symbol,
                    INE_EXCHANGE,
                    Interval.DAILY,
                    datetime(2000, 1, 1),
                    datetime(2100, 12, 31)
                )
                
                # 合并
                existing_dates = {bar.datetime.date() for bar in existing}
                bars_to_save = list(existing)
                
                for bar in symbol_bars:
                    if bar.datetime.date() not in existing_dates:
                        bars_to_save.append(bar)
                        existing_dates.add(bar.datetime.date())
                
                if existing:
                    print(f"      覆盖 {symbol}: 已有{len(existing)}条, 新增{len(symbol_bars)}条, 合并后{len(bars_to_save)}条")
                else:
                    print(f"      新增 {symbol}: 写入{len(symbol_bars)}条")
            else:
                bars_to_save = symbol_bars
                print(f"      新增 {symbol}: 写入{len(symbol_bars)}条")
            
            db.save_bar_data(bars_to_save)
            total_saved += len(symbol_bars)
        
        return total_saved
    except Exception as e:
        print(f"      ❌ 保存失败: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="INE 历史数据导入工具")
    parser.add_argument("--test", action="store_true", help="测试模式（只显示不保存）")
    parser.add_argument("--limit", type=int, default=None, help="限制导入条数（测试用）")
    parser.add_argument("--force", action="store_true", help="覆盖已有数据")
    parser.add_argument("--year", type=int, default=None, help="指定年份（如2026）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📥 INE（上海国际能源交易中心）日K线数据导入工具")
    print("   (修复版：先汇总去重，再保存)")
    print("=" * 60)
    print()
    
    if args.test:
        print("🧪 测试模式：不实际写入数据库")
        print()
    
    if args.limit:
        print(f"📊 限制条数: {args.limit}")
        print()
    
    if args.force:
        print("⚠️ 覆盖模式：会覆盖已有数据")
        print()
    
    if args.year:
        print(f"📅 指定年份: {args.year}")
        print()
    
    stats = import_ine_data(
        test=args.test,
        limit=args.limit,
        force=args.force,
        year=args.year,
    )
    
    if stats:
        print()
        print("=" * 60)
        print("📊 导入统计")
        print("=" * 60)
        print(f"   总记录数: {stats['total']}")
        print(f"   成功写入: {stats['success']}")
        print(f"   错误: {stats['error']}")


if __name__ == "__main__":
    main()
