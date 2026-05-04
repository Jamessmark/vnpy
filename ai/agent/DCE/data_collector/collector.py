"""
DCE 数据采集主流程

负责从大商所 API 下载增量日K线并保存到数据库，
然后更新主力映射表 + 合成 888 加权合约。

通用工具函数已迁移到 ai.agent.common（parse_date / format_date /
get_trade_dates / save_bar_to_db / MappingStore 等），
本文件只保留 DCE 特有的采集逻辑。
"""
import sys
import time as time_module
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval

from ai.agent.common.main_contract_manager import (
    MappingStore,
    symbol_prefix,
    identify_main_and_sub,
    get_previous_different_main,
    calculate_weighted_bar,
)
from ai.agent.common.bar_utils import (
    parse_date,
    format_date,
    get_trade_dates,
    save_bar_to_db,
)
from ai.agent.DCE.dce_constants import CORE_VARIETIES
from .dce_api import get_dce_client


# ─────────────────────────────────────────────────────────────────────────────
# 向后兼容导出（旧代码可能 import VARIETIES）
# ─────────────────────────────────────────────────────────────────────────────
VARIETIES = CORE_VARIETIES


# ─────────────────────────────────────────────────────────────────────────────
# DCE 专有 DB 工具
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_dce_date_in_db(db) -> Optional[date]:
    """获取数据库中 DCE 日K线的最新交易日"""
    overviews = [
        o for o in db.get_bar_overview()
        if o.exchange == Exchange.DCE and o.interval == Interval.DAILY
    ]
    if not overviews:
        return None
    latest = max(o.end for o in overviews if o.end)
    return latest.date() if latest else None


def load_contracts_from_db(variety: str, trade_date: date, db) -> Dict[str, Dict]:
    """
    从数据库加载某品种当日所有合约数据（排除 888 加权合约）。

    Returns:
        {symbol: {symbol, datetime, open, high, low, close, volume, turnover, open_interest}}
    """
    start_dt = datetime.combine(trade_date, time(0, 0))
    end_dt   = datetime.combine(trade_date, time(23, 59))

    overviews  = db.get_bar_overview()
    contracts  = [
        o.symbol for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == Exchange.DCE
        and symbol_prefix(o.symbol) == variety
        and "888" not in o.symbol
    ]

    result: Dict[str, Dict] = {}
    for symbol in contracts:
        bars = db.load_bar_data(symbol, Exchange.DCE, Interval.DAILY, start_dt, end_dt)
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
# DCE 增量采集主流程
# ─────────────────────────────────────────────────────────────────────────────

def daily_update(
    target_date: Optional[str] = None,
    backfill_days: int = 100,
    force_backfill_days: Optional[int] = None,
) -> Dict:
    """
    每日数据更新主流程。

    策略：
      1. 优先从数据库读取已有数据；
      2. 只从 API 下载数据库中缺失的最新日期；
      3. 更新每个品种的主力映射表 + 合成 888 合约。

    Args:
        target_date:         目标日期（YYYYMMDD）；None 则调 API 获取最新交易日
        backfill_days:       首次运行时回填的天数（当前未用）
        force_backfill_days: 强制回填天数（当前未用）

    Returns:
        统计字典 {status, target_date, new_contracts, updated_varieties, errors, ...}
    """
    client        = get_dce_client()
    db            = get_database()
    mapping_store = MappingStore()

    stats: Dict = {
        "start_time":       datetime.now(),
        "target_date":      None,
        "new_contracts":    0,
        "updated_varieties": 0,
        "errors":           [],
    }

    try:
        # ── 1. 确定目标日期 ───────────────────────────────────
        if target_date is None:
            target_date = client.get_max_trade_date()
        stats["target_date"] = target_date
        target_date_obj = parse_date(target_date)

        # ── 2. 检查数据库现有最新日期 ──────────────────────────
        latest_db_date = get_latest_dce_date_in_db(db)

        if latest_db_date is None:
            print("❌ 数据库为空，请先运行 import_excel.py 导入历史数据")
            stats["status"]   = "no_data"
            stats["end_time"] = datetime.now()
            return stats

        # ── 3. 确定增量范围 ────────────────────────────────────
        start_date = latest_db_date + timedelta(days=1)

        if start_date > target_date_obj:
            print(f"✅ 数据已是最新（最新日期: {latest_db_date}）")
            stats["status"]   = "up_to_date"
            stats["end_time"] = datetime.now()
            return stats

        print(f"📥 从 API 下载增量数据: {format_date(start_date)} ~ {target_date}")

        # ── 4. 下载缺失的日期数据 ─────────────────────────────
        trade_dates = get_trade_dates(start_date, target_date_obj)

        for date_str in trade_dates:
            try:
                time_module.sleep(1)  # 防止 API 限频
                all_quotes = client.get_day_quotes(date_str, variety_id="all")

                if not all_quotes:
                    print(f"  ⚠️ {date_str} 无数据（可能非交易日）")
                    continue

                for quote in all_quotes:
                    if not quote.get("contractId"):
                        continue  # 跳过汇总行

                    # turnover 可能是带逗号的字符串
                    turnover_val = quote.get("turnover", 0) or 0
                    if isinstance(turnover_val, str):
                        turnover_val = float(turnover_val.replace(",", ""))
                    else:
                        turnover_val = float(turnover_val)

                    bar_dict = {
                        "symbol":        quote["contractId"],
                        "datetime":      datetime.strptime(date_str, "%Y%m%d"),
                        "open":          float(quote.get("open",  0) or 0),
                        "high":          float(quote.get("high",  0) or 0),
                        "low":           float(quote.get("low",   0) or 0),
                        "close":         float(quote.get("close", 0) or 0),
                        # DCE API 字段是 "volumn"（拼写错误）
                        "volume":        float(quote.get("volumn", 0) or 0),
                        "turnover":      turnover_val,
                        "open_interest": float(quote.get("openInterest", 0) or 0),
                    }

                    save_bar_to_db(
                        symbol       = quote["contractId"],
                        exchange     = Exchange.DCE,
                        bar_dict     = bar_dict,
                        db           = db,
                        gateway_name = "DCE_API",
                    )
                    stats["new_contracts"] += 1

                print(f"  ✅ {date_str} 原始数据已保存（{len(all_quotes)} 个合约）")

            except Exception as e:
                msg = f"{date_str} 下载失败: {e}"
                print(f"  ❌ {msg}")
                stats["errors"].append(msg)

        # ── 5. 更新主力映射 + 合成 888 合约 ───────────────────
        for variety in VARIETIES:
            try:
                _update_variety_contracts(variety, trade_dates, mapping_store, db)
                stats["updated_varieties"] += 1
            except Exception as e:
                msg = f"品种 {variety} 更新失败: {e}"
                print(f"  ❌ {msg}")
                stats["errors"].append(msg)

        stats["status"]   = "success"
        stats["end_time"] = datetime.now()
        duration = (stats["end_time"] - stats["start_time"]).total_seconds()
        print(f"\n✅ 数据更新完成！耗时 {duration:.1f}s")

    except Exception as e:
        stats["status"] = "failed"
        stats["error"]  = str(e)
        print(f"\n❌ 数据更新失败: {e}")
        raise

    finally:
        mapping_store.close()

    return stats


def _update_variety_contracts(
    variety: str,
    dates: List[str],
    mapping_store: MappingStore,
    db,
) -> None:
    """
    逐日更新某品种的主力映射表并合成 888 加权合约。
    """
    for date_str in dates:
        trade_date    = parse_date(date_str)
        all_contracts = load_contracts_from_db(variety, trade_date, db)

        if not all_contracts:
            continue

        # 识别主力和次主力
        try:
            new_main, new_sub = identify_main_and_sub(
                variety, trade_date, all_contracts, mapping_store, exchange="DCE"
            )
        except Exception as e:
            print(f"  ⚠️ {variety} @ {date_str} 主力识别失败: {e}")
            continue

        # 获取旧主力
        old_main = get_previous_different_main(variety, new_main, mapping_store, exchange="DCE")

        # 保存主力映射
        mapping_store.save_mapping(
            product  = variety,
            exchange = "DCE",
            mapping  = [{
                "trade_date":    trade_date,
                "dominant":      new_main,
                "sub_dominant":  new_sub,
                "open_interest": all_contracts[new_main].get("open_interest", 0),
            }],
        )

        # 合成 888 加权合约
        old_main_data = all_contracts.get(old_main) if old_main else None
        try:
            weighted_bar = calculate_weighted_bar(
                variety       = variety,
                old_main_bar  = old_main_data,
                new_main_bar  = all_contracts[new_main],
                sub_bar       = all_contracts[new_sub],
            )
            save_bar_to_db(
                symbol       = f"{variety}888",
                exchange     = Exchange.DCE,
                bar_dict     = weighted_bar,
                db           = db,
                gateway_name = "DCE_888",
            )
        except Exception as e:
            print(f"  ⚠️ {variety}888 @ {date_str} 加权合成失败: {e}")


if __name__ == "__main__":
    result = daily_update(backfill_days=10)
    print(f"\n📊 统计信息:")
    print(f"  目标日期:   {result['target_date']}")
    print(f"  新增合约:   {result['new_contracts']}")
    print(f"  更新品种:   {result['updated_varieties']}")
    if result.get("errors"):
        print(f"  错误数:     {len(result['errors'])}")
