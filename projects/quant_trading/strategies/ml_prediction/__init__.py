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
from .lstm_model import LSTMModel, LSTMConfig
from .xgboost_model import XGBoostModel, XGBoostConfig
from .ml_strategy import MLStrategy

__all__ = [
    "FeatureEngineer",
    "TechnicalFeatureConfig",
    "LSTMModel",
    "LSTMConfig",
    "XGBoostModel",
    "XGBoostConfig",
    "MLStrategy",
]
