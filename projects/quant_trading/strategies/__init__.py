"""
策略模块 - 包含各类量化交易策略实现

子模块：
- statistical_arbitrage: 统计套利策略（配对交易）
- ml_prediction: 机器学习预测策略
- trend_following: 趋势跟踪策略
"""

from .base_strategy import BaseStrategy, StrategyConfig

__all__ = ["BaseStrategy", "StrategyConfig"]
