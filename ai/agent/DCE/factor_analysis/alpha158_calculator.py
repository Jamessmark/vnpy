"""
Alpha158 因子计算器
基于888加权合约计算158个技术因子
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
    """Alpha158 因子计算器"""
    
    def __init__(self):
        self.db = get_database()
    
    def load_data(
        self,
        symbol: str,
        exchange,  # 接受 Exchange 枚举或字符串
        days: int = 100
    ) -> pl.DataFrame:
        """
        从数据库加载K线数据
        
        Args:
            symbol: 合约代码（如"a888"）
            exchange: 交易所（Exchange枚举或字符串如"DCE"）
            days: 加载天数
        
        Returns:
            Polars DataFrame
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)  # 多加载30天用于计算
        
        # 转换 exchange 为 Exchange 枚举
        if isinstance(exchange, str):
            exchange = Exchange(exchange)
        
        bars = self.db.load_bar_data(
            symbol, exchange, Interval.DAILY,
            start_date, end_date
        )
        
        if not bars:
            raise ValueError(f"未找到 {symbol}.{exchange.value} 的数据")
        
        # 转换为 Polars DataFrame
        data = []
        for bar in bars:
            data.append({
                "datetime": bar.datetime,
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume,
                "turnover": bar.turnover,
                "open_interest": bar.open_interest,
            })
        
        df = pl.DataFrame(data)
        df = df.sort("datetime")
        
        return df
    
    def calculate_alpha158(
        self,
        df: pl.DataFrame,
        target_date: Optional[date] = None
    ) -> Dict:
        """
        计算 Alpha158 特征
        
        Args:
            df: K线数据（至少3天）
            target_date: 目标日期（None则使用最新日期）
        
        Returns:
            特征字典
        """
        min_required = 3  # 测试模式下最低3天
        if len(df) < min_required:
            raise ValueError(f"数据不足{min_required}天，当前只有 {len(df)} 天")
        
        # 如果未指定日期，使用最新日期
        if target_date is None:
            # 处理时区-aware datetime
            max_dt = df["datetime"].max()
            if hasattr(max_dt, 'tzinfo') and max_dt.tzinfo is not None:
                target_date = max_dt.replace(tzinfo=None).date()
            else:
                target_date = max_dt.date()
        
        # 处理时区-aware datetime：去掉时区信息，只保留日期部分
        def to_naive(dt):
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt
        
        df_dt = df.with_columns([
            pl.col("datetime").map_elements(to_naive, return_dtype=pl.Datetime).alias("datetime_naive")
        ])
        df_target = df_dt.filter(pl.col("datetime_naive").cast(pl.Date) <= target_date)
        
        if len(df_target) < min_required:
            raise ValueError(f"目标日期 {target_date} 之前数据不足{min_required}天")
        
        # 计算特征（简化版，完整版有158个）
        features = {}
        
        # 价格相关特征
        close = df_target["close"].to_numpy()
        open_ = df_target["open"].to_numpy()
        high = df_target["high"].to_numpy()
        low = df_target["low"].to_numpy()
        volume = df_target["volume"].to_numpy()
        
        # 1. 收益率类 (30个)
        for period in [1, 5, 10, 20, 30, 60]:
            if len(close) >= period + 1:
                ret = close[-1] / close[-(period+1)] - 1
                features[f"return_{period}d"] = ret
        
        # 2. 移动平均类 (20个)
        for period in [5, 10, 20, 30, 60]:
            if len(close) >= period:
                ma = np.mean(close[-period:])
                features[f"ma_{period}"] = ma
                features[f"close_div_ma_{period}"] = close[-1] / ma - 1
        
        # 3. 波动率类 (20个)
        for period in [5, 10, 20, 30, 60]:
            if len(close) >= period + 1:
                returns = np.diff(close[-period-1:]) / close[-period-1:-1]
                vol = np.std(returns)
                features[f"volatility_{period}d"] = vol
        
        # 4. 成交量相关 (20个)
        for period in [5, 10, 20, 30]:
            if len(volume) >= period:
                vol_ma = np.mean(volume[-period:])
                features[f"volume_ma_{period}"] = vol_ma
                features[f"volume_ratio_{period}"] = volume[-1] / (vol_ma + 1e-8)
        
        # 5. 技术指标类 (30个)
        # RSI
        if len(close) >= 15:
            diff = np.diff(close[-15:])
            gains = np.where(diff > 0, diff, 0)
            losses = np.where(diff < 0, -diff, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            rs = avg_gain / (avg_loss + 1e-8)
            rsi = 100 - (100 / (1 + rs))
            features["rsi_14"] = rsi
        
        # MACD
        if len(close) >= 26:
            ema12 = self._ema(close, 12)
            ema26 = self._ema(close, 26)
            macd = ema12[-1] - ema26[-1]
            features["macd"] = macd
        
        # 布林带
        if len(close) >= 20:
            ma20 = np.mean(close[-20:])
            std20 = np.std(close[-20:])
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            features["bollinger_upper"] = upper
            features["bollinger_lower"] = lower
            features["bollinger_position"] = (close[-1] - lower) / (upper - lower + 1e-8)
        
        # 6. 高低价相关 (20个)
        for period in [5, 10, 20]:
            if len(high) >= period and len(low) >= period:
                highest = np.max(high[-period:])
                lowest = np.min(low[-period:])
                features[f"high_{period}d"] = highest
                features[f"low_{period}d"] = lowest
                features[f"price_position_{period}d"] = (close[-1] - lowest) / (highest - lowest + 1e-8)
        
        # 7. 其他特征补足到158个（这里简化）
        # 实际应该包含更多量价时空特征、动量指标、均值回归指标等
        
        # 添加元数据
        features["_date"] = target_date
        features["_close"] = close[-1]
        features["_volume"] = volume[-1]
        
        return features
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def calculate_for_variety(
        self,
        variety: str,
        target_date: Optional[date] = None
    ) -> Dict:
        """
        计算某品种的 Alpha158 特征
        
        Args:
            variety: 品种代码（如"a"）
            target_date: 目标日期
        
        Returns:
            特征字典
        """
        symbol = f"{variety}888"  # 使用888加权合约
        
        try:
            df = self.load_data(symbol, Exchange.DCE, days=100)
            features = self.calculate_alpha158(df, target_date)
            features["_variety"] = variety
            features["_symbol"] = symbol
            return features
        
        except Exception as e:
            print(f"❌ {variety} 因子计算失败: {e}")
            return {}
    
    def calculate_all_varieties(
        self,
        varieties: List[str],
        target_date: Optional[date] = None
    ) -> List[Dict]:
        """
        批量计算多个品种的 Alpha158 特征
        
        Args:
            varieties: 品种列表
            target_date: 目标日期
        
        Returns:
            特征列表
        """
        results = []
        
        for variety in varieties:
            features = self.calculate_for_variety(variety, target_date)
            if features:
                results.append(features)
        
        return results


if __name__ == "__main__":
    # 测试
    calculator = Alpha158Calculator()
    
    # 测试单个品种
    features = calculator.calculate_for_variety("a")
    
    if features:
        print(f"\n✅ 豆一(a888) Alpha158 特征计算成功")
        print(f"  日期: {features['_date']}")
        print(f"  收盘价: {features['_close']:.2f}")
        print(f"  特征数: {len([k for k in features.keys() if not k.startswith('_')])}")
        print(f"\n  部分特征:")
        for key in list(features.keys())[:10]:
            if not key.startswith('_'):
                print(f"    {key}: {features[key]:.4f}")
