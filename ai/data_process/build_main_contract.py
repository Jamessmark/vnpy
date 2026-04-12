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
                sub_dominant   TEXT,
                open_interest  REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (product, exchange, trade_date)
            )
        """)
        # 尝试添加 sub_dominant 列（兼容旧表）
        try:
            self._conn.execute("ALTER TABLE main_contract_mapping ADD COLUMN sub_dominant TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在
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

        mapping 格式：list of {"trade_date": date, "dominant": str, "sub_dominant": str, "open_interest": float}
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
        rows = []
        for row in mapping:
            sub_dom = row.get("sub_dominant", row.get("dominant", ""))
            rows.append((
                product,
                exchange,
                row["trade_date"].isoformat(),
                row["dominant"],
                sub_dom,
                row.get("open_interest", 0.0),
            ))
        self._conn.executemany(
            f"{verb} INTO main_contract_mapping "
            f"(product, exchange, trade_date, dominant, sub_dominant, open_interest) VALUES (?,?,?,?,?,?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def get_all(self, product: str, exchange: str) -> list[dict]:
        """返回某品种全部映射记录，按 trade_date 升序"""
        cur = self._conn.execute(
            "SELECT trade_date, dominant, sub_dominant, open_interest FROM main_contract_mapping "
            "WHERE product=? AND exchange=? ORDER BY trade_date",
            (product, exchange),
        )
        return [
            {
                "trade_date": date.fromisoformat(row[0]),
                "dominant": row[1],
                "sub_dominant": row[2] if len(row) > 2 else row[1],
                "open_interest": row[3] if len(row) > 3 else 0.0,
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
    按交易日选出当天持仓量最大的合约作为主力，第二大的作为次主力。

    【主力判定】：
    使用平滑机制（smoothing_days），新主力必须连续 N 天持仓量第一，才会真正发生切换。
    这样可以避免在换月交接期，两个合约持仓量交替领先导致主力频繁闪跳。

    【次主力判定】：
    使用相同的平滑机制，新次主力必须连续 N 天排在次席（或超越当前次主力），才会真正发生切换。
    特殊保护：如果真实的次主力其实是当前的平滑主力（发生在新老交替期），则暂不切换。
    强制保护：输出的主力和次主力绝对不能是同一个合约（除非该品种当天只有1个合约有数据）。

    返回：list of {
        "trade_date": date,
        "dominant": str,      # 主力合约代码
        "sub_dominant": str,  # 次主力合约代码
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
    
    # 初始次主力：排除主力后持仓量最大的
    candidates = [sym for sym, oi in daily_oi[trade_dates[0]].items() if sym != current_dominant]
    current_sub = max(candidates, key=lambda s: daily_oi[trade_dates[0]][s]) if candidates else current_dominant
    
    # 平滑计数器
    pending_dom: str | None = None
    pending_dom_count: int = 0
    
    pending_sub: str | None = None
    pending_sub_count: int = 0

    mapping: list[dict] = []

    for td in trade_dates:
        oi_today = daily_oi[td]

        # 按 open_interest 降序排序
        sorted_syms = sorted(oi_today.keys(), key=lambda s: oi_today[s], reverse=True)

        # 找出今日实际的主力（OI最大）和次主力（OI第二）
        real_dom = sorted_syms[0] if sorted_syms else current_dominant
        real_sub = sorted_syms[1] if len(sorted_syms) > 1 else current_dominant

        # --- 1. 处理主力平滑切换 ---
        if real_dom == current_dominant:
            pending_dom = None
            pending_dom_count = 0
        elif real_dom == pending_dom:
            pending_dom_count += 1
            if pending_dom_count >= smoothing_days:
                current_dominant = real_dom
                pending_dom = None
                pending_dom_count = 0
        else:
            pending_dom = real_dom
            pending_dom_count = 1

        # --- 2. 处理次主力平滑切换 ---
        # 注意：如果次主力变成了主力，我们需要立即切换次主力，不能等平滑（否则主力次主力会变成同一个）
        if real_sub == current_dominant:
            # 这种情况通常发生在换月交接期，旧主力变成了现在的次主力
            pass

        if real_sub == current_sub:
            pending_sub = None
            pending_sub_count = 0
        elif real_sub == current_dominant:
            # 如果真实次主力其实是当前的平滑主力，这说明不要切
            pending_sub = None
            pending_sub_count = 0
        elif real_sub == pending_sub:
            pending_sub_count += 1
            if pending_sub_count >= smoothing_days:
                current_sub = real_sub
                pending_sub = None
                pending_sub_count = 0
        else:
            pending_sub = real_sub
            pending_sub_count = 1
            
        # 强制保护：主力次主力不能是同一个合约（除非该品种今天只有1个合约有数据）
        final_sub = current_sub
        if final_sub == current_dominant and len(sorted_syms) > 1:
            # 降级取真实次主力
            final_sub = real_sub

        mapping.append({
            "trade_date": td,
            "dominant": current_dominant,
            "sub_dominant": final_sub,
            "open_interest": oi_today.get(current_dominant, 0.0),
        })

    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 第二步：用映射表拼接主连日线
# ─────────────────────────────────────────────────────────────────────────────

def _weighted_bar(
    main_symbol: str,
    main_exchange: Exchange,
    interval: Interval,
    dt: datetime,
    bars: list[BarData],
) -> BarData | None:
    """
    将多根同一时间戳的 BarData 合成为一根加权虚拟 K 线：
      - open/high/low/close：按 volume 加权均价
      - volume / turnover / open_interest：各合约直接求和
    若 bars 为空返回 None；若只有一根则直接使用其价格（避免除零）。
    """
    if not bars:
        return None

    total_volume = sum(b.volume for b in bars)

    if total_volume > 0:
        w_open  = sum(b.open_price  * b.volume for b in bars) / total_volume
        w_high  = sum(b.high_price  * b.volume for b in bars) / total_volume
        w_low   = sum(b.low_price   * b.volume for b in bars) / total_volume
        w_close = sum(b.close_price * b.volume for b in bars) / total_volume
    else:
        # 全部成交量为 0（罕见），退化为简单均价
        n = len(bars)
        w_open  = sum(b.open_price  for b in bars) / n
        w_high  = sum(b.high_price  for b in bars) / n
        w_low   = sum(b.low_price   for b in bars) / n
        w_close = sum(b.close_price for b in bars) / n

    return BarData(
        symbol=main_symbol,
        exchange=main_exchange,
        interval=interval,
        datetime=dt,
        open_price=w_open,
        high_price=w_high,
        low_price=w_low,
        close_price=w_close,
        volume=total_volume,
        turnover=sum(b.turnover for b in bars),
        open_interest=sum(b.open_interest for b in bars),
        gateway_name="DB",
    )


def build_main_daily_bars(
    prefix: str,
    exchange: Exchange,
    mapping: list[dict],
    db,
) -> list[BarData]:
    """
    按主力映射表逐日合成主连日线序列。

    每个交易日取【主力 + 次主力】两个合约的日K线，
    按成交量加权合成价格，成交量/成交额/持仓量直接求和。
    主连 symbol = <prefix>888，exchange = LOCAL
    """
    if not mapping:
        return []

    # 确定日期范围
    all_dates = [row["trade_date"] for row in mapping]
    start_dt = datetime.combine(min(all_dates), time(0, 0))
    end_dt   = datetime.combine(max(all_dates), time(23, 59, 59))

    # 加载该品种所有合约的日K线（排除 LOCAL 主连本身）
    overviews = db.get_bar_overview()
    contracts = [
        o.symbol for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == exchange
        and symbol_prefix(o.symbol) == prefix
    ]

    # symbol -> {trade_date: BarData}
    bar_lookup: dict[str, dict[date, BarData]] = {}
    for sym in contracts:
        bars = db.load_bar_data(sym, exchange, Interval.DAILY, start_dt, end_dt)
        if bars:
            bar_lookup[sym] = {b.datetime.date(): b for b in bars}

    main_bars: list[BarData] = []
    main_exchange = Exchange.LOCAL
    main_symbol = main_contract_symbol(prefix)

    for row in mapping:
        td  = row["trade_date"]
        dom = row["dominant"]
        sub = row.get("sub_dominant", dom)  # 兼容旧数据

        # 收集主力+次主力合约的bar
        day_bars: list[BarData] = []
        if dom in bar_lookup and td in bar_lookup[dom]:
            day_bars.append(bar_lookup[dom][td])
        if sub in bar_lookup and td in bar_lookup[sub]:
            day_bars.append(bar_lookup[sub][td])

        if not day_bars:
            continue

        # 取主力合约的 datetime 作为合成 bar 的时间戳
        bar_dt = day_bars[0].datetime

        main_bar = _weighted_bar(main_symbol, main_exchange, Interval.DAILY, bar_dt, day_bars)
        if main_bar:
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
    按主力映射表逐日合成主连分钟线序列。

    每个交易日取【主力 + 次主力】两个合约的分钟K线，
    对相同时间戳的多根 bar 按成交量加权合成价格，
    成交量/成交额/持仓量直接求和。
    主连 symbol = <prefix>888，exchange = LOCAL
    """
    if not mapping:
        return []

    all_dates = [row["trade_date"] for row in mapping]
    start_dt  = datetime.combine(min(all_dates) - timedelta(days=1), time(15, 0))
    end_dt    = datetime.combine(max(all_dates) + timedelta(days=1), time(3, 0))

    # 加载该品种所有合约的分钟K线（排除 LOCAL 主连本身）
    overviews = db.get_bar_overview()
    contracts = [
        o.symbol for o in overviews
        if o.interval == Interval.MINUTE
        and o.exchange == exchange
        and symbol_prefix(o.symbol) == prefix
    ]

    # sym -> trade_date -> {timestamp -> BarData}
    minute_lookup: dict[str, dict[date, dict[datetime, BarData]]] = {}
    for sym in contracts:
        bars = db.load_bar_data(sym, exchange, Interval.MINUTE, start_dt, end_dt)
        if not bars:
            continue
        by_day: dict[date, dict[datetime, BarData]] = defaultdict(dict)
        for b in bars:
            td = assign_trade_date(b.datetime)
            by_day[td][b.datetime] = b
        minute_lookup[sym] = by_day

    main_bars: list[BarData] = []
    main_exchange = Exchange.LOCAL
    main_symbol = main_contract_symbol(prefix)

    for row in sorted(mapping, key=lambda x: x["trade_date"]):
        td      = row["trade_date"]
        dom_sym = row["dominant"]
        sub_sym = row.get("sub_dominant", dom_sym)

        # 收集主力+次主力合约的 timestamp 集合（以主力合约的时间戳为基准）
        dom_timestamps = set(
            minute_lookup.get(dom_sym, {}).get(td, {}).keys()
        )
        if not dom_timestamps:
            continue

        for ts in sorted(dom_timestamps):
            # 收集该时间戳下主力+次主力的 bar
            ts_bars: list[BarData] = []
            if dom_sym in minute_lookup and td in minute_lookup[dom_sym] and ts in minute_lookup[dom_sym][td]:
                ts_bars.append(minute_lookup[dom_sym][td][ts])
            if sub_sym in minute_lookup and td in minute_lookup[sub_sym] and ts in minute_lookup[sub_sym][td]:
                ts_bars.append(minute_lookup[sub_sym][td][ts])

            main_bar = _weighted_bar(main_symbol, main_exchange, Interval.MINUTE, ts, ts_bars)
            if main_bar:
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
                        "sub_dominant": row.get("sub_dominant", row["dominant"]),
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
