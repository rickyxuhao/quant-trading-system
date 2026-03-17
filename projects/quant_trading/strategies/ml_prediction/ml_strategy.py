"""
机器学习策略 - Backtrader集成

功能：
- 接收模型预测信号
- 信号生成与置信度阈值
- 回测与评估
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import backtrader as bt
import numpy as np
import pandas as pd

from core.logger import get_logger
from projects.quant_trading.strategies.base_strategy import BaseStrategy, StrategyConfig

from .feature_engineering import FeatureEngineer, TechnicalFeatureConfig
from .lstm_model import LSTMModel, LSTMConfig
from .xgboost_model import XGBoostModel, XGBoostConfig

logger = get_logger(__name__)


@dataclass
class MLStrategyConfig(StrategyConfig):
    """ML策略配置"""

    # 信号阈值
    confidence_threshold: float = 0.6  # 最小置信度
    long_threshold: float = 0.55  # 做多阈值 (概率 > 0.55)
    short_threshold: float = 0.45  # 做空阈值 (概率 < 0.45)

    # 仓位管理
    position_size_pct: float = 0.1  # 仓位占比
    max_positions: int = 5  # 最大持仓数

    # 模型更新
    retrain_frequency: int = 63  # 每63天重新训练
    min_train_samples: int = 252  # 最小训练样本数

    # 预测目标
    prediction_horizon: int = 1  # 预测未来1天
    target_type: str = "direction"  # 'direction', 'return', 'quantile'


class MLStrategy(BaseStrategy):
    """
    机器学习预测策略

    集成LSTM或XGBoost模型进行交易信号生成
    """

    params = (
        ("config", None),
        ("model_type", "xgboost"),  # 'xgboost' 或 'lstm'
        ("model_path", None),  # 预训练模型路径
        ("verbose", False),
    )

    def __init__(self):
        super().__init__()

        self.ml_config = self.p.config or MLStrategyConfig()
        self.config = self.ml_config

        # 初始化特征工程器
        self.feature_engineer = FeatureEngineer(
            tech_config=TechnicalFeatureConfig(), lookback_window=20
        )

        # 初始化模型
        self.model: Optional[Union[XGBoostModel, LSTMModel]] = None
        self._init_model()

        # 数据缓存
        self.price_history = []
        self.feature_history = None
        self.prediction_history = []

        # 训练状态
        self.last_train_date = None
        self.days_since_train = 0

    def _init_model(self):
        """初始化模型"""
        if self.p.model_path and Path(self.p.model_path).exists():
            # 加载预训练模型
            if self.p.model_type == "xgboost":
                self.model = XGBoostModel(model_path=self.p.model_path)
            else:
                self.model = LSTMModel(model_path=self.p.model_path)
            logger.info(f"已加载预训练模型: {self.p.model_path}")
        else:
            # 创建新模型
            if self.p.model_type == "xgboost":
                xgb_config = XGBoostConfig(prediction_horizon=self.ml_config.prediction_horizon)
                self.model = XGBoostModel(config=xgb_config)
            else:
                lstm_config = LSTMConfig(prediction_horizon=self.ml_config.prediction_horizon)
                self.model = LSTMModel(config=lstm_config)

    def next(self):
        """核心交易逻辑"""
        # 收集当前bar数据
        current_data = {
            "open": self.data.open[0],
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": self.data.close[0],
            "volume": self.data.volume[0],
        }
        self.price_history.append(current_data)

        # 数据不足时跳过
        if len(self.price_history) < self.ml_config.min_train_samples:
            return

        # 定期重新训练
        if self.days_since_train >= self.ml_config.retrain_frequency:
            self._retrain_model()

        # 生成特征
        features = self._generate_features()
        if features is None or len(features) == 0:
            return

        # 模型预测
        prediction, confidence = self._predict(features)
        if prediction is None:
            return

        self.prediction_history.append(
            {
                "date": self.data.datetime.date(0),
                "prediction": prediction,
                "confidence": confidence,
                "price": self.data.close[0],
            }
        )

        # 根据预测执行交易
        self._execute_trade(prediction, confidence)

        self.days_since_train += 1

    def _generate_features(self) -> Optional[pd.DataFrame]:
        """生成特征"""
        try:
            df = pd.DataFrame(self.price_history)
            df.index = pd.date_range(end=self.data.datetime.date(0), periods=len(df), freq="D")

            features = self.feature_engineer.create_features(df)

            # 保存特征历史供LSTM使用
            self.feature_history = features.copy()

            # 只取最新的一行用于预测 (XGBoost使用)
            if len(features) > 0:
                return features.iloc[[-1]]

        except Exception as e:
            logger.error(f"特征生成失败: {e}")

        return None

    def _predict(self, features: pd.DataFrame):
        """
        模型预测

        Returns:
            (prediction, confidence)
        """
        if self.model is None or self.model.model is None:
            return None, 0

        try:
            if isinstance(self.model, XGBoostModel):
                # XGBoost预测 - 只需要单行特征
                if self.ml_config.target_type == "direction":
                    proba = self.model.predict(features, return_proba=True)
                    if proba is not None and len(proba[0]) == 3:
                        # 三分类: 跌, 平, 涨 (注意: XGBoost输出是映射后的标签 0,1,2)
                        pred_class = np.argmax(proba[0])  # 0, 1, 2
                        prediction = pred_class - 1  # 映射回 -1, 0, 1
                        confidence = np.max(proba[0])
                    else:
                        prediction = self.model.predict(features)[0]
                        confidence = 0.5
                else:
                    prediction = self.model.predict(features)[0]
                    confidence = 0.5

            elif isinstance(self.model, LSTMModel):
                # LSTM预测 - 需要序列数据
                # features 只包含最新一行，但LSTM需要 sequence_length 行历史
                # 从 feature_history 获取最后 sequence_length 行
                seq_len = self.model.config.sequence_length
                if self.feature_history is not None and len(self.feature_history) >= seq_len:
                    # 使用最后 seq_len 行特征进行预测
                    lstm_features = self.feature_history.iloc[-seq_len:]
                    predictions = self.model.predict(lstm_features)
                    if len(predictions) > 0:
                        prediction = predictions[-1]  # 取最后一个预测值
                        # 对于分类任务
                        if self.ml_config.target_type == "direction":
                            proba = self.model.predict(lstm_features, return_confidence=True)
                            if proba is not None and len(proba) > 0:
                                confidence = np.max(proba[-1])
                            else:
                                confidence = 0.5
                        else:
                            confidence = abs(prediction) if prediction != 0 else 0.5
                    else:
                        return None, 0
                else:
                    # 数据不足，无法预测
                    return None, 0

            else:
                return None, 0

            return prediction, confidence

        except Exception as e:
            logger.error(f"预测失败: {e}")
            return None, 0

    def _execute_trade(self, prediction: float, confidence: float):
        """执行交易"""
        # 检查置信度
        if confidence < self.ml_config.confidence_threshold:
            return

        current_position = self.position.size

        # 信号解释
        if self.ml_config.target_type == "direction":
            # 分类信号
            if prediction > 0 and confidence > self.ml_config.long_threshold:
                signal = "long"
            elif prediction < 0 and confidence > (1 - self.ml_config.short_threshold):
                signal = "short"
            else:
                signal = "neutral"
        else:
            # 回归信号
            if prediction > 0.01:  # 预期收益 > 1%
                signal = "long"
            elif prediction < -0.01:
                signal = "short"
            else:
                signal = "neutral"

        # 执行交易
        if signal == "long":
            if current_position <= 0:  # 空仓或空头，平仓并开多
                if current_position < 0:
                    self.close()
                size = self.calculate_position_size(self.data, self.ml_config.position_size_pct)
                if size > 0:
                    self.buy(size=size)
                    self.log(f"买入信号: 预测={prediction:.3f}, 置信度={confidence:.3f}")

        elif signal == "short":
            if current_position >= 0:  # 空仓或多仓，平仓并开空
                if current_position > 0:
                    self.close()
                size = self.calculate_position_size(self.data, self.ml_config.position_size_pct)
                if size > 0:
                    self.sell(size=size)
                    self.log(f"卖出信号: 预测={prediction:.3f}, 置信度={confidence:.3f}")

        elif signal == "neutral" and current_position != 0:
            # 平仓
            self.close()
            self.log(f"平仓信号: 预测={prediction:.3f}")

    def _retrain_model(self):
        """重新训练模型"""
        logger.info(f"开始重新训练模型: {self.data.datetime.date(0)}")

        try:
            # 准备训练数据
            df = pd.DataFrame(self.price_history)
            df.index = pd.date_range(end=self.data.datetime.date(0), periods=len(df), freq="D")

            # 特征工程
            features = self.feature_engineer.create_features(df)
            if len(features) < self.ml_config.min_train_samples:
                logger.warning("训练数据不足")
                return

            # 创建目标
            target = self.feature_engineer.create_target(
                features,
                horizon=self.ml_config.prediction_horizon,
                target_type=self.ml_config.target_type,
            )

            # 数据划分
            split_ratio = 0.8
            train_size = int(len(features) * split_ratio)

            X_train = features.iloc[:train_size]
            y_train = target.iloc[:train_size]
            X_val = features.iloc[train_size:]
            y_val = target.iloc[train_size:]

            # 移除NaN
            train_mask = y_train.notna()
            X_train = X_train[train_mask]
            y_train = y_train[train_mask]

            val_mask = y_val.notna()
            X_val = X_val[val_mask]
            y_val = y_val[val_mask]

            if len(X_train) < 100 or len(X_val) < 20:
                logger.warning("有效训练样本不足")
                return

            # 训练模型
            self.model.fit(X_train, y_train, X_val, y_val, verbose=False)

            # 更新训练状态
            self.last_train_date = self.data.datetime.date(0)
            self.days_since_train = 0

            logger.info("模型重新训练完成")

        except Exception as e:
            logger.error(f"模型训练失败: {e}")

    def stop(self):
        """策略结束"""
        # 保存预测历史
        if self.prediction_history:
            pred_df = pd.DataFrame(self.prediction_history)
            pred_df.to_csv("ml_prediction_history.csv", index=False)
            logger.info(f"预测历史已保存: {len(pred_df)}条记录")

        # 保存模型
        if self.model and self.model.model is not None:
            if self.p.model_type == "xgboost":
                model_path = f"ml_model_{self.p.model_type}.json"
            else:
                model_path = f"ml_model_{self.p.model_type}.keras"
            self.model.save(model_path)

        super().stop()


def create_ml_backtest(
    data_feed: bt.feeds.PandasData,
    model_type: str = "xgboost",
    initial_capital: float = 1_000_000,
    **kwargs,
) -> bt.Cerebro:
    """
    创建ML策略回测

    Args:
        data_feed: 数据feed
        model_type: 'xgboost' 或 'lstm'
        initial_capital: 初始资金
        **kwargs: 其他配置参数

    Returns:
        Cerebro实例
    """
    from projects.quant_trading.strategies.base_strategy import create_cerebro

    config = MLStrategyConfig(initial_capital=initial_capital, **kwargs)

    cerebro = create_cerebro(config)
    cerebro.adddata(data_feed)
    cerebro.addstrategy(MLStrategy, config=config, model_type=model_type)

    return cerebro
