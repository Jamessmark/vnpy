"""
分钟K线转日K线工具

将数据库中录制的 1分钟K线 聚合为 日K线 写回数据库。

支持增量运行：自动跳过已有日K线的交易日，只处理新数据。

使用方法：
    # 转换所有合约
    uv run python examples/data_recorder/minute_to_daily.py

    # 只转换指定合约
    uv run python examples/data_recorder/minute_to_daily.py --symbol cu2606 --exchange SHFE

    # 强制重新计算所有日K线（覆盖已有数据）
    uv run python examples/data_recorder/minute_to_daily.py --force
"""

import argparse
from datetime import datetime, date, time, timedelta

import pandas as pd

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


# =============================================================================
# 交易日划分规则（统一规则，适用于所有品种）
#
#   日盘：09:00 ~ 15:00（CFFEX 到 15:15）
#   夜盘：20:00 ~ 次日凌晨（不同品种结束时间不同，最晚 02:30）
#
#   规则：时间 >= 16:00 的分钟K线，归属「次日」交易日
#         时间 <  16:00 的分钟K线，归属「当日」交易日
#
#   举例：
#     2026-04-01 21:00  →  归属 2026-04-02（次日夜盘）
#     2026-04-02 01:00  →  归属 2026-04-02（当日夜盘尾段，自然日已是4-2，归属当日）
#     2026-04-02 10:00  →  归属 2026-04-02（当日日盘）
# =============================================================================

NIGHT_SESSION_START = time(16, 0)   # 日K线切割点：>= 16:00 归属次日，< 16:00 归属当日


def assign_trade_date(dt: datetime) -> date:
    """
    将分钟K线的时间戳分配到对应的交易日

    规则：
    - 时间 >= 16:00：收盘后/夜盘，归属次日交易日
    - 时间 <  16:00：归属当日交易日
    """
    if dt.time() >= NIGHT_SESSION_START:
        return (dt + timedelta(days=1)).date()
    return dt.date()


def convert_symbol_to_daily(
    symbol: str,
    exchange: Exchange,
    db,
    force: bool = False
) -> int:
    """
    将单个合约的分钟K线聚合为日K线

    返回：生成的日K线数量
    """
    # 查询现有分钟K线范围
    overviews = db.get_bar_overview()
    minute_overview = next(
        (o for o in overviews
         if o.symbol == symbol and o.exchange == exchange and o.interval == Interval.MINUTE),
        None
    )

    if not minute_overview:
        return 0

    # 查询现有日K线范围（用于增量判断）
    daily_overview = next(
        (o for o in overviews
         if o.symbol == symbol and o.exchange == exchange and o.interval == Interval.DAILY),
        None
    )

    # 确定需要处理的起始时间
    if not force and daily_overview and daily_overview.end:
        # 增量模式：只处理最后一根日K线之后的数据（多往前取1天防止当天未完成）
        start = datetime.combine(daily_overview.end.date() - timedelta(days=1), time(0, 0))
    else:
        start = minute_overview.start

    end = datetime.now()

    # 加载分钟K线
    minute_bars = db.load_bar_data(symbol, exchange, Interval.MINUTE, start, end)
    if not minute_bars:
        return 0

    # 转成 DataFrame
    records = []
    for bar in minute_bars:
        records.append({
            "datetime": bar.datetime,
            "open": bar.open_price,
            "high": bar.high_price,
            "low": bar.low_price,
            "close": bar.close_price,
            "volume": bar.volume,
            "turnover": bar.turnover,
            "open_interest": bar.open_interest,
        })

    df = pd.DataFrame(records)
    df["trade_date"] = df["datetime"].apply(assign_trade_date)

    # 按交易日聚合
    daily_df = df.groupby("trade_date").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        turnover=("turnover", "sum"),
        open_interest=("open_interest", "last"),
    ).reset_index()

    # 过滤掉今天未完成的交易日（当天日K线还在进行中）
    today = date.today()
    daily_df = daily_df[daily_df["trade_date"] < today]

    if daily_df.empty:
        return 0

    # 转回 BarData 列表
    daily_bars: list[BarData] = []
    for _, row in daily_df.iterrows():
        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.DAILY,
            datetime=datetime.combine(row["trade_date"], time(0, 0)),
            open_price=row["open"],
            high_price=row["high"],
            low_price=row["low"],
            close_price=row["close"],
            volume=row["volume"],
            turnover=row["turnover"],
            open_interest=row["open_interest"],
            gateway_name="DB",
        )
        daily_bars.append(bar)

    # 写回数据库
    db.save_bar_data(daily_bars)
    return len(daily_bars)


def main() -> None:
    parser = argparse.ArgumentParser(description="分钟K线转日K线工具")
    parser.add_argument("--symbol", help="指定合约代码（如 cu2606），不指定则处理所有合约")
    parser.add_argument("--exchange", help="指定交易所（如 SHFE），配合 --symbol 使用")
    parser.add_argument("--force", action="store_true", help="强制重新计算所有日K线（覆盖已有数据）")
    args = parser.parse_args()

    db = get_database()
    overviews = db.get_bar_overview()

    # 过滤出分钟K线合约列表
    minute_contracts = [
        (o.symbol, o.exchange, o.count)
        for o in overviews
        if o.interval == Interval.MINUTE
    ]

    # 如果指定了合约，只处理该合约
    if args.symbol:
        exchange = Exchange(args.exchange) if args.exchange else None
        minute_contracts = [
            (s, e, c) for s, e, c in minute_contracts
            if s == args.symbol and (exchange is None or e == exchange)
        ]

    total_contracts = len(minute_contracts)
    total_bars = 0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始转换，共 {total_contracts} 个合约...")

    for i, (symbol, exchange, minute_count) in enumerate(minute_contracts, 1):
        try:
            count = convert_symbol_to_daily(symbol, exchange, db, force=args.force)
            total_bars += count
            if count > 0:
                print(f"  [{i:3d}/{total_contracts}] {symbol}.{exchange.value}: 生成 {count} 根日K线")
        except Exception as e:
            print(f"  [{i:3d}/{total_contracts}] {symbol}.{exchange.value}: ❌ 错误 - {e}")

    print()
    print(f"✅ 转换完成：{total_contracts} 个合约，共生成 {total_bars} 根日K线")


if __name__ == "__main__":
    main()
