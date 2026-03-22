"""
多股票回测引擎 - 支持横截面ML策略的回测

功能：
- 定期调仓（日频/周频/月频）
- 横截面预测选股
- 组合权重优化
- 交易成本模拟
- 详细绩效归因
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from pathlib import Path
import logging

import numpy as np
import pandas as pd

from core.logger import get_logger
from projects.quant_trading.backtest.data_manager import DataManager
from projects.quant_trading.backtest.portfolio import Portfolio, Order, OrderSide
from projects.quant_trading.backtest.metrics import MetricsCalculator, PerformanceMetrics
from projects.quant_trading.backtest.risk_manager import RiskManager, RiskConfig
from projects.quant_trading.backtest.stock_filter import StockFilter, FilterPresets

logger = get_logger(__name__)


class RebalanceFrequency(Enum):
    """调仓频率"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


@dataclass
class MultiStockBacktestConfig:
    """多股票回测配置"""

    # 基础配置
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1_000_000.0

    # 训练期配置（严格区分训练/测试，避免前视偏差）
    train_start_date: Optional[datetime] = None  # 训练开始日期
    train_end_date: Optional[datetime] = None    # 训练结束日期（测试期必须在此之后）
    enable_retraining: bool = False              # 是否在回测期间重训练（样本外测试时应为False）

    # 调仓配置
    rebalance_freq: RebalanceFrequency = RebalanceFrequency.WEEKLY
    rebalance_day: int = 1  # 周频：周一(1)；月频：月初(1)

    # 持仓配置
    max_positions: int = 30  # 最大持仓数
    min_positions: int = 5  # 最小持仓数
    position_size_method: str = "equal"  # equal, score_weighted, risk_parity

    # 交易成本
    commission_rate: float = 0.00025  # 佣金万2.5
    min_commission: float = 5.0  # 最低佣金5元
    slippage_rate: float = 0.0002  # 滑点万2
    stamp_tax_rate: float = 0.001  # 印花税千1（卖出）

    # 风控配置
    enable_risk_control: bool = True
    risk_config: RiskConfig = field(default_factory=RiskConfig)

    # 基准
    benchmark: str = "000300.SH"  # 沪深300

    # 数据配置
    lookback_days: int = 60  # 数据回看天数

    # 预测配置
    prediction_horizon: int = 5  # 预测周期
    min_prediction_confidence: float = 0.1

    def __post_init__(self):
        """验证配置"""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.max_positions < self.min_positions:
            raise ValueError("max_positions must be >= min_positions")
        
        # 验证训练期配置
        if self.train_start_date and self.train_end_date:
            if self.train_start_date >= self.train_end_date:
                raise ValueError("train_start_date must be before train_end_date")
            if self.start_date < self.train_end_date:
                logger.warning(
                    f"Test start_date ({self.start_date.date()}) is before train_end_date "
                    f"({self.train_end_date.date()}). This may cause look-ahead bias."
                )


@dataclass
class BacktestResult:
    """回测结果"""

    config: MultiStockBacktestConfig
    portfolio: Portfolio
    metrics: PerformanceMetrics
    nav_history: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame
    daily_returns: pd.DataFrame
    benchmark_returns: Optional[pd.DataFrame] = None
    predictions: Optional[pd.DataFrame] = None
    position_count_history: Optional[pd.DataFrame] = None  # 持仓数量历史
    regime_history: Optional[pd.DataFrame] = None  # 市场状态历史

    def summary(self) -> Dict[str, Any]:
        """生成摘要"""
        return {
            "total_return": self.metrics.total_return,
            "annual_return": self.metrics.annual_return,
            "sharpe_ratio": self.metrics.sharpe_ratio,
            "max_drawdown": self.metrics.max_drawdown,
            "information_ratio": self.metrics.information_ratio,
            "win_rate": self.metrics.win_rate,
            "total_trades": self.metrics.total_trades,
            "final_value": self.portfolio.total_value,
        }

    def save(self, output_dir: str) -> None:
        """保存结果"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 保存净值历史
        self.nav_history.to_csv(output_path / "nav_history.csv")

        # 保存交易记录
        if not self.trades.empty:
            self.trades.to_csv(output_path / "trades.csv", index=False)

        # 保存持仓记录
        if not self.positions.empty:
            self.positions.to_csv(output_path / "positions.csv")

        # 保存日收益
        self.daily_returns.to_csv(output_path / "daily_returns.csv")

        # 保存预测（如有）
        if self.predictions is not None and not self.predictions.empty:
            self.predictions.to_csv(output_path / "predictions.csv", index=False)

        # 保存持仓数量历史
        if self.position_count_history is not None and not self.position_count_history.empty:
            self.position_count_history.to_csv(output_path / "position_count.csv")

        # 保存regime历史
        if self.regime_history is not None and not self.regime_history.empty:
            self.regime_history.to_csv(output_path / "regime_history.csv", index=False)

        # 保存绩效指标
        metrics_dict = self.metrics.to_dict()
        pd.Series(metrics_dict).to_csv(output_path / "metrics.csv")

        # 保存配置
        config_dict = {
            "start_date": self.config.start_date.strftime("%Y-%m-%d"),
            "end_date": self.config.end_date.strftime("%Y-%m-%d"),
            "train_start_date": self.config.train_start_date.strftime("%Y-%m-%d") if self.config.train_start_date else None,
            "train_end_date": self.config.train_end_date.strftime("%Y-%m-%d") if self.config.train_end_date else None,
            "initial_capital": self.config.initial_capital,
            "max_positions": self.config.max_positions,
            "rebalance_freq": self.config.rebalance_freq.value,
        }
        pd.Series(config_dict).to_csv(output_path / "config.csv")

        logger.info(f"Results saved to {output_dir}")


class MultiStockBacktestEngine:
    """
    多股票回测引擎

    支持横截面ML策略的完整回测流程
    """

    def __init__(
        self,
        config: MultiStockBacktestConfig,
        strategy: Any,  # CrossSectionalMLStrategy or similar
        data_manager: Optional[DataManager] = None,
        stock_filter: Optional[StockFilter] = None,
    ):
        self.config = config
        self.strategy = strategy
        self.data_manager = data_manager or DataManager()
        self.stock_filter = stock_filter or StockFilter(self.data_manager)

        # 初始化组合
        self.portfolio = Portfolio(
            initial_cash=config.initial_capital,
            commission_rate=config.commission_rate,
            slip_rate=config.slippage_rate,
        )

        # 初始化风控
        self.risk_manager = None
        if config.enable_risk_control:
            self.risk_manager = RiskManager(config.risk_config)

        # 状态跟踪
        self.nav_history: List[Tuple[datetime, float]] = []
        self.positions_history: List[Dict[str, Any]] = []
        self.predictions_history: List[Dict[str, Any]] = []
        self.position_count_history: List[Dict[str, Any]] = []  # 持仓数量历史
        self.regime_history: List[Dict[str, Any]] = []  # 市场状态历史

        # 交易日历
        self.trade_dates: List[datetime] = []

    def run(self, progress_callback: Optional[Callable] = None) -> BacktestResult:
        """
        执行回测

        Args:
            progress_callback: 进度回调函数 (current, total, date, nav)

        Returns:
            回测结果
        """
        logger.info("=" * 60)
        logger.info("Starting Multi-Stock Backtest")
        logger.info("=" * 60)

        # 1. 获取交易日历
        self.trade_dates = self._get_trade_dates()
        if not self.trade_dates:
            raise ValueError("No trade dates found")

        logger.info(f"Trade dates: {self.trade_dates[0].date()} to {self.trade_dates[-1].date()}")
        logger.info(f"Total days: {len(self.trade_dates)}")

        # 2. 加载基准数据
        benchmark_data = self._load_benchmark_data()

        # 3. 训练策略模型（使用配置的训练期，严格区分训练/测试）
        if self.config.train_start_date and self.config.train_end_date:
            # 使用指定的训练期
            train_start = self.config.train_start_date
            train_end = self.config.train_end_date
            logger.info(f"Using configured training period: {train_start.date()} to {train_end.date()}")
        else:
            # 回退到默认：回测开始前2年
            train_end = self.trade_dates[0] - timedelta(days=1)
            train_start = train_end - timedelta(days=365 * 2)
            logger.info(f"Using default training period: {train_start.date()} to {train_end.date()}")

        try:
            logger.info("Training strategy models...")
            self.strategy.train(train_start, train_end)
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise

        # 4. 回测主循环
        for i, date in enumerate(self.trade_dates):
            self._on_day_start(date)

            # 检查是否需要调仓
            if self._should_rebalance(date, i):
                logger.info(f"\nRebalancing on {date.strftime('%Y-%m-%d')}")
                self._rebalance(date)

            # 更新组合市值
            self._update_portfolio_value(date)

            # 风控检查
            if self.risk_manager:
                self._risk_check(date)

            # 记录状态
            self._record_state(date)

            self._on_day_end(date)

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(self.trade_dates), date, self.portfolio.nav)

            # 定期重训练（仅在启用重训练时，且使用训练期内数据）
            if self.config.enable_retraining and self._should_retrain(date):
                try:
                    logger.info(f"Retraining models on {date.strftime('%Y-%m-%d')}")
                    if self.config.train_start_date and self.config.train_end_date:
                        # 使用滚动窗口：训练结束日期 = 当前日期，训练开始日期 = 训练结束日期 - 2年
                        new_train_end = date
                        new_train_start = max(new_train_end - timedelta(days=365 * 2), self.config.train_start_date)
                    else:
                        new_train_end = date
                        new_train_start = new_train_end - timedelta(days=365 * 2)
                    self.strategy.train(new_train_start, new_train_end)
                except Exception as e:
                    logger.warning(f"Model retraining failed: {e}")

        # 5. 计算绩效
        result = self._calculate_results(benchmark_data)

        logger.info("=" * 60)
        logger.info("Backtest Completed")
        logger.info(f"Final NAV: {self.portfolio.nav:.4f}")
        logger.info(f"Total Return: {result.metrics.total_return*100:.2f}%")
        logger.info(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max Drawdown: {result.metrics.max_drawdown*100:.2f}%")
        logger.info("=" * 60)

        return result

    def _get_trade_dates(self) -> List[datetime]:
        """获取交易日历"""
        try:
            dates = self.data_manager.get_trade_dates(
                self.config.start_date, self.config.end_date
            )
            return dates
        except Exception as e:
            logger.error(f"Failed to get trade dates: {e}")
            return []

    def _load_benchmark_data(self) -> Optional[pd.DataFrame]:
        """加载基准数据"""
        try:
            df = self.data_manager.get_index_data(
                self.config.benchmark,
                self.config.start_date - timedelta(days=30),
                self.config.end_date,
            )
            return df
        except Exception as e:
            logger.warning(f"Failed to load benchmark data: {e}")
            return None

    def _should_rebalance(self, date: datetime, day_index: int) -> bool:
        """判断是否需要调仓"""
        freq = self.config.rebalance_freq

        if freq == RebalanceFrequency.DAILY:
            return True

        elif freq == RebalanceFrequency.WEEKLY:
            # 每周指定日期（周一=1）
            if day_index == 0:
                return True
            prev_date = self.trade_dates[day_index - 1]
            return date.isocalendar()[1] != prev_date.isocalendar()[1]

        elif freq == RebalanceFrequency.MONTHLY:
            # 每月第一天
            if day_index == 0:
                return True
            prev_date = self.trade_dates[day_index - 1]
            return date.month != prev_date.month

        elif freq == RebalanceFrequency.QUARTERLY:
            # 每季度第一天
            if day_index == 0:
                return True
            prev_date = self.trade_dates[day_index - 1]
            return date.month // 3 != prev_date.month // 3

        return False

    def _rebalance(self, date: datetime) -> None:
        """执行调仓"""
        # 1. 获取预测
        try:
            predictions = self.strategy.predict(date)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return

        if predictions.empty:
            logger.warning(f"No predictions on {date}")
            return

        # 2. 选股
        selected_stocks = predictions.head(self.config.max_positions)["ts_code"].tolist()

        if len(selected_stocks) < self.config.min_positions:
            logger.warning(f"Insufficient stocks selected: {len(selected_stocks)}")
            return

        # 3. 获取当前价格
        current_prices = self._get_current_prices(date, selected_stocks)

        if len(current_prices) < len(selected_stocks) * 0.8:
            logger.warning(f"Insufficient price data for rebalancing")
            return

        # 4. 生成目标权重
        target_weights = self.strategy.generate_portfolio_weights(
            date, selected_stocks, method=self.config.position_size_method
        )

        # 5. 执行调仓
        trades = self.portfolio.rebalance(
            target_weights=target_weights,
            current_prices=current_prices,
            date=date,
            min_weight_diff=0.01,  # 最小权重差异1%
        )

        logger.info(f"Executed {len(trades)} trades")

        # 6. 记录预测和regime
        current_regime = predictions.iloc[0].get("regime", "unknown") if not predictions.empty else "unknown"
        for _, row in predictions.head(self.config.max_positions).iterrows():
            self.predictions_history.append({
                "date": date,
                "ts_code": row["ts_code"],
                "predicted_return": row["predicted_return"],
                "confidence": row.get("confidence", 0),
                "selected": row["ts_code"] in selected_stocks,
                "regime": row.get("regime", current_regime),
            })
        
        # 记录regime历史
        self.regime_history.append({
            "date": date,
            "regime": current_regime,
            "num_selected": len(selected_stocks),
        })

    def _get_current_prices(
        self, date: datetime, stock_pool: List[str]
    ) -> Dict[str, float]:
        """获取当前价格"""
        prices = {}

        try:
            market_data = self.data_manager.get_market_data_for_date(
                date, ["ts_code", "close"]
            )

            if market_data.empty:
                return prices

            for ts_code in stock_pool:
                row = market_data[market_data["ts_code"] == ts_code]
                if not row.empty:
                    prices[ts_code] = float(row["close"].values[0])

        except Exception as e:
            logger.error(f"Failed to get current prices: {e}")

        return prices

    def _update_portfolio_value(self, date: datetime) -> None:
        """更新组合市值"""
        if not self.portfolio.positions:
            return

        # 获取持仓价格
        prices = self._get_current_prices(date, list(self.portfolio.positions.keys()))

        if prices:
            self.portfolio.update_market_value(prices)

    def _risk_check(self, date: datetime) -> None:
        """风控检查"""
        if not self.risk_manager:
            return

        # 更新风控数据
        self.risk_manager.update_portfolio_value(date, self.portfolio.total_value)

        # 检查是否需要清仓
        if self.risk_manager.should_clear_position():
            logger.warning(f"Risk limit triggered on {date}, closing all positions")

            prices = self._get_current_prices(
                date, list(self.portfolio.positions.keys())
            )
            self.portfolio.close_all_positions(prices, date)

    def _record_state(self, date: datetime) -> None:
        """记录状态"""
        # 记录净值
        self.nav_history.append((date, self.portfolio.nav))

        # 记录持仓
        num_positions = len(self.portfolio.positions)
        for ts_code, position in self.portfolio.positions.items():
            self.positions_history.append({
                "date": date,
                "ts_code": ts_code,
                "quantity": position.quantity,
                "avg_cost": position.avg_cost,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pnl,
            })
        
        # 记录持仓数量
        self.position_count_history.append({
            "date": date,
            "num_positions": num_positions,
            "total_value": self.portfolio.total_value,
            "cash": self.portfolio.cash,
        })

    def _calculate_results(self, benchmark_data: Optional[pd.DataFrame]) -> BacktestResult:
        """计算回测结果"""
        # 构建净值历史DataFrame
        nav_df = pd.DataFrame(self.nav_history, columns=["date", "nav"])
        nav_df.set_index("date", inplace=True)

        # 计算日收益率
        daily_returns = nav_df["nav"].pct_change().dropna()

        # 计算基准收益
        benchmark_returns = None
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_data["date"] = pd.to_datetime(benchmark_data.index)
            benchmark_data = benchmark_data.set_index("date")
            benchmark_nav = (
                benchmark_data["close"] / benchmark_data["close"].iloc[0]
            )
            benchmark_returns = benchmark_nav.pct_change().dropna()

        # 计算绩效指标
        calculator = MetricsCalculator()

        metrics = calculator.calculate(
            nav_history=self.nav_history,
            benchmark_nav=list(
                zip(benchmark_data.index, benchmark_data["close"])
            )
            if benchmark_data is not None
            else None,
            trades_df=self.portfolio.get_trades_df(),
        )

        # 构建预测DataFrame
        predictions_df = pd.DataFrame(self.predictions_history)
        
        # 构建持仓数量历史DataFrame
        position_count_df = pd.DataFrame(self.position_count_history)
        if not position_count_df.empty:
            position_count_df.set_index("date", inplace=True)
        
        # 构建regime历史DataFrame
        regime_df = pd.DataFrame(self.regime_history)
        if not regime_df.empty:
            regime_df.set_index("date", inplace=True)

        return BacktestResult(
            config=self.config,
            portfolio=self.portfolio,
            metrics=metrics,
            nav_history=nav_df,
            trades=self.portfolio.get_trades_df(),
            positions=pd.DataFrame(self.positions_history),
            daily_returns=daily_returns,
            benchmark_returns=benchmark_returns,
            predictions=predictions_df if not predictions_df.empty else None,
            position_count_history=position_count_df if not position_count_df.empty else None,
            regime_history=regime_df if not regime_df.empty else None,
        )

    def _should_retrain(self, date: datetime) -> bool:
        """判断是否需要重训练"""
        return self.strategy.should_retrain(date)

    def _on_day_start(self, date: datetime) -> None:
        """每日开始处理"""
        pass

    def _on_day_end(self, date: datetime) -> None:
        """每日结束处理"""
        pass
