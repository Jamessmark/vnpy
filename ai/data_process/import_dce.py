"""
DCE（大商所）历史日K线数据导入工具

将 ai/data/dce/ 目录下的 Excel 文件导入到 vnpy 数据库

修复说明：
- 原来按文件逐个保存，导致同一合约的不同日期数据分布在不同文件时互相覆盖
- 现在改为：先汇总所有文件的数据，按 (symbol, date) 去重，再一次性保存

使用方法：
    # 先测试导入
    uv run python ai/data_process/import_dce.py --test --limit 3

    # 全部导入（覆盖已有数据）
    uv run python ai/data_process/import_dce.py --force

    # 导入指定年份
    uv run python ai/data_process/import_dce.py --year 2024 --force
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData


# DCE 交易所代码
DCE_EXCHANGE = Exchange.DCE


def get_all_excel_files(data_dir: Path, year: int = None) -> list:
    """获取所有 Excel 文件"""
    if year:
        year_dir = data_dir / f"allVarietyFtr-{year}"
        if year_dir.exists():
            files = sorted(year_dir.glob("*_ftr.xlsx"))
        else:
            print(f"⚠️ 目录不存在: {year_dir}")
            # 尝试从各年份目录中筛选
            files = []
            for d in data_dir.iterdir():
                if d.is_dir() and str(year) in d.name:
                    files.extend(sorted(d.glob("*_ftr.xlsx")))
    else:
        # 收集所有年份目录（含期货和期权）
        files = []
        for d in sorted(data_dir.iterdir()):
            if d.is_dir() and "allVariety" in d.name:
                files.extend(sorted(d.glob("*.xlsx")))
    return files


def parse_number(val) -> float:
    """解析带逗号的数字"""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s in ('-', ''):
        return 0.0
    # 移除逗号
    s = s.replace(',', '')
    try:
        return float(s)
    except:
        return 0.0


def parse_date(date_val) -> datetime:
    """解析日期"""
    if isinstance(date_val, str):
        s = date_val.strip()
        if len(s) == 8:
            return datetime.strptime(s, "%Y%m%d")
    elif isinstance(date_val, (int, float)):
        return datetime.strptime(str(int(date_val)), "%Y%m%d")
    elif hasattr(date_val, 'strftime'):
        return date_val
    return None


def excel_to_bars(filepath: Path, limit: int = None) -> list:
    """读取 Excel 文件并转换为 BarData 列表"""
    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
        return []
    
    # 限制行数
    if limit:
        df = df.head(limit)
    elif limit is None:
        pass  # 读取全部
    
    bars = []
    for _, row in df.iterrows():
        try:
            # 获取合约代码
            symbol = str(row.get('合约名称', '')).strip()
            if not symbol or symbol == 'nan':
                continue
            
            # 解析日期
            trade_date = parse_date(row.get('交易日期'))
            if not trade_date:
                continue
            
            # 解析价格数据
            open_price = parse_number(row.get('开盘价'))
            high_price = parse_number(row.get('最高价'))
            low_price = parse_number(row.get('最低价'))
            close_price = parse_number(row.get('收盘价'))
            volume = parse_number(row.get('成交量'))
            turnover = parse_number(row.get('成交额'))
            open_interest = parse_number(row.get('持仓量'))
            
            # 处理无效价格
            if close_price == 0:
                continue
            
            # 补齐 OHL
            if open_price == 0:
                open_price = close_price
            if high_price == 0:
                high_price = max(open_price, close_price)
            if low_price == 0:
                low_price = min(open_price, close_price)
            
            bar = BarData(
                symbol=symbol,
                exchange=DCE_EXCHANGE,
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


def import_dce_data(
    test: bool = False,
    limit: int = None,
    force: bool = False,
    year: int = None,
) -> dict:
    """导入 DCE 数据"""
    data_dir = Path(__file__).parent.parent / "data" / "dce"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return {}
    
    files = get_all_excel_files(data_dir, year)
    if not files:
        print(f"❌ 未找到 Excel 文件")
        return {}
    
    print(f"📂 找到 {len(files)} 个 Excel 文件")
    for f in files[:10]:
        print(f"   - {f.parent.name}/{f.name}")
    if len(files) > 10:
        print(f"   ... 还有 {len(files) - 10} 个文件")
    print()
    
    db = get_database()
    stats = {"total": 0, "success": 0, "error": 0}
    all_bars = []
    
    for excel_file in files:
        year_dir = excel_file.parent.name
        print(f"📖 读取 {year_dir}/{excel_file.name}...")
        
        bars = excel_to_bars(excel_file, limit)
        if not bars:
            print(f"   ⚠️ 无有效数据")
            continue
        
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
                    DCE_EXCHANGE,
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
    parser = argparse.ArgumentParser(description="DCE 历史数据导入工具")
    parser.add_argument("--test", action="store_true", help="测试模式（只显示不保存）")
    parser.add_argument("--limit", type=int, default=None, help="限制每个文件导入条数（测试用）")
    parser.add_argument("--force", action="store_true", help="覆盖已有数据")
    parser.add_argument("--year", type=int, default=None, help="指定年份（如2024）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📥 DCE（大商所）日K线数据导入工具")
    print("   (修复版：先汇总去重，再保存)")
    print("=" * 60)
    print()
    
    if args.test:
        print("🧪 测试模式：不实际写入数据库")
        print()
    
    if args.limit:
        print(f"📊 限制每文件条数: {args.limit}")
        print()
    
    if args.force:
        print("⚠️ 覆盖模式：会覆盖已有数据")
        print()
    
    if args.year:
        print(f"📅 指定年份: {args.year}")
        print()
    
    stats = import_dce_data(
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
