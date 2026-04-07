"""
期货主连数据准备工具

从 vnpy SQLite 数据库读取主连日线/分钟线数据，
转存为 AlphaLab 所需的 Parquet 格式。

输出目录结构（默认 ai/data/lab/）：
    lab/
    ├── daily/
    │   ├── MA888.LOCAL.parquet
    │   ├── rb888.LOCAL.parquet
    │   └── ...
    └── minute/
        ├── MA888.LOCAL.parquet
        └── ...

Parquet 列格式（与 AlphaLab.save_bar_data 保持一致）：
    datetime       Datetime  无时区
    open           Float64
    high           Float64
    low            Float64
    close          Float64
    volume         Float64
    turnover       Float64
    open_interest  Float64

用法：
    # 导出所有主连品种日线（默认）
    uv run python ai/data_process/prepare_futures_data.py

    # 同时导出分钟线
    uv run python ai/data_process/prepare_futures_data.py --with-minute

    # 只导出指定品种
    uv run python ai/data_process/prepare_futures_data.py --symbol MA888 SA888 FG888

    # 指定输出目录
    uv run python ai/data_process/prepare_futures_data.py --lab-path ./my_lab

    # 导出后打印合约统计
    uv run python ai/data_process/prepare_futures_data.py --info
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 确保能导入项目根目录的 vnpy（文件位于 ai/data_process/，parent.parent 即项目根目录）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import polars as pl

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval
from vnpy.alpha.lab import AlphaLab


# ─────────────────────────────────────────────────────────────────────────────
# 默认参数
# ─────────────────────────────────────────────────────────────────────────────

# AlphaLab 数据目录：ai/data/lab/
DEFAULT_LAB_PATH = str(Path(__file__).parent.parent / "data" / "lab")

# 建议优先使用的交易所（数据最全）
CZCE_EXCHANGE = Exchange.CZCE

# 主连数据的 exchange 都是 LOCAL
LOCAL_EXCHANGE = Exchange.LOCAL


# ─────────────────────────────────────────────────────────────────────────────
# 核心函数
# ─────────────────────────────────────────────────────────────────────────────

def bars_to_polars(bars) -> pl.DataFrame:
    """将 vnpy BarData 列表转换为 AlphaLab 标准 DataFrame 格式。"""
    data = [
        {
            "datetime": bar.datetime.replace(tzinfo=None),   # 去掉时区，AlphaLab 要求无时区
            "open":          bar.open_price,
            "high":          bar.high_price,
            "low":           bar.low_price,
            "close":         bar.close_price,
            "volume":        bar.volume,
            "turnover":      bar.turnover,
            "open_interest": bar.open_interest,
        }
        for bar in bars
    ]
    if not data:
        return pl.DataFrame()
    return pl.DataFrame(data)


def save_parquet(df: pl.DataFrame, file_path: Path) -> None:
    """增量写入：如果文件已存在则合并去重再保存。"""
    if file_path.exists():
        old_df = pl.read_parquet(file_path)
        df = pl.concat([old_df, df]).unique(subset=["datetime"]).sort("datetime")
    else:
        df = df.sort("datetime")
    df.write_parquet(file_path)


def get_local_888_symbols(db) -> list[tuple[str, Interval]]:
    """
    从数据库 overview 中找出所有 LOCAL 交易所的 888 主连合约，
    返回 [(vt_symbol, interval), ...] 列表。
    """
    overviews = db.get_bar_overview()
    results = []
    for o in overviews:
        if o.exchange != LOCAL_EXCHANGE:
            continue
        if not o.symbol.endswith("888"):
            continue
        if o.interval not in (Interval.DAILY, Interval.MINUTE):
            continue
        results.append((f"{o.symbol}.{o.exchange.value}", o.interval, o.count, o.start, o.end))
    return results


def export_symbol(
    db,
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    lab: AlphaLab,
    force: bool = False,
) -> int:
    """
    导出单个合约的数据到 parquet 文件。
    返回写入的 K 线数量。
    """
    vt_symbol = f"{symbol}.{exchange.value}"

    # 确定输出文件路径
    if interval == Interval.DAILY:
        file_path = lab.daily_path / f"{vt_symbol}.parquet"
    else:
        file_path = lab.minute_path / f"{vt_symbol}.parquet"

    # 增量判断：找到文件已有的最新时间
    start_dt = datetime(2000, 1, 1)
    if not force and file_path.exists():
        existing = pl.read_parquet(file_path)
        if len(existing) > 0:
            latest = existing["datetime"].max()
            if latest is not None:
                start_dt = latest  # 从最新时间开始增量

    end_dt = datetime.now()

    bars = db.load_bar_data(symbol, exchange, interval, start_dt, end_dt)
    if not bars:
        return 0

    df = bars_to_polars(bars)
    if df.is_empty():
        return 0

    save_parquet(df, file_path)
    return len(bars)


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="期货主连数据导出工具：从 vnpy SQLite → AlphaLab Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 导出所有主连品种日线（默认）
  uv run python ai/data_process/prepare_futures_data.py

  # 同时导出分钟线
  uv run python ai/data_process/prepare_futures_data.py --with-minute

  # 只导出指定品种（symbol 为不带交易所的合约代码）
  uv run python ai/data_process/prepare_futures_data.py --symbol MA888 SA888 FG888

  # 强制全量重写（不做增量）
  uv run python ai/data_process/prepare_futures_data.py --force

  # 指定 lab 目录
  uv run python ai/data_process/prepare_futures_data.py --lab-path ./my_lab

  # 查看已导出合约统计
  uv run python ai/data_process/prepare_futures_data.py --info
        """,
    )
    parser.add_argument(
        "--symbol", nargs="+", metavar="SYMBOL",
        help="只导出指定合约（如 MA888 SA888），不指定则导出全部主连"
    )
    parser.add_argument(
        "--with-minute", action="store_true",
        help="同时导出分钟线（默认只导出日线）"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制全量重写（忽略已有文件，不做增量）"
    )
    parser.add_argument(
        "--lab-path", default=DEFAULT_LAB_PATH,
        help=f"AlphaLab 数据目录（默认：{DEFAULT_LAB_PATH}）"
    )
    parser.add_argument(
        "--info", action="store_true",
        help="打印已导出合约的统计信息后退出"
    )
    args = parser.parse_args()

    # ── 初始化 ────────────────────────────────────────────────────────────────
    lab = AlphaLab(args.lab_path)
    db = get_database()

    # ── --info 模式 ───────────────────────────────────────────────────────────
    if args.info:
        print(f"\nAlphaLab 目录：{lab.lab_path}")
        print(f"\n── 日线合约（{lab.daily_path}）──")
        daily_files = sorted(lab.daily_path.glob("*.parquet"))
        if daily_files:
            for f in daily_files:
                df = pl.read_parquet(f)
                start = df["datetime"].min()
                end = df["datetime"].max()
                print(f"  {f.stem:<25}  {len(df):>6} 根  {start} ~ {end}")
        else:
            print("  （暂无数据）")

        print(f"\n── 分钟线合约（{lab.minute_path}）──")
        minute_files = sorted(lab.minute_path.glob("*.parquet"))
        if minute_files:
            for f in minute_files:
                df = pl.read_parquet(f)
                start = df["datetime"].min()
                end = df["datetime"].max()
                print(f"  {f.stem:<25}  {len(df):>8} 根  {start} ~ {end}")
        else:
            print("  （暂无数据）")
        return

    # ── 从数据库 overview 筛选主连合约 ────────────────────────────────────────
    overviews = db.get_bar_overview()

    # 找出所有 LOCAL 交易所的 XXX888 主连合约
    candidate_intervals = [Interval.DAILY]
    if args.with_minute:
        candidate_intervals.append(Interval.MINUTE)

    tasks: list[tuple[str, Exchange, Interval, int]] = []   # (symbol, exchange, interval, count)
    for o in overviews:
        if o.exchange != Exchange.LOCAL:
            continue
        if not o.symbol.endswith("888"):
            continue
        if o.interval not in candidate_intervals:
            continue
        # 过滤 --symbol 参数
        if args.symbol and o.symbol not in args.symbol:
            continue
        tasks.append((o.symbol, o.exchange, o.interval, o.count))

    if not tasks:
        print("未找到符合条件的主连合约，请先运行 build_main_contract.py 生成主连数据。")
        return

    # 按 interval 分组统计
    daily_tasks  = [(s, e, iv, c) for s, e, iv, c in tasks if iv == Interval.DAILY]
    minute_tasks = [(s, e, iv, c) for s, e, iv, c in tasks if iv == Interval.MINUTE]

    print(f"\nAlphaLab 路径：{lab.lab_path}")
    print(f"共 {len(daily_tasks)} 个日线合约、{len(minute_tasks)} 个分钟线合约待导出")
    if args.force:
        print("【强制模式】忽略已有文件，全量重写\n")
    else:
        print("【增量模式】已有文件从最新日期起追加\n")

    # ── 导出日线 ──────────────────────────────────────────────────────────────
    total_daily = 0
    if daily_tasks:
        print(f"── 导出日线 ({'全量' if args.force else '增量'}) ──")
        for symbol, exchange, interval, db_count in sorted(daily_tasks, key=lambda x: x[0]):
            n = export_symbol(db, symbol, exchange, interval, lab, force=args.force)
            vt = f"{symbol}.{exchange.value}"
            status = f"写入 {n} 根" if n > 0 else "无新增数据"
            print(f"  {vt:<25}  (DB总计 {db_count:>5} 根)  →  {status}")
            total_daily += n

    # ── 导出分钟线 ────────────────────────────────────────────────────────────
    total_minute = 0
    if minute_tasks:
        print(f"\n── 导出分钟线 ({'全量' if args.force else '增量'}) ──")
        for symbol, exchange, interval, db_count in sorted(minute_tasks, key=lambda x: x[0]):
            n = export_symbol(db, symbol, exchange, interval, lab, force=args.force)
            vt = f"{symbol}.{exchange.value}"
            status = f"写入 {n} 根" if n > 0 else "无新增数据"
            print(f"  {vt:<25}  (DB总计 {db_count:>6} 根)  →  {status}")
            total_minute += n

    print(f"\n{'─' * 55}")
    print(f"✅ 完成：日线写入 {total_daily} 根，分钟线写入 {total_minute} 根")
    print(f"📁 输出目录：{lab.lab_path}")


if __name__ == "__main__":
    main()
