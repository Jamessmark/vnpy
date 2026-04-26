"""
广州期货交易所期权日K线导入工具

将 ai/data/gfex/ALLOPTIONS2026.csv 导入 vnpy 数据库。
格式：日期,品种名,合约代码,昨结算,开盘,最高,最低,收盘,结算,涨跌,成交量,持仓量,变化,成交额,行权量

使用方法：
    uv run python ai/data_process/import_gfex_options.py
    uv run python ai/data_process/import_gfex_options.py --force
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

DATA_FILE = Path(__file__).parent.parent / "data" / "gfex" / "ALLOPTIONS2026.csv"


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
        return datetime.strptime(s, '%Y%m%d')
    except ValueError:
        try:
            return datetime.strptime(s, '%Y-%m-%d')
        except ValueError:
            return None


def parse_csv(filepath: Path) -> list[BarData]:
    """解析CSV文件"""
    bars: list[BarData] = []
    
    # 跳过第一行（表头描述）
    df = pd.read_csv(filepath, header=None, skiprows=1)
    
    for _, row in df.iterrows():
        try:
            trade_date = parse_date(row[0])
            symbol = str(row[2]).strip()  # 合约代码
            
            if not trade_date or not symbol or symbol == 'nan':
                continue
            
            open_price = parse_number(row[4])  # 开盘
            high_price = parse_number(row[5])    # 最高
            low_price = parse_number(row[6])     # 最低
            close_price = parse_number(row[7])  # 收盘
            volume = parse_number(row[10])       # 成交量
            turnover = parse_number(row[13])      # 成交额
            open_interest = parse_number(row[12]) # 持仓量
            
            # 过滤全零行
            if open_price == 0 and high_price == 0 and close_price == 0:
                continue
            
            bars.append(BarData(
                symbol=symbol,
                exchange=Exchange.GFEX,
                interval=Interval.DAILY,
                datetime=datetime.combine(trade_date.date(), time(0, 0)),
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                turnover=turnover,
                open_interest=open_interest,
                gateway_name="GFEX_OPT",
            ))
        except (ValueError, IndexError):
            continue
    
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
    parser = argparse.ArgumentParser(description="GFEX期权日K线导入工具")
    parser.add_argument("--force", action="store_true", help="强制覆盖模式")
    args = parser.parse_args()

    if not DATA_FILE.exists():
        print(f"❌ 未找到数据文件: {DATA_FILE}")
        return

    print(f"\nGFEX期权日K线导入")
    print(f"{'='*50}")
    print(f"数据文件：{DATA_FILE}")

    # 读取
    print(f"\n📖 读取文件...")
    all_bars = parse_csv(DATA_FILE)
    print(f"   读取 {len(all_bars):,} 根K线")

    # 去重
    print(f"\n📊 去重...")
    all_bars = deduplicate_bars(all_bars)
    print(f"   去重后 {len(all_bars):,} 根K线")

    # 保存
    print(f"\n💾 写入数据库...")
    db = get_database()

    by_symbol: defaultdict[str, list[BarData]] = defaultdict(list)
    for bar in all_bars:
        by_symbol[bar.symbol].append(bar)

    total_saved = 0
    for symbol, bars in sorted(by_symbol.items()):
        existing = db.load_bar_data(symbol, Exchange.GFEX, Interval.DAILY, None, None)
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
