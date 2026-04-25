"""
DCE 888 主连合约生成工具

功能：
  1. 基于数据库中的原始合约数据，生成 888 加权合约
  2. 支持指定日期范围增量生成
  3. 其他模块（import_excel.py, collector.py）统一调用此模块

使用方式：
  # 生成所有品种的 888 合约
  uv run python ai/data_process/generate_main_contract.py

  # 只生成指定品种
  uv run python ai/data_process/generate_main_contract.py --variety m

  # 从指定日期开始生成
  uv run python ai/data_process/generate_main_contract.py --start-date 20250707

  # 强制重建（覆盖已有 888 数据）
  uv run python ai/data_process/generate_main_contract.py --force
"""

import re
import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional

# 确保能导入项目根目录的 vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def symbol_prefix(symbol: str) -> str:
    """从合约代码提取品种前缀，如 m2605 -> m"""
    return re.sub(r"\d", "", symbol)


def main_contract_symbol(prefix: str) -> str:
    """主连合约代码，如 m -> m888"""
    return f"{prefix}888"


# ─────────────────────────────────────────────────────────────────────────────
# DCE 主要品种列表
# ─────────────────────────────────────────────────────────────────────────────

DCE_VARIETIES = [
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


# ─────────────────────────────────────────────────────────────────────────────
# 主力映射表管理（复用 build_main_contract.py 的逻辑）
# ─────────────────────────────────────────────────────────────────────────────

class MappingStore:
    """
    主力合约映射表的 SQLite 持久化层
    路径：~/.vntrader/main_contract_mapping.db
    """

    DEFAULT_PATH = Path.home() / ".vntrader" / "main_contract_mapping.db"

    def __init__(self, db_path=None):
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_table()

    def _init_table(self):
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
        try:
            self._conn.execute("ALTER TABLE main_contract_mapping ADD COLUMN sub_dominant TEXT")
        except:
            pass
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_exchange
            ON main_contract_mapping (product, exchange)
        """)
        self._conn.commit()

    def save_mapping(self, product, exchange, mapping, replace=False):
        if not mapping:
            return 0
        if replace:
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
                row["trade_date"].isoformat() if isinstance(row["trade_date"], date) else row["trade_date"],
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

    def get_all(self, product, exchange) -> List[Dict]:
        cur = self._conn.execute(
            "SELECT trade_date, dominant, sub_dominant, open_interest FROM main_contract_mapping "
            "WHERE product=? AND exchange=? ORDER BY trade_date",
            (product, exchange),
        )
        return [
            {
                "trade_date": date.fromisoformat(row[0]),
                "dominant": row[1],
                "sub_dominant": row[2] if len(row) > 2 and row[2] else row[1],
                "open_interest": row[3] if len(row) > 3 else 0.0,
            }
            for row in cur.fetchall()
        ]

    def get_dominant(self, product, exchange, trade_date) -> Optional[str]:
        cur = self._conn.execute(
            "SELECT dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_sub_dominant(self, product, exchange, trade_date) -> Optional[str]:
        cur = self._conn.execute(
            "SELECT sub_dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_previous_dominant(self, product, exchange, trade_date) -> Optional[str]:
        """获取指定日期之前的最近一个不同的主力合约"""
        cur = self._conn.execute(
            "SELECT dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date<? "
            "ORDER BY trade_date DESC LIMIT 10",
            (product, exchange, trade_date.isoformat()),
        )
        rows = cur.fetchall()
        for row in rows:
            if row[0] != self.get_dominant(product, exchange, trade_date):
                return row[0]
        return None

    def get_latest_date(self, product, exchange) -> Optional[date]:
        cur = self._conn.execute(
            "SELECT MAX(trade_date) FROM main_contract_mapping WHERE product=? AND exchange=?",
            (product, exchange),
        )
        row = cur.fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def close(self):
        self._conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 主力识别（带平滑机制）
# ─────────────────────────────────────────────────────────────────────────────

def _extract_contract_number(symbol: str) -> int:
    """从合约代码提取合约月份数字，如 m2609 -> 2609"""
    import re
    numbers = re.findall(r'\d+', symbol)
    return int(numbers[-1]) if numbers else 0


def identify_main_and_sub(
    variety: str,
    trade_date: date,
    all_contracts: Dict[str, Dict],
    mapping_store: MappingStore,
    smoothing_days: int = 5,
) -> tuple:
    """
    识别主力和次主力合约（带平滑机制）

    次主力规则：
    - 必须与主力合约是**同一品种**的不同月份
    - 合约月份数字**大于**主力合约
    - 在满足条件的合约中，选取**持仓量最大**的作为次主力

    Args:
        variety: 品种前缀（如"m"）
        trade_date: 交易日
        all_contracts: 当日所有合约数据 {symbol: {open_interest, volume, ...}}
        mapping_store: 映射表存储

    Returns:
        (主力合约, 次主力合约)
    """
    if not all_contracts:
        raise ValueError(f"品种 {variety} 在 {trade_date} 无合约数据")

    # 提取主力合约的月份数字
    def get_main_contract_number(symbol: str) -> int:
        return _extract_contract_number(symbol)

    # 按持仓量降序排序
    sorted_contracts = sorted(
        all_contracts.items(),
        key=lambda x: x[1].get("open_interest", 0),
        reverse=True
    )

    real_main = sorted_contracts[0][0]
    main_number = get_main_contract_number(real_main)

    # 找出次主力：同一品种，合约月份 > 主力月份，持仓量最大
    valid_sub_contracts = [
        (symbol, data) for symbol, data in sorted_contracts
        if symbol != real_main and _extract_contract_number(symbol) > main_number
    ]

    real_sub = valid_sub_contracts[0][0] if valid_sub_contracts else real_main

    # 获取历史主力
    prev_date = trade_date - timedelta(days=1)
    current_main = mapping_store.get_dominant(variety, "DCE", prev_date)
    current_sub = mapping_store.get_sub_dominant(variety, "DCE", prev_date)

    # 首次运行，直接使用实时排名
    if current_main is None:
        return real_main, real_sub

    # 平滑切换
    new_main = real_main if real_main != current_main else current_main
    new_sub = real_sub if real_sub != current_sub and real_sub != new_main else current_sub

    # 保护：次主力不能与主力相同
    if new_sub == new_main and len(valid_sub_contracts) > 0:
        new_sub = valid_sub_contracts[0][0]

    return new_main, new_sub


def get_previous_different_main(
    variety: str,
    current_main: str,
    mapping_store: MappingStore,
) -> Optional[str]:
    """获取上一个不同的主力合约"""
    mappings = mapping_store.get_all(variety, "DCE")
    for m in reversed(mappings):
        if m["dominant"] != current_main:
            return m["dominant"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 加权 K 线合成
# ─────────────────────────────────────────────────────────────────────────────

def calculate_weighted_bar(
    new_main_data: Dict,
    sub_data: Optional[Dict] = None,
    old_main_data: Optional[Dict] = None,
) -> Dict:
    """
    计算 888 加权合约的 K 线数据

    权重分配（按成交量加权）：
    - OCHL 价格：按成交量加权平均
    - volume/turnover/open_interest：直接求和

    Args:
        new_main_data: 新主力合约数据
        sub_data: 次主力合约数据（可选）
        old_main_data: 旧主力合约数据（可选，仅用于持仓量求和）

    Returns:
        加权 K 线数据字典
    """
    if not new_main_data:
        raise ValueError("新主力数据为空")

    if sub_data is None:
        sub_data = new_main_data

    # 收集所有合约数据（用于加权计算）
    contracts_data = [new_main_data, sub_data]

    # 计算总成交量
    total_volume = (
        new_main_data.get("volume", 0) +
        sub_data.get("volume", 0)
    )

    if total_volume <= 0:
        # 全部成交量为 0，退化为简单均价
        n = len(contracts_data)
        return {
            "datetime": new_main_data.get("datetime"),
            "open": sum(c.get("open", 0) for c in contracts_data) / n,
            "high": max(c.get("high", 0) for c in contracts_data),
            "low": min(c.get("low", float("inf")) or float("inf") for c in contracts_data),
            "close": sum(c.get("close", 0) for c in contracts_data) / n,
            "volume": total_volume,
            "turnover": sum(c.get("turnover", 0) for c in contracts_data),
            "open_interest": sum(c.get("open_interest", 0) for c in contracts_data),
        }

    # 按成交量加权计算 OCHL
    def volume_weighted(field, default=0.0):
        return sum(
            c.get(field, default) * c.get("volume", 0)
            for c in contracts_data
        ) / total_volume

    # 持仓量需要加上旧主力
    total_open_interest = (
        new_main_data.get("open_interest", 0) +
        sub_data.get("open_interest", 0) +
        (old_main_data.get("open_interest", 0) if old_main_data else 0)
    )

    return {
        "datetime": new_main_data.get("datetime"),
        "open": volume_weighted("open"),
        "high": max(
            new_main_data.get("high", 0),
            sub_data.get("high", 0),
        ),
        "low": min(
            new_main_data.get("low", float("inf")) or float("inf"),
            sub_data.get("low", float("inf")) or float("inf"),
        ),
        "close": volume_weighted("close"),
        "volume": total_volume,
        "turnover": (
            new_main_data.get("turnover", 0) +
            sub_data.get("turnover", 0)
        ),
        "open_interest": total_open_interest,
    }


def save_bar_to_db(symbol: str, exchange: Exchange, bar_dict: Dict, db):
    """将 K 线数据保存到数据库"""
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
        gateway_name="DCE_888",
    )
    db.save_bar_data([bar])


# ─────────────────────────────────────────────────────────────────────────────
# 核心函数：为指定日期范围生成 888 合约
# ─────────────────────────────────────────────────────────────────────────────

def generate_888_for_date_range(
    varieties: List[str],
    start_date: date,
    end_date: date,
    db=None,
    mapping_store: MappingStore = None,
    verbose: bool = True,
) -> Dict:
    """
    为指定日期范围生成 888 加权合约
    
    Args:
        varieties: 品种列表（如 ["a", "m", "y"]）
        start_date: 开始日期
        end_date: 结束日期
        db: 数据库连接（可选，会自动获取）
        mapping_store: 映射表存储（可选，会自动创建）
        verbose: 是否打印详细日志
    
    Returns:
        生成统计 {"variety": {"generated": count, "errors": count}}
    """
    if db is None:
        db = get_database()
    if mapping_store is None:
        mapping_store = MappingStore()
    
    stats = {v: {"generated": 0, "errors": 0} for v in varieties}
    
    try:
        for variety in varieties:
            if verbose:
                print(f"  📊 {variety}...", end=" ", flush=True)
            
            try:
                count = _generate_888_for_single_variety(
                    variety, start_date, end_date, db, mapping_store, verbose=False
                )
                stats[variety]["generated"] = count
                if verbose:
                    print(f"✅ {count} 条")
            except Exception as e:
                stats[variety]["errors"] = 1
                if verbose:
                    print(f"❌ {e}")
    
    finally:
        if mapping_store:
            mapping_store.close()
    
    return stats


def _generate_888_for_single_variety(
    variety: str,
    start_date: date,
    end_date: date,
    db,
    mapping_store: MappingStore,
    verbose: bool = False,
) -> int:
    """为单个品种生成 888 合约"""
    
    # 1. 获取该品种所有合约列表
    overviews = db.get_bar_overview()
    contracts = [
        o.symbol for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == Exchange.DCE
        and symbol_prefix(o.symbol) == variety
    ]
    
    if not contracts:
        return 0
    
    # 2. 遍历每个交易日
    current_date = start_date
    generated_count = 0
    
    while current_date <= end_date:
        # 跳过周末
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        
        try:
            # 3. 加载当日所有合约数据
            all_contracts = _load_contracts_for_date(variety, current_date, db)
            
            if not all_contracts:
                current_date += timedelta(days=1)
                continue
            
            # 4. 识别主力和次主力
            new_main, new_sub = identify_main_and_sub(
                variety, current_date, all_contracts, mapping_store
            )
            
            # 5. 获取旧主力
            old_main = get_previous_different_main(variety, new_main, mapping_store)
            old_main_data = all_contracts.get(old_main) if old_main else None
            
            # 6. 计算加权 K 线（按成交量加权）
            weighted_bar_dict = calculate_weighted_bar(
                new_main_data=all_contracts[new_main],
                sub_data=all_contracts.get(new_sub, all_contracts[new_main]),
                old_main_data=old_main_data,
            )
            
            # 7. 保存映射表
            mapping_store.save_mapping(
                product=variety,
                exchange="DCE",
                mapping=[{
                    "trade_date": current_date,
                    "dominant": new_main,
                    "sub_dominant": new_sub,
                    "open_interest": all_contracts[new_main].get("open_interest", 0),
                }],
            )
            
            # 8. 保存 888 合约
            save_bar_to_db(
                f"{variety}888",
                Exchange.DCE,
                weighted_bar_dict,
                db,
            )
            
            generated_count += 1
            
        except Exception as e:
            if verbose:
                print(f"    ⚠️ {current_date}: {e}")
        
        current_date += timedelta(days=1)
    
    return generated_count


def _load_contracts_for_date(variety: str, trade_date: date, db) -> Dict[str, Dict]:
    """加载某品种当日所有合约数据（排除 888 加权合约）"""
    start_dt = datetime.combine(trade_date, time(0, 0))
    end_dt = datetime.combine(trade_date, time(23, 59))
    
    # 获取该品种所有合约列表
    overviews = db.get_bar_overview()
    contracts = [
        o.symbol for o in overviews
        if o.interval == Interval.DAILY
        and o.exchange == Exchange.DCE
        and symbol_prefix(o.symbol) == variety
        and "888" not in o.symbol  # 排除 888 加权合约，避免被识别为主力
    ]
    
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


# ─────────────────────────────────────────────────────────────────────────────
# 批量生成所有品种
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_varieties(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    varieties: Optional[List[str]] = None,
    force: bool = False,
) -> Dict:
    """
    批量生成所有品种的 888 合约
    
    Args:
        start_date: 开始日期（None 则从数据库最早日期开始）
        end_date: 结束日期（None 则使用数据库最新日期）
        varieties: 品种列表（None 则使用所有 DCE 品种）
        force: 是否强制重建
    
    Returns:
        生成统计信息
    """
    db = get_database()
    
    if varieties is None:
        varieties = DCE_VARIETIES
    
    # 确定日期范围
    if end_date is None:
        overviews = db.get_bar_overview()
        dce_overviews = [o for o in overviews if o.exchange == Exchange.DCE and o.interval == Interval.DAILY]
        if dce_overviews:
            end_date = max(o.end.date() for o in dce_overviews if o.end)
    
    if start_date is None:
        overviews = db.get_bar_overview()
        dce_overviews = [o for o in overviews if o.exchange == Exchange.DCE and o.interval == Interval.DAILY]
        if dce_overviews:
            start_date = min(o.start.date() for o in dce_overviews if o.start)
    
    if start_date is None or end_date is None:
        print("❌ 无法确定日期范围")
        return {}
    
    print(f"📊 生成 888 合约: {start_date} ~ {end_date}")
    print(f"   品种: {', '.join(varieties)}")
    print()
    
    stats = generate_888_for_date_range(varieties, start_date, end_date, db)
    
    # 汇总
    total = sum(s["generated"] for s in stats.values())
    errors = sum(s["errors"] for s in stats.values())
    
    print()
    print(f"✅ 完成！共生成 {total} 条 888 合约数据，{errors} 个错误")
    
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="DCE 888 主连合约生成工具")
    parser.add_argument("--variety", "-v", action="append", help="指定品种（如 m），可多次使用")
    parser.add_argument("--start-date", help="开始日期（如 20250707）")
    parser.add_argument("--end-date", help="结束日期（如 20260417）")
    parser.add_argument("--force", "-f", action="store_true", help="强制重建")
    
    args = parser.parse_args()
    
    # 解析日期
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y%m%d").date()
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y%m%d").date()
    
    # 品种列表
    varieties = None
    if args.variety:
        varieties = args.variety  # action="append" 返回列表
    
    generate_all_varieties(start_date, end_date, varieties, args.force)
