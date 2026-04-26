"""
广期所(广州期货交易所)历史日K线数据导入工具

将 ai/data/gfex/ 目录下的 CSV 文件导入到 vnpy 数据库

修复说明：
- 原来按文件逐个保存，导致同一合约的不同日期数据分布在不同文件时互相覆盖
- 现在改为：先汇总所有文件的数据，按 (symbol, date) 去重，再一次性保存

使用方法：
    # 先测试导入3条
    uv run python ai/data_process/import_gfex.py --test --limit 3

    # 测试全部导入（前100条）
    uv run python ai/data_process/import_gfex.py --test --limit 100

    # 全部导入（覆盖已有数据）
    uv run python ai/data_process/import_gfex.py --force

    # 导入指定年份
    uv run python ai/data_process/import_gfex.py --year 2026 --force
"""

import argparse
from collections import defaultdict
import csv
from datetime import datetime
from pathlib import Path

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData


# 广期所交易所代码
GFEX_EXCHANGE = Exchange.GFEX

# CSV 列索引
COL_DATE = 0       # 交易日期
COL_CODE = 3       # 合约代码
COL_OPEN = 4       # 开盘价
COL_HIGH = 5       # 最高价
COL_LOW = 6        # 最低价
COL_CLOSE = 7      # 收盘价
COL_SETTLE = 8    # 结算价
COL_VOLUME = 11    # 成交量
COL_OI = 12       # 持仓量
COL_TURNOVER = 13 # 成交额


def parse_date(date_str: str) -> datetime:
    """解析日期字符串"""
    return datetime.strptime(date_str, "%Y%m%d")


def read_csv_file(filepath: Path, limit: int = None) -> list:
    """读取CSV文件"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # 跳过第一行标题
        next(reader)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            # 跳过空行
            if not row or not row[0]:
                continue
            records.append(row)
    return records


def row_to_bar(row: list) -> BarData:
    """将CSV行转换为BarData"""
    symbol = row[COL_CODE].strip()
    
    # 解析价格数据
    try:
        open_price = float(row[COL_OPEN])
        high_price = float(row[COL_HIGH])
        low_price = float(row[COL_LOW])
        close_price = float(row[COL_CLOSE])
        volume = float(row[COL_VOLUME])
        turnover = float(row[COL_TURNOVER])
        open_interest = float(row[COL_OI])
    except (ValueError, IndexError):
        return None
    
    return BarData(
        symbol=symbol,
        exchange=GFEX_EXCHANGE,
        interval=Interval.DAILY,
        datetime=parse_date(row[COL_DATE]),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        turnover=turnover,
        open_interest=open_interest,
        gateway_name="DB",
    )


def get_all_csv_files(data_dir: Path, year: int = None) -> list:
    """获取所有CSV文件"""
    if year:
        pattern = f"ALLFUTURES{year}.csv"
        files = list(data_dir.glob(pattern))
    else:
        files = sorted(data_dir.glob("ALLFUTURES*.csv"))
    return files


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


def import_gfex_data(
    test: bool = False,
    limit: int = None,
    force: bool = False,
    year: int = None,
) -> dict:
    """
    导入广期所数据
    
    Args:
        test: 是否测试模式
        limit: 测试模式下的条数限制
        force: 是否覆盖已有数据
        year: 指定年份，None则导入所有年份
    
    Returns:
        统计信息
    """
    data_dir = Path(__file__).parent.parent / "data" / "gfex"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return {}
    
    files = get_all_csv_files(data_dir, year)
    if not files:
        print(f"❌ 未找到CSV文件")
        return {}
    
    print(f"📂 找到 {len(files)} 个CSV文件")
    for f in files:
        print(f"   - {f.name}")
    print()
    
    db = get_database()
    stats = {"total": 0, "success": 0, "error": 0, "skipped": 0}
    all_bars = []
    
    for csv_file in files:
        print(f"📖 读取 {csv_file.name}...")
        
        try:
            records = read_csv_file(csv_file, limit)
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
            stats["error"] += 1
            continue
        
        print(f"   读取到 {len(records)} 条记录")
        
        # 转换为 BarData
        bars = []
        for row in records:
            bar = row_to_bar(row)
            if bar:
                bars.append(bar)
        
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
    """保存K线数据"""
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
                    GFEX_EXCHANGE,
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
    parser = argparse.ArgumentParser(description="广期所历史数据导入工具")
    parser.add_argument("--test", action="store_true", help="测试模式（只显示不保存）")
    parser.add_argument("--limit", type=int, default=None, help="限制导入条数（测试用）")
    parser.add_argument("--force", action="store_true", help="覆盖已有数据")
    parser.add_argument("--year", type=int, default=None, help="指定年份（如2026）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📥 广期所日K线数据导入工具")
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
    
    stats = import_gfex_data(
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
        print(f"   跳过: {stats['skipped']}")


if __name__ == "__main__":
    main()
