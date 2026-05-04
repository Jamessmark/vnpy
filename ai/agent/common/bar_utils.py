"""
通用 Bar 工具函数

提供日期解析、交易日枚举、BarData 保存等与交易所无关的公用工具。
可被任意交易所 Agent 引用。

用法：
    from ai.agent.common.bar_utils import (
        parse_date, format_date, get_trade_dates, save_bar_to_db
    )
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


def parse_date(date_str: str) -> date:
    """解析日期字符串 YYYYMMDD -> date"""
    return datetime.strptime(date_str, "%Y%m%d").date()


def format_date(d: date) -> str:
    """格式化日期 date -> YYYYMMDD"""
    return d.strftime("%Y%m%d")


def get_trade_dates(start_date: date, end_date: date) -> List[str]:
    """
    获取 [start_date, end_date] 范围内的所有工作日（周一到周五）。

    Note:
        这是简化实现，只过滤周末，不考虑节假日。
        如需精确交易日历，请接入真实日历服务。

    Returns:
        日期字符串列表（YYYYMMDD 格式）
    """
    dates: List[str] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 0-4 = 周一到周五
            dates.append(format_date(current))
        current += timedelta(days=1)
    return dates


def save_bar_to_db(
    symbol: str,
    exchange: Exchange,
    bar_dict: Dict,
    db,
    gateway_name: str = "DB",
) -> None:
    """
    将 bar_dict 格式的 K 线数据保存到数据库。

    bar_dict 字段：
        datetime     datetime      时间戳
        open         float         开盘价
        high         float         最高价
        low          float         最低价
        close        float         收盘价
        volume       float         成交量
        turnover     float         成交额（可选，默认 0）
        open_interest float        持仓量（可选，默认 0）

    Args:
        symbol:       合约代码
        exchange:     交易所枚举
        bar_dict:     K 线数据字典
        db:           vnpy 数据库实例（get_database() 的返回值）
        gateway_name: 数据来源标识（默认 "DB"）
    """
    bar = BarData(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.DAILY,
        datetime=bar_dict["datetime"],
        open_price=bar_dict["open"],
        high_price=bar_dict["high"],
        low_price=bar_dict["low"],
        close_price=bar_dict["close"],
        volume=bar_dict["volume"],
        turnover=bar_dict.get("turnover", 0),
        open_interest=bar_dict.get("open_interest", 0),
        gateway_name=gateway_name,
    )
    db.save_bar_data([bar])
