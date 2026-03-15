"""
信号生成模块 - 基于价差的交易信号

功能：
- 价差计算：spread = P1 - β*P2
- Z-score标准化
- 动态阈值信号生成
- ADF动态监测
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)


class Signal(Enum):
    """交易信号枚举"""
    NO_SIGNAL = 0
    LONG_SPREAD = 1      # 做多价差（买入A，卖出B）
    SHORT_SPREAD = -1    # 做空价差（卖出A，买入B）
    CLOSE_POSITION = 2   # 平仓


@dataclass
class SignalConfig:
    """信号配置"""
    # 阈值设置
    entry_threshold: float = 2.0      # 开仓阈值
    exit_threshold: float = 0.5       # 平仓阈值
    stop_threshold: float = 3.5       # 止损阈值

    # ADF监测
    adf_pvalue_threshold: float = 0.1  # ADF检验p值阈值
    dynamic_monitoring: bool = True    # 是否动态监测协整关系

    # 回望窗口
    lookback_window: int = 20          # Z-score计算窗口
    min_lookback: int = 10             # 最小数据要求

    # 趋势过滤
    use_trend_filter: bool = False     # 是否使用趋势过滤
    trend_window: int = 60             # 趋势窗口


class SpreadSignalGenerator:
    """价差信号生成器"""

    def __init__(self, config: Optional[SignalConfig] = None):
        self.config = config or SignalConfig()
        self.spread_history: pd.Series = pd.Series(dtype=float)
        self.zscore_history: pd.Series = pd.Series(dtype=float)
        self.current_signal: Signal = Signal.NO_SIGNAL
        self.position_open_zscore: Optional[float] = None

    def update_spread(self, spread: float, timestamp=None) -> None:
        """
        更新价差数据

        Args:
            spread: 当前价差
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = len(self.spread_history)

        self.spread_history.loc[timestamp] = spread

        # 计算Z-score
        if len(self.spread_history) >= self.config.min_lookback:
            lookback = min(self.config.lookback_window, len(self.spread_history))
            recent_spread = self.spread_history.iloc[-lookback:]
            mean = recent_spread.mean()
            std = recent_spread.std()

            if std > 0:
                zscore = (spread - mean) / std
                self.zscore_history.loc[timestamp] = zscore

    def generate_signal(
        self,
        spread: float,
        adf_pvalue: Optional[float] = None,
        timestamp=None
    ) -> Signal:
        """
        生成交易信号

        Args:
            spread: 当前价差
            adf_pvalue: ADF检验p值（用于动态监测）
            timestamp: 时间戳

        Returns:
            交易信号
        """
        self.update_spread(spread, timestamp)

        # 数据不足
        if len(self.spread_history) < self.config.min_lookback:
            return Signal.NO_SIGNAL

        zscore = self.zscore_history.iloc[-1]

        # ADF动态监测：协整关系破裂时强制平仓
        if self.config.dynamic_monitoring and adf_pvalue is not None:
            if adf_pvalue > self.config.adf_pvalue_threshold:
                if self.current_signal != Signal.NO_SIGNAL:
                    logger.warning(f"协整关系破裂 (p={adf_pvalue:.3f})，强制平仓")
                    self.current_signal = Signal.NO_SIGNAL
                    self.position_open_zscore = None
                    return Signal.CLOSE_POSITION

        # 根据当前持仓状态生成信号
        if self.current_signal == Signal.NO_SIGNAL:
            # 空仓状态，寻找开仓机会
            if zscore > self.config.entry_threshold:
                self.current_signal = Signal.SHORT_SPREAD
                self.position_open_zscore = zscore
                return Signal.SHORT_SPREAD
            elif zscore < -self.config.entry_threshold:
                self.current_signal = Signal.LONG_SPREAD
                self.position_open_zscore = zscore
                return Signal.LONG_SPREAD

        elif self.current_signal == Signal.LONG_SPREAD:
            # 做多价差持仓中
            # 1. 达到平仓阈值
            if zscore >= -self.config.exit_threshold:
                self.current_signal = Signal.NO_SIGNAL
                self.position_open_zscore = None
                return Signal.CLOSE_POSITION
            # 2. 止损
            elif zscore < -self.config.stop_threshold:
                logger.warning(f"多头止损触发: zscore={zscore:.2f}")
                self.current_signal = Signal.NO_SIGNAL
                self.position_open_zscore = None
                return Signal.CLOSE_POSITION

        elif self.current_signal == Signal.SHORT_SPREAD:
            # 做空价差持仓中
            # 1. 达到平仓阈值
            if zscore <= self.config.exit_threshold:
                self.current_signal = Signal.NO_SIGNAL
                self.position_open_zscore = None
                return Signal.CLOSE_POSITION
            # 2. 止损
            elif zscore > self.config.stop_threshold:
                logger.warning(f"空头止损触发: zscore={zscore:.2f}")
                self.current_signal = Signal.NO_SIGNAL
                self.position_open_zscore = None
                return Signal.CLOSE_POSITION

        return Signal.NO_SIGNAL

    def get_zscore(self) -> Optional[float]:
        """获取当前Z-score"""
        if len(self.zscore_history) > 0:
            return self.zscore_history.iloc[-1]
        return None

    def get_spread_stats(self) -> dict:
        """获取价差统计信息"""
        if len(self.spread_history) < self.config.min_lookback:
            return {}

        return {
            "mean": self.spread_history.mean(),
            "std": self.spread_history.std(),
            "min": self.spread_history.min(),
            "max": self.spread_history.max(),
            "current_zscore": self.get_zscore(),
            "percentile_5": self.spread_history.quantile(0.05),
            "percentile_95": self.spread_history.quantile(0.95),
        }

    def reset(self) -> None:
        """重置状态"""
        self.spread_history = pd.Series(dtype=float)
        self.zscore_history = pd.Series(dtype=float)
        self.current_signal = Signal.NO_SIGNAL
        self.position_open_zscore = None


class DynamicThresholdGenerator(SpreadSignalGenerator):
    """动态阈值信号生成器"""

    def __init__(self, config: Optional[SignalConfig] = None, volatility_window: int = 20):
        super().__init__(config)
        self.volatility_window = volatility_window

    def calculate_dynamic_threshold(self) -> tuple[float, float, float]:
        """
        基于波动率计算动态阈值

        Returns:
            (entry_threshold, exit_threshold, stop_threshold)
        """
        if len(self.zscore_history) < self.volatility_window:
            return (
                self.config.entry_threshold,
                self.config.exit_threshold,
                self.config.stop_threshold
            )

        # 计算Z-score的波动率
        recent_volatility = self.zscore_history.iloc[-self.volatility_window:].std()

        # 基础阈值
        base_entry = 2.0
        base_exit = 0.5
        base_stop = 3.5

        # 根据波动率调整
        # 高波动率时放宽阈值，低波动率时收紧
        adjustment = recent_volatility / 1.0  # 1.0为基准波动率

        entry = base_entry * adjustment
        exit_threshold = base_exit * adjustment
        stop = base_stop * adjustment

        return entry, exit_threshold, stop

    def generate_signal(
        self,
        spread: float,
        adf_pvalue: Optional[float] = None,
        timestamp=None
    ) -> Signal:
        """使用动态阈值生成信号"""
        # 更新数据
        self.update_spread(spread, timestamp)

        if len(self.spread_history) < self.config.min_lookback:
            return Signal.NO_SIGNAL

        # 获取动态阈值
        entry_thresh, exit_thresh, stop_thresh = self.calculate_dynamic_threshold()
        zscore = self.zscore_history.iloc[-1]

        # ADF动态监测
        if self.config.dynamic_monitoring and adf_pvalue is not None:
            if adf_pvalue > self.config.adf_pvalue_threshold:
                if self.current_signal != Signal.NO_SIGNAL:
                    self.current_signal = Signal.NO_SIGNAL
                    return Signal.CLOSE_POSITION

        # 信号逻辑
        if self.current_signal == Signal.NO_SIGNAL:
            if zscore > entry_thresh:
                self.current_signal = Signal.SHORT_SPREAD
                return Signal.SHORT_SPREAD
            elif zscore < -entry_thresh:
                self.current_signal = Signal.LONG_SPREAD
                return Signal.LONG_SPREAD

        elif self.current_signal == Signal.LONG_SPREAD:
            if zscore >= -exit_thresh:
                self.current_signal = Signal.NO_SIGNAL
                return Signal.CLOSE_POSITION
            elif zscore < -stop_thresh:
                self.current_signal = Signal.NO_SIGNAL
                return Signal.CLOSE_POSITION

        elif self.current_signal == Signal.SHORT_SPREAD:
            if zscore <= exit_thresh:
                self.current_signal = Signal.NO_SIGNAL
                return Signal.CLOSE_POSITION
            elif zscore > stop_thresh:
                self.current_signal = Signal.NO_SIGNAL
                return Signal.CLOSE_POSITION

        return Signal.NO_SIGNAL
