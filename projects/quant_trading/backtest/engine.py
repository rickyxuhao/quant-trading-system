"""
回测框架 - 回测引擎核心
协调数据、筛选、策略、账户管理，执行回测流程
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum, auto
from pathlib import Path
import logging
import sys

import pandas as pd

# Setup logging
logger = logging.getLogger(__name__)

# Handle imports with proper error handling
try:
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from projects.quant_trading.backtest.data_manager import DataManager, MissingDataError
    from projects.quant_trading.backtest.stock_filter import (
        StockFilter,
        FilterPresets,
    )
    from projects.quant_trading.backtest.portfolio import (
        Portfolio,
        TransactionCost,
    )
    from projects.quant_trading.backtest.strategy import BaseStrategy
    from projects.quant_trading.backtest.risk_manager import RiskManager, RiskConfig
    from projects.quant_trading.backtest.metrics import MetricsCalculator
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    raise


class RebalanceFrequency(Enum):
    """调仓频率"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class BacktestEvent(Enum):
    """回测事件类型"""

    BACKTEST_START = auto()
    BACKTEST_END = auto()
    DAY_START = auto()
    DAY_END = auto()
    REBALANCE_START = auto()
    REBALANCE_END = auto()
    RISK_TRIGGERED = auto()
    DATA_MISSING = auto()
    ERROR = auto()


class BacktestError(Exception):
    """回测引擎异常"""



@dataclass
class BacktestConfig:
    """回测配置"""

    start_date: datetime
    end_date: datetime
    initial_cash: float = 200000.0  # 初始资金20万
    max_positions: int = 10  # 最大持仓10只
    min_positions: int = 3  # 最小持仓3只
    rebalance_freq: str = "weekly"  # 调仓频率: daily/weekly/monthly
    commission_rate: float = 0.00015  # 手续费万1.5
    slippage_rate: float = 0.0002  # 滑点万2
    benchmark: str = "000300.SH"  # 沪深300基准
    enable_risk_control: bool = True  # 启用风控
    risk_config: Optional[RiskConfig] = None  # 风控配置
    max_lookback_days: int = 60  # 最大回看天数
    data_preload: bool = True  # 是否预加载数据
    parallel_loading: bool = False  # 是否并行加载数据
    log_level: str = "INFO"  # 日志级别

    def __post_init__(self) -> None:
        """验证配置"""
        if self.start_date >= self.end_date:
            raise ValueError(f"start_date must be before end_date")
        if self.initial_cash <= 0:
            raise ValueError(f"initial_cash must be positive")
        if self.max_positions < self.min_positions:
            raise ValueError(f"max_positions must be >= min_positions")
        if self.commission_rate < 0 or self.slippage_rate < 0:
            raise ValueError(f"commission_rate and slippage_rate must be non-negative")

    @property
    def rebalance_frequency(self) -> RebalanceFrequency:
        """获取调仓频率枚举"""
        try:
            return RebalanceFrequency(self.rebalance_freq.lower())
        except ValueError:
            logger.warning(
                f"Unknown rebalance frequency: {self.rebalance_freq}, defaulting to WEEKLY"
            )
            return RebalanceFrequency.WEEKLY


@dataclass
class BacktestStats:
    """回测统计信息"""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_days: int = 0
    rebalance_count: int = 0
    trade_count: int = 0
    error_count: int = 0
    data_requests: int = 0
    cache_hits: int = 0

    @property
    def duration_seconds(self) -> float:
        """回测持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "duration_seconds": self.duration_seconds,
            "total_days": self.total_days,
            "rebalance_count": self.rebalance_count,
            "trade_count": self.trade_count,
            "error_count": self.error_count,
            "data_requests": self.data_requests,
            "cache_hits": self.cache_hits,
        }


# Type aliases
EventHandler = Callable[[BacktestEvent, datetime, Optional[Any]], None]
ProgressCallback = Callable[[int, int, datetime, float], None]  # (current, total, date, nav)


class BacktestEngine:
    """
    回测引擎

    协调数据获取、前置筛选、策略执行、账户管理和绩效计算
    """

    def __init__(
        self,
        config: BacktestConfig,
        strategy: BaseStrategy,
        data_manager: Optional[DataManager] = None,
        stock_filter: Optional[StockFilter] = None,
        risk_manager: Optional[RiskManager] = None,
        event_handlers: Optional[Dict[BacktestEvent, List[EventHandler]]] = None,
    ):
        """
        初始化回测引擎

        Args:
            config: 回测配置
            strategy: 策略实例
            data_manager: 数据管理器实例（可选）
            stock_filter: 股票筛选器实例（可选）
            risk_manager: 风控管理器实例（可选）
            event_handlers: 事件处理器字典（可选）
        """
        # Validate inputs
        if not isinstance(config, BacktestConfig):
            raise TypeError(f"config must be BacktestConfig, got {type(config)}")
        if strategy is None:
            raise ValueError("strategy cannot be None")

        self.config = config
        self.strategy = strategy
        self.stats = BacktestStats()

        # Setup logging
        self._setup_logging(config.log_level)

        # Initialize components
        self.data_manager = data_manager or DataManager()
        self.stock_filter = stock_filter or StockFilter(self.data_manager)

        # Initialize portfolio
        tx_cost = TransactionCost(
            commission_rate=config.commission_rate, slip_rate=config.slippage_rate
        )
        self.portfolio = Portfolio(
            initial_cash=config.initial_cash,
            commission_rate=config.commission_rate,
            slip_rate=config.slippage_rate,
        )

        # Initialize risk manager
        if config.enable_risk_control:
            if risk_manager:
                self.risk_manager = risk_manager
            elif config.risk_config:
                self.risk_manager = RiskManager(config.risk_config)
            else:
                self.risk_manager = RiskManager()
        else:
            self.risk_manager = None

        # Event handling
        self._event_handlers: Dict[BacktestEvent, List[EventHandler]] = event_handlers or {}
        self._progress_callback: Optional[ProgressCallback] = None

        # State
        self.current_date: Optional[datetime] = None
        self.trade_dates: List[datetime] = []
        self.is_running = False
        self._stopped = False

        # Data cache
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._benchmark_data: Optional[pd.DataFrame] = None
        self._preloaded_data: Dict[str, pd.DataFrame] = {}

        # Results
        self._results: Optional[Dict[str, Any]] = None

        logger.info(
            f"BacktestEngine initialized: {config.start_date.date()} ~ {config.end_date.date()}"
        )

    def _setup_logging(self, log_level: str) -> None:
        """设置日志级别"""
        level = getattr(logging, log_level.upper(), logging.INFO)
        logging.getLogger("backtest").setLevel(level)
        logger.setLevel(level)

    def register_event_handler(self, event: BacktestEvent, handler: EventHandler) -> None:
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        logger.debug(f"Registered handler for event: {event.name}")

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """设置进度回调函数"""
        self._progress_callback = callback

    def _emit_event(
        self, event: BacktestEvent, date: Optional[datetime] = None, data: Optional[Any] = None
    ) -> None:
        """触发事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(event, date or datetime.now(), data)
            except Exception as e:
                logger.error(f"Event handler error for {event.name}: {e}")

    def stop(self) -> None:
        """停止回测"""
        self._stopped = True
        logger.info("Backtest stop requested")

    def run(self) -> Dict[str, Any]:
        """
        执行回测

        Returns:
            回测结果字典

        Raises:
            BacktestError: 当回测执行失败时
        """
        if self.is_running:
            raise BacktestError("Backtest is already running")

        self._stopped = False
        self.is_running = True
        self.stats.start_time = datetime.now()

        try:
            logger.info("=" * 60)
            logger.info("开始回测")
            logger.info("=" * 60)

            # 1. 获取交易日历
            self.trade_dates = self._get_trade_dates()
            if not self.trade_dates:
                raise BacktestError("没有有效的交易日")

            self.stats.total_days = len(self.trade_dates)

            logger.info(
                f"回测区间: {self.trade_dates[0].strftime('%Y%m%d')} ~ {self.trade_dates[-1].strftime('%Y%m%d')}"
            )
            logger.info(f"交易日数量: {len(self.trade_dates)}")
            logger.info(f"初始资金: ¥{self.config.initial_cash:,.2f}")
            logger.info(f"策略: {self.strategy.get_name()}")
            logger.info("-" * 60)

            # 2. 预加载基准数据
            self._load_benchmark_data()

            # 3. 预加载股票数据（如果启用）
            if self.config.data_preload:
                self._preload_stock_data()

            # 4. 触发开始事件
            self._emit_event(BacktestEvent.BACKTEST_START, self.trade_dates[0])

            # 5. 策略初始化
            self.strategy.on_backtest_start(self.trade_dates[0], self.trade_dates[-1])

            # 6. 回测主循环
            for i, date in enumerate(self.trade_dates):
                if self._stopped:
                    logger.info("Backtest stopped by user")
                    break

                self.current_date = date

                # 进度报告
                self._report_progress(i, date)

                # 执行当日回测
                try:
                    self._on_day_start(date)

                    # 判断是否需要调仓
                    if self._should_rebalance(date, i):
                        self.stats.rebalance_count += 1
                        self._emit_event(BacktestEvent.REBALANCE_START, date)
                        self._rebalance(date)
                        self._emit_event(BacktestEvent.REBALANCE_END, date)

                    # 更新持仓市值
                    self._update_portfolio_value(date)

                    # 风控检查
                    if self.risk_manager:
                        self._risk_check(date)

                    # 记录净值
                    self.portfolio.record_state(date)

                    self._on_day_end(date)

                except Exception as e:
                    self.stats.error_count += 1
                    logger.error(f"Error on {date.strftime('%Y%m%d')}: {e}")
                    self._emit_event(BacktestEvent.ERROR, date, {"error": str(e)})
                    if self.stats.error_count > 10:
                        raise BacktestError(f"Too many errors ({self.stats.error_count}), aborting")

            # 7. 回测结束
            self.is_running = False
            self.stats.end_time = datetime.now()
            self.stats.trade_count = len(self.portfolio.trades)

            logger.info("-" * 60)
            logger.info("回测完成")
            logger.info(f"耗时: {self.stats.duration_seconds:.2f}秒")
            logger.info(f"总交易次数: {self.stats.trade_count}")

            # 8. 策略结束回调
            self.strategy.on_backtest_end()
            self._emit_event(BacktestEvent.BACKTEST_END, self.trade_dates[-1])

            # 9. 返回结果
            self._results = self._get_results()
            return self._results

        except Exception as e:
            self.is_running = False
            self.stats.end_time = datetime.now()
            logger.error(f"Backtest failed: {e}")
            raise BacktestError(f"Backtest execution failed: {e}") from e

    def _report_progress(self, index: int, date: datetime) -> None:
        """报告进度"""
        # 打印进度（每20个交易日）
        if index % 20 == 0 or index == len(self.trade_dates) - 1:
            logger.info(
                f"[{index+1}/{len(self.trade_dates)}] {date.strftime('%Y%m%d')} - "
                f"净值: ¥{self.portfolio.total_value:,.2f}"
            )

        # 调用回调
        if self._progress_callback:
            try:
                self._progress_callback(index + 1, len(self.trade_dates), date, self.portfolio.nav)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def _get_trade_dates(self) -> List[datetime]:
        """获取交易日列表"""
        try:
            dates = self.data_manager.get_trade_dates(self.config.start_date, self.config.end_date)
            return [datetime.strptime(d, "%Y%m%d") for d in dates]
        except Exception as e:
            logger.error(f"Failed to get trade dates: {e}")
            raise BacktestError(f"Failed to get trade dates: {e}")

    def _load_benchmark_data(self) -> None:
        """加载基准数据"""
        try:
            start_str = self.config.start_date.strftime("%Y%m%d")
            end_str = self.config.end_date.strftime("%Y%m%d")

            self._benchmark_data = self.data_manager.get_index_data(
                self.config.benchmark, start_str, end_str
            )
            self.stats.data_requests += 1
            logger.info(f"[基准] 已加载 {self.config.benchmark}")
        except MissingDataError as e:
            logger.warning(f"[警告] 基准数据缺失: {e}")
            self._benchmark_data = None
        except Exception as e:
            logger.error(f"Failed to load benchmark data: {e}")
            self._benchmark_data = None

    def _preload_stock_data(self) -> None:
        """预加载股票数据"""
        logger.info("预加载股票数据...")
        # This can be implemented based on specific requirements
        # For now, we'll use lazy loading

    def _on_day_start(self, date: datetime) -> None:
        """每日开始时的处理"""
        self._emit_event(BacktestEvent.DAY_START, date)
        self.strategy.on_before_trade(date)

    def _on_day_end(self, date: datetime) -> None:
        """每日结束时的处理"""
        self._emit_event(BacktestEvent.DAY_END, date)

    def _should_rebalance(self, date: datetime, day_index: int) -> bool:
        """判断当日是否需要调仓"""
        freq = self.config.rebalance_frequency

        if freq == RebalanceFrequency.DAILY:
            return True
        elif freq == RebalanceFrequency.WEEKLY:
            if day_index == 0:
                return True
            prev_date = self.trade_dates[day_index - 1]
            return prev_date.isocalendar()[1] != date.isocalendar()[1]
        elif freq == RebalanceFrequency.MONTHLY:
            if day_index == 0:
                return True
            prev_date = self.trade_dates[day_index - 1]
            return prev_date.month != date.month
        else:
            return True

    def _rebalance(self, date: datetime) -> None:
        """执行调仓"""
        date_str = date.strftime("%Y%m%d")

        # 1. 前置筛选
        try:
            all_stocks = self.data_manager.get_all_stocks(date_str)
            self.stats.data_requests += 1
        except MissingDataError:
            logger.warning(f"[警告] {date_str} 无股票数据")
            self._emit_event(BacktestEvent.DATA_MISSING, date, {"reason": "no_stock_data"})
            return

        available_stocks = self.stock_filter.filter_stocks(
            date, all_stocks, FilterPresets.moderate()
        )

        if not available_stocks:
            logger.warning(f"[警告] {date_str} 无可交易股票")
            return

        # 2. 预加载策略所需的历史数据
        lookback_days = self.config.max_lookback_days
        start_idx = max(0, self.trade_dates.index(date) - lookback_days)
        data_start_date = self.trade_dates[start_idx]

        stock_data: Dict[str, pd.DataFrame] = {}
        current_prices: Dict[str, float] = {}

        # Load data for available stocks
        for ts_code in available_stocks[:100]:  # Limit to top 100 for performance
            try:
                df = self._get_stock_data(ts_code, data_start_date, date)
                if df is not None and not df.empty:
                    stock_data[ts_code] = df
                    price = self._extract_price(df, date)
                    if price is not None:
                        current_prices[ts_code] = price
            except Exception as e:
                logger.debug(f"Failed to load data for {ts_code}: {e}")
                continue

        if len(stock_data) < self.config.min_positions:
            logger.warning(
                f"[调仓] 可用股票数量 {len(stock_data)} 少于最小持仓 {self.config.min_positions}"
            )
            return

        # 3. 调用策略生成信号
        try:
            target_stocks = self.strategy.generate_signals(
                data=stock_data, current_date=date, available_stocks=list(stock_data.keys())
            )
        except Exception as e:
            logger.error(f"Strategy signal generation failed: {e}")
            return

        # 限制持仓数量
        target_stocks = target_stocks[: self.config.max_positions]

        if len(target_stocks) < self.config.min_positions:
            logger.warning(
                f"[调仓] 选股数量 {len(target_stocks)} 少于最小持仓 {self.config.min_positions}，跳过"
            )
            return

        # 4. 构建目标权重（等权）
        target_weights = {stock: 1.0 / len(target_stocks) for stock in target_stocks}

        # 5. 执行调仓
        trades = self.portfolio.rebalance(
            target_weights=target_weights, current_prices=current_prices, date=date
        )

        if trades:
            logger.info(f"[调仓] {date_str} 执行 {len(trades)} 笔交易")

    def _get_stock_data(
        self, ts_code: str, start_date: datetime, end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """获取股票数据（带缓存）"""
        cache_key = f"{ts_code}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        if cache_key in self._price_cache:
            self.stats.cache_hits += 1
            return self._price_cache[cache_key]

        try:
            df = self.data_manager.get_stock_data(ts_code, start_date, end_date)
            self.stats.data_requests += 1

            # Cache management - limit cache size
            if len(self._price_cache) > 1000:
                # Remove oldest 20% of entries
                keys_to_remove = list(self._price_cache.keys())[:200]
                for key in keys_to_remove:
                    del self._price_cache[key]

            self._price_cache[cache_key] = df
            return df
        except MissingDataError:
            return None
        except Exception as e:
            logger.debug(f"Error loading data for {ts_code}: {e}")
            return None

    def _extract_price(self, df: pd.DataFrame, date: datetime) -> Optional[float]:
        """从DataFrame中提取指定日期的价格"""
        try:
            date_str = date.strftime("%Y%m%d")
            row = df[df["trade_date"] == date]
            if not row.empty:
                return float(row["close"].values[0])

            # Try different date formats
            for col in ["trade_date", "date"]:
                if col in df.columns:
                    row = df[df[col] == date_str]
                    if not row.empty:
                        return float(row["close"].values[0])

            return None
        except Exception as e:
            logger.debug(f"Failed to extract price: {e}")
            return None

    def _update_portfolio_value(self, date: datetime) -> None:
        """更新持仓市值"""
        if not self.portfolio.positions:
            return

        prices: Dict[str, float] = {}
        for ts_code in list(self.portfolio.positions.keys()):
            try:
                df = self._get_stock_data(ts_code, date, date)
                if df is not None and not df.empty:
                    price = self._extract_price(df, date)
                    if price is not None:
                        prices[ts_code] = price
            except Exception as e:
                logger.debug(f"Failed to get price for {ts_code}: {e}")
                continue

        if prices:
            self.portfolio.update_market_value(prices)

        # 更新风控
        if self.risk_manager:
            try:
                self.risk_manager.update_portfolio_value(date, self.portfolio.total_value)
            except Exception as e:
                logger.warning(f"Risk manager update failed: {e}")

    def _risk_check(self, date: datetime) -> None:
        """风控检查"""
        if not self.risk_manager:
            return

        try:
            # 检查是否需要清仓
            if self.risk_manager.should_clear_position():
                logger.warning(f"[风控] {date.strftime('%Y%m%d')} 触发清仓线，清空所有持仓")
                self._emit_event(BacktestEvent.RISK_TRIGGERED, date, {"action": "clear_all"})

                # Get current prices for all positions
                prices: Dict[str, float] = {}
                for ts_code in list(self.portfolio.positions.keys()):
                    df = self._get_stock_data(ts_code, date, date)
                    if df is not None:
                        price = self._extract_price(df, date)
                        if price is not None:
                            prices[ts_code] = price

                self.portfolio.close_all_positions(prices, date)
                return

            # 检查个股止损
            positions_to_close: List[str] = []
            for ts_code, pos in self.portfolio.positions.items():
                if self.risk_manager.check_stop_loss(
                    date, ts_code, pos.current_price, pos.avg_cost
                ):
                    positions_to_close.append(ts_code)

            for ts_code in positions_to_close:
                logger.warning(f"[风控] {ts_code} 触发止损，平仓")
                df = self._get_stock_data(ts_code, date, date)
                if df is not None:
                    price = self._extract_price(df, date)
                    if price is not None:
                        self.portfolio.close_position(ts_code, price, date)

        except Exception as e:
            logger.error(f"Risk check failed: {e}")

    def _get_results(self) -> Dict[str, Any]:
        """获取回测结果"""
        # Calculate metrics
        calculator = MetricsCalculator()
        nav_history = self.portfolio.get_nav_history()

        benchmark_nav = None
        if self._benchmark_data is not None:
            try:
                benchmark_nav = list(
                    zip(
                        pd.to_datetime(self._benchmark_data["trade_date"]),
                        self._benchmark_data["close"].values,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to process benchmark data: {e}")

        trades_df = self.portfolio.get_trades_df()
        metrics = calculator.calculate(nav_history, benchmark_nav, trades_df)

        results = {
            "nav_history": nav_history,
            "trades": trades_df,
            "positions": self.portfolio.get_state_df(),
            "summary": self.portfolio.summary(),
            "metrics": metrics,
            "risk_alerts": (
                self.risk_manager.get_alerts_df() if self.risk_manager else pd.DataFrame()
            ),
            "stats": self.stats.to_dict(),
            "config": {
                "start_date": self.config.start_date,
                "end_date": self.config.end_date,
                "initial_cash": self.config.initial_cash,
                "strategy": self.strategy.get_name(),
            },
        }

        return results

    def save_results(self, output_dir: str) -> None:
        """
        保存回测结果

        Args:
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if self._results is None:
            self._results = self._get_results()

        results = self._results

        # 保存净值历史
        if results["nav_history"]:
            nav_df = pd.DataFrame(results["nav_history"], columns=["date", "nav"])
            nav_df.to_csv(output_path / "nav_history.csv", index=False)

        # 保存交易记录
        if not results["trades"].empty:
            results["trades"].to_csv(output_path / "trades.csv", index=False)

        # 保存持仓
        if not results["positions"].empty:
            results["positions"].to_csv(output_path / "positions.csv", index=False)

        # 保存风控警报
        if not results["risk_alerts"].empty:
            results["risk_alerts"].to_csv(output_path / "risk_alerts.csv", index=False)

        # 保存绩效指标
        if "metrics" in results and results["metrics"]:
            metrics_dict = results["metrics"].to_dict()
            pd.Series(metrics_dict).to_csv(output_path / "metrics.csv", header=["value"])

        # 保存统计信息
        pd.Series(results["stats"]).to_csv(output_path / "stats.csv", header=["value"])

        logger.info(f"[保存] 结果已保存到: {output_dir}")

    def get_results(self) -> Optional[Dict[str, Any]]:
        """获取回测结果（如果已完成）"""
        return self._results


if __name__ == "__main__":
    # Setup logging for testing
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Test backtest engine
    try:
        from projects.quant_trading.backtest.strategy import BuyAndHoldStrategy

        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_cash=200000,
            max_positions=5,
            rebalance_freq="weekly",
        )

        strategy = BuyAndHoldStrategy()
        engine = BacktestEngine(config, strategy)

        results = engine.run()
        print(f"\n回测结果摘要:")
        print(f"总收益率: {results['summary'].get('total_return', 0)*100:.2f}%")
        print(f"最终净值: {results['summary'].get('nav', 0):.4f}")

    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise
