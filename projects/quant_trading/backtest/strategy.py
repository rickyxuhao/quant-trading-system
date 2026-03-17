"""
回测框架 - 策略基类与信号定义

定义策略接口、信号类型和权重分配器。
所有自定义策略必须继承 BaseStrategy 类。

Example:
    >>> class MyStrategy(BaseStrategy):
    ...     def generate_signals(self, data, current_date, available_stocks):
    ...         return [Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, weight=0.2)]
    >>>
    >>> strategy = MyStrategy()
    >>> signals = strategy.generate_signals(data, date, stocks)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

__all__ = [
    "SignalType",
    "Signal",
    "BaseStrategy",
    "BuyAndHoldStrategy",
    "equal_weight_allocator",
    "score_weight_allocator",
]


class SignalType(Enum):
    """交易信号类型"""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """交易信号

    Attributes:
        ts_code: 股票代码
        signal_type: 信号类型（买入/卖出/持有）
        weight: 目标权重（0-1之间）
        score: 信号得分（用于排序）
        reason: 信号原因说明
        timestamp: 信号时间
        meta: 额外元数据
    """

    ts_code: str
    signal_type: SignalType
    weight: float = 0.0
    score: float = 0.0
    reason: str = ""
    timestamp: Optional[datetime] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """验证信号数据"""
        if not self.ts_code:
            raise ValueError("ts_code cannot be empty")
        if not 0 <= self.weight <= 1:
            logger.warning(f"Signal weight {self.weight} not in [0, 1], will be clamped")
            self.weight = max(0.0, min(1.0, self.weight))


class BaseStrategy(ABC):
    """策略基类

    所有自定义策略必须继承此类，并实现 generate_signals 方法。

    Example:
        >>> class MyStrategy(BaseStrategy):
        ...     def __init__(self, param1: int = 10) -> None:
        ...         super().__init__("MyStrategy")
        ...         self.param1 = param1
        ...
        ...     def generate_signals(self, data, current_date, available_stocks):
        ...         return [Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, weight=0.2)]
    """

    def __init__(self, name: str = "BaseStrategy") -> None:
        """初始化策略

        Args:
            name: 策略名称

        Raises:
            ValueError: 当策略名称为空时
        """
        if not name:
            raise ValueError("Strategy name cannot be empty")
        self.name = name
        self.params: Dict[str, Any] = {}
        self.is_initialized = False
        logger.info(f"Strategy {name} created")

    @abstractmethod
    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成交易信号

        子类必须实现此方法，返回目标持仓的股票信号列表。

        Args:
            data: 历史数据字典 {ts_code: DataFrame}
            current_date: 当前日期
            available_stocks: 当日可交易股票列表

        Returns:
            交易信号列表

        Raises:
            NotImplementedError: 当子类未实现此方法时
        """
        raise NotImplementedError("Subclasses must implement generate_signals()")

    def initialize(self, **kwargs: Any) -> None:
        """策略初始化

        子类可重写此方法进行策略初始化（如加载模型、预热缓存等）。

        Args:
            **kwargs: 初始化参数
        """
        self.is_initialized = True
        logger.info(f"Strategy {self.name} initialized")

    def on_backtest_start(self, start_date: datetime, end_date: datetime) -> None:
        """回测开始时的回调

        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
        """
        logger.info(
            f"Backtest started: {start_date.strftime('%Y%m%d')} ~ {end_date.strftime('%Y%m%d')}"
        )

    def on_backtest_end(self) -> None:
        """回测结束时的回调"""
        logger.info(f"Strategy {self.name} backtest ended")

    def on_before_trade(self, current_date: datetime) -> None:
        """每日交易前的回调

        Args:
            current_date: 当前日期
        """

    def on_after_trade(self, current_date: datetime, executed_signals: List[Signal]) -> None:
        """每日交易后的回调

        Args:
            current_date: 当前日期
            executed_signals: 已执行的交易信号
        """

    def get_name(self) -> str:
        """获取策略名称

        Returns:
            策略名称
        """
        return self.name

    def get_description(self) -> str:
        """获取策略描述

        Returns:
            策略描述字符串
        """
        return f"{self.name} - {self.__class__.__doc__ or 'No description'}"

    def set_param(self, key: str, value: Any) -> None:
        """设置策略参数

        Args:
            key: 参数名
            value: 参数值
        """
        self.params[key] = value
        logger.debug(f"Set param {key} = {value}")

    def get_param(self, key: str, default: Optional[Any] = None) -> Any:
        """获取策略参数

        Args:
            key: 参数名
            default: 默认值

        Returns:
            参数值，如果不存在则返回默认值
        """
        return self.params.get(key, default)

    def validate_data(self, data: Dict[str, "pd.DataFrame"]) -> bool:
        """验证数据有效性

        Args:
            data: 数据字典

        Returns:
            数据是否有效
        """
        if not data:
            logger.warning("Data is empty")
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """将策略转换为字典

        Returns:
            策略配置字典
        """
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "params": self.params.copy(),
            "is_initialized": self.is_initialized,
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<{self.__class__.__name__}(name='{self.name}')>"


class BuyAndHoldStrategy(BaseStrategy):
    """买入持有策略

    在回测开始时买入指定股票，然后持有到期。
    作为基准策略使用。

    Example:
        >>> strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ", "000002.SZ"])
        >>> signals = strategy.generate_signals(data, date, available_stocks)
    """

    def __init__(self, target_stocks: Optional[List[str]] = None) -> None:
        """初始化买入持有策略

        Args:
            target_stocks: 目标股票列表，如果为None则买入所有可用股票
        """
        super().__init__("BuyAndHold")
        self.target_stocks = target_stocks
        self._has_initialized = False

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str],
    ) -> List[Signal]:
        """生成交易信号 - 只执行一次买入

        Args:
            data: 历史数据字典
            current_date: 当前日期
            available_stocks: 当日可交易股票列表

        Returns:
            交易信号列表（仅首次调用返回信号）
        """
        if self._has_initialized:
            return []

        self._has_initialized = True

        stocks = self.target_stocks if self.target_stocks else available_stocks[:10]
        signals: List[Signal] = []

        for ts_code in stocks:
            if ts_code in available_stocks:
                signals.append(
                    Signal(
                        ts_code=ts_code,
                        signal_type=SignalType.BUY,
                        weight=1.0 / len(stocks),
                        reason="Buy and hold strategy",
                    )
                )

        logger.info(f"Buy and hold strategy selected {len(signals)} stocks")
        return signals

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = super().to_dict()
        result["target_stocks"] = self.target_stocks
        return result


def equal_weight_allocator(signals: List[Signal]) -> List[Signal]:
    """等权重分配器

    将选中的股票按等权重分配。

    Args:
        signals: 信号列表

    Returns:
        分配权重后的信号列表

    Example:
        >>> signals = [Signal(ts_code="000001.SZ", signal_type=SignalType.BUY)]
        >>> weighted = equal_weight_allocator(signals)
        >>> print(weighted[0].weight)
        1.0
    """
    if not signals:
        return []

    weight = 1.0 / len(signals)
    for signal in signals:
        signal.weight = weight

    return signals


def score_weight_allocator(signals: List[Signal], max_weight: float = 0.3) -> List[Signal]:
    """按得分权重分配器

    根据信号得分进行权重分配，得分越高权重越大。

    Args:
        signals: 信号列表
        max_weight: 单只股票最大权重

    Returns:
        分配权重后的信号列表

    Raises:
        ValueError: 当 max_weight 无效时
    """
    if not signals:
        return []

    if max_weight <= 0 or max_weight > 1:
        raise ValueError(f"max_weight must be in (0, 1], got {max_weight}")

    total_score = sum(abs(s.score) for s in signals)
    if total_score == 0:
        return equal_weight_allocator(signals)

    for signal in signals:
        weight = abs(signal.score) / total_score
        signal.weight = min(weight, max_weight)

    # 重新归一化
    total_weight = sum(s.weight for s in signals)
    if total_weight > 0:
        for signal in signals:
            signal.weight /= total_weight

    return signals


def _setup_test_logging() -> None:
    """设置测试日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


if __name__ == "__main__":
    _setup_test_logging()

    # Test base class
    class TestStrategy(BaseStrategy):
        def __init__(self) -> None:
            super().__init__("Test")

        def generate_signals(
            self,
            data: Dict[str, "pd.DataFrame"],
            current_date: datetime,
            available_stocks: List[str],
        ) -> List[Signal]:
            return [Signal(ts_code=s, signal_type=SignalType.BUY) for s in available_stocks[:5]]

    strategy = TestStrategy()
    print(f"Strategy name: {strategy.get_name()}")
    print(f"Strategy description: {strategy.get_description()}")
    print(f"Strategy dict: {strategy.to_dict()}")

    # Test buy and hold strategy
    bh_strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ", "000002.SZ"])
    print(f"\nBuy and hold strategy: {bh_strategy.get_name()}")
    print(f"Target stocks: {bh_strategy.target_stocks}")

    # Test allocators
    test_signals = [
        Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, score=0.8),
        Signal(ts_code="000002.SZ", signal_type=SignalType.BUY, score=0.5),
    ]

    equal_weight_allocator(test_signals)
    print(f"\nEqual weights: {[s.weight for s in test_signals]}")

    test_signals[0].weight = 0
    test_signals[1].weight = 0
    score_weight_allocator(test_signals)
    print(f"Score weights: {[s.weight for s in test_signals]}")
