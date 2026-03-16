"""
机器学习流程集成测试
"""
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.strategies.ml_prediction.xgboost_model import XGBoostPricePredictor
from projects.quant_trading.strategies.ml_prediction.lstm_model import LSTMPricePredictor
from projects.quant_trading.strategies.ml_prediction.feature_engineering import FeatureEngineer


@pytest.mark.integration
class TestFeatureEngineering:
    """测试特征工程"""

    def test_feature_creation(self):
        """测试特征创建"""
        # 创建样本数据
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame({
            "open": np.random.randn(100).cumsum() + 100,
            "high": np.random.randn(100).cumsum() + 101,
            "low": np.random.randn(100).cumsum() + 99,
            "close": np.random.randn(100).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 100),
        }, index=dates)

        engineer = FeatureEngineer()
        features = engineer.create_features(data)

        # 验证特征被创建
        assert len(features) > 0
        assert "returns" in features.columns or "ma5" in features.columns

    def test_feature_cleaning(self):
        """测试特征清洗"""
        # 创建含有NaN的数据
        dates = pd.date_range("2023-01-01", periods=50, freq="B")
        data = pd.DataFrame({
            "close": [np.nan] * 5 + list(np.random.randn(45).cumsum() + 100),
            "vol": list(np.random.randint(100000, 1000000, 50)),
        }, index=dates)

        engineer = FeatureEngineer()
        cleaned = engineer.clean_features(data)

        # 验证NaN被处理
        assert cleaned.isna().sum().sum() == 0

    def test_feature_scaling(self):
        """测试特征缩放"""
        dates = pd.date_range("2023-01-01", periods=50, freq="B")
        data = pd.DataFrame({
            "feature1": np.random.randn(50) * 100 + 1000,
            "feature2": np.random.randn(50) * 0.01 + 0.1,
        }, index=dates)

        engineer = FeatureEngineer()
        scaled = engineer.scale_features(data)

        # 验证缩放后数据范围
        assert scaled["feature1"].std() < data["feature1"].std()


@pytest.mark.integration
class TestXGBoostModel:
    """测试XGBoost模型"""

    def test_model_initialization(self):
        """测试模型初始化"""
        model = XGBoostPricePredictor(
            lookback_window=20,
            prediction_horizon=5
        )

        assert model.lookback_window == 20
        assert model.prediction_horizon == 5
        assert model.model is None

    def test_data_preparation(self):
        """测试数据准备"""
        model = XGBoostPricePredictor()

        # 创建样本数据
        dates = pd.date_range("2023-01-01", periods=200, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(200).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 200),
        }, index=dates)

        X, y = model.prepare_data(data)

        assert X is not None
        assert y is not None
        assert len(X) == len(y)

    def test_model_training(self):
        """测试模型训练"""
        model = XGBoostPricePredictor(
            lookback_window=10,
            prediction_horizon=1,
            n_estimators=10  # 减少树的数量加快测试
        )

        # 创建样本数据
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 100),
        }, index=dates)

        metrics = model.train(data, test_size=0.2)

        assert model.model is not None
        assert "train_rmse" in metrics or "mse" in metrics

    def test_prediction(self):
        """测试预测"""
        model = XGBoostPricePredictor(
            lookback_window=10,
            prediction_horizon=1,
            n_estimators=5
        )

        # 创建并训练数据
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        train_data = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 100),
        }, index=dates)

        model.train(train_data)

        # 预测
        test_data = train_data.tail(15)
        prediction = model.predict(test_data)

        assert prediction is not None
        assert isinstance(prediction, (float, np.ndarray))

    def test_model_save_load(self):
        """测试模型保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            model = XGBoostPricePredictor(
                lookback_window=10,
                n_estimators=5
            )

            # 训练模型
            dates = pd.date_range("2023-01-01", periods=100, freq="B")
            data = pd.DataFrame({
                "close": np.random.randn(100).cumsum() + 100,
            }, index=dates)

            model.train(data)

            # 保存模型
            model_path = Path(tmpdir) / "test_model.json"
            model.save(str(model_path))

            assert model_path.exists()

            # 加载模型
            new_model = XGBoostPricePredictor()
            new_model.load(str(model_path))

            assert new_model.model is not None


@pytest.mark.integration
class TestLSTMModel:
    """测试LSTM模型"""

    def test_model_initialization(self):
        """测试模型初始化"""
        model = LSTMPricePredictor(
            lookback_window=20,
            prediction_horizon=5,
            lstm_units=32
        )

        assert model.lookback_window == 20
        assert model.lstm_units == 32
        assert model.model is None

    def test_sequence_creation(self):
        """测试序列创建"""
        model = LSTMPricePredictor(lookback_window=10, prediction_horizon=1)

        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100,
        }, index=dates)

        X, y = model.create_sequences(data["close"].values)

        assert X is not None
        assert y is not None
        assert X.shape[0] == y.shape[0]
        assert X.shape[1] == 10  # lookback_window

    def test_model_training(self):
        """测试模型训练"""
        model = LSTMPricePredictor(
            lookback_window=10,
            prediction_horizon=1,
            lstm_units=16,  # 减少单元数加快测试
            epochs=2  # 减少轮数加快测试
        )

        dates = pd.date_range("2023-01-01", periods=150, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(150).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 150),
        }, index=dates)

        history = model.train(data, test_size=0.2)

        assert model.model is not None
        assert history is not None

    def test_prediction(self):
        """测试预测"""
        model = LSTMPricePredictor(
            lookback_window=10,
            prediction_horizon=1,
            lstm_units=16,
            epochs=2
        )

        dates = pd.date_range("2023-01-01", periods=150, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(150).cumsum() + 100,
        }, index=dates)

        model.train(data)

        prediction = model.predict(data)

        assert prediction is not None
        assert len(prediction) > 0


@pytest.mark.integration
class TestMLPipelineIntegration:
    """测试ML管道集成"""

    def test_end_to_end_pipeline(self):
        """测试端到端流程"""
        # 1. 创建特征
        dates = pd.date_range("2023-01-01", periods=200, freq="B")
        raw_data = pd.DataFrame({
            "open": np.random.randn(200).cumsum() + 100,
            "high": np.random.randn(200).cumsum() + 101,
            "low": np.random.randn(200).cumsum() + 99,
            "close": np.random.randn(200).cumsum() + 100,
            "vol": np.random.randint(100000, 1000000, 200),
        }, index=dates)

        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data)

        # 2. 训练XGBoost模型
        xgb_model = XGBoostPricePredictor(
            lookback_window=20,
            prediction_horizon=1,
            n_estimators=10
        )

        metrics = xgb_model.train(features)

        # 3. 验证模型性能
        assert "train_rmse" in metrics or "mse" in metrics

    def test_feature_model_compatibility(self):
        """测试特征与模型兼容性"""
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100,
        }, index=dates)

        engineer = FeatureEngineer()
        features = engineer.create_features(data)

        model = XGBoostPricePredictor(lookback_window=10, n_estimators=5)
        X, y = model.prepare_data(features)

        # 验证特征维度匹配
        assert X.shape[0] > 0
        assert X.shape[1] > 0
        assert len(X) == len(y)

    def test_prediction_signal_generation(self):
        """测试预测信号生成"""
        dates = pd.date_range("2023-01-01", periods=150, freq="B")
        data = pd.DataFrame({
            "close": np.linspace(100, 120, 150) + np.random.randn(150) * 2,
            "vol": np.random.randint(100000, 1000000, 150),
        }, index=dates)

        model = XGBoostPricePredictor(
            lookback_window=10,
            prediction_horizon=1,
            n_estimators=5
        )

        model.train(data)

        # 生成交易信号
        latest_data = data.tail(15)
        prediction = model.predict(latest_data)
        current_price = latest_data["close"].iloc[-1]

        # 根据预测生成信号
        if prediction > current_price * 1.01:  # 预测上涨超过1%
            signal = 1  # 买入
        elif prediction < current_price * 0.99:  # 预测下跌超过1%
            signal = -1  # 卖出
        else:
            signal = 0  # 持有

        assert signal in [-1, 0, 1]
