"""数据加载工具"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import pickle
import logging

from projects.quant_trading.backtest.metrics import MetricsCalculator

logger = logging.getLogger(__name__)


class DataLoader:
    """数据加载器 - 加载回测结果数据"""

    def __init__(self, results_dir: Optional[str] = None):
        """
        初始化数据加载器

        Args:
            results_dir: 回测结果保存目录
        """
        self.results_dir = Path(results_dir) if results_dir else None

    def load_backtest_results(self, results_path: str) -> Optional[Dict[str, Any]]:
        """
        从文件加载回测结果

        Args:
            results_path: 结果文件路径（pickle格式）

        Returns:
            回测结果字典
        """
        try:
            path = Path(results_path)
            if not path.exists():
                logger.warning(f"Results file not found: {results_path}")
                return None

            with open(path, "rb") as f:
                results = pickle.load(f)

            logger.info(f"Loaded backtest results from {results_path}")
            return results

        except Exception as e:
            logger.error(f"Failed to load backtest results: {e}")
            return None

    def save_backtest_results(self, results: Dict[str, Any], output_path: str):
        """
        保存回测结果到文件

        Args:
            results: 回测结果字典
            output_path: 输出文件路径
        """
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "wb") as f:
                pickle.dump(results, f)

            logger.info(f"Saved backtest results to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save backtest results: {e}")

    @staticmethod
    def generate_mock_backtest_results(
        start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, seed: int = 42
    ) -> Dict[str, Any]:
        """
        生成模拟回测结果数据（用于测试和演示）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            seed: 随机种子

        Returns:
            模拟回测结果字典
        """
        np.random.seed(seed)

        if start_date is None:
            start_date = datetime(2020, 1, 1)
        if end_date is None:
            end_date = datetime(2024, 12, 31)

        # 生成交易日
        dates = pd.date_range(start=start_date, end=end_date, freq="B")

        # 生成策略净值（带趋势和波动）
        returns = np.random.normal(0.0003, 0.015, len(dates))
        # 添加一些趋势
        trend = np.linspace(0, 0.3, len(dates))
        returns = returns + trend * 0.0001

        nav = (1 + returns).cumprod()
        nav_history = list(zip(dates, nav))

        # 生成基准净值
        bench_returns = np.random.normal(0.0002, 0.012, len(dates))
        bench_trend = np.linspace(0, 0.2, len(dates))
        bench_returns = bench_returns + bench_trend * 0.00005
        bench_nav = (1 + bench_returns).cumprod()
        benchmark_nav = list(zip(dates, bench_nav))

        # 生成交易记录
        trades_data = []
        trade_dates = dates[::7]  # 每周一次交易

        for i, trade_date in enumerate(trade_dates[:50]):
            side = "buy" if i % 2 == 0 else "sell"
            ts_code = np.random.choice(["600519.SH", "000858.SZ", "000333.SZ", "000002.SZ"])
            price = np.random.uniform(50, 200)
            quantity = np.random.randint(100, 1000) // 100 * 100
            amount = price * quantity
            commission = amount * 0.00015
            slip_cost = amount * 0.0002

            trades_data.append(
                {
                    "date": trade_date,
                    "ts_code": ts_code,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "amount": amount,
                    "commission": commission,
                    "slip_cost": slip_cost,
                    "total_cost": commission + slip_cost,
                }
            )

        trades_df = pd.DataFrame(trades_data)

        # 计算绩效指标
        calculator = MetricsCalculator()
        metrics = calculator.calculate(nav_history, benchmark_nav, trades_df)

        # 生成持仓历史
        positions_data = []
        for i, d in enumerate(dates):
            total_value = 1000000 * nav[i]
            positions_value = total_value * np.random.uniform(0.5, 0.9)
            cash = total_value - positions_value

            positions_data.append(
                {
                    "date": d,
                    "cash": cash,
                    "positions_value": positions_value,
                    "total_value": total_value,
                    "position_count": np.random.randint(3, 11),
                }
            )

        positions_df = pd.DataFrame(positions_data)
        positions_df.set_index("date", inplace=True)

        return {
            "nav_history": nav_history,
            "benchmark_nav": benchmark_nav,
            "trades": trades_df,
            "positions": positions_df,
            "metrics": metrics,
            "summary": {
                "initial_cash": 1000000,
                "final_value": 1000000 * nav[-1],
                "total_return": nav[-1] - 1,
                "total_trades": len(trades_df),
            },
            "config": {
                "start_date": start_date,
                "end_date": end_date,
                "initial_cash": 1000000,
            },
        }

    @staticmethod
    def get_available_strategies() -> List[Dict[str, str]]:
        """
        获取可用策略列表

        Returns:
            策略列表，每项包含id和name
        """
        return [
            {"id": "ma_trend", "name": "MA趋势策略"},
            {"id": "mean_reversion", "name": "均值回归策略"},
            {"id": "ml_prediction", "name": "ML预测策略"},
            {"id": "statistical_arbitrage", "name": "统计套利策略"},
            {"id": "leading_stock", "name": "龙头股策略"},
        ]
