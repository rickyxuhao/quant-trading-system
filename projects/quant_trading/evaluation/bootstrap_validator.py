"""
Bootstrap验证模块 - 提供稳健的统计推断

功能：
- 时间序列Bootstrap（保留自相关结构）
- 块Bootstrap
- 夏普比率的Bootstrap置信区间
- 最大回撤的Bootstrap分布
- 信息比率的Bootstrap检验
- 策略比较的Bootstrap检验
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy import stats

from core.logger import get_logger

logger = get_logger(__name__)


class BootstrapMethod(Enum):
    """Bootstrap方法"""
    STANDARD = "standard"  # 标准Bootstrap
    BLOCK = "block"  # 块Bootstrap（保留时间序列相关性）
    STATIONARY = "stationary"  # 平稳Bootstrap
    CIRCULAR = "circular"  # 循环Bootstrap


@dataclass
class BootstrapResult:
    """Bootstrap结果"""

    original_value: float  # 原始估计值
    bootstrap_mean: float  # Bootstrap均值
    bootstrap_std: float  # Bootstrap标准差
    bias: float  # 偏差
    se: float  # 标准误

    # 置信区间
    ci_lower: float  # 置信区间下限
    ci_upper: float  # 置信区间上限
    confidence_level: float  # 置信水平

    # 分布信息
    bootstrap_distribution: np.ndarray  # Bootstrap分布

    # 假设检验
    pvalue_two_sided: float  # 双侧检验p值
    pvalue_one_sided: float  # 单侧检验p值

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "original": self.original_value,
            "mean": self.bootstrap_mean,
            "std": self.bootstrap_std,
            "bias": self.bias,
            "se": self.se,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "pvalue_two_sided": self.pvalue_two_sided,
            "pvalue_one_sided": self.pvalue_one_sided,
        }


@dataclass
class StrategyComparisonResult:
    """策略比较结果"""

    strategy1_return: float
    strategy2_return: float
    return_difference: float
    return_pvalue: float

    strategy1_sharpe: float
    strategy2_sharpe: float
    sharpe_difference: float
    sharpe_pvalue: float

    strategy1_maxdd: float
    strategy2_maxdd: float
    maxdd_difference: float

    bootstrap_results: Dict[str, BootstrapResult] = field(default_factory=dict)


class BootstrapValidator:
    """
    Bootstrap验证器

    提供稳健的统计推断和置信区间估计
    """

    def __init__(
        self,
        n_bootstrap: int = 1000,
        method: BootstrapMethod = BootstrapMethod.BLOCK,
        block_size: Optional[int] = None,
        confidence_level: float = 0.95,
        random_state: int = 42,
    ):
        self.n_bootstrap = n_bootstrap
        self.method = method
        self.block_size = block_size
        self.confidence_level = confidence_level
        self.random_state = random_state

        np.random.seed(random_state)

    def bootstrap_statistic(
        self,
        data: np.ndarray,
        stat_func: Callable,
        **kwargs
    ) -> BootstrapResult:
        """
        对统计量进行Bootstrap

        Args:
            data: 数据数组
            stat_func: 统计量计算函数

        Returns:
            Bootstrap结果
        """
        # 计算原始统计量
        original_value = stat_func(data)

        # 生成Bootstrap样本
        bootstrap_estimates = []

        for _ in range(self.n_bootstrap):
            if self.method == BootstrapMethod.STANDARD:
                sample = self._standard_bootstrap(data)
            elif self.method == BootstrapMethod.BLOCK:
                sample = self._block_bootstrap(data)
            elif self.method == BootstrapMethod.STATIONARY:
                sample = self._stationary_bootstrap(data)
            else:
                sample = self._circular_bootstrap(data)

            try:
                estimate = stat_func(sample)
                if np.isfinite(estimate):
                    bootstrap_estimates.append(estimate)
            except Exception as e:
                logger.debug(f"Bootstrap iteration failed: {e}")
                continue

        bootstrap_array = np.array(bootstrap_estimates)

        return self._calculate_bootstrap_result(
            original_value, bootstrap_array
        )

    def bootstrap_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: float = 0.0,
    ) -> BootstrapResult:
        """
        Bootstrap夏普比率
        """
        def sharpe_func(r):
            if len(r) < 2:
                return 0.0
            mean = np.mean(r) - risk_free_rate / 252
            std = np.std(r, ddof=1)
            return np.sqrt(252) * mean / std if std > 0 else 0.0

        return self.bootstrap_statistic(returns.values, sharpe_func)

    def bootstrap_max_drawdown(
        self,
        nav_series: pd.Series,
    ) -> BootstrapResult:
        """
        Bootstrap最大回撤
        """
        def maxdd_func(nav):
            if len(nav) < 2:
                return 0.0
            peak = np.maximum.accumulate(nav)
            drawdown = (peak - nav) / peak
            return np.max(drawdown)

        return self.bootstrap_statistic(nav_series.values, maxdd_func)

    def bootstrap_information_ratio(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> BootstrapResult:
        """
        Bootstrap信息比率
        """
        # 对齐
        aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()

        if len(aligned) < 2:
            return self._empty_bootstrap_result()

        strat_ret = aligned.iloc[:, 0]
        bench_ret = aligned.iloc[:, 1]

        def ir_func(data):
            s = data[:len(data)//2]
            b = data[len(data)//2:]

            if len(s) < 2:
                return 0.0

            excess = s - b
            mean_excess = np.mean(excess)
            tracking_error = np.std(excess, ddof=1)

            return np.sqrt(252) * mean_excess / tracking_error if tracking_error > 0 else 0.0

        combined = np.concatenate([strat_ret.values, bench_ret.values])

        return self.bootstrap_statistic(combined, ir_func)

    def bootstrap_annual_return(
        self,
        returns: pd.Series,
    ) -> BootstrapResult:
        """
        Bootstrap年化收益率
        """
        def annual_return_func(r):
            if len(r) < 2:
                return 0.0
            cum_return = np.prod(1 + r) - 1
            n_years = len(r) / 252
            return (1 + cum_return) ** (1 / n_years) - 1 if n_years > 0 else 0.0

        return self.bootstrap_statistic(returns.values, annual_return_func)

    def compare_strategies(
        self,
        returns1: pd.Series,
        returns2: pd.Series,
        nav1: Optional[pd.Series] = None,
        nav2: Optional[pd.Series] = None,
    ) -> StrategyComparisonResult:
        """
        Bootstrap策略比较
        """
        # 对齐
        aligned = pd.concat([returns1, returns2], axis=1).dropna()

        if len(aligned) < 30:
            raise ValueError("Insufficient data for comparison")

        r1 = aligned.iloc[:, 0]
        r2 = aligned.iloc[:, 1]

        # 原始统计量
        sharpe1 = self._calculate_sharpe(r1)
        sharpe2 = self._calculate_sharpe(r2)

        ret1 = self._calculate_annual_return(r1)
        ret2 = self._calculate_annual_return(r2)

        # Bootstrap夏普比率差异
        def sharpe_diff(data):
            mid = len(data) // 2
            r1_boot = data[:mid]
            r2_boot = data[mid:]
            return self._calculate_sharpe(r1_boot) - self._calculate_sharpe(r2_boot)

        combined = np.concatenate([r1.values, r2.values])
        sharpe_diff_result = self.bootstrap_statistic(combined, sharpe_diff)

        # Bootstrap收益差异
        def return_diff(data):
            mid = len(data) // 2
            r1_boot = data[:mid]
            r2_boot = data[mid:]
            return self._calculate_annual_return(r1_boot) - self._calculate_annual_return(r2_boot)

        return_diff_result = self.bootstrap_statistic(combined, return_diff)

        # 最大回撤（如有净值）
        maxdd1, maxdd2 = 0.0, 0.0
        if nav1 is not None and nav2 is not None:
            maxdd1 = self._calculate_max_drawdown(nav1)
            maxdd2 = self._calculate_max_drawdown(nav2)

        return StrategyComparisonResult(
            strategy1_return=ret1,
            strategy2_return=ret2,
            return_difference=ret1 - ret2,
            return_pvalue=return_diff_result.pvalue_two_sided,
            strategy1_sharpe=sharpe1,
            strategy2_sharpe=sharpe2,
            sharpe_difference=sharpe1 - sharpe2,
            sharpe_pvalue=sharpe_diff_result.pvalue_two_sided,
            strategy1_maxdd=maxdd1,
            strategy2_maxdd=maxdd2,
            maxdd_difference=maxdd1 - maxdd2,
            bootstrap_results={
                "sharpe_difference": sharpe_diff_result,
                "return_difference": return_diff_result,
            }
        )

    def _standard_bootstrap(self, data: np.ndarray) -> np.ndarray:
        """标准Bootstrap（独立同分布抽样）"""
        n = len(data)
        indices = np.random.randint(0, n, size=n)
        return data[indices]

    def _block_bootstrap(self, data: np.ndarray) -> np.ndarray:
        """块Bootstrap（保留时间序列相关性）"""
        n = len(data)
        block_size = self.block_size or max(int(np.sqrt(n)), 10)

        n_blocks = int(np.ceil(n / block_size))

        result = []
        for _ in range(n_blocks):
            # 随机选择块起始位置
            start = np.random.randint(0, max(1, n - block_size + 1))
            block = data[start:start + block_size]
            result.extend(block)

        return np.array(result[:n])

    def _stationary_bootstrap(self, data: np.ndarray) -> np.ndarray:
        """平稳Bootstrap（变长块）"""
        n = len(data)
        expected_block_size = self.block_size or max(int(np.sqrt(n)), 10)
        p = 1.0 / expected_block_size  # 几何分布参数

        result = []
        while len(result) < n:
            # 随机选择起始位置
            start = np.random.randint(0, n)
            # 几何分布决定块长度
            block_len = np.random.geometric(p)

            for i in range(block_len):
                result.append(data[(start + i) % n])
                if len(result) >= n:
                    break

        return np.array(result[:n])

    def _circular_bootstrap(self, data: np.ndarray) -> np.ndarray:
        """循环Bootstrap"""
        n = len(data)
        block_size = self.block_size or max(int(np.sqrt(n)), 10)
        n_blocks = int(np.ceil(n / block_size))

        result = []
        for _ in range(n_blocks):
            start = np.random.randint(0, n)
            for i in range(block_size):
                result.append(data[(start + i) % n])

        return np.array(result[:n])

    def _calculate_bootstrap_result(
        self,
        original_value: float,
        bootstrap_distribution: np.ndarray,
    ) -> BootstrapResult:
        """计算Bootstrap结果"""
        if len(bootstrap_distribution) == 0:
            return self._empty_bootstrap_result()

        # 基本统计量
        bootstrap_mean = np.mean(bootstrap_distribution)
        bootstrap_std = np.std(bootstrap_distribution, ddof=1)

        # 偏差
        bias = bootstrap_mean - original_value

        # 标准误
        se = bootstrap_std

        # 百分位置信区间
        alpha = 1 - self.confidence_level
        ci_lower = np.percentile(bootstrap_distribution, alpha / 2 * 100)
        ci_upper = np.percentile(bootstrap_distribution, (1 - alpha / 2) * 100)

        # 偏差校正加速(BCa)置信区间（简化版）
        # 使用百分位区间作为近似

        # 假设检验
        # H0: statistic = 0
        pvalue_two_sided = 2 * min(
            np.mean(bootstrap_distribution <= 0),
            np.mean(bootstrap_distribution >= 0)
        )
        pvalue_one_sided = np.mean(bootstrap_distribution <= 0)

        return BootstrapResult(
            original_value=original_value,
            bootstrap_mean=bootstrap_mean,
            bootstrap_std=bootstrap_std,
            bias=bias,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_distribution,
            pvalue_two_sided=pvalue_two_sided,
            pvalue_one_sided=pvalue_one_sided,
        )

    def _empty_bootstrap_result(self) -> BootstrapResult:
        """创建空的Bootstrap结果"""
        return BootstrapResult(
            original_value=0.0,
            bootstrap_mean=0.0,
            bootstrap_std=0.0,
            bias=0.0,
            se=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            confidence_level=self.confidence_level,
            bootstrap_distribution=np.array([]),
            pvalue_two_sided=1.0,
            pvalue_one_sided=1.0,
        )

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        return np.sqrt(252) * mean / std if std > 0 else 0.0

    def _calculate_annual_return(self, returns: np.ndarray) -> float:
        """计算年化收益"""
        if len(returns) < 2:
            return 0.0
        cum_return = np.prod(1 + returns) - 1
        n_years = len(returns) / 252
        return (1 + cum_return) ** (1 / n_years) - 1 if n_years > 0 else 0.0

    def _calculate_max_drawdown(self, nav: pd.Series) -> float:
        """计算最大回撤"""
        if len(nav) < 2:
            return 0.0
        peak = nav.expanding().max()
        drawdown = (peak - nav) / peak
        return drawdown.max()


class WalkForwardValidator:
    """
    滚动窗口验证器

    实现滚动训练和验证
    """

    def __init__(
        self,
        train_window: int = 252 * 3,  # 3年训练
        test_window: int = 63,  # 季度测试
        step_size: int = 63,  # 季度滚动
    ):
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size

    def generate_splits(
        self,
        dates: pd.DatetimeIndex,
    ) -> List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """
        生成滚动窗口划分

        Returns:
            [(train_dates, test_dates), ...]
        """
        splits = []
        n = len(dates)

        start_idx = self.train_window

        while start_idx + self.test_window <= n:
            train_start = max(0, start_idx - self.train_window)
            train_end = start_idx
            test_end = min(start_idx + self.test_window, n)

            train_dates = dates[train_start:train_end]
            test_dates = dates[train_end:test_end]

            splits.append((train_dates, test_dates))

            start_idx += self.step_size

        return splits
    def validate_strategy(
        self,
        strategy: Any,
        data: pd.DataFrame,
        metric_func: Callable,
    ) -> pd.DataFrame:
        """
        执行滚动窗口验证

        Returns:
            各窗口的绩效指标
        """
        results = []

        dates = data.index
        splits = self.generate_splits(dates)

        for i, (train_dates, test_dates) in enumerate(splits):
            logger.info(f"Fold {i+1}/{len(splits)}")

            # 训练
            train_data = data.loc[train_dates]
            strategy.train(train_data)

            # 测试
            test_data = data.loc[test_dates]
            predictions = strategy.predict(test_data)

            # 计算指标
            metrics = metric_func(test_data, predictions)
            metrics["fold"] = i + 1
            metrics["train_start"] = train_dates[0]
            metrics["train_end"] = train_dates[-1]
            metrics["test_start"] = test_dates[0]
            metrics["test_end"] = test_dates[-1]

            results.append(metrics)

        return pd.DataFrame(results)


def bootstrap_sharpe_confidence_interval(
    returns: pd.Series,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> Tuple[float, float, float]:
    """
    计算夏普比率的Bootstrap置信区间

    Returns:
        (原始夏普比率, 下限, 上限)
    """
    validator = BootstrapValidator(
        n_bootstrap=n_bootstrap,
        method=BootstrapMethod.BLOCK,
        confidence_level=confidence_level,
    )

    result = validator.bootstrap_sharpe_ratio(returns)

    return result.original_value, result.ci_lower, result.ci_upper


def bootstrap_backtest_metrics(
    returns: pd.Series,
    nav: pd.Series,
    n_bootstrap: int = 1000,
) -> Dict[str, BootstrapResult]:
    """
    Bootstrap回测关键指标

    Returns:
        {metric_name: BootstrapResult}
    """
    validator = BootstrapValidator(
        n_bootstrap=n_bootstrap,
        method=BootstrapMethod.BLOCK,
    )

    results = {
        "annual_return": validator.bootstrap_annual_return(returns),
        "sharpe_ratio": validator.bootstrap_sharpe_ratio(returns),
        "max_drawdown": validator.bootstrap_max_drawdown(nav),
    }

    return results
