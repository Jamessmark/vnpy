"""
每日补齐脚本：分钟K → 日K → 主连(888)

目标：
1) 每天下午 16:00 后执行一次
2) 自动探测数据库中“期货”数据缺口
3) 先补日K（由分钟K聚合）
4) 再补主连888（由日K重建）

示例：
    # 仅探测，不落库
    uv run python ai/agent/main_contract_builder/daily_backfill.py --exchange DCE --dry-run

    # 执行单交易所
    uv run python ai/agent/main_contract_builder/daily_backfill.py --exchange DCE

    # 执行全部交易所
    uv run python ai/agent/main_contract_builder/daily_backfill.py --all

    # 包含当日（默认不包含，避免未收盘）
    uv run python ai/agent/main_contract_builder/daily_backfill.py --exchange DCE --include-today
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData

from ai.agent.common.main_contract_manager import symbol_prefix
from ai.agent.main_contract_builder.builder import (
    _to_exchange,
    _is_futures,
    get_varieties_in_db,
    rebuild_variety,
)


# 交易日切割点：>=16:00 视为下一交易日（夜盘）
NIGHT_SESSION_START = time(16, 0)


def assign_trade_date(dt: datetime) -> date:
    """分钟K时间戳映射到交易日"""
    if dt.time() >= NIGHT_SESSION_START:
        return (dt + timedelta(days=1)).date()
    return dt.date()


@dataclass
class SymbolDailyBackfillStat:
    symbol: str
    exchange: str
    latest_minute_trade_date: Optional[str]
    latest_daily_date: Optional[str]
    generated_daily_bars: int
    skipped_existing_dates: int
    message: str = ""


@dataclass
class VarietyMainBackfillStat:
    variety: str
    exchange: str
    latest_daily_date: Optional[str]
    latest_main888_date: Optional[str]
    generated_main888_bars: int
    errors: int
    message: str = ""


def _latest_daily_overview_map(overviews, exchange_enum) -> Dict[str, date]:
    """按 symbol 汇总最新日K日期（仅期货原始合约，不含888）"""
    result: Dict[str, date] = {}
    for o in overviews:
        if o.exchange != exchange_enum or o.interval != Interval.DAILY:
            continue
        if not _is_futures(o.symbol):
            continue
        if not o.end:
            continue
        d = o.end.date()
        old = result.get(o.symbol)
        if old is None or d > old:
            result[o.symbol] = d
    return result


def _latest_minute_overview_map(overviews, exchange_enum) -> Dict[str, date]:
    """按 symbol 汇总最新分钟K交易日（仅期货原始合约，不含888）"""
    result: Dict[str, date] = {}
    for o in overviews:
        if o.exchange != exchange_enum or o.interval != Interval.MINUTE:
            continue
        if not _is_futures(o.symbol):
            continue
        if not o.end:
            continue
        d = assign_trade_date(o.end)
        old = result.get(o.symbol)
        if old is None or d > old:
            result[o.symbol] = d
    return result


def convert_symbol_minute_to_daily(
    symbol: str,
    exchange_enum,
    db,
    minute_ov=None,
    daily_ov=None,
    include_today: bool = False,
    dry_run: bool = False,
) -> SymbolDailyBackfillStat:
    """单合约：分钟K增量聚合补日K"""
    latest_minute_trade_date = assign_trade_date(minute_ov.end) if minute_ov and minute_ov.end else None
    latest_daily_date = daily_ov.end.date() if daily_ov and daily_ov.end else None

    if not minute_ov or not minute_ov.start:
        return SymbolDailyBackfillStat(
            symbol=symbol,
            exchange=exchange_enum.value,
            latest_minute_trade_date=str(latest_minute_trade_date) if latest_minute_trade_date else None,
            latest_daily_date=str(latest_daily_date) if latest_daily_date else None,
            generated_daily_bars=0,
            skipped_existing_dates=0,
            message="无分钟K",
        )

    # 增量窗口：从最后日K前一天开始（防止跨日边界漏算）
    if latest_daily_date:
        start_dt = datetime.combine(latest_daily_date - timedelta(days=1), time(0, 0))
    else:
        start_dt = minute_ov.start

    end_dt = datetime.now()

    minute_bars = db.load_bar_data(symbol, exchange_enum, Interval.MINUTE, start_dt, end_dt)
    if not minute_bars:
        return SymbolDailyBackfillStat(
            symbol=symbol,
            exchange=exchange_enum.value,
            latest_minute_trade_date=str(latest_minute_trade_date) if latest_minute_trade_date else None,
            latest_daily_date=str(latest_daily_date) if latest_daily_date else None,
            generated_daily_bars=0,
            skipped_existing_dates=0,
            message="分钟K窗口内无数据",
        )

    # 聚合：trade_date -> OHLCV
    agg: Dict[date, Dict] = {}
    for bar in minute_bars:
        td = assign_trade_date(bar.datetime)
        row = agg.get(td)
        if row is None:
            agg[td] = {
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume,
                "turnover": bar.turnover,
                "open_interest": bar.open_interest,
            }
        else:
            row["high"] = max(row["high"], bar.high_price)
            row["low"] = min(row["low"], bar.low_price)
            row["close"] = bar.close_price
            row["volume"] += bar.volume
            row["turnover"] += bar.turnover
            row["open_interest"] = bar.open_interest

    if not agg:
        return SymbolDailyBackfillStat(
            symbol=symbol,
            exchange=exchange_enum.value,
            latest_minute_trade_date=str(latest_minute_trade_date) if latest_minute_trade_date else None,
            latest_daily_date=str(latest_daily_date) if latest_daily_date else None,
            generated_daily_bars=0,
            skipped_existing_dates=0,
            message="聚合后为空",
        )

    # 默认不包含当日
    today = date.today()
    candidates = [d for d in sorted(agg.keys()) if include_today or d < today]
    if not candidates:
        return SymbolDailyBackfillStat(
            symbol=symbol,
            exchange=exchange_enum.value,
            latest_minute_trade_date=str(latest_minute_trade_date) if latest_minute_trade_date else None,
            latest_daily_date=str(latest_daily_date) if latest_daily_date else None,
            generated_daily_bars=0,
            skipped_existing_dates=0,
            message="无可落库交易日（可能只包含当日）",
        )

    # 现有日K日期集合（用于去重）
    existing_daily_dates: Set[date] = set()
    if daily_ov and daily_ov.start and daily_ov.end:
        existing = db.load_bar_data(symbol, exchange_enum, Interval.DAILY, daily_ov.start, daily_ov.end)
        existing_daily_dates = {b.datetime.date() for b in existing}

    bars_to_save: List[BarData] = []
    skipped = 0
    for d in candidates:
        if d in existing_daily_dates:
            skipped += 1
            continue
        row = agg[d]
        bars_to_save.append(
            BarData(
                symbol=symbol,
                exchange=exchange_enum,
                interval=Interval.DAILY,
                datetime=datetime.combine(d, time(0, 0)),
                open_price=row["open"],
                high_price=row["high"],
                low_price=row["low"],
                close_price=row["close"],
                volume=row["volume"],
                turnover=row["turnover"],
                open_interest=row["open_interest"],
                gateway_name="MIN2DAY",
            )
        )

    if bars_to_save and not dry_run:
        db.save_bar_data(bars_to_save)

    return SymbolDailyBackfillStat(
        symbol=symbol,
        exchange=exchange_enum.value,
        latest_minute_trade_date=str(latest_minute_trade_date) if latest_minute_trade_date else None,
        latest_daily_date=str(latest_daily_date) if latest_daily_date else None,
        generated_daily_bars=len(bars_to_save),
        skipped_existing_dates=skipped,
        message="dry-run" if dry_run else "ok",
    )


def backfill_exchange(
    exchange: str,
    include_today: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
) -> Dict:
    """单交易所补齐：分钟->日K，再日K->主连"""
    exchange_enum = _to_exchange(exchange)
    db = get_database()

    overviews = db.get_bar_overview()
    minute_latest = _latest_minute_overview_map(overviews, exchange_enum)
    daily_latest = _latest_daily_overview_map(overviews, exchange_enum)

    minute_ov_map = {
        o.symbol: o
        for o in overviews
        if o.exchange == exchange_enum and o.interval == Interval.MINUTE and _is_futures(o.symbol)
    }
    daily_ov_map = {
        o.symbol: o
        for o in overviews
        if o.exchange == exchange_enum and o.interval == Interval.DAILY and _is_futures(o.symbol)
    }

    # 1) 合约级别：找需要从分钟补日K的 symbols
    symbols_need_daily: List[str] = []
    for symbol, m_latest in minute_latest.items():
        d_latest = daily_latest.get(symbol)
        if d_latest is None or m_latest > d_latest:
            symbols_need_daily.append(symbol)

    symbols_need_daily = sorted(symbols_need_daily)

    if verbose:
        print(f"\n{'='*60}")
        print(f"🏛️  {exchange} 每日补齐")
        print(f"  分钟合约数: {len(minute_latest)}")
        print(f"  日K合约数:  {len(daily_latest)}")
        print(f"  需补日K:    {len(symbols_need_daily)}")
        print(f"  模式: {'DRY-RUN' if dry_run else 'EXECUTE'}")

    daily_stats: List[SymbolDailyBackfillStat] = []
    for i, symbol in enumerate(symbols_need_daily, 1):
        st = convert_symbol_minute_to_daily(
            symbol=symbol,
            exchange_enum=exchange_enum,
            db=db,
            minute_ov=minute_ov_map.get(symbol),
            daily_ov=daily_ov_map.get(symbol),
            include_today=include_today,
            dry_run=dry_run,
        )
        daily_stats.append(st)
        if verbose and (st.generated_daily_bars > 0 or st.message != "ok"):
            print(f"  [{i}/{len(symbols_need_daily)}] {symbol}: +{st.generated_daily_bars} 日K, skip={st.skipped_existing_dates} ({st.message})")

    # 2) 品种级别：探测日K vs 主连888 缺口，增量补主连
    overviews_after = db.get_bar_overview() if not dry_run else overviews

    # 品种最新日K
    variety_daily_latest: Dict[str, date] = {}
    for o in overviews_after:
        if o.exchange != exchange_enum or o.interval != Interval.DAILY:
            continue
        if not _is_futures(o.symbol):
            continue
        if not o.end:
            continue
        v = symbol_prefix(o.symbol)
        old = variety_daily_latest.get(v)
        d = o.end.date()
        if old is None or d > old:
            variety_daily_latest[v] = d

    # 品种最新888
    variety_main_latest: Dict[str, date] = {}
    for o in overviews_after:
        if o.exchange != exchange_enum or o.interval != Interval.DAILY:
            continue
        if "888" not in o.symbol:
            continue
        if not o.end:
            continue
        v = symbol_prefix(o.symbol)
        old = variety_main_latest.get(v)
        d = o.end.date()
        if old is None or d > old:
            variety_main_latest[v] = d

    varieties = sorted(get_varieties_in_db(exchange_enum, db))
    varieties_need_main: List[str] = []
    for v in varieties:
        d_latest = variety_daily_latest.get(v)
        m_latest = variety_main_latest.get(v)
        if d_latest is None:
            continue
        if m_latest is None or d_latest > m_latest:
            varieties_need_main.append(v)

    if verbose:
        print(f"  需补主连品种: {len(varieties_need_main)}")

    main_stats: List[VarietyMainBackfillStat] = []
    for i, v in enumerate(varieties_need_main, 1):
        d_latest = variety_daily_latest.get(v)
        m_latest = variety_main_latest.get(v)

        if dry_run:
            main_stats.append(
                VarietyMainBackfillStat(
                    variety=v,
                    exchange=exchange,
                    latest_daily_date=str(d_latest) if d_latest else None,
                    latest_main888_date=str(m_latest) if m_latest else None,
                    generated_main888_bars=0,
                    errors=0,
                    message="dry-run",
                )
            )
            continue

        try:
            r = rebuild_variety(v, exchange=exchange, force=False, verbose=False)
            main_stats.append(
                VarietyMainBackfillStat(
                    variety=v,
                    exchange=exchange,
                    latest_daily_date=str(d_latest) if d_latest else None,
                    latest_main888_date=str(m_latest) if m_latest else None,
                    generated_main888_bars=int(r.get("generated", 0)),
                    errors=int(r.get("errors", 0)),
                    message="ok",
                )
            )
            if verbose:
                print(f"  [{i}/{len(varieties_need_main)}] {v}888: +{r.get('generated', 0)}")
        except Exception as e:
            main_stats.append(
                VarietyMainBackfillStat(
                    variety=v,
                    exchange=exchange,
                    latest_daily_date=str(d_latest) if d_latest else None,
                    latest_main888_date=str(m_latest) if m_latest else None,
                    generated_main888_bars=0,
                    errors=1,
                    message=str(e),
                )
            )

    summary = {
        "exchange": exchange,
        "dry_run": dry_run,
        "minute_symbols": len(minute_latest),
        "daily_symbols": len(daily_latest),
        "symbols_need_daily": len(symbols_need_daily),
        "daily_generated_total": sum(s.generated_daily_bars for s in daily_stats),
        "daily_skipped_total": sum(s.skipped_existing_dates for s in daily_stats),
        "varieties_need_main": len(varieties_need_main),
        "main_generated_total": sum(s.generated_main888_bars for s in main_stats),
        "main_errors_total": sum(s.errors for s in main_stats),
        "daily_stats": [asdict(s) for s in daily_stats if s.generated_daily_bars > 0 or s.message != "ok"],
        "main_stats": [asdict(s) for s in main_stats],
    }

    if verbose:
        print(f"  ✅ 日K新增: {summary['daily_generated_total']} | 主连新增: {summary['main_generated_total']} | 主连错误: {summary['main_errors_total']}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="每日16:00补齐脚本：分钟K->日K->主连(888)")
    parser.add_argument("--exchange", "-e", default="DCE", help="交易所（DCE/CZCE/SHFE/INE/GFEX/CFFEX）")
    parser.add_argument("--all", "-a", action="store_true", help="处理全部交易所")
    parser.add_argument("--include-today", action="store_true", help="包含当日交易日（默认不包含）")
    parser.add_argument("--dry-run", action="store_true", help="只探测不落库")
    parser.add_argument("--json", action="store_true", help="打印JSON结果")
    parser.add_argument("--report", type=Path, default=None, help="写入JSON报告路径")
    args = parser.parse_args()

    targets = ["DCE", "CZCE", "SHFE", "INE", "GFEX", "CFFEX"] if args.all else [args.exchange.upper()]

    all_summary: Dict[str, Dict] = {}
    for ex in targets:
        try:
            all_summary[ex] = backfill_exchange(
                exchange=ex,
                include_today=args.include_today,
                dry_run=args.dry_run,
                verbose=True,
            )
        except Exception as e:
            all_summary[ex] = {"exchange": ex, "error": str(e)}
            print(f"❌ {ex} 失败: {e}")

    result = {
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "targets": targets,
        "dry_run": args.dry_run,
        "include_today": args.include_today,
        "by_exchange": all_summary,
    }

    if args.json:
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n📄 报告已写入: {args.report.resolve()}")


if __name__ == "__main__":
    main()
