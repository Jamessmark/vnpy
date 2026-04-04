"""
郑商所 2026 年期货日K线导入工具

将 ai/data/czce/2026/ 目录下的所有品种文件批量导入 vnpy 数据库。
合约代码统一转换为4位年份格式（如 MA601 → MA2601）。

使用方法：
    uv run python ai/data_process/import_czce_2026.py

    # 只导入指定品种
    uv run python ai/data_process/import_czce_2026.py --symbols MA SA TA
"""

import argparse
import re
import sys
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

DATA_DIR = Path(__file__).parent.parent / "data" / "czce" / "2026"
FILE_YEAR = 2026


# ─────────────────────────────────────────────────────────────
# 合约代码转换（3位 → 4位年份格式）
# ─────────────────────────────────────────────────────────────

def czce_code_to_vnpy(raw_code: str) -> str | None:
    """
    将郑商所3位合约代码转换为4位年份格式

    例：
      MA601 → MA2601  （甲醇 2026年01月）
      SA612 → SA2612  （纯碱 2026年12月）
      TA709 → TA2709  （PTA  2027年09月）
    """
    code = raw_code.strip()
    if not code:
        return None

    m = re.match(r'^([A-Za-z]+)(\d+)$', code)
    if not m:
        return None

    prefix = m.group(1).upper()
    digits = m.group(2)

    if len(digits) == 3:
        # 郑商所3位格式：年末位 + 月份2位
        year_digit = int(digits[0])
        month_str = digits[1:3]
        # 推断完整年份（2026年代）
        decade = (FILE_YEAR // 10) * 10   # 2020
        full_year = decade + year_digit
        if full_year < FILE_YEAR - 2:
            full_year += 10
        return f"{prefix}{full_year % 100:02d}{month_str}"

    elif len(digits) == 4:
        # 已是4位，直接返回
        return f"{prefix}{digits}"

    return None


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


def parse_line(line: str) -> BarData | None:
    """
    解析一行郑商所日K线数据

    列格式（竖线分隔）：
    交易日期 | 合约代码 | 昨结算 | 今开盘 | 最高价 | 最低价 | 今收盘 | 今结算 |
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
        raw_code   = parts[1].strip()
        open_price  = parse_number(parts[3])
        high_price  = parse_number(parts[4])
        low_price   = parse_number(parts[5])
        close_price = parse_number(parts[6])
        volume      = parse_number(parts[10])
        turnover    = parse_number(parts[13]) * 10000 if len(parts) > 13 else 0.0
        open_interest = parse_number(parts[11])
    except (ValueError, IndexError):
        return None

    # 过滤全零行
    if open_price == 0 and high_price == 0 and close_price == 0:
        return None

    symbol = czce_code_to_vnpy(raw_code)
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
        gateway_name="CZCE_HIST",
    )


# ─────────────────────────────────────────────────────────────
# 文件解析
# ─────────────────────────────────────────────────────────────

def parse_file(filepath: Path) -> list[BarData]:
    """解析单个品种文件"""
    bars: list[BarData] = []
    try:
        with open(filepath, encoding='gbk', errors='replace') as f:
            for line in f:
                bar = parse_line(line)
                if bar:
                    bars.append(bar)
    except FileNotFoundError:
        print(f"  ⚠️  文件不存在: {filepath}")
    return bars


# ─────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="郑商所2026年日K线导入工具")
    parser.add_argument(
        "--symbols", nargs="+",
        help="只导入指定品种（如 MA SA TA），不指定则导入全部"
    )
    args = parser.parse_args()

    # 获取待导入的文件列表
    all_files = sorted(DATA_DIR.glob("*FUTURES2026.txt"))
    if not all_files:
        print(f"❌ 未找到数据文件，请先运行 download_czce.py 下载")
        print(f"   期望路径：{DATA_DIR}")
        return

    if args.symbols:
        filter_set = {s.upper() for s in args.symbols}
        files = [f for f in all_files if f.name[:f.name.index('FUTURES')] in filter_set]
    else:
        files = all_files

    print(f"\n郑商所 2026 年日K线导入")
    print(f"{'='*50}")
    print(f"数据目录：{DATA_DIR}")
    print(f"待导入文件：{len(files)} 个")

    db = get_database()
    total_bars = 0

    for fpath in files:
        symbol_prefix = fpath.name.split('FUTURES')[0]
        bars = parse_file(fpath)
        if not bars:
            print(f"  {symbol_prefix}: 无有效数据，跳过")
            continue

        print(f"  {symbol_prefix}: {len(bars):,} 条 → 写入数据库...", end="", flush=True)
        db.save_bar_data(bars)
        total_bars += len(bars)
        print(f" ✅")

    print(f"\n{'='*50}")
    print(f"✅ 导入完成，共写入 {total_bars:,} 条日K线")

    # 重建 CZCE 日K overview（确保新数据被索引）
    print("\n重建 CZCE 日K overview 索引...")
    import sqlite3
    db_path = Path.home() / ".vntrader" / "database.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM dbbaroverview WHERE exchange='CZCE' AND interval='d'")
        conn.execute("""
            INSERT INTO dbbaroverview (symbol, exchange, interval, count, start, end)
            SELECT symbol, exchange, interval,
                   COUNT(*) AS count,
                   MIN(datetime) AS start,
                   MAX(datetime) AS end
            FROM dbbardata
            WHERE exchange='CZCE' AND interval='d'
            GROUP BY symbol, exchange, interval
        """)
        count = conn.execute(
            "SELECT COUNT(*) FROM dbbaroverview WHERE exchange='CZCE' AND interval='d'"
        ).fetchone()[0]
        conn.commit()
    print(f"✅ overview 重建完成，共 {count} 条记录")


if __name__ == "__main__":
    main()
