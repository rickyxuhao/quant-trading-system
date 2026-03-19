"""
VectorBT 参数优化器

使用 vectorbt 进行高性能参数优化：
- 贝叶斯优化（Bayesian Optimization）
- 网格搜索（Grid Search）
- Walk-forward 优化

与现有回测引擎集成，优化后的参数用于 BacktestEngine 精细回测。

作者: Claude
创建日期: 2026-03-19
"""

from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings

import numpy as np
import pandas as pd

# VectorBT 导入
try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False
    warnings.warn("vectorbt not installed. Run: pip install vectorbt")

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Dict[str, float]
    all_results: pd.DataFrame
    optimization_time: float

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "best_metrics": self.best_metrics,
            "optimization_time": self.optimization_time,
        }


class BaseOptimizer:
    """优化器基类"""

    def __init__(
        self,
        strategy_fn: Callable,
        param_space: Dict[str, Union[List, Tuple]],
        metric: str = "sharpe_ratio",
        maximize: bool = True,
    ):
        """
        初始化优化器

        Args:
            strategy_fn: 策略函数，接收参数返回回测结果
            param_space: 参数空间，如 {"lookback": [5, 10, 20], "threshold": (0.1, 0.5)}
            metric: 优化目标指标，如 "sharpe_ratio", "total_return", "calmar_ratio"
            maximize: 是否最大化目标
        """
        self.strategy_fn = strategy_fn
        self.param_space = param_space
        self.metric = metric
        self.maximize = maximize
        self.results: List[Dict] = []

    def optimize(self, **kwargs) -> OptimizationResult:
        """执行优化，子类实现"""
        raise NotImplementedError

    def _evaluate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估一组参数

        Args:
            params: 参数字典

        Returns:
            包含参数和结果的字典
        """
        try:
            start_time = datetime.now()
            result = self.strategy_fn(**params)
            elapsed = (datetime.now() - start_time).total_seconds()

            return {
                "params": params,
                "metrics": result,
                "score": result.get(self.metric, 0),
                "elapsed": elapsed,
            }
        except Exception as e:
            logger.warning(f"Parameter evaluation failed: {params}, error: {e}")
            return {
                "params": params,
                "metrics": {},
                "score": float("-inf") if self.maximize else float("inf"),
                "elapsed": 0,
                "error": str(e),
            }


class GridSearchOptimizer(BaseOptimizer):
    """
    网格搜索优化器

    穷举所有参数组合，支持并行计算

    Example:
        >>> optimizer = GridSearchOptimizer(
        ...     strategy_fn=my_strategy,
        ...     param_space={
        ...         "lookback": [5, 10, 20, 60],
        ...         "threshold": [0.1, 0.2, 0.3],
        ...     },
        ...     metric="sharpe_ratio",
        ... )
        >>> result = optimizer.optimize(n_jobs=4)
        >>> print(result.best_params)
    """

    def optimize(
        self,
        n_jobs: int = -1,
        verbose: bool = True,
    ) -> OptimizationResult:
        """
        执行网格搜索

        Args:
            n_jobs: 并行进程数，-1 表示使用所有 CPU
            verbose: 是否打印进度

        Returns:
            OptimizationResult
        """
        import multiprocessing as mp

        start_time = datetime.now()

        # 生成所有参数组合
        param_names = list(self.param_space.keys())
        param_values = []

        for name in param_names:
            value = self.param_space[name]
            if isinstance(value, tuple) and len(value) == 2:
                # 范围参数，生成网格
                param_values.append(np.linspace(value[0], value[1], 5).tolist())
            else:
                param_values.append(value)

        all_combinations = list(itertools.product(*param_values))
        total = len(all_combinations)

        logger.info(f"Grid search: {total} parameter combinations")

        # 并行评估
        n_jobs = n_jobs if n_jobs > 0 else mp.cpu_count()
        n_jobs = min(n_jobs, total)

        self.results = []

        if n_jobs == 1:
            # 串行执行
            for i, values in enumerate(all_combinations):
                params = dict(zip(param_names, values))
                result = self._evaluate_params(params)
                self.results.append(result)

                if verbose and (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{total}")
        else:
            # 并行执行
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                futures = {
                    executor.submit(
                        self._evaluate_params,
                        dict(zip(param_names, values))
                    ): values
                    for values in all_combinations
                }

                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    self.results.append(result)
                    completed += 1

                    if verbose and completed % 10 == 0:
                        logger.info(f"Progress: {completed}/{total}")

        # 找出最优参数
        best_result = self._find_best_result()
        elapsed = (datetime.now() - start_time).total_seconds()

        # 构建结果 DataFrame
        results_df = self._build_results_df()

        return OptimizationResult(
            best_params=best_result["params"],
            best_score=best_result["score"],
            best_metrics=best_result.get("metrics", {}),
            all_results=results_df,
            optimization_time=elapsed,
        )

    def _find_best_result(self) -> Dict:
        """找出最优结果"""
        if not self.results:
            return {"params": {}, "score": 0}

        valid_results = [r for r in self.results if "error" not in r]
        if not valid_results:
            return {"params": {}, "score": 0}

        if self.maximize:
            best = max(valid_results, key=lambda x: x["score"])
        else:
            best = min(valid_results, key=lambda x: x["score"])

        return best

    def _build_results_df(self) -> pd.DataFrame:
        """构建结果 DataFrame"""
        rows = []
        for result in self.results:
            row = {
                **result["params"],
                "score": result["score"],
                **{f"metric_{k}": v for k, v in result.get("metrics", {}).items()},
            }
            rows.append(row)
        return pd.DataFrame(rows)


class BayesianOptimizer(BaseOptimizer):
    """
    贝叶斯优化器

    使用高斯过程进行高效参数搜索，适合参数空间较大的情况

    需要安装: pip install scikit-optimize

    Example:
        >>> optimizer = BayesianOptimizer(
        ...     strategy_fn=my_strategy,
        ...     param_space={
        ...         "lookback": (5, 60),  # 连续范围
        ...         "threshold": (0.05, 0.5),
        ...     },
        ...     metric="sharpe_ratio",
        ... )
        >>> result = optimizer.optimize(n_calls=50)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from skopt import gp_minimize
            from skopt.space import Real, Integer, Categorical
            self.skopt_available = True
            self.Real = Real
            self.Integer = Integer
            self.Categorical = Categorical
            self.gp_minimize = gp_minimize
        except ImportError:
            self.skopt_available = False
            logger.warning("scikit-optimize not installed. Run: pip install scikit-optimize")

    def optimize(
        self,
        n_calls: int = 50,
        n_random_starts: int = 10,
        verbose: bool = True,
    ) -> OptimizationResult:
        """
        执行贝叶斯优化

        Args:
            n_calls: 总评估次数
            n_random_starts: 随机起始点数量
            verbose: 是否打印进度

        Returns:
            OptimizationResult
        """
        if not self.skopt_available:
            raise ImportError("scikit-optimize not installed")

        start_time = datetime.now()

        # 构建 skopt 搜索空间
        dimensions = []
        param_names = []

        for name, value in self.param_space.items():
            param_names.append(name)
            if isinstance(value, tuple):
                if all(isinstance(v, int) for v in value):
                    dimensions.append(self.Integer(value[0], value[1], name=name))
                else:
                    dimensions.append(self.Real(value[0], value[1], name=name))
            elif isinstance(value, list):
                dimensions.append(self.Categorical(value, name=name))

        # 目标函数（最小化，所以取负值）
        def objective(x):
            params = dict(zip(param_names, x))
            result = self._evaluate_params(params)
            score = result["score"]
            return -score if self.maximize else score

        # 执行优化
        logger.info(f"Bayesian optimization: {n_calls} calls")

        result = self.gp_minimize(
            objective,
            dimensions,
            n_calls=n_calls,
            n_random_starts=n_random_starts,
            verbose=verbose,
        )

        # 提取结果
        best_params = dict(zip(param_names, result.x))
        best_score = -result.fun if self.maximize else result.fun

        # 重新计算最优参数的完整指标
        best_result = self._evaluate_params(best_params)

        elapsed = (datetime.now() - start_time).total_seconds()

        # 构建所有结果的 DataFrame（从 skopt 结果中提取）
        results_df = self._build_results_from_skopt(result, param_names)

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            best_metrics=best_result.get("metrics", {}),
            all_results=results_df,
            optimization_time=elapsed,
        )

    def _build_results_from_skopt(
        self,
        result,
        param_names: List[str],
    ) -> pd.DataFrame:
        """从 skopt 结果构建 DataFrame"""
        rows = []
        for i, (x, y) in enumerate(zip(result.x_iters, result.func_vals)):
            row = dict(zip(param_names, x))
            row["score"] = -y if self.maximize else y
            rows.append(row)
        return pd.DataFrame(rows)


class WalkForwardOptimizer:
    """
    Walk-forward 优化器

    结合参数优化和滚动回测，防止过拟合

    Example:
        >>> optimizer = WalkForwardOptimizer(
        ...     strategy_fn=my_strategy,
        ...     param_space={"lookback": [5, 10, 20]},
        ... )
        >>> result = optimizer.optimize(
        ...     data=data,
        ...     train_days=252,
        ...     test_days=63,
        ...     step_days=63,
        ... )
    """

    def __init__(
        self,
        strategy_fn: Callable,
        param_space: Dict[str, Union[List, Tuple]],
        inner_optimizer: str = "grid",  # "grid" or "bayesian"
    ):
        """
        初始化

        Args:
            strategy_fn: 策略函数
            param_space: 参数空间
            inner_optimizer: 内部优化器类型
        """
        self.strategy_fn = strategy_fn
        self.param_space = param_space
        self.inner_optimizer = inner_optimizer

    def optimize(
        self,
        data: pd.DataFrame,
        train_days: int = 252,
        test_days: int = 63,
        step_days: int = 63,
        n_jobs: int = 1,
    ) -> Dict[str, Any]:
        """
        执行 Walk-forward 优化

        Args:
            data: 完整数据集
            train_days: 训练窗口天数
            test_days: 测试窗口天数
            step_days: 滚动步长
            n_jobs: 并行进程数

        Returns:
            包含各窗口结果的字典
        """
        start_time = datetime.now()

        # 构建滚动窗口
        dates = data.index.get_level_values("datetime").unique()
        dates = dates.sort_values()

        windows = []
        for i in range(0, len(dates) - train_days - test_days, step_days):
            train_end = i + train_days
            test_end = min(train_end + test_days, len(dates))

            windows.append({
                "train_start": dates[i],
                "train_end": dates[train_end - 1],
                "test_start": dates[train_end],
                "test_end": dates[test_end - 1],
                "train_dates": dates[i:train_end],
                "test_dates": dates[train_end:test_end],
            })

        logger.info(f"Walk-forward optimization: {len(windows)} windows")

        # 对每个窗口进行优化和测试
        window_results = []

        for i, window in enumerate(windows):
            logger.info(f"Processing window {i + 1}/{len(windows)}: "
                       f"{window['train_start'].date()} to {window['test_end'].date()}")

            # 分割数据
            train_data = data[data.index.get_level_values("datetime").isin(window["train_dates"])]
            test_data = data[data.index.get_level_values("datetime").isin(window["test_dates"])]

            # 在训练集上优化参数
            if self.inner_optimizer == "bayesian":
                inner_opt = BayesianOptimizer(
                    lambda **params: self.strategy_fn(train_data, **params),
                    self.param_space,
                )
                opt_result = inner_opt.optimize(n_calls=30, n_random_starts=5)
            else:
                inner_opt = GridSearchOptimizer(
                    lambda **params: self.strategy_fn(train_data, **params),
                    self.param_space,
                )
                opt_result = inner_opt.optimize(n_jobs=n_jobs)

            # 在测试集上验证最优参数
            test_metrics = self.strategy_fn(test_data, **opt_result.best_params)

            window_results.append({
                "window": i + 1,
                "train_start": window["train_start"],
                "train_end": window["train_end"],
                "test_start": window["test_start"],
                "test_end": window["test_end"],
                "best_params": opt_result.best_params,
                "train_score": opt_result.best_score,
                "test_metrics": test_metrics,
            })

        elapsed = (datetime.now() - start_time).total_seconds()

        # 分析结果稳定性
        stability_analysis = self._analyze_stability(window_results)

        return {
            "window_results": window_results,
            "stability_analysis": stability_analysis,
            "optimization_time": elapsed,
        }

    def _analyze_stability(self, window_results: List[Dict]) -> Dict:
        """分析参数稳定性"""
        if not window_results:
            return {}

        # 统计各参数的出现频率
        param_counts = {}
        for result in window_results:
            for param, value in result["best_params"].items():
                if param not in param_counts:
                    param_counts[param] = {}
                if value not in param_counts[param]:
                    param_counts[param][value] = 0
                param_counts[param][value] += 1

        # 计算各窗口的测试性能
        test_scores = [r["test_metrics"].get("sharpe_ratio", 0) for r in window_results]

        return {
            "param_stability": {
                param: max(counts.values()) / len(window_results)
                for param, counts in param_counts.items()
            },
            "test_score_mean": np.mean(test_scores),
            "test_score_std": np.std(test_scores),
            "test_score_min": np.min(test_scores),
            "test_score_max": np.max(test_scores),
        }


# ============== 便捷函数 ==============

def optimize_strategy(
    strategy_fn: Callable,
    param_space: Dict[str, Union[List, Tuple]],
    method: str = "grid",
    **kwargs,
) -> OptimizationResult:
    """
    便捷优化函数

    Args:
        strategy_fn: 策略函数
        param_space: 参数空间
        method: "grid", "bayesian", or "walkforward"
        **kwargs: 优化器特定参数

    Example:
        >>> result = optimize_strategy(
        ...     strategy_fn=my_strategy,
        ...     param_space={"lookback": [5, 10, 20]},
        ...     method="grid",
        ...     n_jobs=4,
        ... )
    """
    if method == "grid":
        optimizer = GridSearchOptimizer(strategy_fn, param_space)
        return optimizer.optimize(**kwargs)
    elif method == "bayesian":
        optimizer = BayesianOptimizer(strategy_fn, param_space)
        return optimizer.optimize(**kwargs)
    elif method == "walkforward":
        optimizer = WalkForwardOptimizer(strategy_fn, param_space)
        return optimizer.optimize(**kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    # 测试
    print("Testing VectorBT Optimizer...")

    # 示例策略函数
    def dummy_strategy(lookback: int = 20, threshold: float = 0.1, **kwargs):
        """示例策略，返回模拟指标"""
        return {
            "sharpe_ratio": np.random.randn() * 0.5 + 1.0,
            "total_return": np.random.randn() * 0.1 + 0.2,
            "max_drawdown": np.random.randn() * 0.05 + 0.15,
        }

    # 测试网格搜索
    optimizer = GridSearchOptimizer(
        strategy_fn=dummy_strategy,
        param_space={
            "lookback": [5, 10, 20],
            "threshold": [0.05, 0.1, 0.2],
        },
        metric="sharpe_ratio",
    )

    result = optimizer.optimize(n_jobs=1, verbose=False)
    print(f"Best params: {result.best_params}")
    print(f"Best score: {result.best_score:.4f}")
    print(f"Optimization time: {result.optimization_time:.2f}s")

    print("\nOptimizer module loaded successfully")
