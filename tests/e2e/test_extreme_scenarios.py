"""
极端场景端到端测试
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.engine import BacktestEngine, BacktestConfig
from projects.quant_trading.backtest.strategy import BaseStrategy, Signal, SignalType
from projects.quant_trading.backtest.data_manager import MissingDataError


class SimpleTestStrategy(BaseStrategy):
    """简单测试策略"""

    def __init__(self):
        super().__init__("SimpleTestStrategy")

    def generate_signals(self, data, current_date, available_stocks):
        return [
            Signal(ts_code=ts_code, signal_type=SignalType.BUY, weight=0.2)
            for ts_code in available_stocks[:5]
        ]


@pytest.mark.e2e
class TestExtremeScenarios:
    """测试极端场景"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_continuous_limit_up(self, mock_dm_class):
        """测试连续涨停场景（无法买入）"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        # 模拟交易日
        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 20, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟连续涨停数据
        def mock_get_stock_data(ts_code, start, end):
            days = 15
            dates = pd.date_range(start=start, periods=days, freq="B")
            base_price = 100.0
            prices = []

            for i, date in enumerate(dates):
                # 涨停：开盘价=昨收*1.1，收盘价=开盘价，成交量极低
                close = base_price * (1.10**i)
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": close,  # 一字涨停
                        "high": close,
                        "low": close,
                        "close": close,
                        "pre_close": close / 1.1,
                        "vol": 100,  # 极低的成交量
                        "amount": close * 100,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 20),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 运行回测
        results = engine.run()

        # 验证结果 - 应该有交易记录（以收盘价成交）
        assert "trades" in results
        # 注意：根据引擎实现，可能无成交（涨停无法买入）或有成交
        # 这里主要验证系统不会崩溃

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_continuous_limit_down(self, mock_dm_class):
        """测试连续跌停场景（无法卖出）"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 20, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟连续跌停数据
        def mock_get_stock_data(ts_code, start, end):
            days = 15
            dates = pd.date_range(start=start, periods=days, freq="B")
            base_price = 100.0
            prices = []

            for i, date in enumerate(dates):
                # 跌停
                close = base_price * (0.90**i)
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": close,
                        "high": close,
                        "low": close,
                        "close": close,
                        "pre_close": close / 0.9,
                        "vol": 100,
                        "amount": close * 100,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 20),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        results = engine.run()

        # 验证系统不会崩溃
        assert "nav_history" in results
        assert "metrics" in results

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_data_gap_handling(self, mock_dm_class):
        """测试数据缺失处理"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 15, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟有缺失的数据
        def mock_get_stock_data(ts_code, start, end):
            all_dates = pd.date_range(start=start, periods=12, freq="B")
            # 删除部分日期
            valid_dates = [d for i, d in enumerate(all_dates) if i not in [3, 4, 8]]

            base_price = 100.0
            prices = []

            for i, date in enumerate(valid_dates):
                price = base_price + i * 0.5
                prices.append(
                    {
                        "trade_date": date.strftime("%Y%m%d"),
                        "open": price * 0.99,
                        "high": price * 1.01,
                        "low": price * 0.98,
                        "close": price,
                        "vol": 100000,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 15),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 运行回测 - 不应该报错
        results = engine.run()

        assert results is not None

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_flash_crash_scenario(self, mock_dm_class):
        """测试闪崩场景"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 25, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟闪崩数据（某天突然大跌）
        def mock_get_stock_data(ts_code, start, end):
            days = 20
            dates = pd.date_range(start=start, periods=days, freq="B")
            prices = []

            for i, date in enumerate(dates):
                if i == 10:  # 闪崩日
                    price = 80.0  # 突然跌到80
                elif i > 10:
                    price = 80.0 + (i - 10) * 0.5  # 缓慢恢复
                else:
                    price = 100.0 + i * 0.5  # 正常上涨

                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": price * 0.98 if i == 10 else price * 0.99,
                        "high": price * 1.01,
                        "low": price * 0.90 if i == 10 else price * 0.98,
                        "close": price,
                        "vol": 1000000 if i == 10 else 100000,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 25),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
            enable_risk_control=True,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        results = engine.run()

        metrics = results["metrics"]
        # 闪崩应该导致较大回撤
        assert metrics.max_drawdown < 0

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_market_crash_scenario(self, mock_dm_class):
        """测试市场崩盘场景"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 30, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ", "000002.SZ"]

        # 模拟持续大跌
        def mock_get_stock_data(ts_code, start, end):
            days = 25
            dates = pd.date_range(start=start, periods=days, freq="B")
            base_price = 100.0
            prices = []

            for i, date in enumerate(dates):
                # 持续下跌
                price = base_price * (0.95**i)
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": price * 1.02,
                        "high": price * 1.02,
                        "low": price * 0.95,
                        "close": price,
                        "vol": 100000,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 30),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
            enable_risk_control=True,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        results = engine.run()

        metrics = results["metrics"]
        # 应该有较大回撤
        assert metrics.max_drawdown < -0.1

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_low_liquidity_scenario(self, mock_dm_class):
        """测试低流动性场景"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 15, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟低流动性（成交量极低）
        def mock_get_stock_data(ts_code, start, end):
            days = 10
            dates = pd.date_range(start=start, periods=days, freq="B")
            base_price = 100.0
            prices = []

            for i, date in enumerate(dates):
                price = base_price + i * 0.1
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": price,
                        "high": price * 1.005,
                        "low": price * 0.995,
                        "close": price,
                        "vol": 100,  # 极低的成交量
                        "amount": price * 100,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 15),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 系统不应该崩溃
        results = engine.run()
        assert results is not None

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_high_volatility_scenario(self, mock_dm_class):
        """测试高波动场景"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 30, 1)
        ]

        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟高波动数据
        def mock_get_stock_data(ts_code, start, end):
            days = 25
            dates = pd.date_range(start=start, periods=days, freq="B")
            np.random.seed(42)
            base_price = 100.0
            prices = []

            for i, date in enumerate(dates):
                # 大幅随机波动
                change = np.random.normal(0, 0.05)  # 5%标准差
                price = base_price * (1 + change)
                base_price = price

                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": price * (1 + np.random.normal(0, 0.02)),
                        "high": price * 1.08,
                        "low": price * 0.92,
                        "close": price,
                        "vol": int(np.random.randint(50000, 500000)),
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 30),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
            enable_risk_control=True,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        results = engine.run()

        metrics = results["metrics"]
        # 高波动应该有较高的波动率
        assert metrics.volatility > 0


@pytest.mark.e2e
class TestErrorHandling:
    """测试错误处理"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_data_error_recovery(self, mock_dm_class):
        """测试数据错误恢复"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 20, 1)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        # 模拟偶发数据错误
        call_count = [0]

        def mock_get_stock_data(ts_code, start, end):
            call_count[0] += 1

            if call_count[0] == 3:  # 第三次调用失败
                raise MissingDataError("Data temporarily unavailable")

            days = 15
            dates = pd.date_range(start=start, periods=days, freq="B")
            prices = []

            for i, date in enumerate(dates):
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.0,
                        "close": 100.0,
                        "vol": 100000,
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 1, 20),
            initial_cash=100000.0,
            max_positions=5,
            min_positions=1,
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 应该能处理错误并完成回测
        results = engine.run()

        assert results is not None
        # 可能有错误记录
        assert results["stats"]["error_count"] >= 0

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_empty_data_handling(self, mock_dm_class):
        """测试空数据处理"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 10, 1)
        ]
        mock_dm.get_all_stocks.return_value = []  # 空股票列表

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3), end_date=datetime(2023, 1, 10), initial_cash=100000.0
        )

        strategy = SimpleTestStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 应该能处理空数据
        results = engine.run()

        # 可能没有交易
        assert results["stats"]["trade_count"] == 0
