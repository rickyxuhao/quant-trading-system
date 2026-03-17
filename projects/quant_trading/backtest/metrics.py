"""
回测框架 - 绩效指标计算模块

计算各类回测绩效指标，包括收益指标、风险指标、风险调整收益指标、
交易指标以及相对基准指标。

Example:
    >>> from datetime import datetime
    >>> import pandas as pd
    >>> calculator = MetricsCalculator(risk_free_rate=0.03)
    >>> nav_history = [(datetime(2024, 1, i), 1.0 + i * 0.01) for i in range(1, 30)]
    >>> metrics = calculator.calculate(nav_history)
    >>> print(metrics.sharpe_ratio)
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

# Setup logging
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型枚举"""

    RETURN = "return"
    RISK = "risk"
    RISK_ADJUSTED = "risk_adjusted"
    TRADE = "trade"
    RELATIVE = "relative"


class MetricsError(Exception):
    """绩效指标计算异常"""


@dataclass
class PerformanceMetrics:
    """
    绩效指标数据类

    包含收益指标、风险指标、风险调整收益指标、交易指标和相对基准指标。
    所有指标以浮点数或整数形式存储，便于后续处理和格式化展示。

    Attributes:
        # 收益指标
        total_return: 总收益率（小数形式，如0.15表示15%）
        annual_return: 年化收益率
        cumulative_return: 累计收益金额

        # 风险指标
        max_drawdown: 最大回撤比例
        max_drawdown_duration: 最大回撤持续天数
        volatility: 年化波动率
        downside_volatility: 下行波动率（只计算负收益）
        var_95: 95%置信水平的VaR值
        cvar_95: 95%置信水平的CVaR（条件VaR）

        # 风险调整收益
        sharpe_ratio: 夏普比率
        sortino_ratio: 索提诺比率
        calmar_ratio: Calmar比率
        omega_ratio: Omega比率

        # 交易指标
        win_rate: 胜率（小数形式）
        profit_loss_ratio: 盈亏比
        total_trades: 总交易次数
        avg_trade_return: 平均交易收益
        max_consecutive_wins: 最大连续盈利次数
        max_consecutive_losses: 最大连续亏损次数

        # 相对基准
        alpha: Alpha值
        beta: Beta值
        information_ratio: 信息比率
        tracking_error: 跟踪误差
        excess_return: 超额收益
        up_capture: 上涨捕获率
        down_capture: 下跌捕获率
    """

    # 收益指标
    total_return: float = 0.0
    annual_return: float = 0.0
    cumulative_return: float = 0.0

    # 风险指标
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    volatility: float = 0.0
    downside_volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0

    # 风险调整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0

    # 交易指标
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # 相对基准
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    excess_return: float = 0.0
    up_capture: float = 0.0
    down_capture: float = 0.0

    def to_dict(self, format_output: bool = False) -> Dict[str, Union[str, float, int]]:
        """
        转换为字典

        Args:
            format_output: 是否将数值格式化为字符串（如百分比形式）

        Returns:
            包含所有指标的字典
        """
        data = {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "cumulative_return": self.cumulative_return,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": self.volatility,
            "downside_volatility": self.downside_volatility,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "omega_ratio": self.omega_ratio,
            "win_rate": self.win_rate,
            "profit_loss_ratio": self.profit_loss_ratio,
            "total_trades": self.total_trades,
            "avg_trade_return": self.avg_trade_return,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "alpha": self.alpha,
            "beta": self.beta,
            "information_ratio": self.information_ratio,
            "tracking_error": self.tracking_error,
            "excess_return": self.excess_return,
            "up_capture": self.up_capture,
            "down_capture": self.down_capture,
        }

        if format_output:
            formatted = {}
            for key, value in data.items():
                if isinstance(value, float):
                    if key in [
                        "total_return",
                        "annual_return",
                        "cumulative_return",
                        "max_drawdown",
                        "volatility",
                        "downside_volatility",
                        "var_95",
                        "cvar_95",
                        "excess_return",
                        "tracking_error",
                        "up_capture",
                        "down_capture",
                        "avg_trade_return",
                        "win_rate",
                    ]:
                        formatted[key] = f"{value * 100:.2f}%"
                    else:
                        formatted[key] = f"{value:.4f}"
                else:
                    formatted[key] = value
            return formatted

        return data

    def get_by_type(self, metric_type: MetricType) -> Dict[str, Any]:
        """
        按类型获取指标

        Args:
            metric_type: 指标类型（MetricType枚举）

        Returns:
            该类型的指标字典
        """
        type_mapping = {
            MetricType.RETURN: {
                "total_return": self.total_return,
                "annual_return": self.annual_return,
                "cumulative_return": self.cumulative_return,
            },
            MetricType.RISK: {
                "max_drawdown": self.max_drawdown,
                "max_drawdown_duration": self.max_drawdown_duration,
                "volatility": self.volatility,
                "downside_volatility": self.downside_volatility,
                "var_95": self.var_95,
                "cvar_95": self.cvar_95,
            },
            MetricType.RISK_ADJUSTED: {
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "calmar_ratio": self.calmar_ratio,
                "omega_ratio": self.omega_ratio,
            },
            MetricType.TRADE: {
                "win_rate": self.win_rate,
                "profit_loss_ratio": self.profit_loss_ratio,
                "total_trades": self.total_trades,
                "avg_trade_return": self.avg_trade_return,
                "max_consecutive_wins": self.max_consecutive_wins,
                "max_consecutive_losses": self.max_consecutive_losses,
            },
            MetricType.RELATIVE: {
                "alpha": self.alpha,
                "beta": self.beta,
                "information_ratio": self.information_ratio,
                "tracking_error": self.tracking_error,
                "excess_return": self.excess_return,
                "up_capture": self.up_capture,
                "down_capture": self.down_capture,
            },
        }
        return type_mapping.get(metric_type, {})

    def __str__(self) -> str:
        """格式化输出绩效报告"""
        lines = [
            "=" * 60,
            "回测绩效报告",
            "=" * 60,
            f"总收益率: {self.total_return * 100:+.2f}%",
            f"年化收益率: {self.annual_return * 100:+.2f}%",
            "",
            f"最大回撤: {self.max_drawdown * 100:.2f}%",
            f"最大回撤持续天数: {self.max_drawdown_duration}",
            f"年化波动率: {self.volatility * 100:.2f}%",
            f"下行波动率: {self.downside_volatility * 100:.2f}%",
            f"VaR (95%): {self.var_95 * 100:.2f}%",
            f"CVaR (95%): {self.cvar_95 * 100:.2f}%",
            "",
            f"夏普比率: {self.sharpe_ratio:.2f}",
            f"索提诺比率: {self.sortino_ratio:.2f}",
            f"Calmar比率: {self.calmar_ratio:.2f}",
            f"Omega比率: {self.omega_ratio:.2f}",
            "",
            f"胜率: {self.win_rate * 100:.2f}%",
            f"盈亏比: {self.profit_loss_ratio:.2f}",
            f"总交易次数: {self.total_trades}",
            f"平均交易收益: {self.avg_trade_return * 100:+.2f}%",
            f"最大连续盈利: {self.max_consecutive_wins}",
            f"最大连续亏损: {self.max_consecutive_losses}",
            "",
            f"Alpha: {self.alpha:.4f}",
            f"Beta: {self.beta:.4f}",
            f"信息比率: {self.information_ratio:.2f}",
            f"跟踪误差: {self.tracking_error * 100:.2f}%",
            f"超额收益(相对基准): {self.excess_return * 100:+.2f}%",
            f"上涨捕获率: {self.up_capture * 100:.2f}%",
            f"下跌捕获率: {self.down_capture * 100:.2f}%",
            "=" * 60,
        ]
        return "\n".join(lines)


class MetricsCalculator:
    """
    绩效指标计算器

    负责计算完整的回测绩效指标体系，包括收益、风险、风险调整收益、
    交易统计以及相对基准指标。

    Attributes:
        risk_free_rate: 无风险利率（年化）
        trading_days_per_year: 每年交易日数

    Example:
        >>> calculator = MetricsCalculator(risk_free_rate=0.03)
        >>> metrics = calculator.calculate(nav_history, benchmark_nav, trades_df)
        >>> print(metrics.sharpe_ratio)
    """

    def __init__(self, risk_free_rate: float = 0.03, trading_days_per_year: int = 252):
        """
        初始化计算器

        Args:
            risk_free_rate: 无风险利率（年化），默认3%
            trading_days_per_year: 每年交易日数，默认252

        Raises:
            MetricsError: 当参数无效时
        """
        if risk_free_rate < 0:
            raise MetricsError(f"Risk-free rate cannot be negative: {risk_free_rate}")
        if trading_days_per_year <= 0:
            raise MetricsError(f"Trading days per year must be positive: {trading_days_per_year}")

        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
        self._sqrt_trading_days = np.sqrt(trading_days_per_year)

        logger.debug(
            f"MetricsCalculator initialized: rf={risk_free_rate}, days={trading_days_per_year}"
        )

    def calculate(
        self,
        nav_history: List[Tuple[datetime, float]],
        benchmark_nav: Optional[List[Tuple[datetime, float]]] = None,
        trades_df: Optional[pd.DataFrame] = None,
    ) -> PerformanceMetrics:
        """
        计算完整绩效指标

        Args:
            nav_history: 净值历史列表，格式为 [(date, nav), ...]
            benchmark_nav: 基准净值历史列表，格式相同（可选）
            trades_df: 交易记录DataFrame（可选）

        Returns:
            PerformanceMetrics 包含所有计算出的指标

        Raises:
            MetricsError: 当计算过程中发生错误时
        """
        metrics = PerformanceMetrics()

        if not nav_history or len(nav_history) < 2:
            logger.warning("Insufficient NAV history for metrics calculation")
            return metrics

        try:
            # 转换为DataFrame
            df = self._prepare_nav_df(nav_history)

            if df is None or df.empty:
                logger.warning("Empty NAV data after preparation")
                return metrics

            daily_returns = df["daily_return"].dropna()

            if len(daily_returns) < 2:
                logger.warning("Insufficient daily returns for metrics calculation")
                return metrics

            # 1. 收益指标
            metrics = self._calculate_return_metrics(metrics, df, daily_returns)

            # 2. 风险指标
            metrics = self._calculate_risk_metrics(metrics, df, daily_returns)

            # 3. 风险调整收益
            metrics = self._calculate_risk_adjusted_metrics(metrics, daily_returns)

            # 4. 交易指标
            if trades_df is not None and not trades_df.empty:
                metrics = self._calculate_trade_metrics(metrics, trades_df)

            # 5. 相对基准指标
            if benchmark_nav and len(benchmark_nav) > 1:
                metrics = self._calculate_relative_metrics(metrics, df, benchmark_nav)

            logger.info(
                f"Metrics calculated: total_return={metrics.total_return * 100:.2f}%, "
                f"sharpe={metrics.sharpe_ratio:.2f}, max_dd={metrics.max_drawdown * 100:.2f}%"
            )

            return metrics

        except Exception as e:
            logger.error(f"Metrics calculation failed: {e}")
            raise MetricsError(f"Failed to calculate metrics: {e}") from e

    def _prepare_nav_df(self, nav_history: List[Tuple[datetime, float]]) -> Optional[pd.DataFrame]:
        """
        准备净值DataFrame

        Args:
            nav_history: 净值历史列表

        Returns:
            处理后的DataFrame，包含date、nav、daily_return列
        """
        try:
            df = pd.DataFrame(nav_history, columns=["date", "nav"])

            # Ensure date column is datetime
            if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = pd.to_datetime(df["date"])

            df = df.sort_values("date").drop_duplicates(subset=["date"])

            # 计算日收益率
            df["daily_return"] = df["nav"].pct_change()

            return df
        except Exception as e:
            logger.error(f"Failed to prepare NAV DataFrame: {e}")
            return None

    def _calculate_return_metrics(
        self, metrics: PerformanceMetrics, df: pd.DataFrame, daily_returns: pd.Series
    ) -> PerformanceMetrics:
        """计算收益指标"""
        start_nav = df["nav"].iloc[0]
        end_nav = df["nav"].iloc[-1]

        metrics.total_return = (end_nav / start_nav) - 1
        metrics.cumulative_return = end_nav - start_nav

        days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
        if days > 0:
            metrics.annual_return = (1 + metrics.total_return) ** (365 / days) - 1

        return metrics

    def _calculate_risk_metrics(
        self, metrics: PerformanceMetrics, df: pd.DataFrame, daily_returns: pd.Series
    ) -> PerformanceMetrics:
        """计算风险指标"""
        # 最大回撤
        metrics.max_drawdown, metrics.max_drawdown_duration = self._calc_max_drawdown(df)

        # 波动率
        metrics.volatility = daily_returns.std() * self._sqrt_trading_days

        # 下行波动率（只计算负收益）
        downside_returns = daily_returns[daily_returns < 0]
        metrics.downside_volatility = (
            downside_returns.std() * self._sqrt_trading_days if len(downside_returns) > 0 else 0.0
        )

        # VaR和CVaR
        metrics.var_95 = np.percentile(daily_returns, 5)
        metrics.cvar_95 = daily_returns[daily_returns <= metrics.var_95].mean()

        return metrics

    def _calculate_risk_adjusted_metrics(
        self, metrics: PerformanceMetrics, daily_returns: pd.Series
    ) -> PerformanceMetrics:
        """计算风险调整收益指标"""
        # 夏普比率
        if metrics.volatility > 1e-10:
            excess_return = metrics.annual_return - self.risk_free_rate
            metrics.sharpe_ratio = excess_return / metrics.volatility

        # 索提诺比率
        if metrics.downside_volatility > 1e-10:
            excess_return = metrics.annual_return - self.risk_free_rate
            metrics.sortino_ratio = excess_return / metrics.downside_volatility

        # Calmar比率
        if metrics.max_drawdown > 1e-10:
            metrics.calmar_ratio = metrics.annual_return / metrics.max_drawdown

        # Omega比率
        positive_returns = daily_returns[daily_returns > 0].sum()
        negative_returns = abs(daily_returns[daily_returns < 0].sum())
        if negative_returns > 1e-10:
            metrics.omega_ratio = positive_returns / negative_returns

        return metrics

    def _calculate_trade_metrics(
        self, metrics: PerformanceMetrics, trades_df: pd.DataFrame
    ) -> PerformanceMetrics:
        """计算交易指标"""
        metrics.total_trades = len(trades_df)

        try:
            win_rate, pl_ratio, avg_return, max_consec_wins, max_consec_losses = (
                self._calc_trade_metrics_advanced(trades_df)
            )

            metrics.win_rate = win_rate
            metrics.profit_loss_ratio = pl_ratio
            metrics.avg_trade_return = avg_return
            metrics.max_consecutive_wins = max_consec_wins
            metrics.max_consecutive_losses = max_consec_losses
        except Exception as e:
            logger.warning(f"Trade metrics calculation failed: {e}")

        return metrics

    def _calculate_relative_metrics(
        self,
        metrics: PerformanceMetrics,
        strategy_df: pd.DataFrame,
        benchmark_nav: List[Tuple[datetime, float]],
    ) -> PerformanceMetrics:
        """计算相对基准指标"""
        try:
            alpha, beta, info_ratio, tracking_error, excess_return, up_capture, down_capture = (
                self._calc_relative_metrics_advanced(strategy_df, benchmark_nav)
            )

            metrics.alpha = alpha
            metrics.beta = beta
            metrics.information_ratio = info_ratio
            metrics.tracking_error = tracking_error
            metrics.excess_return = excess_return
            metrics.up_capture = up_capture
            metrics.down_capture = down_capture
        except Exception as e:
            logger.warning(f"Relative metrics calculation failed: {e}")

        return metrics

    def _calc_max_drawdown(self, df: pd.DataFrame) -> Tuple[float, int]:
        """
        计算最大回撤及持续天数

        Args:
            df: 包含nav列的DataFrame

        Returns:
            (最大回撤比例, 最大回撤持续天数)
        """
        df = df.copy()
        df["peak"] = df["nav"].cummax()
        df["drawdown"] = (df["nav"] - df["peak"]) / df["peak"]

        max_dd = abs(df["drawdown"].min())

        # 计算最大回撤持续天数
        max_dd_duration = 0
        current_duration = 0
        in_drawdown = False

        for dd in df["drawdown"]:
            if dd < -1e-10:  # 考虑浮点精度
                if not in_drawdown:
                    in_drawdown = True
                    current_duration = 1
                else:
                    current_duration += 1
                max_dd_duration = max(max_dd_duration, current_duration)
            else:
                in_drawdown = False
                current_duration = 0

        return max_dd, max_dd_duration

    def _calc_trade_metrics_advanced(
        self, trades_df: pd.DataFrame
    ) -> Tuple[float, float, float, int, int]:
        """
        计算交易胜率、盈亏比、平均收益、连续输赢次数

        Args:
            trades_df: 交易记录DataFrame

        Returns:
            (胜率, 盈亏比, 平均收益, 最大连续盈利次数, 最大连续亏损次数)
        """
        if trades_df.empty:
            return 0.0, 0.0, 0.0, 0, 0

        # 尝试识别买卖方向
        side_col = None
        for col in ["side", "action", "direction"]:
            if col in trades_df.columns:
                side_col = col
                break

        if side_col is None:
            logger.warning("No side column found in trades data")
            return 0.0, 0.0, 0.0, 0, 0

        profits = []
        consecutive_wins = 0
        consecutive_losses = 0
        max_consec_wins = 0
        max_consec_losses = 0

        for ts_code in trades_df["ts_code"].unique():
            stock_trades = trades_df[trades_df["ts_code"] == ts_code]

            # 尝试多种可能的列名
            buy_trades = stock_trades[stock_trades[side_col].str.lower().isin(["buy", "b"])]
            sell_trades = stock_trades[
                stock_trades[side_col].str.lower().isin(["sell", "s", "sale"])
            ]

            if buy_trades.empty or sell_trades.empty:
                continue

            # 计算买卖成本
            buy_amount = buy_trades["amount"].sum() if "amount" in buy_trades.columns else 0
            sell_amount = sell_trades["amount"].sum() if "amount" in sell_trades.columns else 0

            commission = 0
            if "commission" in stock_trades.columns:
                commission = stock_trades["commission"].sum()

            total_buy = buy_amount + commission * 0.5
            total_sell = sell_amount - commission * 0.5
            profit = total_sell - total_buy
            profits.append(profit)

            # 追踪连续盈亏
            if profit > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consec_wins = max(max_consec_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consec_losses = max(max_consec_losses, consecutive_losses)

        if not profits:
            return 0.0, 0.0, 0.0, 0, 0

        profits = np.array(profits)
        wins = profits[profits > 0]
        losses = profits[profits < 0]

        win_rate = len(wins) / len(profits) if len(profits) > 0 else 0.0

        avg_profit = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0.0
        pl_ratio = avg_profit / avg_loss if avg_loss > 1e-10 else 0.0

        total_amount = trades_df["amount"].sum() if "amount" in trades_df.columns else 1.0
        avg_return = (
            profits.mean() / (total_amount / len(trades_df))
            if len(trades_df) > 0 and total_amount > 0
            else 0.0
        )

        return win_rate, pl_ratio, avg_return, max_consec_wins, max_consec_losses

    def _calc_relative_metrics_advanced(
        self, strategy_df: pd.DataFrame, benchmark_nav: List[Tuple[datetime, float]]
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        计算相对基准的指标（增强版）

        Args:
            strategy_df: 策略净值DataFrame
            benchmark_nav: 基准净值历史

        Returns:
            (Alpha, Beta, 信息比率, 跟踪误差, 超额收益, 上涨捕获率, 下跌捕获率)
        """
        bench_df = pd.DataFrame(benchmark_nav, columns=["date", "nav"])

        # Ensure datetime type
        if not pd.api.types.is_datetime64_any_dtype(bench_df["date"]):
            bench_df["date"] = pd.to_datetime(bench_df["date"])

        bench_df = bench_df.sort_values("date")
        bench_df["daily_return"] = bench_df["nav"].pct_change()

        merged = pd.merge(
            strategy_df[["date", "daily_return"]],
            bench_df[["date", "daily_return"]],
            on="date",
            suffixes=("_strat", "_bench"),
        ).dropna()

        if len(merged) < 2:
            logger.warning("Insufficient data for relative metrics calculation")
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        strat_returns = merged["daily_return_strat"]
        bench_returns = merged["daily_return_bench"]

        # Beta
        covariance = np.cov(strat_returns, bench_returns)[0, 1]
        benchmark_variance = np.var(bench_returns)
        beta = covariance / benchmark_variance if benchmark_variance > 1e-10 else 0.0

        # Alpha（年化）
        strat_annual = strat_returns.mean() * self.trading_days_per_year
        bench_annual = bench_returns.mean() * self.trading_days_per_year
        alpha = strat_annual - (self.risk_free_rate + beta * (bench_annual - self.risk_free_rate))

        # 超额收益
        excess_return = strat_annual - bench_annual

        # 跟踪误差
        tracking_diff = strat_returns - bench_returns
        tracking_error = tracking_diff.std() * self._sqrt_trading_days

        # 信息比率
        information_ratio = excess_return / tracking_error if tracking_error > 1e-10 else 0.0

        # 上涨/下跌捕获率
        up_market = bench_returns > 0
        down_market = bench_returns < 0

        up_capture = 0.0
        down_capture = 0.0

        if up_market.sum() > 0:
            up_capture = strat_returns[up_market].sum() / bench_returns[up_market].sum()

        if down_market.sum() > 0:
            down_capture = strat_returns[down_market].sum() / bench_returns[down_market].sum()

        return (
            alpha,
            beta,
            information_ratio,
            tracking_error,
            excess_return,
            up_capture,
            down_capture,
        )

    def calculate_rolling_metrics(
        self, nav_history: List[Tuple[datetime, float]], window: int = 20
    ) -> pd.DataFrame:
        """
        计算滚动指标

        Args:
            nav_history: 净值历史
            window: 滚动窗口大小

        Returns:
            包含滚动指标的DataFrame
        """
        df = self._prepare_nav_df(nav_history)

        if df is None or len(df) < window:
            return pd.DataFrame()

        df["rolling_volatility"] = (
            df["daily_return"].rolling(window).std() * self._sqrt_trading_days
        )
        df["rolling_return"] = df["nav"].pct_change(window)

        # 滚动最大回撤
        df["rolling_peak"] = df["nav"].rolling(window, min_periods=1).max()
        df["rolling_drawdown"] = (df["nav"] - df["rolling_peak"]) / df["rolling_peak"]

        # 滚动夏普
        df["rolling_sharpe"] = (
            df["daily_return"].rolling(window).mean() * self.trading_days_per_year
            - self.risk_free_rate
        ) / (df["daily_return"].rolling(window).std() * self._sqrt_trading_days)

        return df[
            ["date", "rolling_volatility", "rolling_return", "rolling_drawdown", "rolling_sharpe"]
        ]

    def get_summary_report(self, metrics: PerformanceMetrics) -> str:
        """
        生成摘要报告

        Args:
            metrics: 绩效指标

        Returns:
            格式化报告字符串
        """
        return str(metrics)


def create_default_calculator() -> MetricsCalculator:
    """
    创建默认配置的计算器

    Returns:
        使用默认参数（无风险利率3%，252交易日）的计算器实例
    """
    return MetricsCalculator()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Test
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")

    # Generate random returns
    nav = 1.0
    nav_history = []
    for date in dates:
        ret = np.random.normal(0.0005, 0.02)
        nav *= 1 + ret
        nav_history.append((date, nav))

    bench_nav = 1.0
    benchmark_nav = []
    for date in dates:
        ret = np.random.normal(0.0003, 0.015)
        bench_nav *= 1 + ret
        benchmark_nav.append((date, bench_nav))

    calculator = MetricsCalculator()
    metrics = calculator.calculate(nav_history, benchmark_nav)

    print(metrics)

    # Test rolling metrics
    rolling = calculator.calculate_rolling_metrics(nav_history, window=20)
    print("\n滚动指标示例:")
    print(rolling.tail())
