"""
特征工程模块 - 技术指标和宏观因子特征构建

功能：
- 技术指标：TA-Lib集成
- 宏观因子：国债收益率、汇率
- 交叉特征：个股-行业收益差
- 时序特征：滞后、滚动统计
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
import warnings

import numpy as np
import pandas as pd
import talib

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TechnicalFeatureConfig:
    """技术指标特征配置"""
    # 趋势指标
    use_sma: bool = True
    sma_periods: List[int] = field(default_factory=lambda: [5, 10, 20, 60])
    use_ema: bool = True
    ema_periods: List[int] = field(default_factory=lambda: [12, 26])

    # 动量指标
    use_rsi: bool = True
    rsi_period: int = 14
    use_macd: bool = True
    use_stoch: bool = True

    # 波动率指标
    use_bollinger: bool = True
    bb_period: int = 20
    use_atr: bool = True
    atr_period: int = 14

    # 成交量指标
    use_obv: bool = True
    use_vwap: bool = True

    # 价格形态
    use_price_patterns: bool = True


@dataclass
class MacroFeatureConfig:
    """宏观因子配置"""
    use_bond_yield: bool = True  # 国债收益率
    use_exchange_rate: bool = False  # 汇率
    use_market_index: bool = True  # 市场指数
    use_sector_index: bool = True  # 行业指数


class FeatureEngineer:
    """特征工程器"""

    def __init__(
        self,
        tech_config: Optional[TechnicalFeatureConfig] = None,
        macro_config: Optional[MacroFeatureConfig] = None,
        lookback_window: int = 20
    ):
        self.tech_config = tech_config or TechnicalFeatureConfig()
        self.macro_config = macro_config or MacroFeatureConfig()
        self.lookback_window = lookback_window
        self.feature_names: List[str] = []

    def create_features(
        self,
        price_df: pd.DataFrame,
        market_df: Optional[pd.DataFrame] = None,
        sector_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        构建完整特征集

        Args:
            price_df: 价格数据 DataFrame with columns: open, high, low, close, volume
            market_df: 市场指数数据
            sector_df: 行业指数数据

        Returns:
            特征DataFrame
        """
        df = price_df.copy()

        # 基础价格特征
        df = self._add_price_features(df)

        # 技术指标
        if self.tech_config:
            df = self._add_technical_features(df)

        # 宏观/市场特征
        if market_df is not None:
            df = self._add_market_features(df, market_df)

        # 行业特征
        if sector_df is not None:
            df = self._add_sector_features(df, sector_df)

        # 时序特征
        df = self._add_temporal_features(df)

        # 删除NaN值
        df = df.dropna()

        self.feature_names = [c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume']]
        logger.info(f"特征工程完成: {len(self.feature_names)}个特征, {len(df)}条样本")

        return df

    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加基础价格特征"""
        # 收益率
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

        # 价格位置
        df['price_position'] = (df['close'] - df['low'].rolling(20).min()) / \
                               (df['high'].rolling(20).max() - df['low'].rolling(20).min())

        # 价格波动
        df['price_range'] = (df['high'] - df['low']) / df['close']
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 1e-10)

        # 成交量特征
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        df['volume_change'] = df['volume'].pct_change()

        return df

    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标特征"""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values

        # 趋势指标 - SMA
        if self.tech_config.use_sma:
            for period in self.tech_config.sma_periods:
                df[f'sma_{period}'] = talib.SMA(close, timeperiod=period)
                df[f'sma_dist_{period}'] = (df['close'] - df[f'sma_{period}']) / df[f'sma_{period}']

        # 趋势指标 - EMA
        if self.tech_config.use_ema:
            for period in self.tech_config.ema_periods:
                df[f'ema_{period}'] = talib.EMA(close, timeperiod=period)

        # 动量指标 - RSI
        if self.tech_config.use_rsi:
            df['rsi'] = talib.RSI(close, timeperiod=self.tech_config.rsi_period)
            df['rsi_signal'] = (df['rsi'] - 50) / 50  # 归一化到[-1, 1]

        # MACD
        if self.tech_config.use_macd:
            macd, macd_signal, macd_hist = talib.MACD(
                close, fastperiod=12, slowperiod=26, signalperiod=9
            )
            df['macd'] = macd
            df['macd_signal'] = macd_signal
            df['macd_hist'] = macd_hist

        # 随机指标
        if self.tech_config.use_stoch:
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)
            df['stoch_k'] = slowk
            df['stoch_d'] = slowd

        # 布林带
        if self.tech_config.use_bollinger:
            upper, middle, lower = talib.BBANDS(
                close, timeperiod=self.tech_config.bb_period, nbdevup=2, nbdevdn=2
            )
            df['bb_upper'] = upper
            df['bb_middle'] = middle
            df['bb_lower'] = lower
            df['bb_position'] = (df['close'] - lower) / (upper - lower + 1e-10)
            df['bb_width'] = (upper - lower) / middle

        # ATR
        if self.tech_config.use_atr:
            df['atr'] = talib.ATR(high, low, close, timeperiod=self.tech_config.atr_period)
            df['atr_ratio'] = df['atr'] / df['close']

        # OBV
        if self.tech_config.use_obv:
            df['obv'] = talib.OBV(close, volume)
            df['obv_ma'] = df['obv'].rolling(20).mean()

        # 价格形态
        if self.tech_config.use_price_patterns:
            # 简单形态识别
            df['doji'] = talib.CDLDOJI(open=df['open'].values, high=high, low=low, close=close)
            df['hammer'] = talib.CDLHAMMER(open=df['open'].values, high=high, low=low, close=close)
            df['engulfing'] = talib.CDLENGULFING(open=df['open'].values, high=high, low=low, close=close)

        return df

    def _add_market_features(self, df: pd.DataFrame, market_df: pd.DataFrame) -> pd.DataFrame:
        """添加市场指数特征"""
        # 对齐数据
        market_aligned = market_df['close'].reindex(df.index, method='ffill')

        # 市场收益率
        df['market_return'] = market_aligned.pct_change()
        df['market_ma'] = market_aligned.rolling(20).mean()

        # 相对强弱
        stock_return = df['close'].pct_change(20)
        market_return = market_aligned.pct_change(20)
        df['relative_strength'] = stock_return - market_return

        # Beta (滚动)
        df['beta'] = self._calculate_rolling_beta(
            df['close'].pct_change(),
            market_aligned.pct_change(),
            window=60
        )

        return df

    def _add_sector_features(self, df: pd.DataFrame, sector_df: pd.DataFrame) -> pd.DataFrame:
        """添加行业指数特征"""
        sector_aligned = sector_df['close'].reindex(df.index, method='ffill')

        # 行业相对收益
        df['sector_return'] = sector_aligned.pct_change()
        df['sector_relative'] = df['returns'] - df['sector_return']

        # 行业内排名 (需要多只股票的截面数据，这里简化处理)

        return df

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加时序特征"""
        # 滞后特征
        for lag in [1, 2, 3, 5]:
            df[f'returns_lag_{lag}'] = df['returns'].shift(lag)
            df[f'volume_lag_{lag}'] = df['volume_ratio'].shift(lag)

        # 滚动统计特征
        for window in [5, 10, 20]:
            df[f'returns_volatility_{window}'] = df['returns'].rolling(window).std()
            df[f'returns_skew_{window}'] = df['returns'].rolling(window).skew()
            df[f'volume_ma_{window}'] = df['volume_ratio'].rolling(window).mean()

        # 时间特征
        df['dayofweek'] = df.index.dayofweek
        df['month'] = df.index.month
        df['quarter'] = df.index.quarter

        return df

    def _calculate_rolling_beta(
        self,
        stock_returns: pd.Series,
        market_returns: pd.Series,
        window: int = 60
    ) -> pd.Series:
        """计算滚动Beta"""
        beta = pd.Series(index=stock_returns.index, dtype=float)

        for i in range(window, len(stock_returns)):
            y = stock_returns.iloc[i-window:i].dropna()
            x = market_returns.iloc[i-window:i].dropna()

            common_idx = y.index.intersection(x.index)
            if len(common_idx) < window // 2:
                continue

            y = y.loc[common_idx]
            x = x.loc[common_idx]

            # 简单线性回归计算beta
            cov = np.cov(y, x)[0, 1]
            var = np.var(x)
            if var > 0:
                beta.iloc[i] = cov / var

        return beta

    def create_target(
        self,
        df: pd.DataFrame,
        horizon: int = 1,
        target_type: str = 'direction'
    ) -> pd.Series:
        """
        创建预测目标

        Args:
            df: 特征DataFrame
            horizon: 预测 horizon (天数)
            target_type: 'direction'(涨跌), 'return'(收益率), 'quantile'(分位数)

        Returns:
            目标Series
        """
        future_return = df['close'].shift(-horizon) / df['close'] - 1

        if target_type == 'direction':
            # 分类：1=涨, 0=平, -1=跌
            target = pd.cut(future_return, bins=[-np.inf, -0.005, 0.005, np.inf], labels=[-1, 0, 1])
            target = target.astype(int)
        elif target_type == 'return':
            # 回归：未来收益率
            target = future_return
        elif target_type == 'quantile':
            # 分位数标签
            target = pd.qcut(future_return, q=5, labels=[0, 1, 2, 3, 4])
            target = target.astype(int)

        return target

    def prepare_train_test_split(
        self,
        df: pd.DataFrame,
        target: pd.Series,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15
    ) -> Dict[str, pd.DataFrame]:
        """
        时序数据划分

        Returns:
            {'X_train', 'y_train', 'X_val', 'y_val', 'X_test', 'y_test'}
        """
        # 对齐数据
        common_idx = df.index.intersection(target.index)
        df = df.loc[common_idx]
        target = target.loc[common_idx]

        # 选择特征列
        feature_cols = [c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df[feature_cols]
        y = target

        # 时序划分
        n = len(X)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]

        X_val = X.iloc[train_end:val_end]
        y_val = y.iloc[train_end:val_end]

        X_test = X.iloc[val_end:]
        y_test = y.iloc[val_end:]

        logger.info(f"数据划分: 训练集{len(X_train)}, 验证集{len(X_val)}, 测试集{len(X_test)}")

        return {
            'X_train': X_train,
            'y_train': y_train,
            'X_val': X_val,
            'y_val': y_val,
            'X_test': X_test,
            'y_test': y_test
        }

    def normalize_features(
        self,
        data_dict: Dict[str, pd.DataFrame],
        method: str = 'zscore'
    ) -> Dict[str, pd.DataFrame]:
        """
        特征归一化

        Args:
            data_dict: 数据字典
            method: 'zscore' 或 'minmax'
        """
        result = data_dict.copy()
        X_train = data_dict['X_train']

        if method == 'zscore':
            mean = X_train.mean()
            std = X_train.std()

            for key in ['X_train', 'X_val', 'X_test']:
                result[key] = (data_dict[key] - mean) / (std + 1e-10)

        elif method == 'minmax':
            min_val = X_train.min()
            max_val = X_train.max()

            for key in ['X_train', 'X_val', 'X_test']:
                result[key] = (data_dict[key] - min_val) / (max_val - min_val + 1e-10)

        # 保存归一化参数
        self.norm_params = {'mean': mean, 'std': std} if method == 'zscore' else {'min': min_val, 'max': max_val}

        return result
