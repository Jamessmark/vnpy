"""
主力合约管理模块
负责主力合约识别、换月判断、加权合成等核心逻辑
"""
import re
import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


class MappingStore:
    """
    主力合约映射表的 SQLite 持久化层
    
    数据库路径：~/.vntrader/main_contract_mapping.db
    """
    
    DEFAULT_PATH = Path.home() / ".vntrader" / "main_contract_mapping.db"
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_table()
    
    def _init_table(self) -> None:
        """初始化数据库表"""
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
    
    def save_mapping(
        self,
        product: str,
        exchange: str,
        mapping: List[Dict],
        replace: bool = False,
    ) -> int:
        """
        写入映射表
        
        Args:
            product: 品种前缀（如"a"）
            exchange: 交易所（如"DCE"）
            mapping: list of {"trade_date": date, "dominant": str, "sub_dominant": str, "open_interest": float}
            replace: 是否覆盖已有数据
        """
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
    
    def get_all(self, product: str, exchange: str) -> List[Dict]:
        """返回某品种全部映射记录"""
        cur = self._conn.execute(
            "SELECT trade_date, dominant, sub_dominant, open_interest FROM main_contract_mapping "
            "WHERE product=? AND exchange=? ORDER BY trade_date",
            (product, exchange),
        )
        return [
            {
                "trade_date": date.fromisoformat(row[0]),
                "dominant": row[1],
                "sub_dominant": row[2] if row[2] else row[1],
                "open_interest": row[3] if len(row) > 3 else 0.0,
            }
            for row in cur.fetchall()
        ]
    
    def get_dominant(self, product: str, exchange: str, trade_date: date) -> Optional[str]:
        """查询某天的主力合约代码"""
        cur = self._conn.execute(
            "SELECT dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None
    
    def get_sub_dominant(self, product: str, exchange: str, trade_date: date) -> Optional[str]:
        """查询某天的次主力合约代码"""
        cur = self._conn.execute(
            "SELECT sub_dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None
    
    def get_switches(self, product: str, exchange: str) -> List[Dict]:
        """返回该品种所有换月节点"""
        all_rows = self.get_all(product, exchange)
        switches = []
        prev = None
        for row in all_rows:
            if row["dominant"] != prev:
                switches.append({"trade_date": row["trade_date"], "dominant": row["dominant"]})
                prev = row["dominant"]
        return switches
    
    def get_latest_date(self, product: str, exchange: str) -> Optional[date]:
        """返回该品种映射表中最新的交易日"""
        cur = self._conn.execute(
            "SELECT MAX(trade_date) FROM main_contract_mapping WHERE product=? AND exchange=?",
            (product, exchange),
        )
        row = cur.fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None
    
    def close(self) -> None:
        self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def symbol_prefix(symbol: str) -> str:
    """从合约代码提取品种前缀，如 MA2605 -> MA，rb2605 -> rb"""
    return re.sub(r"\d", "", symbol)


def _extract_contract_number(symbol: str) -> int:
    """从合约代码提取合约月份数字，如 m2609 -> 2609"""
    numbers = re.findall(r'\d+', symbol)
    return int(numbers[-1]) if numbers else 0


def identify_main_and_sub(
    variety: str,
    trade_date: date,
    all_contracts: Dict[str, Dict],
    mapping_store: MappingStore,
    smoothing_days: int = 5
) -> Tuple[str, str]:
    """
    识别主力和次主力合约（带平滑机制）

    次主力规则：
    - 必须与主力合约是**同一品种**的不同月份
    - 合约月份数字**大于**主力合约
    - 在满足条件的合约中，选取**持仓量最大**的作为次主力

    Args:
        variety: 品种前缀（如"a"）
        trade_date: 交易日
        all_contracts: 当日所有合约数据 {symbol: {open_interest, ...}}
        mapping_store: 映射表存储
        smoothing_days: 平滑天数（默认5天）

    Returns:
        (主力合约, 次主力合约)
    """
    if not all_contracts:
        raise ValueError(f"品种 {variety} 在 {trade_date} 无合约数据")

    # 按持仓量降序排序
    sorted_contracts = sorted(
        all_contracts.items(),
        key=lambda x: x[1].get("open_interest", 0),
        reverse=True
    )

    # 实时主力
    real_main = sorted_contracts[0][0]
    main_number = _extract_contract_number(real_main)

    # 找出次主力：同一品种，合约月份 > 主力月份，持仓量最大
    valid_sub_contracts = [
        (symbol, data) for symbol, data in sorted_contracts
        if symbol != real_main and _extract_contract_number(symbol) > main_number
    ]

    real_sub = valid_sub_contracts[0][0] if valid_sub_contracts else real_main

    # 获取历史主力和次主力
    prev_date = trade_date - timedelta(days=1)
    current_main = mapping_store.get_dominant(variety, "DCE", prev_date)
    current_sub = mapping_store.get_sub_dominant(variety, "DCE", prev_date)

    # 首次运行，直接使用实时排名
    if current_main is None:
        return real_main, real_sub

    # 平滑判断：需要连续 N 天领先才切换
    # 这里简化实现：如果实时第一名 != 当前主力，则切换
    # 完整实现需要维护计数器（参考 build_main_contract.py）
    new_main = real_main if real_main != current_main else current_main
    new_sub = real_sub if real_sub != current_sub and real_sub != new_main else current_sub

    # 强制保护：次主力不能与主力相同，且必须是主力之后的合约
    if new_sub == new_main and len(valid_sub_contracts) > 0:
        new_sub = valid_sub_contracts[0][0]

    return new_main, new_sub


def get_previous_different_main(
    variety: str,
    current_main: str,
    mapping_store: MappingStore
) -> Optional[str]:
    """
    获取上一个不同的主力合约
    
    例如：
        2026-01-01 ~ 2026-04-15: a2505 是主力
        2026-04-16 ~ 今天: a2507 是主力
        此时返回 a2505
    """
    switches = mapping_store.get_switches(variety, "DCE")
    
    if not switches:
        return None
    
    # 按日期降序排序
    switches = sorted(switches, key=lambda x: x["trade_date"], reverse=True)
    
    # 找到第一个不等于当前主力的记录
    for switch in switches:
        if switch["dominant"] != current_main:
            return switch["dominant"]
    
    return None


def calculate_weighted_bar(
    variety: str,
    old_main_bar: Optional[Dict],
    new_main_bar: Dict,
    sub_bar: Dict
) -> Dict:
    """
    计算加权合成K线
    
    包含3个合约：旧主力（如有数据） + 新主力 + 次主力
    价格：按成交量加权
    量能：直接求和
    """
    # 收集有效合约
    contracts = []
    if old_main_bar and old_main_bar.get('volume', 0) > 0:
        contracts.append(old_main_bar)
    contracts.append(new_main_bar)
    if sub_bar.get('symbol') != new_main_bar.get('symbol'):  # 强制保护
        contracts.append(sub_bar)
    
    if not contracts:
        raise ValueError("No valid contracts for weighted bar")
    
    total_volume = sum(c.get('volume', 0) for c in contracts)
    
    if total_volume > 0:
        weighted_open = sum(c['open'] * c['volume'] for c in contracts) / total_volume
        weighted_high = sum(c['high'] * c['volume'] for c in contracts) / total_volume
        weighted_low = sum(c['low'] * c['volume'] for c in contracts) / total_volume
        weighted_close = sum(c['close'] * c['volume'] for c in contracts) / total_volume
    else:
        # 成交量为0（罕见），简单均价
        n = len(contracts)
        weighted_open = sum(c['open'] for c in contracts) / n
        weighted_high = sum(c['high'] for c in contracts) / n
        weighted_low = sum(c['low'] for c in contracts) / n
        weighted_close = sum(c['close'] for c in contracts) / n
    
    return {
        "symbol": f"{variety}888",
        "datetime": new_main_bar['datetime'],
        "open": weighted_open,
        "high": weighted_high,
        "low": weighted_low,
        "close": weighted_close,
        "volume": total_volume,
        "open_interest": sum(c.get('open_interest', 0) for c in contracts),
        "turnover": sum(c.get('turnover', 0) for c in contracts),
    }
