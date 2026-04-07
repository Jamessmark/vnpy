"""
K 线数据加载模块
从 vnpy 数据库读取指定品种的最近 N 天日 K 线数据，并计算常用衍生指标
额外从 MainContractStore 加载换月记录，丰富 LLM 分析素材
"""

import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any

# 项目根目录
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from ai.data_process.build_main_contract import MappingStore


def load_recent_bars(
    symbol: str,
    exchange_str: str,
    days: int = 20,
    end_date: datetime | None = None,
) -> list[BarData]:
    """
    从 vnpy 数据库加载最近 N 天的日 K 线

    Args:
        symbol:       合约代码，如 "MA888"
        exchange_str: 交易所字符串，如 "LOCAL"
        days:         回溯天数（日历日），默认 20
        end_date:     截止日期，默认今天

    Returns:
        list[BarData]，按日期升序排列
    """
    if end_date is None:
        end_date = datetime.now().replace(hour=23, minute=59, second=59)

    # 往前多取日历天，保证有足够的交易日
    start_date = end_date - timedelta(days=max(days * 2, 60))

    db = get_database()
    exchange = Exchange(exchange_str)

    bars = db.load_bar_data(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.DAILY,
        start=start_date,
        end=end_date,
    )

    bars = sorted(bars, key=lambda b: b.datetime)
    return bars[-days:] if len(bars) >= days else bars


def load_recent_switches(
    product: str,
    exchange: str,
    days: int = 60,
    end_date: datetime | None = None,
) -> list[dict]:
    """
    从 MainContractStore 获取最近 N 天内的换月节点

    Returns:
        list[{"trade_date": date, "dominant": str}]，最近几次换月
    """
    if end_date is None:
        end_date = datetime.now()
    cutoff = (end_date - timedelta(days=days)).date()

    try:
        store = MappingStore()
        switches = store.get_switches(product, exchange)
        # 只取 cutoff 之后的换月，最多返回 5 条
        recent = [s for s in switches if s["trade_date"] >= cutoff]
        return recent[-5:]
    except Exception:
        return []


def bars_to_summary(
    bars: list[BarData],
    name: str,
    recent_switches: list[dict] | None = None,
) -> dict[str, Any]:
    """
    将 K 线列表转换为结构化摘要（含衍生指标 + 换月信息），供 LLM 使用

    Returns:
        dict，包含 name、symbol、bars（逐日数据列表）、stats（统计信息）、switches（换月节点）
    """
    if not bars:
        return {"name": name, "symbol": "", "bars": [], "stats": {}, "switches": []}

    daily = []
    for bar in bars:
        daily.append({
            "date":          bar.datetime.strftime("%Y-%m-%d"),
            "open":          round(bar.open_price, 2),
            "high":          round(bar.high_price, 2),
            "low":           round(bar.low_price, 2),
            "close":         round(bar.close_price, 2),
            "volume":        int(bar.volume),
            "open_interest": int(bar.open_interest),
            "amplitude_pct": round((bar.high_price - bar.low_price) / bar.open_price * 100, 2)
            if bar.open_price else 0,
        })

    # 计算涨跌幅
    for i in range(1, len(daily)):
        prev_close = bars[i - 1].close_price
        curr_close = bars[i].close_price
        daily[i]["chg_pct"] = round((curr_close - prev_close) / prev_close * 100, 2) if prev_close else 0
    if daily:
        daily[0]["chg_pct"] = 0.0

    # 统计摘要
    closes  = [b.close_price for b in bars]
    volumes = [b.volume for b in bars]
    oi_list = [b.open_interest for b in bars]
    latest  = bars[-1]

    stats = {
        "latest_close":     round(latest.close_price, 2),
        "latest_date":      latest.datetime.strftime("%Y-%m-%d"),
        "latest_oi":        int(latest.open_interest),
        "period_high":      round(max(b.high_price for b in bars), 2),
        "period_low":       round(min(b.low_price for b in bars), 2),
        "total_chg_pct":    round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else 0,
        "avg_volume":       int(sum(volumes) / len(volumes)),
        "oi_chg":           int(oi_list[-1] - oi_list[0]) if oi_list else 0,   # 区间持仓量变化
        "trend":            "上涨" if closes[-1] > closes[0] else "下跌" if closes[-1] < closes[0] else "横盘",
    }

    # 换月节点（格式化为字符串）
    switch_strs = [
        f"{s['trade_date'].isoformat()} 切换至 {s['dominant']}"
        for s in (recent_switches or [])
    ]

    return {
        "name":     name,
        "symbol":   bars[0].vt_symbol,
        "bars":     daily,
        "stats":    stats,
        "switches": switch_strs,   # 最近换月记录
    }


def load_all_symbols(
    watch_symbols: list[tuple],
    days: int = 20,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    批量加载所有监控品种的数据（含换月信息）

    Args:
        watch_symbols: [(symbol, exchange_str, name, product_prefix, product_exchange), ...]
                       后两项可选，用于查询换月记录

    Returns:
        list[dict]，每个元素是 bars_to_summary 的结果
    """
    results = []
    for item in watch_symbols:
        symbol, exchange_str, name = item[0], item[1], item[2]
        product_prefix   = item[3] if len(item) > 3 else None
        product_exchange = item[4] if len(item) > 4 else None

        print(f"  [数据] 加载 {name}（{symbol}.{exchange_str}）...", flush=True)
        try:
            bars = load_recent_bars(symbol, exchange_str, days=days, end_date=end_date)

            # 加载换月信息
            switches = []
            if product_prefix and product_exchange:
                switches = load_recent_switches(product_prefix, product_exchange, days=days * 3, end_date=end_date)
                if switches:
                    print(f"         换月记录：{len(switches)} 条（最近 {days*3} 天内）")

            summary = bars_to_summary(bars, name, recent_switches=switches)
            results.append(summary)
            print(f"         ✓ {len(bars)} 根日K线，最新收盘 {summary['stats'].get('latest_close', 'N/A')}")
        except Exception as e:
            print(f"         ✗ 加载失败：{e}")
            results.append({"name": name, "symbol": f"{symbol}.{exchange_str}", "bars": [], "stats": {}, "switches": []})
    return results
