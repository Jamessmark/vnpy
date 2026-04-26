"""
大连商品交易所期权日K线导入工具

将 ai/data/dce/allVarietyOpt/ 目录下的所有期权文件导入 vnpy 数据库。
格式：品种名称, 合约名称, 交易日期, 开盘价, 最高价, 最低价, 收盘价, 前结算价, 结算价, 涨跌, ...

使用方法：
    uv run python ai/data_process/import_dce_options.py
    uv run python ai/data_process/import_dce_options.py --force
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData

DATA_DIR = Path(__file__).parent.parent / "data" / "dce" / "allVarietyOpt"


def parse_number(s) -> float:
    if pd.isna(s):
        return 0.0
    s = str(s).strip().replace(',', '')
    if not s or s == '-':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(s) -> datetime | None:
    if pd.isna(s):
        return None
    s = str(s).strip()
    try:
        # 尝试 20260105 格式
        return datetime.strptime(s, '%Y%m%d')
    except ValueError:
        try:
            return datetime.strptime(s, '%Y-%m-%d')
        except ValueError:
            return None


def parse_file(filepath: Path) -> list[BarData]:
    """解析单个期权文件"""
    bars: list[BarData] = []
    try:
        # 跳过第一行（表头描述）
        df = pd.read_excel(filepath, header=None, skiprows=1)
        
        for _, row in df.iterrows():
            try:
                symbol = str(row[1]).strip()  # 合约名称
                trade_date = parse_date(row[2])
                if not trade_date or not symbol:
                    continue
                
                open_price = parse_number(row[3])
                high_price = parse_number(row[4])
                low_price = parse_number(row[5])
                close_price = parse_number(row[6])
                volume = parse_number(row[10])
                turnover = parse_number(row[13])
                open_interest = parse_number(row[11])
                
                # 过滤全零行
                if open_price == 0 and high_price == 0 and close_price == 0:
                    continue
                
                bars.append(BarData(
                    symbol=symbol,
                    exchange=Exchange.DCE,
                    interval=Interval.DAILY,
                    datetime=datetime.combine(trade_date.date(), time(0, 0)),
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    turnover=turnover,
                    open_interest=open_interest,
                    gateway_name="DCE_OPT",
                ))
            except (ValueError, IndexError):
                continue
    except FileNotFoundError:
        print(f"  ⚠️  文件不存在: {filepath}")
    return bars


def deduplicate_bars(bars: list[BarData]) -> list[BarData]:
    """按 (symbol, date) 去重"""
    seen: dict[tuple[str, str], BarData] = {}
    for bar in bars:
        key = (bar.symbol, bar.datetime.date().isoformat())
        if key not in seen:
            seen[key] = bar
    return list(seen.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="DCE期权日K线导入工具")
    parser.add_argument("--force", action="store_true", help="强制覆盖模式")
    args = parser.parse_args()

    all_files = sorted(DATA_DIR.glob("*.xlsx"))
    if not all_files:
        print(f"❌ 未找到数据文件: {DATA_DIR}")
        return

    print(f"\nDCE期权日K线导入")
    print(f"{'='*50}")
    print(f"数据目录：{DATA_DIR}")
    print(f"待导入文件：{len(all_files)} 个")

    # 汇总所有文件
    print(f"\n📖 第一步：读取所有文件...")
    all_bars: list[BarData] = []
    for fpath in all_files:
        bars = parse_file(fpath)
        all_bars.extend(bars)
        print(f"   {fpath.name}: {len(bars)} 条")
    print(f"   合计 {len(all_bars):,} 根K线")

    # 去重
    print(f"\n📊 第二步：去重...")
    all_bars = deduplicate_bars(all_bars)
    print(f"   去重后 {len(all_bars):,} 根K线")

    # 保存
    print(f"\n💾 第三步：写入数据库...")
    db = get_database()

    by_symbol: defaultdict[str, list[BarData]] = defaultdict(list)
    for bar in all_bars:
        by_symbol[bar.symbol].append(bar)

    total_saved = 0
    for symbol, bars in sorted(by_symbol.items()):
        existing = db.load_bar_data(symbol, Exchange.DCE, Interval.DAILY, None, None)
        existing_dates = {bar.datetime.date() for bar in existing}

        if args.force:
            new_bars = bars
        else:
            new_bars = [b for b in bars if b.datetime.date() not in existing_dates]

        if new_bars:
            db.save_bar_data(bars)
            total_saved += len(bars)
    
    print(f"\n{'='*50}")
    print(f"✅ 导入完成")
    print(f"   总记录数: {len(all_bars):,}")
    print(f"   成功写入: {total_saved:,}")


if __name__ == "__main__":
    main()
