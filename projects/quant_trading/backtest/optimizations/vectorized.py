"""
向量化回测模块

提供向量化回测实现，比事件驱动回测更快。
适用于简单策略的快速回测和参数扫描。
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.metrics import MetricsCalculator, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class VectorizedResult:
    """向量化回测结果"""

    nav_history: List[Tuple[datetime, float]]
    returns: pd.Series
    positions: pd.DataFrame
    trades: pd.DataFrame
    metrics: PerformanceMetrics


class VectorizedBacktester:
    """向量化回测器

    使用向量化计算进行快速回测，适合简单策略。

    注意：向量化回测不支持复杂的风控逻辑和滑点模型，
    主要用于参数扫描和策略初筛。

    Example:
        >>> backtester = VectorizedBacktester(initial_cash=100000)
        >>> signals = generate_signals(data)  # 生成交易信号
        >>> result = backtester.run(data, signals)
        >>> print(f"Return: {result.metrics.total_return}")
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.0002,
    ):
        """初始化向量化回测器

        Args:
            initial_cash: 初始资金
            commission_rate: 佣金率
            slippage_rate: 滑点率
        """
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

    def run(
        self,
        prices: pd.DataFrame,
        signals: pd.DataFrame,
        position_size: float = 1.0,
    ) -> VectorizedResult:
        """执行向量化回测

        Args:
            prices: 价格DataFrame，index为日期，columns为股票代码
            signals: 信号DataFrame，1表示买入，-1表示卖出，0表示持有
            position_size: 仓位比例

        Returns:
            VectorizedResult 回测结果
        """
        logger.info("Starting vectorized backtest")

        # 计算收益率
        returns = prices.pct_change().fillna(0)

        # 信号延迟一天执行（避免未来函数）
        delayed_signals = signals.shift(1).fillna(0)

        # 计算策略收益率
        strategy_returns = (delayed_signals * returns).sum(axis=1) * position_size

        # 计算交易成本
        turnover = (signals.diff().abs()).sum(axis=1) * 0.5
        transaction_costs = turnover * (self.commission_rate * 2 + self.slippage_rate * 2)

        # 扣除交易成本
        net_returns = strategy_returns - transaction_costs

        # 计算净值
        nav = (1 + net_returns).cumprod() * self.initial_cash

        # 生成净值历史
        nav_history = [(idx, float(val)) for idx, val in nav.items()]

        # 计算绩效指标
        calculator = MetricsCalculator()
        metrics = calculator.calculate(nav_history)

        # 生成交易记录
        trades = self._generate_trades(signals, prices)

        # 生成持仓记录
        positions = self._generate_positions(signals)

        result = VectorizedResult(
            nav_history=nav_history,
            returns=net_returns,
            positions=positions,
            trades=trades,
            metrics=metrics,
        )

        logger.info(f"Vectorized backtest completed: return={metrics.total_return:.2%}")

        return result

    def _generate_trades(
        self,
        signals: pd.DataFrame,
        prices: pd.DataFrame,
    ) -> pd.DataFrame:
        """生成交易记录"""
        trades = []

        for col in signals.columns:
            signal_series = signals[col]
            price_series = prices[col]

            # 找出买卖信号变化点
            changes = signal_series.diff().fillna(0)

            for date, change in changes.items():
                if change != 0:
                    side = "buy" if change > 0 else "sell"
                    trades.append(
                        {
                            "date": date,
                            "ts_code": col,
                            "side": side,
                            "price": price_series[date],
                        }
                    )

        return pd.DataFrame(trades)

    def _generate_positions(self, signals: pd.DataFrame) -> pd.DataFrame:
        """生成持仓记录"""
        return signals.copy()

    def run_multi_strategy(
        self,
        prices: pd.DataFrame,
        strategy_signals: Dict[str, pd.DataFrame],
    ) -> Dict[str, VectorizedResult]:
        """运行多个策略对比

        Args:
            prices: 价格DataFrame
            strategy_signals: 策略信号字典 {策略名: 信号DataFrame}

        Returns:
            策略结果字典
        """
        results = {}

        for name, signals in strategy_signals.items():
            logger.info(f"Running strategy: {name}")
            result = self.run(prices, signals)
            results[name] = result

        return results

    def optimize_position_size(
        self,
        prices: pd.DataFrame,
        signals: pd.DataFrame,
        size_range: np.ndarray = np.linspace(0.1, 1.0, 10),
    ) -> Tuple[float, VectorizedResult]:
        """优化仓位大小

        Args:
            prices: 价格DataFrame
            signals: 信号DataFrame
            size_range: 仓位比例范围

        Returns:
            (最佳仓位, 最佳结果)
        """
        best_size = size_range[0]
        best_result = None
        best_sharpe = -np.inf

        for size in size_range:
            result = self.run(prices, signals, position_size=size)
            sharpe = result.metrics.sharpe_ratio

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_size = size
                best_result = result

        logger.info(f"Optimal position size: {best_size:.2f} (sharpe={best_sharpe:.2f})")

        return best_size, best_result
