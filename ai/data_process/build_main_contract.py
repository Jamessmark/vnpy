"""
商品期货主连数据生成工具

功能：
  1. 遍历数据库中所有品种的日K线，按交易日选出持仓量（open_interest）最大的合约
     作为当日主力，生成【主力映射表】并持久化到 ~/.vntrader/main_contract_mapping.db
  2. 按映射表从数据库读取对应具体合约的 BarData，
     拼接成完整的不复权主连序列，写入数据库：
       symbol = <PREFIX>888   exchange = LOCAL   interval = DAILY / MINUTE
  3. 日线和分钟线都生成，分钟线用日线主力决定当日主力（不盘中切换）

命名规则：
  CZCE 品种大写：MA888.LOCAL / SA888.LOCAL ...
  其他品种小写：rb888.LOCAL / cu888.LOCAL ...

持久化映射表：
  路径：~/.vntrader/main_contract_mapping.db（SQLite）
  可用 MappingStore 直接查询：
    store = MappingStore()
    # 查某品种所有切换记录
    store.get_switches("MA", "CZCE")
    # 查某天的主力合约
    store.get_dominant("MA", "CZCE", date(2025, 6, 1))

运行方式：
  # 预览模式（仅打印映射表，不写数据库）
  uv run python ai/data_process/build_main_contract.py --dry-run

  # 生成所有品种主连
  uv run python ai/data_process/build_main_contract.py

  # 只处理指定品种
  uv run python ai/data_process/build_main_contract.py --symbol MA --exchange CZCE

  # 强制重建（覆盖已有主连数据）
  uv run python ai/data_process/build_main_contract.py --force

  # 导出映射表 CSV
  uv run python ai/data_process/build_main_contract.py --export-mapping mapping.csv
"""

import re
import sys
import csv
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, date, time, timedelta
from collections import defaultdict

# 确保能导入项目根目录的 vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

# 夜盘切割点：>= 16:00 的分钟K归属下一个交易日
_NIGHT_CUT = time(16, 0)


def assign_trade_date(dt: datetime) -> date:
    """将分钟K线的时间戳分配到对应的自然交易日"""
    if dt.time() >= _NIGHT_CUT:
        return (dt + timedelta(days=1)).date()
    return dt.date()


def symbol_prefix(symbol: str) -> str:
    """从合约代码提取品种前缀，如 MA2605 -> MA，rb2605 -> rb"""
    return re.sub(r"\d", "", symbol)


def main_contract_symbol(prefix: str) -> str:
    """主连合约代码，如 MA -> MA888，rb -> rb888"""
    return f"{prefix}888"


# ─────────────────────────────────────────────────────────────────────────────
# MappingStore：主力映射表的 SQLite 持久化层
# ─────────────────────────────────────────────────────────────────────────────

class MappingStore:
    """
    负责读写主力映射表的 SQLite 数据库。

    数据库路径：~/.vntrader/main_contract_mapping.db

    表结构：
        product      TEXT     品种前缀，如 MA / rb
        exchange     TEXT     交易所，如 CZCE / SHFE
        trade_date   TEXT     交易日，ISO 格式 YYYY-MM-DD
        dominant     TEXT     当日主力合约代码，如 MA2605
        open_interest REAL    当日主力合约持仓量

    主键：(product, exchange, trade_date)
    """

    DEFAULT_PATH = Path.home() / ".vntrader" / "main_contract_mapping.db"

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False：允许在多线程环境（如 Dash worker）中使用同一连接
        # MappingStore 只做只读查询，无并发写入风险
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_table()

    def _init_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS main_contract_mapping (
                product        TEXT NOT NULL,
                exchange       TEXT NOT NULL,
                trade_date     TEXT NOT NULL,
                dominant       TEXT NOT NULL,
                open_interest  REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (product, exchange, trade_date)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_exchange
            ON main_contract_mapping (product, exchange)
        """)
        self._conn.commit()

    # ── 写入 ──────────────────────────────────────────────────────────────────

    def save_mapping(
        self,
        product: str,
        exchange: str,
        mapping: list[dict],
        replace: bool = False,
    ) -> int:
        """
        写入映射表（增量 INSERT OR IGNORE，或 replace=True 时全量覆盖）。

        mapping 格式：list of {"trade_date": date, "dominant": str, "open_interest": float}
        返回：实际插入/更新的行数
        """
        if not mapping:
            return 0

        if replace:
            # 先删除该品种的历史记录，再重新写入
            self._conn.execute(
                "DELETE FROM main_contract_mapping WHERE product=? AND exchange=?",
                (product, exchange),
            )

        verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        rows = [
            (product, exchange, row["trade_date"].isoformat(), row["dominant"], row["open_interest"])
            for row in mapping
        ]
        self._conn.executemany(
            f"{verb} INTO main_contract_mapping "
            f"(product, exchange, trade_date, dominant, open_interest) VALUES (?,?,?,?,?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def get_all(self, product: str, exchange: str) -> list[dict]:
        """返回某品种全部映射记录，按 trade_date 升序"""
        cur = self._conn.execute(
            "SELECT trade_date, dominant, open_interest FROM main_contract_mapping "
            "WHERE product=? AND exchange=? ORDER BY trade_date",
            (product, exchange),
        )
        return [
            {
                "trade_date": date.fromisoformat(row[0]),
                "dominant": row[1],
                "open_interest": row[2],
            }
            for row in cur.fetchall()
        ]

    def get_dominant(self, product: str, exchange: str, trade_date: date) -> str | None:
        """查询某天的主力合约代码，无记录则返回 None"""
        cur = self._conn.execute(
            "SELECT dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_switches(self, product: str, exchange: str) -> list[dict]:
        """
        返回该品种所有换月节点（dominant 发生变化的行）。

        返回格式：list of {"trade_date": date, "dominant": str}
        """
        all_rows = self.get_all(product, exchange)
        switches = []
        prev = None
        for row in all_rows:
            if row["dominant"] != prev:
                switches.append({"trade_date": row["trade_date"], "dominant": row["dominant"]})
                prev = row["dominant"]
        return switches

    def get_latest_date(self, product: str, exchange: str) -> date | None:
        """返回该品种映射表中最新的交易日，无记录则返回 None"""
        cur = self._conn.execute(
            "SELECT MAX(trade_date) FROM main_contract_mapping WHERE product=? AND exchange=?",
            (product, exchange),
        )
        row = cur.fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def list_products(self) -> list[tuple[str, str]]:
        """返回所有已有映射记录的 (product, exchange) 元组列表"""
        cur = self._conn.execute(
            "SELECT DISTINCT product, exchange FROM main_contract_mapping ORDER BY exchange, product"
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
# 第一步：生成主力映射表
# ─────────────────────────────────────────────────────────────────────────────

def build_dominant_mapping(
    prefix: str,
    exchange: Exchange,
    db,
    smoothing_days: int = 5,
) -> list[dict]:
    """
    按交易日选出当天持仓量最大的合约作为主力。

    smoothing_days：新主力需连续领先 smoothing_days 天才切换，避免频繁换月。
    默认值 5 与期货通换月策略对齐（实测 MA 2025-12-16 换月吻合）。

    返回：list of {
        "trade_date": date,
        "dominant": str,    # 主力合约代码
        "open_interest": float,
    }
    """
    # 加载该品种所有合约的日K线 overview（排除 LOCAL 主连本身）
    overviews = db.get_bar_overview()
    contracts = [
        o for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == exchange
        and symbol_prefix(o.symbol) == prefix
    ]

    if not contracts:
        return []

    # 确定查询时间范围
    start = min(o.start for o in contracts if o.start)
    end = max(o.end for o in contracts if o.end)
    start_dt = datetime.combine(start.date(), time(0, 0))
    end_dt = datetime.combine(end.date(), time(23, 59, 59))

    # 加载所有候选合约的日K线
    symbol_bars: dict[str, list[BarData]] = {}
    for o in contracts:
        bars = db.load_bar_data(o.symbol, exchange, Interval.DAILY, start_dt, end_dt)
        if bars:
            symbol_bars[o.symbol] = bars

    if not symbol_bars:
        return []

    # 构建每个交易日的 open_interest 字典
    # daily_oi[trade_date] = {symbol: open_interest}
    daily_oi: dict[date, dict[str, float]] = defaultdict(dict)
    for sym, bars in symbol_bars.items():
        for bar in bars:
            td = bar.datetime.date()
            daily_oi[td][sym] = bar.open_interest

    # 按交易日排序
    trade_dates = sorted(daily_oi.keys())
    if not trade_dates:
        return []

    # 平滑换月：当前主力和候选队列
    current_dominant = max(daily_oi[trade_dates[0]], key=daily_oi[trade_dates[0]].get)
    pending_new: str | None = None
    pending_count: int = 0

    mapping: list[dict] = []

    for td in trade_dates:
        oi_today = daily_oi[td]

        # 按 open_interest 降序找出最大持仓合约
        best = max(oi_today, key=oi_today.get)

        if best == current_dominant:
            pending_new = None
            pending_count = 0
        elif best == pending_new:
            pending_count += 1
            if pending_count >= smoothing_days:
                current_dominant = best
                pending_new = None
                pending_count = 0
        else:
            pending_new = best
            pending_count = 1

        mapping.append({
            "trade_date": td,
            "dominant": current_dominant,
            "open_interest": oi_today.get(current_dominant, 0.0),
        })

    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 第二步：用映射表拼接主连日线
# ─────────────────────────────────────────────────────────────────────────────

def build_main_daily_bars(
    prefix: str,
    exchange: Exchange,
    mapping: list[dict],
    db,
) -> list[BarData]:
    """
    按主力映射表逐日拼接日K线，生成不复权主连日线序列。
    主连 symbol = <prefix>888，exchange = LOCAL
    """
    if not mapping:
        return []

    dom_dates: dict[str, list[date]] = defaultdict(list)
    for row in mapping:
        dom_dates[row["dominant"]].append(row["trade_date"])

    bar_lookup: dict[str, dict[date, BarData]] = {}
    for sym, dates in dom_dates.items():
        start_dt = datetime.combine(min(dates), time(0, 0))
        end_dt = datetime.combine(max(dates), time(23, 59, 59))
        bars = db.load_bar_data(sym, exchange, Interval.DAILY, start_dt, end_dt)
        bar_lookup[sym] = {b.datetime.date(): b for b in bars}

    main_bars: list[BarData] = []
    main_exchange = Exchange.LOCAL
    main_symbol = main_contract_symbol(prefix)

    for row in mapping:
        td = row["trade_date"]
        sym = row["dominant"]
        src_bar = bar_lookup.get(sym, {}).get(td)
        if src_bar is None:
            continue

        main_bar = BarData(
            symbol=main_symbol,
            exchange=main_exchange,
            interval=Interval.DAILY,
            datetime=src_bar.datetime,
            open_price=src_bar.open_price,
            high_price=src_bar.high_price,
            low_price=src_bar.low_price,
            close_price=src_bar.close_price,
            volume=src_bar.volume,
            turnover=src_bar.turnover,
            open_interest=src_bar.open_interest,
            gateway_name="DB",
        )
        main_bars.append(main_bar)

    return main_bars


# ─────────────────────────────────────────────────────────────────────────────
# 第三步：用映射表拼接主连分钟线
# ─────────────────────────────────────────────────────────────────────────────

def build_main_minute_bars(
    prefix: str,
    exchange: Exchange,
    mapping: list[dict],
    db,
) -> list[BarData]:
    """
    按主力映射表逐日拼接分钟K线（当日主力固定，不盘中切换）。
    主连 symbol = <prefix>888，exchange = LOCAL
    """
    if not mapping:
        return []

    date_to_dom: dict[date, str] = {row["trade_date"]: row["dominant"] for row in mapping}
    dom_dates: dict[str, list[date]] = defaultdict(list)
    for td, sym in date_to_dom.items():
        dom_dates[sym].append(td)

    minute_lookup: dict[str, dict[date, list[BarData]]] = {}
    for sym, dates in dom_dates.items():
        start_dt = datetime.combine(min(dates) - timedelta(days=1), time(15, 0))
        end_dt = datetime.combine(max(dates) + timedelta(days=1), time(3, 0))
        bars = db.load_bar_data(sym, exchange, Interval.MINUTE, start_dt, end_dt)
        if not bars:
            continue
        day_bars: dict[date, list[BarData]] = defaultdict(list)
        for b in bars:
            td = assign_trade_date(b.datetime)
            day_bars[td].append(b)
        minute_lookup[sym] = day_bars

    main_bars: list[BarData] = []
    main_exchange = Exchange.LOCAL
    main_symbol = main_contract_symbol(prefix)

    for row in sorted(mapping, key=lambda x: x["trade_date"]):
        td = row["trade_date"]
        sym = row["dominant"]
        src_day_bars = minute_lookup.get(sym, {}).get(td, [])

        for src_bar in src_day_bars:
            main_bar = BarData(
                symbol=main_symbol,
                exchange=main_exchange,
                interval=Interval.MINUTE,
                datetime=src_bar.datetime,
                open_price=src_bar.open_price,
                high_price=src_bar.high_price,
                low_price=src_bar.low_price,
                close_price=src_bar.close_price,
                volume=src_bar.volume,
                turnover=src_bar.turnover,
                open_interest=src_bar.open_interest,
                gateway_name="DB",
            )
            main_bars.append(main_bar)

    return main_bars


# ─────────────────────────────────────────────────────────────────────────────
# 处理单个品种
# ─────────────────────────────────────────────────────────────────────────────

def process_product(
    prefix: str,
    exchange: Exchange,
    db,
    store: MappingStore,
    force: bool = False,
    dry_run: bool = False,
    with_minute: bool = True,
    smoothing_days: int = 2,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    处理单个品种，返回 (写入日线数量, 写入分钟线数量)
    """
    main_symbol = main_contract_symbol(prefix)
    main_vt = f"{main_symbol}.LOCAL"

    if verbose:
        print(f"\n[{prefix}.{exchange.value}] → {main_vt}")

    # ── 1. 生成完整主力映射表 ──────────────────────────────
    mapping = build_dominant_mapping(prefix, exchange, db, smoothing_days=smoothing_days)
    if not mapping:
        if verbose:
            print(f"  ⚠️  无日线数据，跳过")
        return 0, 0

    if verbose:
        changes = []
        prev_dom = None
        for row in mapping:
            if row["dominant"] != prev_dom:
                changes.append(f"{row['trade_date']} → {row['dominant']}")
                prev_dom = row["dominant"]
        print(f"  映射表：{len(mapping)} 个交易日，共 {len(changes)} 次切换")
        for c in changes[-5:]:
            print(f"    {c}")

    if dry_run:
        return 0, 0

    # ── 2. 持久化映射表到 SQLite ───────────────────────────
    store.save_mapping(
        product=prefix,
        exchange=exchange.value,
        mapping=mapping,
        replace=force,
    )

    # ── 3. 增量判断（日线）──────────────────────────────────
    overviews = db.get_bar_overview()
    main_daily_overview = next(
        (o for o in overviews
         if o.symbol == main_symbol
         and o.exchange == Exchange.LOCAL
         and o.interval == Interval.DAILY),
        None,
    )

    if not force and main_daily_overview and main_daily_overview.end:
        cutoff = main_daily_overview.end.date()
        mapping_new = [r for r in mapping if r["trade_date"] >= cutoff]
    else:
        mapping_new = mapping

    # ── 4. 拼接日线 ────────────────────────────────────────
    daily_bars = build_main_daily_bars(prefix, exchange, mapping_new, db)
    daily_count = 0
    if daily_bars:
        db.save_bar_data(daily_bars)
        daily_count = len(daily_bars)
        if verbose:
            print(f"  日线：写入 {daily_count} 根")

    # ── 5. 增量判断（分钟线）───────────────────────────────
    minute_count = 0
    if with_minute:
        main_minute_overview = next(
            (o for o in overviews
             if o.symbol == main_symbol
             and o.exchange == Exchange.LOCAL
             and o.interval == Interval.MINUTE),
            None,
        )
        if not force and main_minute_overview and main_minute_overview.end:
            cutoff_m = main_minute_overview.end.date()
            mapping_min_new = [r for r in mapping if r["trade_date"] >= cutoff_m]
        else:
            mapping_min_new = mapping

        minute_bars = build_main_minute_bars(prefix, exchange, mapping_min_new, db)
        if minute_bars:
            db.save_bar_data(minute_bars)
            minute_count = len(minute_bars)
            if verbose:
                print(f"  分钟线：写入 {minute_count} 根")

    return daily_count, minute_count


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="商品期货主连数据生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 预览模式，打印所有品种的主力映射摘要，不写数据库
  uv run python ai/data_process/build_main_contract.py --dry-run

  # 生成全部品种主连
  uv run python ai/data_process/build_main_contract.py

  # 只处理 MA（郑商所）
  uv run python ai/data_process/build_main_contract.py --symbol MA --exchange CZCE

  # 强制重建 rb（上期所）
  uv run python ai/data_process/build_main_contract.py --symbol rb --exchange SHFE --force

  # 导出完整主力映射表到 CSV
  uv run python ai/data_process/build_main_contract.py --export-mapping mapping.csv --dry-run
        """
    )
    parser.add_argument("--symbol", help="只处理指定品种前缀（如 MA 或 rb）")
    parser.add_argument("--exchange", help="配合 --symbol 使用的交易所（如 CZCE / SHFE）")
    parser.add_argument("--force", action="store_true", help="强制重建，覆盖已有主连数据和映射表")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，只打印映射表，不写数据库")
    parser.add_argument("--no-minute", action="store_true", help="不生成分钟主连（只生成日线主连）")
    parser.add_argument("--smoothing", type=int, default=5, help="换月平滑天数（默认 5，与期货通策略对齐）")
    parser.add_argument("--export-mapping", metavar="FILE", help="导出完整主力映射表到 CSV 文件")
    args = parser.parse_args()

    db = get_database()
    overviews = db.get_bar_overview()

    # 收集所有日线品种（排除 LOCAL 主连本身）
    products: dict[tuple[str, Exchange], None] = {}
    for o in overviews:
        if o.interval != Interval.DAILY:
            continue
        if o.exchange == Exchange.LOCAL:
            continue
        prefix = symbol_prefix(o.symbol)
        if not prefix:
            continue
        products[(prefix, o.exchange)] = None

    # 过滤指定品种
    if args.symbol:
        target_prefix = args.symbol
        target_exchange = Exchange(args.exchange) if args.exchange else None
        products = {
            k: v for k, v in products.items()
            if k[0] == target_prefix and (target_exchange is None or k[1] == target_exchange)
        }

    if not products:
        print("未找到符合条件的品种")
        return

    all_mapping_rows: list[dict] = []

    total_daily = 0
    total_minute = 0
    product_list = sorted(products.keys(), key=lambda x: (x[1].value, x[0]))
    print(f"共 {len(product_list)} 个品种待处理")
    if args.dry_run:
        print("【预览模式】不写入数据库\n")

    with MappingStore() as store:
        for prefix, exchange in product_list:
            mapping = build_dominant_mapping(prefix, exchange, db, smoothing_days=args.smoothing)

            if args.export_mapping and mapping:
                for row in mapping:
                    all_mapping_rows.append({
                        "product": prefix,
                        "exchange": exchange.value,
                        "trade_date": row["trade_date"].isoformat(),
                        "dominant": row["dominant"],
                        "open_interest": row["open_interest"],
                    })

            d, m = process_product(
                prefix=prefix,
                exchange=exchange,
                db=db,
                store=store,
                force=args.force,
                dry_run=args.dry_run,
                with_minute=not args.no_minute,
                smoothing_days=args.smoothing,
            )
            total_daily += d
            total_minute += m

    print(f"\n{'─' * 50}")
    if not args.dry_run:
        print(f"✅ 完成：共写入日线 {total_daily} 根，分钟线 {total_minute} 根")
        print(f"📦 映射表已持久化到：{MappingStore.DEFAULT_PATH}")
    else:
        print(f"✅ 预览完成（未写入数据库）")

    if args.export_mapping and all_mapping_rows:
        csv_path = Path(args.export_mapping)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["product", "exchange", "trade_date", "dominant", "open_interest"])
            writer.writeheader()
            writer.writerows(all_mapping_rows)
        print(f"📄 主力映射表已导出：{csv_path}（{len(all_mapping_rows)} 行）")


if __name__ == "__main__":
    main()
