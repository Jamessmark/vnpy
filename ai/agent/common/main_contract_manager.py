"""
主力合约管理模块 — 通用版

负责主力合约识别、换月判断、加权合成等核心逻辑，
与具体交易所无关（交易所由调用方传入）。

包含：
  - MappingStore：主力映射表 SQLite 持久化层
  - symbol_prefix：提取品种前缀
  - identify_main_and_sub：识别主力/次主力（带平滑）
  - get_previous_different_main：获取上一个不同的主力
  - calculate_weighted_bar：多合约成交量加权合成

用法：
    from ai.agent.common.main_contract_manager import (
        MappingStore, identify_main_and_sub, calculate_weighted_bar
    )
"""
import re
import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple


class MappingStore:
    """
    主力合约映射表的 SQLite 持久化层

    数据库路径：~/.vntrader/main_contract_mapping.db

    表结构：
        product       TEXT   品种前缀，如 a / MA / rb
        exchange      TEXT   交易所，如 DCE / CZCE / SHFE
        trade_date    TEXT   交易日（ISO 格式 YYYY-MM-DD）
        dominant      TEXT   当日主力合约代码
        sub_dominant  TEXT   当日次主力合约代码
        open_interest REAL   主力合约持仓量

    主键：(product, exchange, trade_date)
    """

    DEFAULT_PATH = Path.home() / ".vntrader" / "main_contract_mapping.db"

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False：允许 Dash 等多线程只读场景复用同一连接
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_table()

    def _init_table(self) -> None:
        """初始化数据库表和索引"""
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
        # 兼容旧表（无 sub_dominant 列）
        try:
            self._conn.execute(
                "ALTER TABLE main_contract_mapping ADD COLUMN sub_dominant TEXT"
            )
        except sqlite3.OperationalError:
            pass
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
        mapping: List[Dict],
        replace: bool = False,
    ) -> int:
        """
        写入映射表（增量 INSERT OR IGNORE，或 replace=True 时全量覆盖）。

        mapping 格式：list of {
            "trade_date": date | str,
            "dominant": str,
            "sub_dominant": str,        # 可选
            "open_interest": float,     # 可选
        }

        Returns:
            实际插入/更新的行数
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
            td = row["trade_date"]
            trade_date_str = td.isoformat() if isinstance(td, date) else td
            sub_dom = row.get("sub_dominant", row.get("dominant", ""))
            rows.append((
                product,
                exchange,
                trade_date_str,
                row["dominant"],
                sub_dom,
                row.get("open_interest", 0.0),
            ))

        self._conn.executemany(
            f"{verb} INTO main_contract_mapping "
            f"(product, exchange, trade_date, dominant, sub_dominant, open_interest) "
            f"VALUES (?,?,?,?,?,?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def get_all(self, product: str, exchange: str) -> List[Dict]:
        """返回某品种全部映射记录，按 trade_date 升序"""
        cur = self._conn.execute(
            "SELECT trade_date, dominant, sub_dominant, open_interest "
            "FROM main_contract_mapping "
            "WHERE product=? AND exchange=? ORDER BY trade_date",
            (product, exchange),
        )
        return [
            {
                "trade_date":    date.fromisoformat(row[0]),
                "dominant":      row[1],
                "sub_dominant":  row[2] if row[2] else row[1],
                "open_interest": row[3] if len(row) > 3 else 0.0,
            }
            for row in cur.fetchall()
        ]

    def get_dominant(self, product: str, exchange: str, trade_date: date) -> Optional[str]:
        """查询某天的主力合约代码，无记录返回 None"""
        cur = self._conn.execute(
            "SELECT dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_sub_dominant(self, product: str, exchange: str, trade_date: date) -> Optional[str]:
        """查询某天的次主力合约代码，无记录返回 None"""
        cur = self._conn.execute(
            "SELECT sub_dominant FROM main_contract_mapping "
            "WHERE product=? AND exchange=? AND trade_date=?",
            (product, exchange, trade_date.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_switches(self, product: str, exchange: str) -> List[Dict]:
        """返回该品种所有换月节点（dominant 发生变化的行）"""
        all_rows = self.get_all(product, exchange)
        switches = []
        prev = None
        for row in all_rows:
            if row["dominant"] != prev:
                switches.append({"trade_date": row["trade_date"], "dominant": row["dominant"]})
                prev = row["dominant"]
        return switches

    def get_latest_date(self, product: str, exchange: str) -> Optional[date]:
        """返回该品种映射表中最新的交易日，无记录返回 None"""
        cur = self._conn.execute(
            "SELECT MAX(trade_date) FROM main_contract_mapping WHERE product=? AND exchange=?",
            (product, exchange),
        )
        row = cur.fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def list_products(self) -> List[Tuple[str, str]]:
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
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def symbol_prefix(symbol: str) -> str:
    """从合约代码提取品种前缀，如 MA2605 -> MA，rb2605 -> rb"""
    return re.sub(r"\d", "", symbol)


def _extract_contract_number(symbol: str) -> int:
    """从合约代码提取月份数字，如 m2609 -> 2609"""
    numbers = re.findall(r"\d+", symbol)
    return int(numbers[-1]) if numbers else 0


# ─────────────────────────────────────────────────────────────────────────────
# 主力识别
# ─────────────────────────────────────────────────────────────────────────────

def identify_main_and_sub(
    variety: str,
    trade_date: date,
    all_contracts: Dict[str, Dict],
    mapping_store: MappingStore,
    exchange: str = "DCE",
    smoothing_days: int = 5,
) -> Tuple[str, str]:
    """
    识别主力和次主力合约（带平滑机制）。

    次主力规则：
      - 必须是同一品种的不同月份
      - 合约月份数字 > 主力合约月份数字
      - 满足以上条件中持仓量最大的

    Args:
        variety:       品种前缀（如 "a"、"rb"、"MA"）
        trade_date:    交易日
        all_contracts: 当日所有合约数据 {symbol: {open_interest, ...}}
        mapping_store: MappingStore 实例
        exchange:      交易所字符串（默认 "DCE"）
        smoothing_days: 预留参数，兼容接口

    Returns:
        (主力合约, 次主力合约)
    """
    if not all_contracts:
        raise ValueError(f"品种 {variety} 在 {trade_date} 无合约数据")

    # 按持仓量降序
    sorted_contracts = sorted(
        all_contracts.items(),
        key=lambda x: x[1].get("open_interest", 0),
        reverse=True,
    )

    real_main   = sorted_contracts[0][0]
    main_number = _extract_contract_number(real_main)

    # 次主力：同品种、月份更远、持仓量最大
    valid_sub = [
        (sym, data) for sym, data in sorted_contracts
        if sym != real_main and _extract_contract_number(sym) > main_number
    ]
    real_sub = valid_sub[0][0] if valid_sub else real_main

    # 平滑：查历史
    prev_date    = trade_date - timedelta(days=1)
    current_main = mapping_store.get_dominant(variety, exchange, prev_date)
    current_sub  = mapping_store.get_sub_dominant(variety, exchange, prev_date)

    if current_main is None:
        return real_main, real_sub

    new_main = real_main if real_main != current_main else current_main
    new_sub  = (
        real_sub
        if real_sub != current_sub and real_sub != new_main
        else current_sub
    )

    # 强制保护：次主力不能与主力相同
    if new_sub == new_main and valid_sub:
        new_sub = valid_sub[0][0]

    return new_main, new_sub


def get_previous_different_main(
    variety: str,
    current_main: str,
    mapping_store: MappingStore,
    exchange: str = "DCE",
) -> Optional[str]:
    """
    获取上一个不同于 current_main 的主力合约代码。

    Args:
        variety:      品种前缀
        current_main: 当前主力合约
        mapping_store: MappingStore 实例
        exchange:     交易所字符串

    Returns:
        上一个不同主力合约代码；无则返回 None
    """
    switches = mapping_store.get_switches(variety, exchange)
    if not switches:
        return None

    switches = sorted(switches, key=lambda x: x["trade_date"], reverse=True)
    for sw in switches:
        if sw["dominant"] != current_main:
            return sw["dominant"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 加权合成
# ─────────────────────────────────────────────────────────────────────────────

def calculate_weighted_bar(
    variety: str,
    old_main_bar: Optional[Dict],
    new_main_bar: Dict,
    sub_bar: Dict,
) -> Dict:
    """
    将旧主力 + 新主力 + 次主力三个合约按成交量加权合成为一根 K 线。

    - 价格：按成交量加权均价
    - 成交量 / 持仓量 / 成交额：直接求和

    Args:
        variety:      品种前缀（用于生成 888 合约代码）
        old_main_bar: 旧主力合约数据（可为 None 或 volume=0）
        new_main_bar: 新主力合约数据（必填）
        sub_bar:      次主力合约数据（必填）

    Returns:
        合成后的 bar 字典
    """
    contracts: List[Dict] = []
    if old_main_bar and old_main_bar.get("volume", 0) > 0:
        contracts.append(old_main_bar)
    contracts.append(new_main_bar)
    if sub_bar.get("symbol") != new_main_bar.get("symbol"):
        contracts.append(sub_bar)

    if not contracts:
        raise ValueError("No valid contracts for weighted bar")

    total_volume = sum(c.get("volume", 0) for c in contracts)

    if total_volume > 0:
        def _w(field: str) -> float:
            return sum(c[field] * c["volume"] for c in contracts) / total_volume
        w_open, w_high, w_low, w_close = _w("open"), _w("high"), _w("low"), _w("close")
    else:
        n = len(contracts)
        w_open  = sum(c["open"]  for c in contracts) / n
        w_high  = sum(c["high"]  for c in contracts) / n
        w_low   = sum(c["low"]   for c in contracts) / n
        w_close = sum(c["close"] for c in contracts) / n

    return {
        "symbol":        f"{variety}888",
        "datetime":      new_main_bar["datetime"],
        "open":          w_open,
        "high":          w_high,
        "low":           w_low,
        "close":         w_close,
        "volume":        total_volume,
        "open_interest": sum(c.get("open_interest", 0) for c in contracts),
        "turnover":      sum(c.get("turnover", 0)      for c in contracts),
    }
