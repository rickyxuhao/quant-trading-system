"""
并行回测模块

支持多进程并行参数扫描和回测。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from functools import partial
from multiprocessing import Pool, cpu_count
import multiprocessing as mp

from projects.quant_trading.backtest.engine import BacktestEngine, BacktestConfig
from projects.quant_trading.backtest.strategy import BaseStrategy

logger = logging.getLogger(__name__)


def _run_single_backtest(
    params: Dict[str, Any],
    config_template: BacktestConfig,
    strategy_factory: Callable[[Dict[str, Any]], BaseStrategy],
) -> Dict[str, Any]:
    """运行单个回测任务（用于多进程）

    Args:
        params: 策略参数字典
        config_template: 回测配置模板
        strategy_factory: 策略工厂函数

    Returns:
        回测结果字典
    """
    try:
        # 创建策略实例
        strategy = strategy_factory(params)

        # 创建引擎
        engine = BacktestEngine(config_template, strategy)

        # 运行回测
        results = engine.run()

        return {
            "params": params,
            "success": True,
            "results": results,
            "metrics": results.get("metrics", {}),
        }

    except Exception as e:
        logger.error(f"Backtest failed for params {params}: {e}")
        return {
            "params": params,
            "success": False,
            "error": str(e),
        }


def run_parallel_backtests(
    param_grid: List[Dict[str, Any]],
    config: BacktestConfig,
    strategy_factory: Callable[[Dict[str, Any]], BaseStrategy],
    n_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """并行运行多组参数回测

    Args:
        param_grid: 参数组合列表
        config: 回测配置模板
        strategy_factory: 策略工厂函数，接收参数返回策略实例
        n_workers: 并行工作进程数，默认使用CPU核心数

    Returns:
        回测结果列表

    Example:
        >>> param_grid = [
        ...     {"ma_short": 5, "ma_long": 20},
        ...     {"ma_short": 10, "ma_long": 30},
        ... ]
        >>> def factory(params):
        ...     return MAStrategy(**params)
        >>> results = run_parallel_backtests(param_grid, config, factory)
    """
    if n_workers is None:
        n_workers = min(cpu_count(), len(param_grid))

    n_workers = max(1, min(n_workers, len(param_grid)))

    logger.info(f"Running {len(param_grid)} backtests with {n_workers} workers")

    if n_workers == 1:
        # 单进程模式
        results = [
            _run_single_backtest(params, config, strategy_factory)
            for params in param_grid
        ]
        return results

    # 多进程模式
    with Pool(n_workers) as pool:
        results = pool.map(
            partial(_run_single_backtest, config_template=config, strategy_factory=strategy_factory),
            param_grid,
        )

    logger.info(f"Parallel backtests completed: {len([r for r in results if r['success']])}/{len(results)} successful")

    return results


class ParallelBacktestRunner:
    """并行回测运行器

    提供更灵活的并行回测控制。

    Example:
        >>> runner = ParallelBacktestRunner(max_workers=4)
        >>> runner.add_task(params1, config1, strategy1)
        >>> runner.add_task(params2, config2, strategy2)
        >>> results = runner.run_all()
    """

    def __init__(self, max_workers: Optional[int] = None):
        """初始化运行器

        Args:
            max_workers: 最大工作进程数
        """
        self.max_workers = max_workers or cpu_count()
        self._tasks: List[Dict[str, Any]] = []
        self._results: List[Dict[str, Any]] = []

    def add_task(
        self,
        params: Dict[str, Any],
        config: BacktestConfig,
        strategy_factory: Callable[[Dict[str, Any]], BaseStrategy],
    ):
        """添加回测任务

        Args:
            params: 策略参数
            config: 回测配置
            strategy_factory: 策略工厂函数
        """
        self._tasks.append({
            "params": params,
            "config": config,
            "strategy_factory": strategy_factory,
        })

    def run_all(self) -> List[Dict[str, Any]]:
        """运行所有任务

        Returns:
            回测结果列表
        """
        if not self._tasks:
            logger.warning("No tasks to run")
            return []

        # 按配置分组，相同配置的任务可以并行
        results = []

        for task in self._tasks:
            result = _run_single_backtest(
                task["params"],
                task["config"],
                task["strategy_factory"],
            )
            results.append(result)

        self._results = results
        return results

    def run_parallel(self) -> List[Dict[str, Any]]:
        """并行运行所有任务

        Returns:
            回测结果列表
        """
        if not self._tasks:
            logger.warning("No tasks to run")
            return []

        n_workers = min(self.max_workers, len(self._tasks))

        with Pool(n_workers) as pool:
            results = pool.starmap(
                _run_single_backtest_wrapper,
                [(t["params"], t["config"], t["strategy_factory"]) for t in self._tasks],
            )

        self._results = results
        return results

    def get_best_result(self, metric: str = "sharpe_ratio") -> Optional[Dict[str, Any]]:
        """获取最佳结果

        Args:
            metric: 评价指标

        Returns:
            最佳结果字典
        """
        if not self._results:
            return None

        successful = [r for r in self._results if r.get("success")]
        if not successful:
            return None

        # 按指标排序
        def get_metric(result):
            metrics = result.get("results", {}).get("metrics", {})
            if hasattr(metrics, metric):
                return getattr(metrics, metric)
            return metrics.get(metric, float("-inf"))

        return max(successful, key=get_metric)

    def clear_tasks(self):
        """清空任务列表"""
        self._tasks.clear()
        self._results.clear()


def _run_single_backtest_wrapper(
    params: Dict[str, Any],
    config: BacktestConfig,
    strategy_factory: Callable[[Dict[str, Any]], BaseStrategy],
) -> Dict[str, Any]:
    """包装函数用于starmap"""
    return _run_single_backtest(params, config, strategy_factory)
