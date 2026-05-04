"""
Alpha158 因子计算器 — 通用版

基于 888 加权主连合约计算技术因子，支持任意交易所品种。
可被 DCE、SHFE、CZCE 等各交易所 Agent 直接引用。

用法示例：
    from ai.agent.common.factor_analysis import Alpha158Calculator
    from vnpy.trader.constant import Exchange

    calc = Alpha158Calculator()
    features = calc.calculate_for_symbol("a888", Exchange.DCE)
    # 或：
    features = calc.calculate_for_symbol("rb888", Exchange.LOCAL)
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

import polars as pl
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval


class Alpha158Calculator:
    """
    Alpha158 技术因子计算器

    与交易所无关；只需传入合约代码 + 交易所即可计算因子。
    品种特有逻辑（如 888 合约命名规则）由调用方处理。
    """

    def __init__(self):
        self.db = get_database()

    def load_data(
        self,
        symbol: str,
        exchange,  # 接受 Exchange 枚举或字符串
        days: int = 100,
    ) -> pl.DataFrame:
        """
        从数据库加载日K线数据。

        Args:
            symbol: 合约代码（如 "a888"、"rb888"）
            exchange: 交易所（Exchange 枚举或字符串如 "DCE"）
            days: 最多加载最近 N 天（额外多取 30 天用于计算缓冲）

        Returns:
            Polars DataFrame，列：datetime / open / high / low / close / volume / turnover / open_interest
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)

        if isinstance(exchange, str):
            exchange = Exchange(exchange)

        bars = self.db.load_bar_data(
            symbol, exchange, Interval.DAILY,
            start_date, end_date,
        )

        if not bars:
            raise ValueError(f"未找到 {symbol}.{exchange.value} 的数据")

        data = []
        for bar in bars:
            data.append({
                "datetime": bar.datetime,
                "open":     bar.open_price,
                "high":     bar.high_price,
                "low":      bar.low_price,
                "close":    bar.close_price,
                "volume":   bar.volume,
                "turnover": bar.turnover,
                "open_interest": bar.open_interest,
            })

        df = pl.DataFrame(data).sort("datetime")
        return df

    def calculate_alpha158(
        self,
        df: pl.DataFrame,
        target_date: Optional[date] = None,
    ) -> Dict:
        """
        计算 Alpha158 特征（简化版，核心 60+ 个技术因子）。

        Args:
            df: K线数据（至少 3 行）
            target_date: 目标日期；None 则使用最新日期

        Returns:
            特征字典（以 "_" 开头的为元数据字段）
        """
        min_required = 3
        if len(df) < min_required:
            raise ValueError(f"数据不足 {min_required} 天，当前只有 {len(df)} 天")

        # 确定目标日期
        if target_date is None:
            max_dt = df["datetime"].max()
            if hasattr(max_dt, "tzinfo") and max_dt.tzinfo is not None:
                target_date = max_dt.replace(tzinfo=None).date()
            else:
                target_date = max_dt.date()

        def to_naive(dt):
            if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        df_dt = df.with_columns([
            pl.col("datetime").map_elements(to_naive, return_dtype=pl.Datetime).alias("datetime_naive")
        ])
        df_target = df_dt.filter(pl.col("datetime_naive").cast(pl.Date) <= target_date)

        if len(df_target) < min_required:
            raise ValueError(f"目标日期 {target_date} 之前数据不足 {min_required} 天")

        features: Dict = {}

        close  = df_target["close"].to_numpy()
        open_  = df_target["open"].to_numpy()
        high   = df_target["high"].to_numpy()
        low    = df_target["low"].to_numpy()
        volume = df_target["volume"].to_numpy()

        # ── 1. 收益率类 ──────────────────────────────────────────
        for period in [1, 5, 10, 20, 30, 60]:
            if len(close) >= period + 1:
                features[f"return_{period}d"] = close[-1] / close[-(period + 1)] - 1

        # ── 2. 移动平均类 ──────────────────────────────────────
        for period in [5, 10, 20, 30, 60]:
            if len(close) >= period:
                ma = np.mean(close[-period:])
                features[f"ma_{period}"] = ma
                features[f"close_div_ma_{period}"] = close[-1] / ma - 1

        # ── 3. 波动率类 ────────────────────────────────────────
        for period in [5, 10, 20, 30, 60]:
            if len(close) >= period + 1:
                returns = np.diff(close[-period - 1:]) / close[-period - 1:-1]
                features[f"volatility_{period}d"] = np.std(returns)

        # ── 4. 成交量相关 ──────────────────────────────────────
        for period in [5, 10, 20, 30]:
            if len(volume) >= period:
                vol_ma = np.mean(volume[-period:])
                features[f"volume_ma_{period}"]    = vol_ma
                features[f"volume_ratio_{period}"] = volume[-1] / (vol_ma + 1e-8)

        # ── 5. 技术指标类 ──────────────────────────────────────
        # RSI(14)
        if len(close) >= 15:
            diff   = np.diff(close[-15:])
            gains  = np.where(diff > 0, diff, 0)
            losses = np.where(diff < 0, -diff, 0)
            rs     = np.mean(gains) / (np.mean(losses) + 1e-8)
            features["rsi_14"] = 100 - (100 / (1 + rs))

        # MACD
        if len(close) >= 26:
            ema12 = self._ema(close, 12)
            ema26 = self._ema(close, 26)
            features["macd"] = ema12[-1] - ema26[-1]

        # 布林带
        if len(close) >= 20:
            ma20  = np.mean(close[-20:])
            std20 = np.std(close[-20:])
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            features["bollinger_upper"]    = upper
            features["bollinger_lower"]    = lower
            features["bollinger_position"] = (close[-1] - lower) / (upper - lower + 1e-8)

        # ── 6. 高低价相关 ──────────────────────────────────────
        for period in [5, 10, 20]:
            if len(high) >= period and len(low) >= period:
                highest = np.max(high[-period:])
                lowest  = np.min(low[-period:])
                features[f"high_{period}d"]           = highest
                features[f"low_{period}d"]            = lowest
                features[f"price_position_{period}d"] = (
                    (close[-1] - lowest) / (highest - lowest + 1e-8)
                )

        # ── 元数据 ────────────────────────────────────────────
        features["_date"]   = target_date
        features["_close"]  = close[-1]
        features["_volume"] = volume[-1]

        return features

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    def calculate_for_symbol(
        self,
        symbol: str,
        exchange,
        target_date: Optional[date] = None,
        days: int = 100,
    ) -> Dict:
        """
        直接按合约代码计算因子（通用入口）。

        Args:
            symbol: 合约代码（如 "a888"、"MA888"、"rb888"）
            exchange: 交易所（Exchange 枚举或字符串）
            target_date: 目标日期
            days: 回看天数

        Returns:
            特征字典；失败时返回空字典
        """
        if isinstance(exchange, str):
            exchange = Exchange(exchange)
        try:
            df = self.load_data(symbol, exchange, days=days)
            features = self.calculate_alpha158(df, target_date)
            features["_symbol"]   = symbol
            features["_exchange"] = exchange.value
            return features
        except Exception as e:
            print(f"❌ {symbol}.{exchange if isinstance(exchange, str) else exchange.value} 因子计算失败: {e}")
            return {}

    def calculate_for_variety(
        self,
        variety: str,
        exchange=Exchange.DCE,
        target_date: Optional[date] = None,
        days: int = 100,
    ) -> Dict:
        """
        按品种前缀计算因子，自动拼接 888 合约代码。

        Args:
            variety: 品种前缀（如 "a"、"rb"、"MA"）
            exchange: 交易所
            target_date: 目标日期
            days: 回看天数

        Returns:
            特征字典（含 _variety 字段）
        """
        symbol = f"{variety}888"
        features = self.calculate_for_symbol(symbol, exchange, target_date, days)
        if features:
            features["_variety"] = variety
        return features

    def calculate_all_varieties(
        self,
        varieties: List[str],
        exchange=Exchange.DCE,
        target_date: Optional[date] = None,
    ) -> List[Dict]:
        """批量计算多个品种的 Alpha158 特征"""
        results = []
        for variety in varieties:
            features = self.calculate_for_variety(variety, exchange, target_date)
            if features:
                results.append(features)
        return results


if __name__ == "__main__":
    calc = Alpha158Calculator()

    features = calc.calculate_for_variety("a", Exchange.DCE)
    if features:
        print(f"\n✅ 豆一(a888.DCE) Alpha158 特征计算成功")
        print(f"  日期:   {features['_date']}")
        print(f"  收盘价: {features['_close']:.2f}")
        count = len([k for k in features if not k.startswith("_")])
        print(f"  特征数: {count}")
        for key in list(features.keys())[:10]:
            if not key.startswith("_"):
                print(f"    {key}: {features[key]:.4f}")
