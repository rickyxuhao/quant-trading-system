"""
策略基类单元测试
"""

import pytest
from datetime import datetime

import pandas as pd

from projects.quant_trading.backtest.strategy import (
    BaseStrategy,
    Signal,
    SignalType,
    BuyAndHoldStrategy,
    equal_weight_allocator,
    score_weight_allocator,
)


class TestSignal:
    """测试Signal数据类"""

    def test_signal_creation(self):
        """测试信号创建"""
        signal = Signal(
            ts_code="000001.SZ",
            signal_type=SignalType.BUY,
            weight=0.2,
            score=0.8,
            reason="Test signal",
        )

        assert signal.ts_code == "000001.SZ"
        assert signal.signal_type == SignalType.BUY
        assert signal.weight == 0.2
        assert signal.score == 0.8

    def test_signal_weight_clamping(self):
        """测试权重限制在[0,1]范围内"""
        signal = Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, weight=1.5)  # 超出范围

        assert signal.weight == 1.0

        signal = Signal(ts_code="000002.SZ", signal_type=SignalType.BUY, weight=-0.5)  # 负数

        assert signal.weight == 0.0

    def test_signal_empty_ts_code(self):
        """测试空股票代码"""
        with pytest.raises(ValueError, match="cannot be empty"):
            Signal(ts_code="", signal_type=SignalType.BUY)


class TestBaseStrategy:
    """测试策略基类"""

    class ConcreteStrategy(BaseStrategy):
        """具体策略实现（用于测试）"""

        def generate_signals(self, data, current_date, available_stocks):
            return [
                Signal(ts_code=stock, signal_type=SignalType.BUY, weight=0.2)
                for stock in available_stocks[:5]
            ]

    def test_strategy_init(self):
        """测试策略初始化"""
        strategy = self.ConcreteStrategy(name="TestStrategy")

        assert strategy.name == "TestStrategy"
        assert strategy.is_initialized is False
        assert strategy.params == {}

    def test_empty_name_raises_error(self):
        """测试空名称抛出错误"""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.ConcreteStrategy(name="")

    def test_initialize(self):
        """测试策略初始化方法"""
        strategy = self.ConcreteStrategy()
        strategy.initialize(param1=10, param2="test")

        assert strategy.is_initialized is True

    def test_set_get_param(self):
        """测试参数设置和获取"""
        strategy = self.ConcreteStrategy()

        strategy.set_param("ma_short", 5)
        strategy.set_param("ma_long", 20)

        assert strategy.get_param("ma_short") == 5
        assert strategy.get_param("ma_long") == 20
        assert strategy.get_param("nonexistent") is None
        assert strategy.get_param("nonexistent", "default") == "default"

    def test_get_name(self):
        """测试获取策略名称"""
        strategy = self.ConcreteStrategy(name="MyStrategy")
        assert strategy.get_name() == "MyStrategy"

    def test_get_description(self):
        """测试获取策略描述"""
        strategy = self.ConcreteStrategy(name="TestStrategy")
        desc = strategy.get_description()

        assert "TestStrategy" in desc

    def test_to_dict(self):
        """测试转换为字典"""
        strategy = self.ConcreteStrategy(name="TestStrategy")
        strategy.set_param("param1", 10)
        strategy.initialize()

        data = strategy.to_dict()

        assert data["name"] == "TestStrategy"
        assert data["class"] == "ConcreteStrategy"
        assert data["is_initialized"] is True
        assert data["params"]["param1"] == 10

    def test_validate_data_empty(self):
        """测试空数据验证"""
        strategy = self.ConcreteStrategy()
        result = strategy.validate_data({})

        assert result is False

    def test_validate_data_valid(self):
        """测试有效数据验证"""
        strategy = self.ConcreteStrategy()
        data = {"000001.SZ": pd.DataFrame(), "000002.SZ": pd.DataFrame()}
        result = strategy.validate_data(data)

        assert result is True

    def test_generate_signals_abstract(self):
        """测试抽象方法必须实现"""

        class IncompleteStrategy(BaseStrategy):
            pass

        with pytest.raises(TypeError, match="abstract"):
            IncompleteStrategy()

    def test_on_backtest_start(self):
        """测试回测开始回调"""
        strategy = self.ConcreteStrategy()
        strategy.on_backtest_start(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 12, 31))
        # 方法应该正常执行不报错

    def test_on_backtest_end(self):
        """测试回测结束回调"""
        strategy = self.ConcreteStrategy()
        strategy.on_backtest_end()
        # 方法应该正常执行不报错

    def test_on_before_trade(self):
        """测试交易前回调"""
        strategy = self.ConcreteStrategy()
        strategy.on_before_trade(datetime(2023, 1, 5))
        # 方法应该正常执行不报错

    def test_on_after_trade(self):
        """测试交易后回调"""
        strategy = self.ConcreteStrategy()
        signals = [Signal(ts_code="000001.SZ", signal_type=SignalType.BUY)]
        strategy.on_after_trade(datetime(2023, 1, 5), signals)
        # 方法应该正常执行不报错


class TestBuyAndHoldStrategy:
    """测试买入持有策略"""

    def test_init_with_target_stocks(self):
        """测试指定目标股票初始化"""
        strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ", "000002.SZ"])

        assert strategy.target_stocks == ["000001.SZ", "000002.SZ"]

    def test_generate_signals_first_call(self):
        """测试首次调用生成信号"""
        strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ", "000002.SZ"])

        data = {"000001.SZ": pd.DataFrame(), "000002.SZ": pd.DataFrame()}
        available_stocks = ["000001.SZ", "000002.SZ", "600000.SH"]

        signals = strategy.generate_signals(
            data=data, current_date=datetime(2023, 1, 5), available_stocks=available_stocks
        )

        assert len(signals) == 2
        assert all(s.signal_type == SignalType.BUY for s in signals)
        assert all(s.weight == 0.5 for s in signals)

    def test_generate_signals_subsequent_calls(self):
        """测试后续调用不生成信号"""
        strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ"])

        data = {"000001.SZ": pd.DataFrame()}
        available_stocks = ["000001.SZ"]

        # 第一次调用
        signals1 = strategy.generate_signals(data, datetime(2023, 1, 5), available_stocks)
        assert len(signals1) == 1

        # 第二次调用（应该返回空列表）
        signals2 = strategy.generate_signals(data, datetime(2023, 1, 6), available_stocks)
        assert len(signals2) == 0

    def test_generate_signals_filter_unavailable(self):
        """测试过滤不可用的股票"""
        strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ", "999999.SZ"])

        data = {"000001.SZ": pd.DataFrame()}
        available_stocks = ["000001.SZ"]  # 999999.SZ 不可用

        signals = strategy.generate_signals(
            data=data, current_date=datetime(2023, 1, 5), available_stocks=available_stocks
        )

        assert len(signals) == 1
        assert signals[0].ts_code == "000001.SZ"

    def test_generate_signals_no_target(self):
        """测试无目标股票时使用前10只"""
        strategy = BuyAndHoldStrategy(target_stocks=None)

        data = {f"{i:06d}.SZ": pd.DataFrame() for i in range(1, 20)}
        available_stocks = list(data.keys())

        signals = strategy.generate_signals(
            data=data, current_date=datetime(2023, 1, 5), available_stocks=available_stocks
        )

        assert len(signals) == 10
        assert all(s.weight == 0.1 for s in signals)

    def test_to_dict(self):
        """测试转换为字典"""
        strategy = BuyAndHoldStrategy(target_stocks=["000001.SZ"])

        data = strategy.to_dict()

        assert data["target_stocks"] == ["000001.SZ"]
        assert data["name"] == "BuyAndHold"


class TestWeightAllocators:
    """测试权重分配器"""

    def test_equal_weight_allocator(self):
        """测试等权重分配"""
        signals = [
            Signal(ts_code="000001.SZ", signal_type=SignalType.BUY),
            Signal(ts_code="000002.SZ", signal_type=SignalType.BUY),
            Signal(ts_code="600000.SH", signal_type=SignalType.BUY),
        ]

        result = equal_weight_allocator(signals)

        assert len(result) == 3
        assert all(s.weight == pytest.approx(1 / 3, 0.001) for s in result)

    def test_equal_weight_allocator_empty(self):
        """测试空信号列表"""
        result = equal_weight_allocator([])
        assert result == []

    def test_score_weight_allocator(self):
        """测试按得分权重分配"""
        signals = [
            Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, score=0.8),
            Signal(ts_code="000002.SZ", signal_type=SignalType.BUY, score=0.2),
        ]

        result = score_weight_allocator(signals)

        assert len(result) == 2
        # 权重与得分成正比，但会被max_weight=0.3限制，然后重新归一化
        # 初始权重: 0.8/(0.8+0.2)=0.8, 0.2/(0.8+0.2)=0.2
        # 限制后: min(0.8, 0.3)=0.3, min(0.2, 0.3)=0.2
        # 归一化: 0.3/0.5=0.6, 0.2/0.5=0.4
        assert result[0].weight == pytest.approx(0.6, 0.01)
        assert result[1].weight == pytest.approx(0.4, 0.01)

    def test_score_weight_allocator_with_max_weight(self):
        """测试带最大权重限制的得分分配"""
        signals = [
            Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, score=0.9),
            Signal(ts_code="000002.SZ", signal_type=SignalType.BUY, score=0.1),
        ]

        result = score_weight_allocator(signals, max_weight=0.5)

        # 初始权重: 0.9/(0.9+0.1)=0.9, 0.1/(0.9+0.1)=0.1
        # 限制后: min(0.9, 0.5)=0.5, min(0.1, 0.5)=0.1
        # 归一化: 0.5/0.6=0.833, 0.1/0.6=0.167
        assert result[0].weight == pytest.approx(0.833, 0.01)
        assert result[1].weight == pytest.approx(0.167, 0.01)

    def test_score_weight_allocator_zero_scores(self):
        """测试所有信号得分为0时回退到等权"""
        signals = [
            Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, score=0),
            Signal(ts_code="000002.SZ", signal_type=SignalType.BUY, score=0),
        ]

        result = score_weight_allocator(signals)

        assert all(s.weight == 0.5 for s in result)

    def test_score_weight_allocator_empty(self):
        """测试空信号列表"""
        result = score_weight_allocator([])
        assert result == []

    def test_score_weight_allocator_invalid_max_weight(self):
        """测试无效最大权重"""
        signals = [Signal(ts_code="000001.SZ", signal_type=SignalType.BUY, score=0.5)]

        with pytest.raises(ValueError, match="max_weight must be in"):
            score_weight_allocator(signals, max_weight=1.5)

        with pytest.raises(ValueError, match="max_weight must be in"):
            score_weight_allocator(signals, max_weight=0)
