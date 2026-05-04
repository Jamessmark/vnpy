"""
主连数据重建器（交易所通用）

从 vnpy 数据库中已有的原始合约日K线，批量回溯所有历史交易日，
逐日识别主力合约并合成 888 加权 K 线写回数据库。

与 DCE/collector.py 的区别：
  collector.py  —— 只处理 "最新交易日 → 今天" 的增量
  builder.py    —— 从数据库中第一天开始全量重建历史

用法：
    from ai.agent.main_contract_builder.builder import rebuild_all, rebuild_variety

    # 重建 DCE 全部品种
    stats = rebuild_all(exchange="DCE")

    # 仅重建指定品种
    stats = rebuild_all(exchange="DCE", varieties=["a", "m"])

    # 只重建某一个品种，返回逐日统计
    result = rebuild_variety("m", exchange="DCE")
"""
import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from ai.agent.common.main_contract_manager import (
    MappingStore,
    symbol_prefix,
    identify_main_and_sub,
    get_previous_different_main,
    calculate_weighted_bar,
)
from ai.agent.common.bar_utils import save_bar_to_db


# ─────────────────────────────────────────────────────────────────────────────
# 交易所名称 → Exchange 枚举 映射
# ─────────────────────────────────────────────────────────────────────────────
_EXCHANGE_MAP: Dict[str, Exchange] = {
    "DCE":  Exchange.DCE,
    "CZCE": Exchange.CZCE,
    "SHFE": Exchange.SHFE,
    "INE":  Exchange.INE,
    "GFEX": Exchange.GFEX,
    "CFFEX": Exchange.CFFEX,
}


def _to_exchange(exchange: str) -> Exchange:
    """字符串 → Exchange 枚举，不区分大小写"""
    key = exchange.upper()
    if key not in _EXCHANGE_MAP:
        raise ValueError(f"不支持的交易所: {exchange}，可选: {list(_EXCHANGE_MAP)}")
    return _EXCHANGE_MAP[key]


def _is_option(symbol: str) -> bool:
    """
    判断是否为期权合约代码。

    期权特征（任一满足即为期权）：
      1. `-O` 结尾（大商所/郑商所期权，如 a2307-O、CF2307-O）
      2. `-C-` 或 `-P-` 出现在任意位置（CFFEX/郑商所期权，如 IO2307-C-4400、CY2001-C-2800）
      3. 品种代码后有 C 或 P 再跟数字（非月份）：
         - 无连字符：CY2001C2800（郑商所）
         - 有连字符：CU2307C50000（SHFE/INE）
         - 短格式： l2307-C（部分品种）
      4. `-C` 单独结尾

    注意：
      CZCE 期货月份用 3 位数字（如 CY001 = 2001 年 1 月到期），
      而期权格式是 CY2001C2800 或 CY2001-C-2800，
      本函数通过"品种字母后跟 C/P/数字序列"来区分。
    """
    import re
    s = symbol.upper()

    # 1. -O 结尾（大商所/郑商所）
    if s.endswith("-O"):
        return True

    # 2. -C- 或 -P- 出现任意位置（郑商所/部分 GFEX）
    if "-C-" in s or "-P-" in s:
        return True

    # 3. 提取"品种字母"部分（去掉末尾的数字）后的字符含 C 或 P + 数字序列
    #    即：品种(如 CU/CY/IO) + 数字(如 2307) + C/P + 行权价
    #    用正则 "字母序列 + 数字序列 + C/P + 数字序列" 匹配
    if re.search(r"[A-Z]+\d+C\d", s):
        return True   # CY2001C2800, CY2001-C-2800, CU2307C50000

    # 4. -C 单独结尾（如 l2307-C、pg2307-C）
    if re.search(r"-\d+-C$", s) or s.endswith("-C"):
        return True

    return False


def _is_futures(symbol: str) -> bool:
    """判断是否为期货合约（排除期权、888 合成合约）"""
    if "888" in symbol:
        return False
    if _is_option(symbol):
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 数据库工具函数
# ─────────────────────────────────────────────────────────────────────────────

def get_varieties_in_db(exchange: Exchange, db) -> List[str]:
    """
    从数据库 overview 中读取该交易所所有期货品种前缀。

    排除：888 合成合约、期权合约。

    Returns:
        品种前缀列表，如 ["a", "b", "c", ...]
    """
    overviews = db.get_bar_overview()
    prefixes  = set()
    for o in overviews:
        if o.exchange == exchange and o.interval == Interval.DAILY:
            if not _is_futures(o.symbol):
                continue
            prefix = symbol_prefix(o.symbol)
            if prefix and not prefix.isdigit():
                prefixes.add(prefix)
    return sorted(prefixes)


def get_all_trade_dates_for_variety(
    variety: str,
    exchange: Exchange,
    db,
) -> List[date]:
    """
    从数据库 overview 中取该品种所有原始合约的日期范围，
    然后枚举 [最早日期, 最晚日期] 的所有工作日。

    之所以用枚举而不是直接查每天有无数据：
      - 避免节假日（无数据的交易日）造成映射表空洞
      - load_contracts_from_db 返回空字典时直接跳过即可

    Returns:
        按升序排列的 date 列表
    """
    overviews = [
        o for o in db.get_bar_overview()
        if o.exchange == exchange
        and o.interval == Interval.DAILY
        and _is_futures(o.symbol)
        and symbol_prefix(o.symbol) == variety
    ]
    if not overviews:
        return []

    min_date = min(o.start for o in overviews if o.start).date()
    max_date = max(o.end   for o in overviews if o.end  ).date()

    dates: List[date] = []
    cur = min_date
    while cur <= max_date:
        if cur.weekday() < 5:   # 只保留工作日
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


def load_all_contracts_bulk(
    variety: str,
    exchange: Exchange,
    db,
) -> Dict[str, Dict[str, Dict]]:
    """
    一次性加载某品种所有合约在全部历史日期的 K 线数据（内存版）。

    对每个合约只发 1 次 load_bar_data 查询，然后在内存里按日期组织数据。
    替代逐日调用 load_day_contracts，大幅减少数据库 IO。

    Returns:
        {(symbol, date): bar_dict}  即 {合约代码: {日期date: bar数据}}
    """
    # 1. 取合约列表
    overviews = db.get_bar_overview()
    contract_symbols = [
        o.symbol for o in overviews
        if o.exchange == exchange
        and o.interval == Interval.DAILY
        and _is_futures(o.symbol)
        and symbol_prefix(o.symbol) == variety
    ]

    if not contract_symbols:
        return {}

    # 2. 取日期范围
    v_overviews = [
        o for o in overviews
        if o.exchange == exchange
        and o.interval == Interval.DAILY
        and _is_futures(o.symbol)
        and symbol_prefix(o.symbol) == variety
    ]
    min_dt = min(o.start for o in v_overviews if o.start)
    max_dt = max(o.end   for o in v_overviews if o.end  )
    if min_dt is None or max_dt is None:
        return {}

    # 3. 每个合约只查一次全量
    result: Dict[str, Dict[str, Dict]] = {}  # {symbol: {date_str: bar_dict}}
    for symbol in contract_symbols:
        bars = db.load_bar_data(symbol, exchange, Interval.DAILY, min_dt, max_dt)
        contract_dict: Dict[str, Dict] = {}
        for bar in bars:
            d = bar.datetime.date().isoformat()  # 用 ISO 字符串作 key
            if d not in contract_dict:  # 同一天取第一条
                contract_dict[d] = {
                    "symbol":        symbol,
                    "datetime":      bar.datetime,
                    "open":          bar.open_price,
                    "high":          bar.high_price,
                    "low":           bar.low_price,
                    "close":         bar.close_price,
                    "volume":        bar.volume,
                    "turnover":      bar.turnover,
                    "open_interest": bar.open_interest,
                }
        result[symbol] = contract_dict

    return result


def load_day_contracts(
    variety: str,
    trade_date: date,
    exchange: Exchange,
    db,
    _contract_symbols_cache: Optional[List[str]] = None,
) -> Dict[str, Dict]:
    """
    从数据库加载某品种某天的全部原始合约数据（排除 888）。

    Args:
        variety:                品种前缀
        trade_date:             交易日
        exchange:               交易所枚举
        db:                     vnpy 数据库
        _contract_symbols_cache: 预先查好的合约列表（加速批量调用）

    Returns:
        {symbol: {symbol, datetime, open, high, low, close, volume, turnover, open_interest}}
    """
    start_dt = datetime.combine(trade_date, time(0, 0))
    end_dt   = datetime.combine(trade_date, time(23, 59))

    if _contract_symbols_cache is None:
        overviews = db.get_bar_overview()
        _contract_symbols_cache = [
            o.symbol for o in overviews
            if o.exchange == exchange
            and o.interval == Interval.DAILY
            and _is_futures(o.symbol)
            and symbol_prefix(o.symbol) == variety
        ]

    result: Dict[str, Dict] = {}
    for symbol in _contract_symbols_cache:
        bars = db.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        if bars:
            bar = bars[0]
            result[symbol] = {
                "symbol":        symbol,
                "datetime":      bar.datetime,
                "open":          bar.open_price,
                "high":          bar.high_price,
                "low":           bar.low_price,
                "close":         bar.close_price,
                "volume":        bar.volume,
                "turnover":      bar.turnover,
                "open_interest": bar.open_interest,
            }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 核心重建函数
# ─────────────────────────────────────────────────────────────────────────────

def rebuild_variety(
    variety: str,
    exchange: str = "DCE",
    force: bool = True,
    db=None,
    mapping_store: Optional[MappingStore] = None,
    verbose: bool = True,
) -> Dict:
    """
    重建单个品种的全部历史主连（888）K 线。

    流程：
      1. 从 overview 取该品种所有日期范围
      2. 逐日加载当天原始合约数据
      3. identify_main_and_sub 识别主力/次主力
      4. 保存主力映射到 MappingStore
      5. calculate_weighted_bar 合成 888 K 线
      6. 写回数据库（save_bar_to_db）

    Args:
        variety:       品种前缀，如 "a"、"m"、"rb"
        exchange:      交易所字符串，如 "DCE"、"SHFE"
        force:         True = 覆盖已有的 888 数据；False = 已有数据的日期跳过
        db:            vnpy 数据库实例（None 时自动 get_database()）
        mapping_store: MappingStore 实例（None 时自动创建）
        verbose:       是否打印进度

    Returns:
        {
            "variety": str,
            "exchange": str,
            "total_dates": int,       # 枚举的工作日数
            "skipped": int,           # 无原始数据的交易日
            "generated": int,         # 成功生成 888 K 线的天数
            "errors": int,            # 失败的天数
            "mapping_rows": int,      # 写入映射表的行数
            "date_range": (start, end) | None,
        }
    """
    exchange_str  = exchange.upper()
    exchange_enum = _to_exchange(exchange_str)

    _own_db    = db is None
    _own_store = mapping_store is None

    if _own_db:
        db = get_database()
    if _own_store:
        mapping_store = MappingStore()

    stats = {
        "variety":     variety,
        "exchange":    exchange_str,
        "total_dates": 0,
        "skipped":     0,
        "generated":   0,
        "errors":      0,
        "mapping_rows": 0,
        "date_range":  None,
    }

    try:
        # ── 1. 取历史日期范围 ─────────────────────────────────────────
        trade_dates = get_all_trade_dates_for_variety(variety, exchange_enum, db)
        if not trade_dates:
            if verbose:
                print(f"  ⚠️  {variety}.{exchange_str}: 数据库无原始合约数据，跳过")
            return stats

        stats["total_dates"] = len(trade_dates)
        stats["date_range"]  = (trade_dates[0], trade_dates[-1])

        if verbose:
            print(f"\n📈 {variety}.{exchange_str}  "
                  f"{trade_dates[0]} ~ {trade_dates[-1]}  "
                  f"共 {len(trade_dates)} 个工作日")

        # ── 2. 如果 force=False，取已有 888 的日期集合用于跳过 ────────
        existing_888_dates: set = set()
        if not force:
            symbol_888 = f"{variety}888"
            try:
                bars_888 = db.load_bar_data(
                    symbol_888, exchange_enum, Interval.DAILY,
                    datetime.combine(trade_dates[0],  time(0, 0)),
                    datetime.combine(trade_dates[-1], time(23, 59)),
                )
                existing_888_dates = {b.datetime.date() for b in bars_888}
                if verbose and existing_888_dates:
                    print(f"   ↳ 已有 {len(existing_888_dates)} 天 888 数据，将跳过")
            except Exception:
                pass

        # ── 3. 一次性加载全部历史数据到内存 ──────────────────────────
        if verbose:
            print(f"   ⏳ 加载历史数据到内存...")
        bulk_data = load_all_contracts_bulk(variety, exchange_enum, db)
        if not bulk_data:
            if verbose:
                print(f"  ⚠️  {variety}.{exchange_str}: 无法加载历史数据，跳过")
            return stats
        all_symbols = sorted(bulk_data.keys())
        if verbose:
            print(f"   ✅ 已加载 {len(all_symbols)} 个合约，内存查询无 IO")

        # ── 4. 逐日处理（内存查表，无数据库 IO）───────────────────
        batch_bars: List[BarData] = []

        for trade_date in trade_dates:
            # 跳过已有数据（非 force 模式）
            if not force and trade_date in existing_888_dates:
                continue

            date_str = trade_date.isoformat()

            # 加载当日原始合约（从内存查表，零数据库 IO）
            all_contracts: Dict[str, Dict] = {}
            for symbol in all_symbols:
                bar_dict = bulk_data[symbol].get(date_str)
                if bar_dict:
                    all_contracts[symbol] = bar_dict
            if not all_contracts:
                stats["skipped"] += 1
                continue

            try:
                # 识别主力/次主力
                new_main, new_sub = identify_main_and_sub(
                    variety, trade_date, all_contracts,
                    mapping_store, exchange=exchange_str
                )

                # 保存映射行（identify_main_and_sub 下一天会用到）
                mapping_store.save_mapping(
                    product  = variety,
                    exchange = exchange_str,
                    mapping  = [{
                        "trade_date":    trade_date,
                        "dominant":      new_main,
                        "sub_dominant":  new_sub,
                        "open_interest": all_contracts[new_main].get("open_interest", 0),
                    }],
                )
                stats["mapping_rows"] += 1

                # 获取旧主力数据（需校验是否在当天数据中）
                old_main = get_previous_different_main(
                    variety, new_main, mapping_store, exchange=exchange_str
                )
                old_main_data = all_contracts.get(old_main) if old_main else None

                # 校验次主力是否在当天数据中（主力合约已在前面的 identify_main_and_sub 里保证存在）
                # 次主力可能在历史映射里，但当天已退市（无 K 线数据），此时找一个替代合约
                sub_data = all_contracts.get(new_sub)
                if sub_data is None:
                    candidates = {
                        sym: data for sym, data in all_contracts.items()
                        if sym != new_main
                    }
                    if candidates:
                        sub_data = max(candidates.values(), key=lambda x: x.get("open_interest", 0))
                        if verbose:
                            print(f"   ⚠️  {trade_date} 次主力 {new_sub} 已退市，"
                                  f"替换为 {sub_data['symbol']}")
                    else:
                        # 当天只有 1 个合约：用同一合约兼作次主力（加权平均时两权重合一，等价于单合约）
                        sub_data = all_contracts[new_main]
                        if verbose:
                            print(f"   ⚠️  {trade_date} 仅 1 个合约 {new_main}，"
                                  f"次主力与其相同")

                # 合成 888 K 线
                weighted_bar = calculate_weighted_bar(
                    variety      = variety,
                    old_main_bar = old_main_data,
                    new_main_bar = all_contracts[new_main],
                    sub_bar      = sub_data,
                )

                # 攒批量写库
                batch_bars.append(BarData(
                    symbol        = f"{variety}888",
                    exchange      = exchange_enum,
                    interval      = Interval.DAILY,
                    datetime      = weighted_bar["datetime"],
                    open_price    = weighted_bar["open"],
                    high_price    = weighted_bar["high"],
                    low_price     = weighted_bar["low"],
                    close_price   = weighted_bar["close"],
                    volume        = weighted_bar["volume"],
                    turnover      = weighted_bar.get("turnover", 0),
                    open_interest = weighted_bar.get("open_interest", 0),
                    gateway_name  = "MAIN_888",
                ))
                stats["generated"] += 1

                # 每 500 根批量写一次，减少 IO
                if len(batch_bars) >= 500:
                    db.save_bar_data(batch_bars)
                    batch_bars.clear()

            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    print(f"   ❌ {trade_date} 失败: {e}")

        # 写入剩余数据
        if batch_bars:
            db.save_bar_data(batch_bars)

        if verbose:
            print(f"   ✅ 生成 {stats['generated']} 根 888 K线 | "
                  f"跳过无数据 {stats['skipped']} 天 | "
                  f"错误 {stats['errors']} 天")

    finally:
        if _own_store:
            mapping_store.close()

    return stats


def rebuild_all(
    exchange: str = "DCE",
    varieties: Optional[List[str]] = None,
    force: bool = True,
    verbose: bool = True,
) -> Dict:
    """
    批量重建某交易所所有（或指定）品种的历史主连（888）数据。

    Args:
        exchange:   交易所字符串（大小写不敏感），如 "DCE"、"SHFE"
        varieties:  品种列表；None 时自动从数据库中探测所有品种
        force:      True = 覆盖重建；False = 已有 888 数据的日期跳过
        verbose:    是否打印进度

    Returns:
        {
            "exchange": str,
            "varieties_total": int,
            "varieties_ok": int,
            "varieties_skip": int,
            "total_generated": int,
            "total_errors": int,
            "details": {variety: stats_dict, ...}
        }
    """
    exchange_str  = exchange.upper()
    exchange_enum = _to_exchange(exchange_str)
    db            = get_database()
    mapping_store = MappingStore()

    # 探测品种列表
    if varieties is None:
        varieties = get_varieties_in_db(exchange_enum, db)
        if verbose:
            print(f"📦 自动探测到 {exchange_str} 共 {len(varieties)} 个品种：{varieties}")
    else:
        varieties = [v.lower() for v in varieties]

    summary = {
        "exchange":         exchange_str,
        "varieties_total":  len(varieties),
        "varieties_ok":     0,
        "varieties_skip":   0,
        "total_generated":  0,
        "total_errors":     0,
        "details":          {},
    }

    print(f"\n{'='*60}")
    print(f"🔨 开始重建 {exchange_str} 主连（888）历史数据")
    print(f"   品种数: {len(varieties)}  force={force}")
    print(f"{'='*60}")

    try:
        for i, variety in enumerate(varieties, 1):
            print(f"\n[{i}/{len(varieties)}]", end="")
            try:
                result = rebuild_variety(
                    variety       = variety,
                    exchange      = exchange_str,
                    force         = force,
                    db            = db,
                    mapping_store = mapping_store,
                    verbose       = verbose,
                )
                summary["details"][variety] = result
                if result["generated"] > 0:
                    summary["varieties_ok"]    += 1
                    summary["total_generated"] += result["generated"]
                else:
                    summary["varieties_skip"]  += 1
                summary["total_errors"] += result["errors"]
            except Exception as e:
                print(f"   ❌ 品种 {variety} 整体失败: {e}")
                summary["varieties_skip"] += 1
                summary["details"][variety] = {"error": str(e)}

    finally:
        mapping_store.close()

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 重建完成 — {exchange_str}")
    print(f"{'='*60}")
    print(f"  品种总数:   {summary['varieties_total']}")
    print(f"  成功品种:   {summary['varieties_ok']}")
    print(f"  跳过品种:   {summary['varieties_skip']}")
    print(f"  生成K线总数: {summary['total_generated']}")
    print(f"  错误总数:   {summary['total_errors']}")

    return summary
