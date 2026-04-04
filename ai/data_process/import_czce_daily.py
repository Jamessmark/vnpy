"""
郑商所历史日K线导入工具

支持两种文件格式：
  1. 合并文件（2020-2023）：ALLFUTURES20xx.txt，第2列为"品种代码"（如 AP001）
  2. 分品种文件（2024-2025）：XXFUTURES20xx.txt，第2列为"合约代码"（如 MA401）

合约代码转换规则（郑商所3位 → vnpy标准4位）：
  AP001 → AP2001（2020年01月）
  AP101 → AP2101（2021年01月）
  MA401 → MA2401（2024年01月）

使用方法：
  # 导入所有年份
  uv run python ai/data_conv/import_czce_daily.py

  # 只导入指定年份
  uv run python ai/data_conv/import_czce_daily.py --year 2024

  # 只导入指定品种（2024年）
  uv run python ai/data_conv/import_czce_daily.py --year 2024 --symbol MA
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime, time

# 确保能 import vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval

# ─────────────────────────────────────────────────────────────
# 数据文件路径配置
# ─────────────────────────────────────────────────────────────

DATA_ROOT = Path(__file__).parent.parent / "data" / "last"

# 单文件年份（所有品种合并）
SINGLE_FILE_YEARS = {
    2020: DATA_ROOT / "ALLFUTURES2020.txt",
    2021: DATA_ROOT / "ALLFUTURES2021.txt",
    2022: DATA_ROOT / "ALLFUTURES2022.txt",
    2023: DATA_ROOT / "ALLFUTURES2023.txt",
}

# 分品种目录年份
MULTI_FILE_YEARS = {
    2024: DATA_ROOT / "ALLFUTURES2024",
    2025: DATA_ROOT / "ALLFUTURES2025",
}


# ─────────────────────────────────────────────────────────────
# 合约代码转换
# ─────────────────────────────────────────────────────────────

def czce_code_to_vnpy(raw_code: str, file_year: int) -> str | None:
    """
    将郑商所3位合约代码转换为 vnpy 标准格式

    郑商所格式：品种前缀 + 年份末位 + 月份2位
      AP001 → 品种AP，年份末位0（2020），月份01
      MA401 → 品种MA，年份末位4（2024），月份01

    vnpy格式：品种前缀 + 4位年份 + 月份2位（总长=品种长+4位）
      AP001 → AP2001
      MA401 → MA2401

    参数：
      raw_code: 原始合约代码，如 "MA401  " （可能有空格）
      file_year: 文件所属年份，如 2024，用于推断完整年份
    """
    code = raw_code.strip()
    if not code:
        return None

    # 分离字母前缀和数字部分
    m = re.match(r'^([A-Za-z]+)(\d+)$', code)
    if not m:
        return None

    prefix = m.group(1).upper()
    digits = m.group(2)

    if len(digits) == 3:
        # 郑商所3位格式：年末位 + 月份2位
        year_digit = int(digits[0])
        month_str = digits[1:3]

        # 推断完整年份：用文件年份的十位+个位推断
        # file_year=2024，year_digit=4 → 2024；year_digit=5 → 2025
        # file_year=2020，year_digit=0 → 2020；year_digit=1 → 2021
        decade = (file_year // 10) * 10  # 2020
        full_year = decade + year_digit
        # 如果推断年份比文件年份早超过5年，则可能是下个十年
        if full_year < file_year - 2:
            full_year += 10

        return f"{prefix}{full_year % 100:02d}{month_str}"

    elif len(digits) == 4:
        # 已经是4位格式，直接返回
        return f"{prefix}{digits}"

    return None


# ─────────────────────────────────────────────────────────────
# 解析单行数据
# ─────────────────────────────────────────────────────────────

def parse_number(s: str) -> float:
    """解析带逗号的数字字符串"""
    s = s.strip().replace(',', '')
    if not s or s == '-':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_line(line: str, file_year: int) -> BarData | None:
    """
    解析一行郑商所日K线数据

    列格式（竖线分隔）：
    交易日期 | 品种/合约代码 | 昨结算 | 今开盘 | 最高价 | 最低价 | 今收盘 | 今结算 |
    涨跌1 | 涨跌2 | 成交量(手) | 持仓量 | 增减量 | 成交额(万元) | 交割结算价
    """
    line = line.strip()
    if not line:
        return None

    # 只处理以日期开头的行
    if not re.match(r'^\d{4}-\d{2}-\d{2}', line):
        return None

    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 13:
        return None

    try:
        trade_date = datetime.strptime(parts[0].strip(), '%Y-%m-%d')
        raw_code = parts[1].strip()
        # open = 今开盘（第4列，index=3）
        open_price = parse_number(parts[3])
        high_price = parse_number(parts[4])
        low_price  = parse_number(parts[5])
        close_price = parse_number(parts[6])
        # 今结算作为额外信息，暂用 close
        volume = parse_number(parts[10])
        # 成交额（万元）→ 元
        turnover = parse_number(parts[13]) * 10000 if len(parts) > 13 else 0.0
        open_interest = parse_number(parts[11])
    except (ValueError, IndexError):
        return None

    # 过滤无效行（开高低收都为0）
    if open_price == 0 and high_price == 0 and close_price == 0:
        return None

    # 转换合约代码
    symbol = czce_code_to_vnpy(raw_code, file_year)
    if not symbol:
        return None

    bar = BarData(
        symbol=symbol,
        exchange=Exchange.CZCE,
        interval=Interval.DAILY,
        datetime=datetime.combine(trade_date.date(), time(0, 0)),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        turnover=turnover,
        open_interest=open_interest,
        gateway_name="CZCE_HIST",
    )
    return bar


# ─────────────────────────────────────────────────────────────
# 文件解析入口
# ─────────────────────────────────────────────────────────────

def parse_file(filepath: Path, file_year: int, filter_symbol: str | None = None) -> list[BarData]:
    """解析单个数据文件，返回 BarData 列表"""
    bars: list[BarData] = []

    try:
        # 郑商所文件编码通常是 GBK
        with open(filepath, encoding='gbk', errors='replace') as f:
            for line in f:
                bar = parse_line(line, file_year)
                if bar is None:
                    continue
                if filter_symbol and not bar.symbol.upper().startswith(filter_symbol.upper()):
                    continue
                bars.append(bar)
    except FileNotFoundError:
        print(f"  ⚠️  文件不存在: {filepath}")

    return bars


def load_year(year: int, filter_symbol: str | None = None) -> list[BarData]:
    """加载某一年的所有数据"""
    all_bars: list[BarData] = []

    if year in SINGLE_FILE_YEARS:
        filepath = SINGLE_FILE_YEARS[year]
        bars = parse_file(filepath, year, filter_symbol)
        print(f"  {filepath.name}: {len(bars):,} 条")
        all_bars.extend(bars)

    elif year in MULTI_FILE_YEARS:
        dir_path = MULTI_FILE_YEARS[year]
        txt_files = sorted(dir_path.glob("*FUTURES*.txt"))
        for fpath in txt_files:
            # 从文件名提取品种前缀用于过滤
            fname_prefix = fpath.name.split('FUTURES')[0]
            if filter_symbol and fname_prefix.upper() != filter_symbol.upper():
                continue
            bars = parse_file(fpath, year, filter_symbol)
            if bars:
                print(f"  {fpath.name}: {len(bars):,} 条")
            all_bars.extend(bars)
    else:
        print(f"  ⚠️  年份 {year} 没有配置数据路径")

    return all_bars


# ─────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="郑商所历史日K线导入工具")
    parser.add_argument("--year", type=int, help="只导入指定年份（如 2024）")
    parser.add_argument("--symbol", help="只导入指定品种（如 MA，不区分大小写）")
    args = parser.parse_args()

    db = get_database()

    years = [args.year] if args.year else sorted(list(SINGLE_FILE_YEARS.keys()) + list(MULTI_FILE_YEARS.keys()))

    total_bars = 0
    for year in years:
        print(f"\n[{year}] 加载数据...")
        bars = load_year(year, args.symbol)
        if not bars:
            print(f"  没有数据")
            continue

        print(f"  → 写入数据库 {len(bars):,} 条...", end="", flush=True)
        db.save_bar_data(bars)
        total_bars += len(bars)
        print(f" ✅")

    print(f"\n{'='*50}")
    print(f"✅ 导入完成，共写入 {total_bars:,} 条日K线")

    # 统计数据库中 CZCE 日K线情况
    overviews = db.get_bar_overview()
    czce_daily = [o for o in overviews if o.exchange == Exchange.CZCE and o.interval == Interval.DAILY]
    if czce_daily:
        total = sum(o.count for o in czce_daily)
        earliest = min(o.start for o in czce_daily)
        latest = max(o.end for o in czce_daily)
        print(f"数据库 CZCE 日K线：{len(czce_daily)} 个合约，{total:,} 条，{earliest.date()} ~ {latest.date()}")


if __name__ == "__main__":
    main()
