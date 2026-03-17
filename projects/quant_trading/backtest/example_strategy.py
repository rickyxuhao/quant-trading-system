"""
回测框架 - 示例策略模块

实现多种常用量化交易策略：
- 动量策略（MomentumStrategy）: 基于过去N日收益率排序选股
- 均值回归策略（MeanReversionStrategy）: 基于超跌反弹原理选股
- 双动量策略（DualMomentumStrategy）: 绝对动量+相对动量双重筛选
- RSI策略（RSIStrategy）: 基于RSI超买超卖信号选股

Example:
    >>> strategy = MomentumStrategy(lookback_period=20, top_n=10)
    >>> selected_stocks = strategy.generate_signals(
    ...     data={'000001.SZ': df1, '000002.SZ': df2},
    ...     current_date=datetime(2024, 1, 15),
    ...     available_stocks=['000001.SZ', '000002.SZ']
    ... )
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd


# Setup logging
logger = logging.getLogger(__name__)

# Add project root to path for imports
try:
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from projects.quant_trading.backtest.strategy import (
        BaseStrategy,
        Signal,
        SignalType,
    )
except ImportError as e:
    logger.error(f"Failed to import Strategy base class: {e}")

    # Define minimal base classes for standalone usage
    class Signal:  # type: ignore[no-redef]
        def __init__(
            self, ts_code: str, signal_type: Any, weight: float = 0.0, **kwargs: Any
        ) -> None:
            self.ts_code = ts_code
            self.signal_type = signal_type
            self.weight = weight
            self.score = kwargs.get("score", 0.0)
            self.reason = kwargs.get("reason", "")

    class BaseStrategy:  # type: ignore[no-redef]
        def __init__(self, name: str = "", params: Optional[Dict[str, Any]] = None) -> None:
            self.name = name
            self.params = params or {}

        def get_name(self) -> str:
            return self.name


__all__ = [
    "StockScore",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "DualMomentumStrategy",
    "RSIStrategy",
    "create_strategy",
]


@dataclass
class StockScore:
    """股票评分数据类

    Attributes:
        ts_code: 股票代码
        score: 评分值
        metrics: 附加指标字典
    """

    ts_code: str
    score: float
    metrics: Dict[str, Any]


class MomentumStrategy(BaseStrategy):
    """动量策略

    基于过去N日的收益率排序，选择涨幅最大的M只股票持有。
    可配合成交量过滤，排除流动性不足的股票。

    Attributes:
        lookback_period: 回看周期（交易日），默认20日
        top_n: 选股数量，默认10只
        min_volume: 最小成交量（手），默认10000

    Example:
        >>> strategy = MomentumStrategy(lookback_period=20, top_n=10, min_volume=10000)
        >>> stocks = strategy.generate_signals(data, current_date, available_stocks)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        top_n: int = 10,
        min_volume: int = 10000,
        **kwargs: Any,
    ) -> None:
        """初始化动量策略

        Args:
            lookback_period: 回看周期（交易日）
            top_n: 选股数量
            min_volume: 最小成交量过滤（手）

        Raises:
            ValueError: 当参数无效时
        """
        super().__init__(name="MomentumStrategy")
        if lookback_period <= 0:
            raise ValueError(f"lookback_period must be positive, got {lookback_period}")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")
        if min_volume < 0:
            raise ValueError(f"min_volume must be non-negative, got {min_volume}")

        self.lookback_period = lookback_period
        self.top_n = top_n
        self.min_volume = min_volume
        self.params.update(kwargs)

        logger.debug(
            f"MomentumStrategy initialized: lookback={lookback_period}, "
            f"top_n={top_n}, min_volume={min_volume}"
        )

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成交易信号 - 选择动量最强的股票

        Args:
            data: 股票数据字典 {ts_code: DataFrame}
            current_date: 当前日期
            available_stocks: 可选股票列表

        Returns:
            交易信号列表，按动量从高到低排序
        """
        if not self.validate_data(data):
            logger.warning("Data validation failed, no signals generated")
            return []

        momentum_scores: List[StockScore] = []

        for ts_code in available_stocks:
            if ts_code not in data:
                continue

            df = data[ts_code]
            if df.empty or len(df) < self.lookback_period:
                continue

            try:
                df_period = df.tail(self.lookback_period)

                start_price = df_period["close"].iloc[0]
                end_price = df_period["close"].iloc[-1]

                if start_price <= 0 or end_price <= 0:
                    logger.debug(f"Invalid price for {ts_code}: {start_price}, {end_price}")
                    continue

                momentum = (end_price - start_price) / start_price
                avg_volume = df_period["vol"].mean() if "vol" in df_period.columns else float("inf")

                if avg_volume < self.min_volume:
                    continue

                momentum_scores.append(
                    StockScore(
                        ts_code=ts_code,
                        score=momentum,
                        metrics={
                            "momentum": momentum,
                            "end_price": end_price,
                            "avg_volume": avg_volume,
                        },
                    )
                )
            except (KeyError, IndexError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating momentum for {ts_code}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error for {ts_code}: {e}")
                continue

        if not momentum_scores:
            logger.info("No stocks passed momentum filter")
            return []

        # Sort by momentum (descending)
        momentum_scores.sort(key=lambda x: x.score, reverse=True)
        selected = momentum_scores[: self.top_n]

        # Create signals
        signals: List[Signal] = []
        for item in selected:
            signals.append(
                Signal(
                    ts_code=item.ts_code,
                    signal_type=SignalType.BUY,
                    score=item.score,
                    reason=f"Momentum={item.metrics['momentum']*100:+.2f}%",
                )
            )

        if signals:
            logger.info(f"[Momentum] Selected {len(signals)} stocks:")
            for i, item in enumerate(selected, 1):
                logger.info(
                    f"  {i}. {item.ts_code}: "
                    f"momentum={item.metrics['momentum']*100:+.2f}%, "
                    f"volume={item.metrics['avg_volume']:,.0f}"
                )

        return signals


class MeanReversionStrategy(BaseStrategy):
    """均值回归策略

    选择跌幅最大的M只股票持有（超跌反弹原理）。
    可设置最大跌幅限制，排除跌幅过大的股票（防止黑天鹅）。

    Attributes:
        lookback_period: 回看周期（交易日），默认20日
        top_n: 选股数量，默认10只
        max_drop: 最大跌幅限制（排除跌幅过大的股票），默认-30%

    Example:
        >>> strategy = MeanReversionStrategy(lookback_period=20, top_n=10, max_drop=-0.30)
        >>> stocks = strategy.generate_signals(data, current_date, available_stocks)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        top_n: int = 10,
        max_drop: float = -0.30,
        **kwargs: Any,
    ) -> None:
        """初始化均值回归策略

        Args:
            lookback_period: 回看周期（交易日）
            top_n: 选股数量
            max_drop: 最大跌幅限制（负数，如-0.30表示-30%）

        Raises:
            ValueError: 当参数无效时
        """
        super().__init__(name="MeanReversionStrategy")
        if lookback_period <= 0:
            raise ValueError(f"lookback_period must be positive, got {lookback_period}")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")
        if max_drop > 0:
            raise ValueError(f"max_drop should be negative, got {max_drop}")

        self.lookback_period = lookback_period
        self.top_n = top_n
        self.max_drop = max_drop
        self.params.update(kwargs)

        logger.debug(
            f"MeanReversionStrategy initialized: lookback={lookback_period}, "
            f"top_n={top_n}, max_drop={max_drop}"
        )

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成交易信号 - 选择跌幅最大的股票

        Args:
            data: 股票数据字典 {ts_code: DataFrame}
            current_date: 当前日期
            available_stocks: 可选股票列表

        Returns:
            交易信号列表
        """
        if not self.validate_data(data):
            logger.warning("Data validation failed, no signals generated")
            return []

        reversal_scores: List[StockScore] = []

        for ts_code in available_stocks:
            if ts_code not in data:
                continue

            df = data[ts_code]
            if df.empty or len(df) < self.lookback_period:
                continue

            try:
                df_period = df.tail(self.lookback_period)

                start_price = df_period["close"].iloc[0]
                end_price = df_period["close"].iloc[-1]

                if start_price <= 0 or end_price <= 0:
                    continue

                returns = (end_price - start_price) / start_price

                # Exclude stocks with excessive drop
                if returns < self.max_drop:
                    continue

                reversal_scores.append(
                    StockScore(
                        ts_code=ts_code,
                        score=returns,  # Negative value indicates decline
                        metrics={"returns": returns, "end_price": end_price},
                    )
                )
            except (KeyError, IndexError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating reversion for {ts_code}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error for {ts_code}: {e}")
                continue

        if not reversal_scores:
            logger.info("No stocks passed mean reversion filter")
            return []

        # Sort by returns (ascending, select largest declines)
        reversal_scores.sort(key=lambda x: x.score)
        selected = reversal_scores[: self.top_n]

        # Create signals
        signals: List[Signal] = []
        for item in selected:
            signals.append(
                Signal(
                    ts_code=item.ts_code,
                    signal_type=SignalType.BUY,
                    score=item.score,
                    reason=f"Returns={item.metrics['returns']*100:+.2f}%",
                )
            )

        if signals:
            logger.info(f"[Mean Reversion] Selected {len(signals)} stocks:")
            for i, item in enumerate(selected, 1):
                logger.info(f"  {i}. {item.ts_code}: returns={item.metrics['returns']*100:+.2f}%")

        return signals


class DualMomentumStrategy(BaseStrategy):
    """双动量策略（绝对动量 + 相对动量）

    1. 绝对动量：股票自身过去N日收益为正（趋势向上）
    2. 相对动量：在绝对动量股票中选择收益最高的M只

    这种策略可以过滤掉整体市场下跌时的逆势操作。

    Attributes:
        lookback_period: 回看周期（交易日），默认20日
        top_n: 选股数量，默认10只
        min_momentum: 最小动量阈值，默认0.0

    Example:
        >>> strategy = DualMomentumStrategy(lookback_period=20, top_n=10)
        >>> stocks = strategy.generate_signals(data, current_date, available_stocks)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        top_n: int = 10,
        min_momentum: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """初始化双动量策略

        Args:
            lookback_period: 回看周期（交易日）
            top_n: 选股数量
            min_momentum: 最小动量阈值（绝对动量筛选）

        Raises:
            ValueError: 当参数无效时
        """
        super().__init__(name="DualMomentumStrategy")
        if lookback_period <= 0:
            raise ValueError(f"lookback_period must be positive, got {lookback_period}")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")

        self.lookback_period = lookback_period
        self.top_n = top_n
        self.min_momentum = min_momentum
        self.params.update(kwargs)

        logger.debug(
            f"DualMomentumStrategy initialized: lookback={lookback_period}, "
            f"top_n={top_n}, min_momentum={min_momentum}"
        )

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成交易信号 - 双动量筛选

        Args:
            data: 股票数据字典 {ts_code: DataFrame}
            current_date: 当前日期
            available_stocks: 可选股票列表

        Returns:
            交易信号列表
        """
        if not self.validate_data(data):
            logger.warning("Data validation failed, no signals generated")
            return []

        momentum_scores: List[StockScore] = []

        for ts_code in available_stocks:
            if ts_code not in data:
                continue

            df = data[ts_code]
            if df.empty or len(df) < self.lookback_period:
                continue

            try:
                df_period = df.tail(self.lookback_period)

                start_price = df_period["close"].iloc[0]
                end_price = df_period["close"].iloc[-1]

                if start_price <= 0 or end_price <= 0:
                    continue

                momentum = (end_price - start_price) / start_price

                momentum_scores.append(
                    StockScore(
                        ts_code=ts_code,
                        score=momentum,
                        metrics={"momentum": momentum, "end_price": end_price},
                    )
                )
            except (KeyError, IndexError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating dual momentum for {ts_code}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error for {ts_code}: {e}")
                continue

        if not momentum_scores:
            logger.info("No stocks available for dual momentum screening")
            return []

        # Absolute momentum filter (keep only positive returns)
        positive_momentum = [s for s in momentum_scores if s.score > self.min_momentum]

        if not positive_momentum:
            logger.info(
                f"[Dual Momentum] No positive momentum stocks (threshold={self.min_momentum*100:.1f}%), holding cash"
            )
            return []

        # Relative momentum sort (select highest returns among positive)
        positive_momentum.sort(key=lambda x: x.score, reverse=True)
        selected = positive_momentum[: self.top_n]

        # Create signals
        signals: List[Signal] = []
        for item in selected:
            signals.append(
                Signal(
                    ts_code=item.ts_code,
                    signal_type=SignalType.BUY,
                    score=item.score,
                    reason=f"Momentum={item.metrics['momentum']*100:+.2f}%",
                )
            )

        if signals:
            logger.info(
                f"[Dual Momentum] Absolute filter: {len(positive_momentum)} positive stocks"
            )
            logger.info(f"[Dual Momentum] Selected {len(signals)} stocks:")
            for i, item in enumerate(selected, 1):
                logger.info(f"  {i}. {item.ts_code}: momentum={item.metrics['momentum']*100:+.2f}%")

        return signals


class RSIStrategy(BaseStrategy):
    """RSI策略（相对强弱指标）

    基于RSI指标进行超买超卖判断。
    - RSI < 超卖阈值: 买入信号
    - RSI > 超买阈值: 卖出信号

    Attributes:
        rsi_period: RSI计算周期，默认14日
        oversold: 超卖阈值，默认30
        overbought: 超买阈值，默认70
        top_n: 选股数量，默认10只

    Example:
        >>> strategy = RSIStrategy(rsi_period=14, oversold=30, overbought=70)
        >>> stocks = strategy.generate_signals(data, current_date, available_stocks)
    """

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        top_n: int = 10,
        **kwargs: Any,
    ) -> None:
        """初始化RSI策略

        Args:
            rsi_period: RSI计算周期
            oversold: 超卖阈值
            overbought: 超买阈值
            top_n: 选股数量

        Raises:
            ValueError: 当参数无效时
        """
        super().__init__(name="RSIStrategy")
        if rsi_period <= 0:
            raise ValueError(f"rsi_period must be positive, got {rsi_period}")
        if not 0 <= oversold <= 100:
            raise ValueError(f"oversold must be in [0, 100], got {oversold}")
        if not 0 <= overbought <= 100:
            raise ValueError(f"overbought must be in [0, 100], got {overbought}")
        if oversold >= overbought:
            raise ValueError(f"oversold ({oversold}) must be less than overbought ({overbought})")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")

        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.top_n = top_n
        self.params.update(kwargs)

    def _calculate_rsi(self, prices: "pd.Series") -> float:
        """计算RSI指标

        Args:
            prices: 价格序列

        Returns:
            RSI值（0-100）

        Raises:
            ValueError: 当价格数据无效时
        """
        import pandas as pd

        if prices.empty:
            raise ValueError("Price series is empty")

        deltas = prices.diff().dropna()
        if deltas.empty:
            return 50.0

        gain = (deltas.where(deltas > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=self.rsi_period).mean()

        # Handle division by zero
        rs = pd.Series([0.0] * len(gain), index=gain.index)
        mask = (loss != 0) & loss.notna()
        rs[mask] = gain[mask] / loss[mask]

        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty else 50.0

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成RSI交易信号

        Args:
            data: 股票数据字典
            current_date: 当前日期
            available_stocks: 可选股票列表

        Returns:
            交易信号列表
        """
        if not self.validate_data(data):
            logger.warning("Data validation failed, no signals generated")
            return []

        rsi_scores: List[StockScore] = []

        for ts_code in available_stocks:
            if ts_code not in data:
                continue

            df = data[ts_code]
            min_periods = self.rsi_period + 5
            if df.empty or len(df) < min_periods:
                continue

            try:
                prices = df["close"]
                rsi = self._calculate_rsi(prices)

                # Select oversold stocks (low RSI)
                if rsi < self.oversold:
                    rsi_scores.append(
                        StockScore(
                            ts_code=ts_code,
                            score=100 - rsi,  # Lower RSI = higher score
                            metrics={"rsi": rsi},
                        )
                    )
            except (KeyError, IndexError) as e:
                logger.warning(f"Error calculating RSI for {ts_code}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error for {ts_code}: {e}")
                continue

        if not rsi_scores:
            logger.info(f"No oversold stocks found (RSI < {self.oversold})")
            return []

        # Sort by RSI score (descending)
        rsi_scores.sort(key=lambda x: x.score, reverse=True)
        selected = rsi_scores[: self.top_n]

        # Create signals
        signals: List[Signal] = []
        for item in selected:
            signals.append(
                Signal(
                    ts_code=item.ts_code,
                    signal_type=SignalType.BUY,
                    score=item.score,
                    reason=f"RSI={item.metrics['rsi']:.1f} (oversold)",
                )
            )

        if signals:
            logger.info(f"[RSI] Selected {len(signals)} oversold stocks:")
            for i, item in enumerate(selected, 1):
                logger.info(f"  {i}. {item.ts_code}: RSI={item.metrics['rsi']:.1f}")

        return signals


def create_strategy(strategy_type: str, **params: Any) -> BaseStrategy:
    """策略工厂函数

    根据策略类型名称创建对应的策略实例。

    Args:
        strategy_type: 策略类型名称
            - 'momentum': 动量策略
            - 'mean_reversion': 均值回归策略
            - 'dual_momentum': 双动量策略
            - 'rsi': RSI策略
        **params: 策略参数

    Returns:
        策略实例

    Raises:
        ValueError: 当策略类型未知时

    Example:
        >>> strategy = create_strategy('momentum', lookback_period=20, top_n=10)
        >>> print(strategy.get_name())
        MomentumStrategy
    """
    strategy_map: Dict[str, type[BaseStrategy]] = {
        "momentum": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "dual_momentum": DualMomentumStrategy,
        "rsi": RSIStrategy,
    }

    strategy_type_lower = strategy_type.lower()
    if strategy_type_lower not in strategy_map:
        available = ", ".join(strategy_map.keys())
        raise ValueError(f"Unknown strategy type: '{strategy_type}'. " f"Available: [{available}]")

    strategy_class = strategy_map[strategy_type_lower]
    return strategy_class(**params)


def _setup_test_logging() -> None:
    """设置测试日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


if __name__ == "__main__":
    _setup_test_logging()

    # Test strategies
    print("=" * 60)
    print("Strategy Tests")
    print("=" * 60)

    # Test MomentumStrategy
    momentum = MomentumStrategy(lookback_period=20, top_n=5)
    print(f"\nStrategy name: {momentum.get_name()}")

    import pandas as pd

    test_data = {
        "000001.SZ": pd.DataFrame(
            {
                "trade_date": pd.date_range("20240101", periods=25),
                "close": [10.0 + i * 0.1 for i in range(25)],
                "vol": [100000] * 25,
            }
        ),
        "000002.SZ": pd.DataFrame(
            {
                "trade_date": pd.date_range("20240101", periods=25),
                "close": [20.0 - i * 0.1 for i in range(25)],
                "vol": [80000] * 25,
            }
        ),
        "000003.SZ": pd.DataFrame(
            {
                "trade_date": pd.date_range("20240101", periods=25),
                "close": [15.0 + i * 0.05 for i in range(25)],
                "vol": [50000] * 25,
            }
        ),
    }

    signals = momentum.generate_signals(
        test_data, datetime(2024, 1, 25), ["000001.SZ", "000002.SZ", "000003.SZ"]
    )
    print(f"\nMomentum strategy selected: {[s.ts_code for s in signals]}")

    # Test MeanReversionStrategy
    reversion = MeanReversionStrategy(lookback_period=20, top_n=5)
    signals2 = reversion.generate_signals(
        test_data, datetime(2024, 1, 25), ["000001.SZ", "000002.SZ", "000003.SZ"]
    )
    print(f"Mean reversion selected: {[s.ts_code for s in signals2]}")

    # Test DualMomentumStrategy
    dual = DualMomentumStrategy(lookback_period=20, top_n=5)
    signals3 = dual.generate_signals(
        test_data, datetime(2024, 1, 25), ["000001.SZ", "000002.SZ", "000003.SZ"]
    )
    print(f"Dual momentum selected: {[s.ts_code for s in signals3]}")

    # Test strategy factory
    print("\nStrategy factory test:")
    factory_strategy = create_strategy("momentum", lookback_period=10, top_n=3)
    print(f"Factory created strategy: {factory_strategy.get_name()}")

    # Test invalid strategy type
    try:
        create_strategy("invalid_strategy")
    except ValueError as e:
        print(f"Expected error: {e}")
