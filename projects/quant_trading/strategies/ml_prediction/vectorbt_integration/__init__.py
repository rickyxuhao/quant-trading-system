"""
VectorBT 集成模块

集成 vectorbt 的高性能回测和优化功能：
1. 参数优化（贝叶斯优化、超参搜索）
2. Walk-forward 分析（滚动回测）

与现有回测引擎的关系：
- vectorbt 用于快速参数扫描和优化
- 最终策略使用现有 BacktestEngine 进行精细回测

作者: Claude
创建日期: 2026-03-19
"""

from .optimizer import (
    BayesianOptimizer,
    GridSearchOptimizer,
    WalkForwardOptimizer,
    OptimizationResult,
)

from .walk_forward import (
    WalkForwardAnalyzer,
    WalkForwardConfig,
    RollingWindowSplitter,
)

__all__ = [
    "BayesianOptimizer",
    "GridSearchOptimizer",
    "WalkForwardOptimizer",
    "OptimizationResult",
    "WalkForwardAnalyzer",
    "WalkForwardConfig",
    "RollingWindowSplitter",
]
