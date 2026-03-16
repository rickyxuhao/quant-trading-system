"""
性能优化模块

提供回测性能优化功能，包括并行回测、缓存优化等。
"""
from .parallel import run_parallel_backtests, ParallelBacktestRunner
from .cache import CacheManager, cached
from .vectorized import VectorizedBacktester

__all__ = [
    "run_parallel_backtests",
    "ParallelBacktestRunner",
    "CacheManager",
    "cached",
    "VectorizedBacktester",
]
