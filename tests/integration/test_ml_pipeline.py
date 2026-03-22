"""
机器学习流程集成测试
"""

import pytest

import pandas as pd
import numpy as np

from projects.quant_trading.strategies.ml_prediction.feature_engineering import FeatureEngineer

try:
    from projects.quant_trading.strategies.ml_prediction.lstm_model import LSTMPricePredictor
    HAS_LSTM = True
except Exception:
    LSTMPricePredictor = None  # type: ignore
    HAS_LSTM = False


@pytest.mark.integration
class TestFeatureEngineering:
    """测试特征工程"""

    def test_feature_creation(self):
        """测试特征创建"""
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame(
            {
                "open": np.random.randn(100).cumsum() + 100,
                "high": np.random.randn(100).cumsum() + 101,
                "low": np.random.randn(100).cumsum() + 99,
                "close": np.random.randn(100).cumsum() + 100,
                "volume": np.random.randint(100000, 1000000, 100).astype(float),
            },
            index=dates,
        )

        engineer = FeatureEngineer()
        features = engineer.create_features(data)

        assert len(features) > 0
        assert features.shape[1] > 0

    def test_feature_dropna(self):
        """验证 create_features 内部自动去除 NaN"""
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame(
            {
                "open": np.random.randn(100).cumsum() + 100,
                "high": np.random.randn(100).cumsum() + 101,
                "low": np.random.randn(100).cumsum() + 99,
                "close": np.random.randn(100).cumsum() + 100,
                "volume": np.random.randint(100000, 1000000, 100).astype(float),
            },
            index=dates,
        )

        engineer = FeatureEngineer()
        features = engineer.create_features(data)

        # create_features calls dropna() internally
        assert features.isna().sum().sum() == 0

    def test_feature_has_numeric_columns(self):
        """验证特征列均为数值型"""
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame(
            {
                "open": np.random.randn(100).cumsum() + 100,
                "high": np.random.randn(100).cumsum() + 101,
                "low": np.random.randn(100).cumsum() + 99,
                "close": np.random.randn(100).cumsum() + 100,
                "volume": np.random.randint(100000, 1000000, 100).astype(float),
            },
            index=dates,
        )

        engineer = FeatureEngineer()
        features = engineer.create_features(data)

        numeric_cols = features.select_dtypes(include=[np.number]).columns
        assert len(numeric_cols) > 0



@pytest.mark.integration
@pytest.mark.skipif(not HAS_LSTM, reason="TensorFlow not available (NumPy compat issue)")
class TestLSTMModel:
    """测试LSTM模型"""

    def test_model_initialization(self):
        """测试模型初始化"""
        model = LSTMPricePredictor(lookback_window=20, prediction_horizon=5, lstm_units=32)

        assert model.lookback_window == 20
        assert model.lstm_units == 32
        assert model.model is None

    def test_sequence_creation(self):
        """测试序列创建"""
        model = LSTMPricePredictor(lookback_window=10, prediction_horizon=1)

        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        data = pd.DataFrame(
            {
                "close": np.random.randn(100).cumsum() + 100,
            },
            index=dates,
        )

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
            epochs=2,  # 减少轮数加快测试
        )

        dates = pd.date_range("2023-01-01", periods=150, freq="B")
        data = pd.DataFrame(
            {
                "close": np.random.randn(150).cumsum() + 100,
                "vol": np.random.randint(100000, 1000000, 150),
            },
            index=dates,
        )

        history = model.train(data, test_size=0.2)

        assert model.model is not None
        assert history is not None

    def test_prediction(self):
        """测试预测"""
        model = LSTMPricePredictor(
            lookback_window=10, prediction_horizon=1, lstm_units=16, epochs=2
        )

        dates = pd.date_range("2023-01-01", periods=150, freq="B")
        data = pd.DataFrame(
            {
                "close": np.random.randn(150).cumsum() + 100,
            },
            index=dates,
        )

        model.train(data)

        prediction = model.predict(data)

        assert prediction is not None
        assert len(prediction) > 0


@pytest.mark.integration
class TestMLPipelineIntegration:
    """测试ML管道集成"""

    def test_end_to_end_pipeline(self):
        """测试端到端流程"""
        # 创建特征并验证输出非空
        dates = pd.date_range("2023-01-01", periods=200, freq="B")
        raw_data = pd.DataFrame(
            {
                "open": np.random.randn(200).cumsum() + 100,
                "high": np.random.randn(200).cumsum() + 101,
                "low": np.random.randn(200).cumsum() + 99,
                "close": np.random.randn(200).cumsum() + 100,
                "volume": np.random.randint(100000, 1000000, 200).astype(float),
            },
            index=dates,
        )

        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data)

        assert len(features) > 0
        assert features.shape[1] > 0
