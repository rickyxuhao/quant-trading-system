"""
回测流程集成测试
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.engine import (
    BacktestEngine, BacktestConfig, BacktestEvent, BacktestError
)
from projects.quant_trading.backtest.strategy import BaseStrategy, Signal, SignalType


class SimpleTestStrategy(BaseStrategy):
    """简单测试策略"""

    def __init__(self, signal_stocks=None):
        super().__init__("SimpleTestStrategy")
        self.signal_stocks = signal_stocks or ["000001.SZ", "000002.SZ"]

    def generate_signals(self, data, current_date, available_stocks):
        signals = []
        for ts_code in self.signal_stocks:
            if ts_code in available_stocks:
                signals.append(Signal(
                    ts_code=ts_code,
                    signal_type=SignalType.BUY,
                    weight=1.0 / len(self.signal_stocks),
                    reason="Test signal"
                ))
        return signals


@pytest.mark.integration
class TestFullBacktestWorkflow:
    """测试完整回测流程"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_full_backtest_execution(self, mock_dm_class):
        """测试完整回测执行"""
        # 设置mock数据管理器
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        # 模拟交易日
        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 32, 2)  # 约15个交易日
        ]

        # 模拟股票列表
        mock_dm.get_all_stocks.return_value = [
            "000001.SZ", "000002.SZ", "600000.SH", "600519.SH"
        ]

        # 模拟股票数据
        dates = pd.date_range("2023-01-01", periods=30, freq="B")
        base_price = 100.0
        price_data = []
        for i, date in enumerate(dates):
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": base_price * (1 + i * 0.001),
                "high": base_price * (1 + i * 0.001 + 0.01),
                "low": base_price * (1 + i * 0.001 - 0.01),
                "close": base_price * (1 + i * 0.001),
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        # 创建配置和策略
        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 31),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=2,
            rebalance_freq="weekly"
        )

        strategy = SimpleTestStrategy()

        # 创建引擎并运行
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)
        results = engine.run()

        # 验证结果
        assert "nav_history" in results
        assert "metrics" in results
        assert "trades" in results
        assert results["config"]["strategy"] == "SimpleTestStrategy"

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_backtest_with_risk_management(self, mock_dm_class):
        """测试带风控的回测"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 20, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ", "000002.SZ"]

        # 创建有回撤的数据
        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        price_data = []
        for i, date in enumerate(dates):
            if i < 5:
                close = 100.0 * (1 + i * 0.02)  # 上涨
            else:
                close = 110.0 * (1 - (i - 4) * 0.05)  # 大幅下跌
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.98,
                "close": close,
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 31),
            initial_cash=100000.0,
            enable_risk_control=True,
            max_positions=5,
            min_positions=1
        )

        from projects.quant_trading.backtest.risk_manager import RiskConfig
        risk_config = RiskConfig(max_drawdown_limit=0.15)

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        results = engine.run()

        # 验证有风控警报
        assert "risk_alerts" in results

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_backtest_events_triggered(self, mock_dm_class):
        """测试回测事件触发"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 10, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        dates = pd.date_range("2023-01-01", periods=5, freq="B")
        price_data = []
        for i, date in enumerate(dates):
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 10),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 监听事件
        events_triggered = []

        def event_handler(event, date, data):
            events_triggered.append((event, date))

        engine.register_event_handler(BacktestEvent.BACKTEST_START, event_handler)
        engine.register_event_handler(BacktestEvent.BACKTEST_END, event_handler)
        engine.register_event_handler(BacktestEvent.REBALANCE_START, event_handler)

        engine.run()

        # 验证事件被触发
        event_types = [e[0] for e in events_triggered]
        assert BacktestEvent.BACKTEST_START in event_types
        assert BacktestEvent.BACKTEST_END in event_types

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_progress_callback(self, mock_dm_class):
        """测试进度回调"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 15, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        price_data = []
        for i, date in enumerate(dates):
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 15),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        progress_calls = []

        def progress_callback(current, total, date, nav):
            progress_calls.append((current, total, nav))

        engine.set_progress_callback(progress_callback)
        engine.run()

        # 验证进度回调被调用
        assert len(progress_calls) > 0


@pytest.mark.integration
class TestBacktestResults:
    """测试回测结果"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_results_structure(self, mock_dm_class):
        """测试结果结构"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 20, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ", "000002.SZ"]
        mock_dm.get_index_data.return_value = pd.DataFrame({
            "trade_date": pd.date_range("2023-01-01", periods=10),
            "close": [4000.0 + i * 10 for i in range(10)]
        })

        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        price_data = []
        for i, date in enumerate(dates):
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.0 + i,
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 20),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)
        results = engine.run()

        # 验证结果结构
        required_keys = [
            "nav_history", "trades", "positions", "summary",
            "metrics", "risk_alerts", "stats", "config"
        ]
        for key in required_keys:
            assert key in results, f"Missing key: {key}"

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_metrics_calculation(self, mock_dm_class):
        """测试绩效指标计算"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d"))
            for i in range(3, 32, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 创建有正收益的数据
        dates = pd.date_range("2023-01-01", periods=15, freq="B")
        price_data = []
        base_price = 100.0
        for i, date in enumerate(dates):
            close = base_price * (1 + i * 0.005)  # 稳定上涨
            price_data.append({
                "trade_date": date.strftime("%Y%m%d"),
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.98,
                "close": close,
                "vol": 100000,
            })

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 31),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)
        results = engine.run()

        metrics = results["metrics"]

        # 验证关键指标
        assert hasattr(metrics, "total_return")
        assert hasattr(metrics, "sharpe_ratio")
        assert hasattr(metrics, "max_drawdown")
        assert metrics.total_trades >= 0


@pytest.mark.integration
class TestBacktestErrors:
    """测试回测错误处理"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_no_trade_dates(self, mock_dm_class):
        """测试无交易日"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm
        mock_dm.get_trade_dates.return_value = []

        config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            initial_cash=100000.0
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        with pytest.raises(BacktestError, match="没有有效的交易日"):
            engine.run()

    def test_already_running(self):
        """测试重复运行"""
        config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            initial_cash=100000.0
        )

        strategy = SimpleTestStrategy()

        # 使用mock避免实际运行
        with patch.object(BacktestEngine, "run") as mock_run:
            engine = BacktestEngine(config, strategy)
            engine.is_running = True

            with pytest.raises(BacktestError, match="already running"):
                engine.run()

    def test_invalid_config(self):
        """测试无效配置"""
        with pytest.raises(ValueError, match="start_date must be before"):
            BacktestConfig(
                start_date=datetime(2023, 12, 31),
                end_date=datetime(2023, 1, 1),
                initial_cash=100000.0
            )

    def test_invalid_initial_cash(self):
        """测试无效初始资金"""
        with pytest.raises(ValueError, match="initial_cash must be positive"):
            BacktestConfig(
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_cash=0
            )
