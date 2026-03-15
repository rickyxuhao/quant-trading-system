"""
LSTM模型实现 - 时序预测

功能：
- 滚动窗口训练
- 时序交叉验证
- 防止未来信息泄露
"""

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import (
    LSTM, Dense, Dropout, BatchNormalization,
    Input, Bidirectional, Attention, Concatenate
)
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.optimizers import Adam

from core.logger import get_logger

logger = get_logger(__name__)

# 设置TensorFlow日志级别
tf.get_logger().setLevel('ERROR')


@dataclass
class LSTMConfig:
    """LSTM模型配置"""
    # 网络结构
    lstm_units: List[int] = None  # 每层的单元数
    num_layers: int = 2
    dropout_rate: float = 0.2
    use_bidirectional: bool = False
    use_attention: bool = False

    # 训练参数
    batch_size: int = 32
    epochs: int = 100
    learning_rate: float = 0.001
    early_stopping_patience: int = 10
    reduce_lr_patience: int = 5

    # 序列参数
    sequence_length: int = 20  # 输入序列长度
    prediction_horizon: int = 1  # 预测未来天数

    def __post_init__(self):
        if self.lstm_units is None:
            self.lstm_units = [64, 32]


class LSTMModel:
    """LSTM预测模型"""

    def __init__(self, config: Optional[LSTMConfig] = None, model_path: Optional[str] = None):
        self.config = config or LSTMConfig()
        self.model: Optional[Model] = None
        self.history = None
        self.feature_names: List[str] = []

        if model_path and Path(model_path).exists():
            self.load(model_path)

    def build_model(self, num_features: int, num_outputs: int = 1) -> Model:
        """
        构建LSTM模型

        Args:
            num_features: 输入特征数量
            num_outputs: 输出维度 (1为回归, >1为分类)
        """
        inputs = Input(shape=(self.config.sequence_length, num_features))

        x = inputs

        # LSTM层
        for i, units in enumerate(self.config.lstm_units):
            return_sequences = (i < len(self.config.lstm_units) - 1) or self.config.use_attention

            if self.config.use_bidirectional:
                x = Bidirectional(
                    LSTM(units, return_sequences=return_sequences)
                )(x)
            else:
                x = LSTM(units, return_sequences=return_sequences)(x)

            x = BatchNormalization()(x)
            x = Dropout(self.config.dropout_rate)(x)

        # Attention机制
        if self.config.use_attention:
            attention = Attention()([x, x])
            x = tf.reduce_mean(attention, axis=1)
        else:
            # 如果只有一个LSTM层且不需要attention
            if len(self.config.lstm_units) == 1 and not self.config.use_bidirectional:
                x = tf.squeeze(x, axis=1) if len(x.shape) > 2 else x

        # 输出层
        if num_outputs == 1:
            outputs = Dense(1, activation='linear', name='output')(x)
            loss = 'mse'
            metrics = ['mae']
        else:
            # 分类任务
            outputs = Dense(num_outputs, activation='softmax', name='output')(x)
            loss = 'sparse_categorical_crossentropy'
            metrics = ['accuracy']

        model = Model(inputs=inputs, outputs=outputs)

        optimizer = Adam(learning_rate=self.config.learning_rate)
        model.compile(optimizer=optimizer, loss=loss, metrics=metrics)

        self.model = model
        logger.info(f"LSTM模型构建完成: {num_features}特征 -> {num_outputs}输出")

        return model

    def prepare_sequences(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        sequence_length: Optional[int] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        准备序列数据

        Args:
            X: 特征DataFrame
            y: 目标Series
            sequence_length: 序列长度

        Returns:
            (X_seq, y_seq)
        """
        seq_len = sequence_length or self.config.sequence_length

        X_values = X.values
        sequences = []
        targets = []

        for i in range(len(X_values) - seq_len + 1):
            seq = X_values[i:i + seq_len]
            sequences.append(seq)

            if y is not None:
                targets.append(y.iloc[i + seq_len - 1])

        X_seq = np.array(sequences)
        y_seq = np.array(targets) if y is not None else None

        return X_seq, y_seq

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        verbose: int = 1
    ) -> Dict:
        """
        训练模型

        Args:
            X_train: 训练特征
            y_train: 训练目标
            X_val: 验证特征
            y_val: 验证目标
            verbose: 日志级别

        Returns:
            训练历史
        """
        self.feature_names = X_train.columns.tolist()

        # 准备序列数据
        X_train_seq, y_train_seq = self.prepare_sequences(X_train, y_train)

        if X_val is not None and y_val is not None:
            X_val_seq, y_val_seq = self.prepare_sequences(X_val, y_val)
            validation_data = (X_val_seq, y_val_seq)
        else:
            validation_data = None

        # 确定输出维度
        num_features = X_train.shape[1]
        num_outputs = len(np.unique(y_train)) if y_train.dtype == int else 1

        # 构建模型
        if self.model is None:
            self.build_model(num_features, num_outputs)

        # 回调函数
        callbacks = []

        if validation_data is not None:
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=self.config.early_stopping_patience,
                restore_best_weights=True,
                verbose=verbose
            )
            callbacks.append(early_stopping)

            reduce_lr = ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=self.config.reduce_lr_patience,
                min_lr=1e-6,
                verbose=verbose
            )
            callbacks.append(reduce_lr)

        # 训练
        logger.info(f"开始训练: {len(X_train_seq)}个序列样本")

        self.history = self.model.fit(
            X_train_seq, y_train_seq,
            batch_size=self.config.batch_size,
            epochs=self.config.epochs,
            validation_data=validation_data,
            callbacks=callbacks,
            verbose=verbose
        )

        # 训练总结
        final_loss = self.history.history['loss'][-1]
        logger.info(f"训练完成. Final loss: {final_loss:.4f}")

        if validation_data is not None:
            val_loss = self.history.history['val_loss'][-1]
            logger.info(f"Validation loss: {val_loss:.4f}")

        return self.history.history

    def predict(self, X: pd.DataFrame, return_confidence: bool = False) -> np.ndarray:
        """
        预测

        Args:
            X: 特征DataFrame
            return_confidence: 是否返回置信度

        Returns:
            预测结果
        """
        if self.model is None:
            raise ValueError("模型未训练")

        X_seq, _ = self.prepare_sequences(X)

        if len(X_seq) == 0:
            return np.array([])

        predictions = self.model.predict(X_seq, verbose=0)

        if return_confidence and predictions.shape[-1] > 1:
            # 返回分类概率作为置信度
            return predictions

        return predictions.flatten()

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        评估模型

        Returns:
            评估指标字典
        """
        X_seq, y_seq = self.prepare_sequences(X_test, y_test)

        if len(X_seq) == 0:
            return {}

        results = self.model.evaluate(X_seq, y_seq, verbose=0)

        metrics = {}
        for i, metric_name in enumerate(self.model.metrics_names):
            metrics[metric_name] = results[i]

        # 额外计算方向准确率
        predictions = self.predict(X_test)
        if len(predictions) == len(y_seq):
            if y_test.dtype == int or len(np.unique(y_test)) <= 3:
                # 分类任务
                pred_classes = np.sign(predictions) if predictions.dtype == float else predictions
                actual_classes = y_seq
                metrics['direction_accuracy'] = np.mean(pred_classes == actual_classes)
            else:
                # 回归任务 - 计算方向准确率
                pred_direction = np.sign(predictions)
                actual_direction = np.sign(y_seq)
                metrics['direction_accuracy'] = np.mean(pred_direction == actual_direction)

        return metrics

    def rolling_window_train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        window_size: int = 252 * 3,  # 3年训练窗口
        step_size: int = 63,  # 季度滚动
        min_train_size: int = 252
    ) -> List[Dict]:
        """
        滚动窗口训练

        Returns:
            各窗口的训练结果列表
        """
        results = []
        n = len(X)

        start_idx = min_train_size

        while start_idx + window_size < n:
            train_end = start_idx
            test_end = min(start_idx + window_size, n)

            logger.info(f"滚动窗口训练: {X.index[start_idx]} - {X.index[test_end-1]}")

            X_train = X.iloc[start_idx - min_train_size:start_idx]
            y_train = y.iloc[start_idx - min_train_size:start_idx]
            X_test = X.iloc[start_idx:test_end]
            y_test = y.iloc[start_idx:test_end]

            # 重新初始化模型
            self.model = None
            self.fit(X_train, y_train, verbose=0)

            # 评估
            metrics = self.evaluate(X_test, y_test)
            metrics['window_start'] = str(X.index[start_idx])
            metrics['window_end'] = str(X.index[test_end-1])

            results.append(metrics)

            start_idx += step_size

        return results

    def save(self, path: str) -> None:
        """保存模型"""
        if self.model is None:
            raise ValueError("模型未训练")

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save(path)

        # 保存配置
        config_path = Path(path).with_suffix('.config.pkl')
        import pickle
        with open(config_path, 'wb') as f:
            pickle.dump({
                'config': self.config,
                'feature_names': self.feature_names
            }, f)

        logger.info(f"模型已保存到: {path}")

    def load(self, path: str) -> None:
        """加载模型"""
        self.model = load_model(path)

        # 加载配置
        config_path = Path(path).with_suffix('.config.pkl')
        if config_path.exists():
            import pickle
            with open(config_path, 'rb') as f:
                data = pickle.load(f)
                self.config = data['config']
                self.feature_names = data['feature_names']

        logger.info(f"模型已从{path}加载")
