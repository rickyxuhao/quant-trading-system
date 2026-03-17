"""
机器学习预测策略包 - LSTM/XGBoost价格预测模型

包含模块：
- feature_engineering: 特征工程
- model_trainer: 模型训练管道
- lstm_model: LSTM模型实现
- xgboost_model: XGBoost模型实现
- ml_strategy: Backtrader集成策略
"""

from .feature_engineering import FeatureEngineer, TechnicalFeatureConfig
from .xgboost_model import XGBoostModel, XGBoostConfig

# Lazy imports for TensorFlow-dependent modules
def __getattr__(name):
    if name in ("LSTMModel", "LSTMConfig"):
        from .lstm_model import LSTMModel, LSTMConfig
        return locals()[name]
    if name in ("MLStrategy", "MLStrategyConfig"):
        from .ml_strategy import MLStrategy, MLStrategyConfig
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "FeatureEngineer",
    "TechnicalFeatureConfig",
    "LSTMModel",
    "LSTMConfig",
    "XGBoostModel",
    "XGBoostConfig",
    "MLStrategy",
    "MLStrategyConfig",
]
