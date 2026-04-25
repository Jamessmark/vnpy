"""
数据采集主流程
负责协调 DCE API 数据下载、主力合约识别、加权合成等操作
"""
import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional

# 确保能导入项目根目录的 vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval

from .dce_api import get_dce_client
from .main_contract_manager import (
    MappingStore,
    symbol_prefix,
    identify_main_and_sub,
    get_previous_different_main,
    calculate_weighted_bar
)


# 大商所主要品种列表
VARIETIES = [
    "a",   # 豆一
    "b",   # 豆二
    "c",   # 玉米
    "cs",  # 玉米淀粉
    "m",   # 豆粕
    "y",   # 豆油
    "p",   # 棕榈油
    "jd",  # 鸡蛋
    "l",   # 塑料
    "v",   # PVC
    "pp",  # 聚丙烯
    "j",   # 焦炭
    "jm",  # 焦煤
    "i",   # 铁矿石
    "eg",  # 乙二醇
    "eb",  # 苯乙烯
    "pg",  # 液化石油气
]


def parse_date(date_str: str) -> date:
    """解析日期字符串 YYYYMMDD -> date"""
    return datetime.strptime(date_str, "%Y%m%d").date()


def format_date(d: date) -> str:
    """格式化日期 date -> YYYYMMDD"""
    return d.strftime("%Y%m%d")


def get_trade_dates(start_date: date, end_date: date) -> List[str]:
    """
    获取指定范围内的所有日期（简化版，实际应查询交易日历）
    
    TODO: 接入真实交易日历
    """
    dates = []
    current = start_date
    while current <= end_date:
        # 简单过滤周末
        if current.weekday() < 5:  # 0-4 代表周一到周五
            dates.append(format_date(current))
        current += timedelta(days=1)
    return dates


def get_latest_date_in_db(db) -> Optional[date]:
    """获取数据库中最新的交易日"""
    overviews = db.get_bar_overview()
    dce_overviews = [
        o for o in overviews 
        if o.exchange == Exchange.DCE and o.interval == Interval.DAILY
    ]
    
    if not dce_overviews:
        return None
    
    latest = max(o.end for o in dce_overviews if o.end)
    return latest.date() if latest else None


def get_earliest_date_in_db(symbol: str, exchange: Exchange, db) -> Optional[date]:
    """获取某合约在数据库中的最早日期"""
    overviews = db.get_bar_overview()
    target = [
        o for o in overviews 
        if o.symbol == symbol and o.exchange == exchange and o.interval == Interval.DAILY
    ]
    
    if not target:
        return None
    
    earliest = min(o.start for o in target if o.start)
    return earliest.date() if earliest else None


def load_contracts_from_db(variety: str, trade_date: date, db) -> Dict[str, Dict]:
    """从数据库加载某品种当日所有合约数据（排除 888 加权合约）"""
    start_dt = datetime.combine(trade_date, time(0, 0))
    end_dt = datetime.combine(trade_date, time(23, 59))
    
    # 获取该品种所有合约列表
    overviews = db.get_bar_overview()
    contracts = [
        o.symbol for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == Exchange.DCE
        and symbol_prefix(o.symbol) == variety
        and "888" not in o.symbol  # 排除 888 加权合约
    ]
    
    # 加载各合约当日数据
    result = {}
    for symbol in contracts:
        bars = db.load_bar_data(symbol, Exchange.DCE, Interval.DAILY, start_dt, end_dt)
        if bars:
            bar = bars[0]
            result[symbol] = {
                "symbol": symbol,
                "datetime": bar.datetime,
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume,
                "turnover": bar.turnover,
                "open_interest": bar.open_interest,
            }
    
    return result


def save_bar_to_db(symbol: str, exchange: Exchange, bar_dict: Dict, db):
    """将K线数据保存到数据库"""
    bar = BarData(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.DAILY,
        datetime=bar_dict['datetime'],
        open_price=bar_dict['open'],
        high_price=bar_dict['high'],
        low_price=bar_dict['low'],
        close_price=bar_dict['close'],
        volume=bar_dict['volume'],
        turnover=bar_dict.get('turnover', 0),
        open_interest=bar_dict.get('open_interest', 0),
        gateway_name="DCE_MAIN",
    )
    db.save_bar_data([bar])


def daily_update(
    target_date: Optional[str] = None,
    backfill_days: int = 100,
    force_backfill_days: Optional[int] = None
) -> Dict:
    """
    每日数据更新主流程
    
    策略：
    1. 优先从数据库读取已有数据
    2. 只从 API 下载数据库中没有的最新数据
    
    Args:
        target_date: 目标日期（YYYYMMDD），None则使用最新交易日
        backfill_days: 首次运行时回填的天数
        force_backfill_days: 强制回填天数（忽略现有数据，直接下载指定天数）
    
    Returns:
        更新统计信息
    """
    client = get_dce_client()
    db = get_database()
    mapping_store = MappingStore()
    
    stats = {
        "start_time": datetime.now(),
        "target_date": None,
        "new_contracts": 0,
        "updated_varieties": 0,
        "errors": []
    }
    
    try:
        # Step 1: 确定目标日期
        if target_date is None:
            target_date = client.get_max_trade_date()
        
        stats["target_date"] = target_date
        target_date_obj = parse_date(target_date)
        
        # Step 2: 检查数据库中已有数据
        latest_db_date = get_latest_date_in_db(db)
        
        if latest_db_date is None:
            # 数据库为空，首次运行需要导入历史数据
            print(f"❌ 数据库为空，请先运行 import_excel.py 导入历史数据")
            stats["status"] = "no_data"
            stats["end_time"] = datetime.now()
            return stats
        
        # Step 3: 确定需要下载的日期范围
        start_date = latest_db_date + timedelta(days=1)
        
        if start_date > target_date_obj:
            print(f"✅ 数据已是最新（最新日期: {latest_db_date}）")
            stats["end_time"] = datetime.now()
            stats["status"] = "up_to_date"
            return stats
        
        print(f"📥 从 API 下载增量数据: {format_date(start_date)} ~ {target_date}")
        
        # Step 4: 只下载缺失的日期
        trade_dates = get_trade_dates(start_date, target_date_obj)
        
        for date_str in trade_dates:
            try:
                # 下载当日全部合约（带延时，防止API限频）
                import time as time_module
                time_module.sleep(1)
                all_quotes = client.get_day_quotes(date_str, variety_id="all")
                
                if not all_quotes:
                    print(f"  ⚠️ {date_str} 无数据（可能非交易日）")
                    continue
                
                # 保存原始合约到数据库
                for quote in all_quotes:
                    # 过滤掉 subtotal rows (contractId is None)
                    if not quote.get('contractId'):
                        continue
                    
                    # 处理 turnover 可能是字符串的情况
                    turnover_val = quote.get('turnover', 0)
                    if turnover_val is None:
                        turnover_val = 0
                    elif isinstance(turnover_val, str):
                        turnover_val = float(turnover_val.replace(',', ''))
                    else:
                        turnover_val = float(turnover_val)
                    
                    bar_dict = {
                        "symbol": quote['contractId'],
                        # DCE API 没有 tradeDate 字段，使用传入的 date_str
                        "datetime": datetime.strptime(date_str, "%Y%m%d"),
                        # DCE API 字段名是 open/high/low/close（不是 openPrice 等）
                        "open": float(quote.get('open', 0) or 0),
                        "high": float(quote.get('high', 0) or 0),
                        "low": float(quote.get('low', 0) or 0),
                        "close": float(quote.get('close', 0) or 0),
                        # DCE API 字段名是 volumn（不是 volume）
                        "volume": float(quote.get('volumn', 0) or 0),
                        "turnover": turnover_val,
                        "open_interest": float(quote.get('openInterest', 0) or 0),
                    }
                    
                    save_bar_to_db(
                        quote['contractId'],
                        Exchange.DCE,
                        bar_dict,
                        db
                    )
                    stats["new_contracts"] += 1
                
                print(f"  ✅ {date_str} 原始数据已保存（{len(all_quotes)} 个合约）")
                
            except Exception as e:
                error_msg = f"{date_str} 下载失败: {e}"
                print(f"  ❌ {error_msg}")
                stats["errors"].append(error_msg)
        
        # Step 4: 更新每个品种的主力映射表 + 生成888合约
        for variety in VARIETIES:
            try:
                update_variety_contracts(variety, trade_dates, mapping_store, db)
                stats["updated_varieties"] += 1
            except Exception as e:
                error_msg = f"品种 {variety} 更新失败: {e}"
                print(f"  ❌ {error_msg}")
                stats["errors"].append(error_msg)
        
        stats["status"] = "success"
        stats["end_time"] = datetime.now()
        duration = (stats["end_time"] - stats["start_time"]).total_seconds()
        print(f"\n✅ 数据更新完成！耗时 {duration:.1f}秒")
        
    except Exception as e:
        stats["status"] = "failed"
        stats["error"] = str(e)
        print(f"\n❌ 数据更新失败: {e}")
        raise
    
    finally:
        mapping_store.close()
    
    return stats


def update_variety_contracts(
    variety: str,
    dates: List[str],
    mapping_store: MappingStore,
    db
):
    """更新品种的主力映射表 + 生成888合约"""
    
    for date_str in dates:
        trade_date = parse_date(date_str)
        
        # 1. 从数据库加载当日全部合约数据
        all_contracts = load_contracts_from_db(variety, trade_date, db)
        
        if not all_contracts:
            continue
        
        # 2. 识别主力和次主力
        try:
            new_main, new_sub = identify_main_and_sub(
                variety, trade_date, all_contracts, mapping_store
            )
        except Exception as e:
            print(f"  ⚠️ {variety} @ {date_str} 主力识别失败: {e}")
            continue
        
        # 3. 获取旧主力
        old_main = get_previous_different_main(variety, new_main, mapping_store)
        
        # 4. 保存主力映射
        mapping_store.save_mapping(
            product=variety,
            exchange="DCE",
            mapping=[{
                "trade_date": trade_date,
                "dominant": new_main,
                "sub_dominant": new_sub,
                "open_interest": all_contracts[new_main].get('open_interest', 0)
            }]
        )
        
        # 5. 生成888加权合约（按成交量加权）
        old_main_data = all_contracts.get(old_main) if old_main else None
        new_main_data = all_contracts[new_main]
        sub_data = all_contracts[new_sub]
        
        try:
            weighted_bar = calculate_weighted_bar(
                new_main_data=new_main_data,
                sub_data=sub_data,
                old_main_data=old_main_data,
            )
            
            # 保存888合约
            save_bar_to_db(f"{variety}888", Exchange.DCE, weighted_bar, db)
            
        except Exception as e:
            print(f"  ⚠️ {variety}888 @ {date_str} 加权合成失败: {e}")


if __name__ == "__main__":
    # 测试运行
    result = daily_update(backfill_days=10)
    print(f"\n📊 统计信息:")
    print(f"  目标日期: {result['target_date']}")
    print(f"  新增合约数据: {result['new_contracts']}")
    print(f"  更新品种数: {result['updated_varieties']}")
    if result.get('errors'):
        print(f"  错误数: {len(result['errors'])}")
