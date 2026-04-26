"""
郑商所期权日K线导入工具

将 ai/data/czce_options/{year}/ 目录下的所有期权数据导入 vnpy 数据库。
合约代码格式：SR603C4600 → SR2603-C-4600

使用方法：
    uv run python ai/data_process/import_czce_options.py
    uv run python ai/data_process/import_czce_options.py --year 2026
    uv run python ai/data_process/import_czce_options.py --force  # 强制覆盖模式
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path

# 确保能 import vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData

# ─────────────────────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────────────────────

DATA_ROOT = Path(__file__).parent.parent / "data" / "czce_options"


# ─────────────────────────────────────────────────────────────
# 合约代码转换
# SR603C4600 → SR2603-C-4600
# SR605P5800 → SR2605-P-5800
# ─────────────────────────────────────────────────────────────

def czce_option_code_to_vnpy(raw_code: str, file_year: int = 2026) -> str | None:
    """
    将郑商所期权代码转换为vnpy格式

    例：
      SR603C4600 → SR2603-C-4600  （白糖 2026年03月 看涨期权 行权价4600）
      SR605P5800 → SR2605-P-5800  （白糖 2026年05月 看跌期权 行权价5800）
    """
    code = raw_code.strip()
    if not code:
        return None

    # SR603C4600 格式: 品种(2位) + 年月(3位) + C/P(1位) + 行权价(变长)
    m = re.match(r'^([A-Za-z]+)(\d{3})([CP])(\d+)$', code)
    if not m:
        return None

    prefix = m.group(1).upper()
    digits = m.group(2)  # 如 603
    option_type = m.group(3)  # C 或 P
    strike = m.group(4)  # 行权价

    # 3位格式：末位数字是年份 + 月份2位
    year_digit = int(digits[0])
    month_str = digits[1:3]

    # 推断完整年份
    decade = (file_year // 10) * 10
    full_year = decade + year_digit
    if full_year < file_year - 2:
        full_year += 10

    return f"{prefix}{full_year % 100:02d}{month_str}-{option_type}-{strike}"


# ─────────────────────────────────────────────────────────────
# 行解析
# ─────────────────────────────────────────────────────────────

def parse_number(s: str) -> float:
    s = s.strip().replace(',', '')
    if not s or s == '-':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_line(line: str, file_year: int) -> BarData | None:
    """
    解析一行郑商所期权日K线数据

    列格式（竖线分隔）：
    交易日期 | 合约代码 | 昨结算 | 今开盘 | 最高价 | 最低价 | 今收盘 | 今结算 |
    涨跌1 | 涨跌2 | 成交量 | 持仓量 | 增减量 | 成交额 | DELTA | 隐含波动率 | 行权量
    """
    line = line.strip()
    if not line:
        return None

    # 只处理以日期开头的行
    if not re.match(r'^\d{4}-\d{2}-\d{2}', line):
        return None

    # 按竖线分割
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 14:
        return None

    try:
        trade_date = datetime.strptime(parts[0].strip(), '%Y-%m-%d')
        raw_code = parts[1].strip()
        open_price = parse_number(parts[3])
        high_price = parse_number(parts[4])
        low_price = parse_number(parts[5])
        close_price = parse_number(parts[6])
        volume = parse_number(parts[10])
        turnover = parse_number(parts[13]) * 10000 if len(parts) > 13 else 0.0
        open_interest = parse_number(parts[11])
    except (ValueError, IndexError):
        return None

    # 过滤全零行
    if open_price == 0 and high_price == 0 and close_price == 0:
        return None

    symbol = czce_option_code_to_vnpy(raw_code, file_year)
    if not symbol:
        return None

    return BarData(
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
        gateway_name="CZCE_OPT",
    )


# ─────────────────────────────────────────────────────────────
# 文件解析
# ─────────────────────────────────────────────────────────────

def parse_file(filepath: Path, file_year: int) -> list[BarData]:
    """解析单个品种文件"""
    bars: list[BarData] = []
    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            for line in f:
                bar = parse_line(line, file_year)
                if bar:
                    bars.append(bar)
    except FileNotFoundError:
        print(f"  ⚠️  文件不存在: {filepath}")
    return bars


# ─────────────────────────────────────────────────────────────
# 去重
# ─────────────────────────────────────────────────────────────

def deduplicate_bars(bars: list[BarData]) -> list[BarData]:
    """按 (symbol, date) 去重"""
    seen: dict[tuple[str, str], BarData] = {}
    for bar in bars:
        key = (bar.symbol, bar.datetime.date().isoformat())
        if key not in seen:
            seen[key] = bar
    return list(seen.values())


# ─────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="郑商所期权日K线导入工具")
    parser.add_argument("--year", type=int, default=2026, help="数据年份（默认2026）")
    parser.add_argument(
        "--symbols", nargs="+",
        help="只导入指定品种（如 SR CF），不指定则导入全部"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制覆盖模式"
    )
    args = parser.parse_args()

    data_dir = DATA_ROOT / str(args.year)

    # 获取待导入的文件列表
    all_files = sorted(data_dir.glob("*OPTIONS*.txt"))
    if not all_files:
        print(f"❌ 未找到数据文件，请先运行 download_czce_options.py 下载")
        print(f"   期望路径：{data_dir}")
        return

    if args.symbols:
        filter_set = {s.upper() for s in args.symbols}
        files = [f for f in all_files if any(f.name.startswith(s) for s in filter_set)]
    else:
        files = all_files

    print(f"\n郑商所期权 {args.year} 年日K线导入")
    print(f"{'='*50}")
    print(f"数据目录：{data_dir}")
    print(f"待导入文件：{len(files)} 个")
    if args.force:
        print("⚠️  覆盖模式")

    # 第一步：汇总所有文件
    print(f"\n📖 第一步：读取所有文件...")
    all_bars: list[BarData] = []
    for fpath in files:
        bars = parse_file(fpath, args.year)
        all_bars.extend(bars)
        print(f"   {fpath.name}: {len(bars)} 条")
    print(f"   汇总得到 {len(all_bars):,} 根K线")

    # 第二步：去重
    print(f"\n📊 第二步：去重...")
    all_bars = deduplicate_bars(all_bars)
    print(f"   去重后 {len(all_bars):,} 根K线")

    # 第三步：按 symbol 分组保存
    print(f"\n💾 第三步：写入数据库...")
    db = get_database()

    by_symbol: defaultdict[str, list[BarData]] = defaultdict(list)
    for bar in all_bars:
        by_symbol[bar.symbol].append(bar)

    total_saved = 0
    for symbol, bars in sorted(by_symbol.items()):
        existing = db.load_bar_data(symbol, Exchange.CZCE, Interval.DAILY, None, None)
        existing_dates = {bar.datetime.date() for bar in existing}

        if args.force:
            new_bars = bars
        else:
            new_bars = [b for b in bars if b.datetime.date() not in existing_dates]

        if new_bars:
            db.save_bar_data(bars)  # 保存全部（包含旧的）
            total_saved += len(bars)
            print(f"   {symbol}: {len(bars)} 条")
        else:
            print(f"   {symbol}: {len(bars)} 条 (无需更新)")

    print(f"\n{'='*50}")
    print(f"✅ 导入完成")
    print(f"   总记录数: {len(all_bars):,}")
    print(f"   成功写入: {total_saved:,}")


if __name__ == "__main__":
    main()
