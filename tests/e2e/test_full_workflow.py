"""
完整工作流端到端测试
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.engine import BacktestEngine, BacktestConfig
from projects.quant_trading.backtest.strategy import BaseStrategy, Signal, SignalType


class MAStrategy(BaseStrategy):
    """简单均线策略（用于测试）"""

    def __init__(self, ma_short=5, ma_long=20):
        super().__init__("MAStrategy")
        self.ma_short = ma_short
        self.ma_long = ma_long

    def generate_signals(self, data, current_date, available_stocks):
        signals = []

        for ts_code in available_stocks[:10]:  # 限制股票数量
            if ts_code not in data:
                continue

            df = data[ts_code]
            if len(df) < self.ma_long:
                continue

            # 计算均线
            ma_short_val = df["close"].iloc[-self.ma_short :].mean()
            ma_long_val = df["close"].iloc[-self.ma_long :].mean()

            if ma_short_val > ma_long_val:
                signals.append(
                    Signal(
                        ts_code=ts_code,
                        signal_type=SignalType.BUY,
                        weight=0.1,
                        reason=f"MA{self.ma_short} > MA{self.ma_long}",
                    )
                )

        return signals


@pytest.mark.e2e
class TestFullWorkflow:
    """测试完整工作流"""

    @patch("projects.quant_trading.backtest.engine.DataManager")
    @patch("projects.quant_trading.backtest.engine.StockFilter")
    def test_data_to_backtest_workflow(self, mock_filter_class, mock_dm_class):
        """测试数据获取到回测完整流程"""
        # 设置mock数据管理器
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        # 模拟交易日
        trade_dates = []
        for i in range(3, 100):
            try:
                date = datetime(2023, 1, i)
                if date.weekday() < 5:
                    trade_dates.append(date.strftime("%Y%m%d"))
            except:
                break

        mock_dm.get_trade_dates.return_value = trade_dates[:50]  # 限制为50个交易日

        # 模拟股票列表
        mock_dm.get_all_stocks.return_value = [
            "000001.SZ",
            "000002.SZ",
            "600000.SH",
            "600519.SH",
            "000858.SZ",
        ]

        # 模拟股票数据 - 带均线交叉的模式
        def mock_get_stock_data(ts_code, start, end):
            days = 60
            dates = pd.date_range(start=start, periods=days, freq="B")

            # 创建有趋势的数据
            base_price = 100.0
            prices = []
            for i in range(days):
                if i < 30:
                    trend = i * 0.002  # 上涨趋势
                else:
                    trend = 30 * 0.002 - (i - 30) * 0.001  # 趋平

                price = base_price * (1 + trend + np.random.randn() * 0.01)
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
                        "open": price * 0.99,
                        "high": price * 1.02,
                        "low": price * 0.98,
                        "close": price,
                        "vol": np.random.randint(100000, 1000000),
                    }
                )

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            return df

        mock_dm.get_stock_data.side_effect = mock_get_stock_data

        # 设置mock筛选器
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.filter_stocks.return_value = ["000001.SZ", "000002.SZ", "600000.SH"]

        # 1. 创建策略
        strategy = MAStrategy(ma_short=5, ma_long=20)

        # 2. 创建回测配置
        config = BacktestConfig(
            start_date=datetime(2023, 1, 3),
            end_date=datetime(2023, 3, 31),
            initial_cash=200000.0,
            max_positions=10,
            min_positions=3,
            rebalance_freq="weekly",
            enable_risk_control=True,
        )

        # 3. 创建回测引擎
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        # 4. 运行回测
        results = engine.run()

        # 5. 验证结果
        assert "nav_history" in results
        assert "trades" in results
        assert "metrics" in results

        # 验证净值历史
        assert len(results["nav_history"]) > 0

        # 验证绩效指标
        metrics = results["metrics"]
        assert hasattr(metrics, "total_return")
        assert hasattr(metrics, "sharpe_ratio")
        assert hasattr(metrics, "max_drawdown")

        print(f"\n回测结果:")
        print(f"  总收益率: {metrics.total_return*100:.2f}%")
        print(f"  夏普比率: {metrics.sharpe_ratio:.2f}")
        print(f"  最大回撤: {metrics.max_drawdown*100:.2f}%")

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_multi_strategy_comparison(self, mock_dm_class):
        """测试多策略对比"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        # 模拟数据
        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 50, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ", "000002.SZ"]

        def mock_get_stock_data(ts_code, start, end):
            days = 30
            dates = pd.date_range(start=start, periods=days, freq="B")
            prices = []
            for i in range(days):
                price = 100.0 + i * 0.1 + np.random.randn() * 0.5
                prices.append(
                    {
                        "trade_date": dates[i].strftime("%Y%m%d"),
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

        # 测试多个策略
        strategies = [
            ("MA5_10", MAStrategy(ma_short=5, ma_long=10)),
            ("MA10_20", MAStrategy(ma_short=10, ma_long=20)),
        ]

        results_summary = []

        for name, strategy in strategies:
            config = BacktestConfig(
                start_date=datetime(2023, 1, 3),
                end_date=datetime(2023, 2, 28),
                initial_cash=100000.0,
                max_positions=5,
                min_positions=1,
            )

            engine = BacktestEngine(config, strategy, data_manager=mock_dm)
            results = engine.run()
            metrics = results["metrics"]

            results_summary.append(
                {
                    "strategy": name,
                    "total_return": metrics.total_return,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "max_drawdown": metrics.max_drawdown,
                }
            )

        # 验证至少有一个策略有结果
        assert len(results_summary) == 2

        for result in results_summary:
            print(f"\n策略: {result['strategy']}")
            print(f"  总收益率: {result['total_return']*100:.2f}%")
            print(f"  夏普比率: {result['sharpe_ratio']:.2f}")

    @patch("projects.quant_trading.backtest.engine.DataManager")
    def test_backtest_with_persistence(self, mock_dm_class, tmp_path):
        """测试回测结果持久化"""
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm

        mock_dm.get_trade_dates.return_value = [
            (datetime(2023, 1, i).strftime("%Y%m%d")) for i in range(3, 20, 2)
        ]
        mock_dm.get_all_stocks.return_value = ["000001.SZ"]

        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        price_data = []
        for i, date in enumerate(dates):
            price_data.append(
                {
                    "trade_date": date.strftime("%Y%m%d"),
                    "open": 100.0 + i,
                    "high": 101.0 + i,
                    "low": 99.0 + i,
                    "close": 100.0 + i,
                    "vol": 100000,
                }
            )

        df = pd.DataFrame(price_data)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mock_dm.get_stock_data.return_value = df

        config = BacktestConfig(
            start_date=datetime(2023, 1, 3), end_date=datetime(2023, 1, 20), initial_cash=100000.0
        )

        strategy = MAStrategy()
        engine = BacktestEngine(config, strategy, data_manager=mock_dm)

        engine.run()

        # 保存结果
        output_dir = tmp_path / "backtest_results"
        engine.save_results(str(output_dir))

        # 验证文件被创建
        assert (output_dir / "nav_history.csv").exists()
        assert (output_dir / "trades.csv").exists()
        assert (output_dir / "metrics.csv").exists()

        # 验证可以读取
        nav_df = pd.read_csv(output_dir / "nav_history.csv")
        assert len(nav_df) > 0
