"""
ML策略回测接口（预留）

展示如何将ML模型接入现有回测框架。
继承BaseStrategy，实现generate_signals方法。

Example:
    >>> from projects.portfolio_analysis.ml import MLStrategy
    >>> strategy = MLStrategy(model_path="models/xgboost_model.pkl")
    >>> signals = strategy.generate_signals(data, current_date, available_stocks)
"""

import os
import pickle
import logging
from abc import abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.strategy import BaseStrategy, Signal, SignalType
from projects.quant_trading.backtest.data_manager import DataManager

logger = logging.getLogger(__name__)


class MLStrategy(BaseStrategy):
    """
    ML策略基类（预留接口）

    展示如何将ML模型接入现有回测框架。

    Attributes:
        model: ML模型实例
        feature_cols: 特征列名列表
        confidence_threshold: 信号置信度阈值

    Example:
        >>> strategy = MLStrategy(model_path="models/lgb_model.pkl")
        >>> signals = strategy.generate_signals(data, date, stocks)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        name: str = "MLStrategy",
        confidence_threshold: float = 0.7,
        top_k: int = 10
    ):
        """初始化ML策略

        Args:
            model_path: 模型文件路径
            name: 策略名称
            confidence_threshold: 信号置信度阈值
            top_k: 选股数量
        """
        super().__init__(name)
        self.model = None
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.top_k = top_k
        self.feature_cols: List[str] = []
        self.scaler = None

        if model_path and os.path.exists(model_path):
            self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """加载ML模型

        Args:
            model_path: 模型文件路径
        """
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)

            if isinstance(model_data, dict):
                self.model = model_data.get('model')
                self.scaler = model_data.get('scaler')
                self.feature_cols = model_data.get('feature_cols', [])
            else:
                self.model = model_data

            logger.info(f"模型已加载: {model_path}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def generate_signals(
        self,
        data: Dict[str, "pd.DataFrame"],
        current_date: datetime,
        available_stocks: List[str]
    ) -> List[Signal]:
        """生成交易信号

        Args:
            data: 历史数据字典 {ts_code: DataFrame}
            current_date: 当前日期
            available_stocks: 当日可交易股票列表

        Returns:
            交易信号列表
        """
        if self.model is None:
            logger.warning("模型未加载，返回空信号")
            return []

        signals = []
        predictions = []

        for ts_code in available_stocks:
            if ts_code not in data:
                continue

            try:
                # 准备特征
                features = self._extract_features(data[ts_code], current_date)

                if features is None or len(features) == 0:
                    continue

                # 模型预测
                score = self._predict(features)

                if score > self.confidence_threshold:
                    predictions.append({
                        'ts_code': ts_code,
                        'score': score,
                        'features': features
                    })

            except Exception as e:
                logger.debug(f"预测失败 {ts_code}: {e}")
                continue

        # 按得分排序，取Top K
        predictions.sort(key=lambda x: x['score'], reverse=True)
        top_predictions = predictions[:self.top_k]

        # 生成信号
        total_score = sum(p['score'] for p in top_predictions)

        for pred in top_predictions:
            weight = pred['score'] / total_score if total_score > 0 else 1.0 / len(top_predictions)

            signals.append(Signal(
                ts_code=pred['ts_code'],
                signal_type=SignalType.BUY,
                score=pred['score'],
                weight=min(weight, 0.3),  # 单只最大30%权重
                reason=f"ML预测得分: {pred['score']:.3f}",
                timestamp=current_date,
                meta={
                    'model_name': self.name,
                    'features': pred['features'].to_dict() if isinstance(pred['features'], pd.Series) else {}
                }
            ))

        logger.info(f"ML策略生成 {len(signals)} 个信号")
        return signals

    @abstractmethod
    def _extract_features(
        self,
        df: pd.DataFrame,
        current_date: datetime
    ) -> Optional[pd.Series]:
        """提取特征

        Args:
            df: 股票历史数据
            current_date: 当前日期

        Returns:
            特征向量
        """
        raise NotImplementedError("子类必须实现 _extract_features 方法")

    def _predict(self, features: pd.Series) -> float:
        """模型预测

        Args:
            features: 特征向量

        Returns:
            预测得分 (0-1)
        """
        try:
            # 标准化
            if self.scaler is not None:
                features_scaled = self.scaler.transform([features.values])
                prediction = self.model.predict_proba(features_scaled)[0][1]
            else:
                prediction = self.model.predict_proba([features.values])[0][1]

            return float(prediction)
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return 0.0

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, **kwargs) -> None:
        """训练模型（预留接口）

        Args:
            X_train: 训练特征
            y_train: 训练标签
            **kwargs: 其他参数
        """
        raise NotImplementedError("子类必须实现 train 方法")

    def save_model(self, model_path: str) -> None:
        """保存模型

        Args:
            model_path: 保存路径
        """
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_cols': self.feature_cols,
            'created_at': datetime.now().isoformat()
        }

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"模型已保存: {model_path}")


class FeatureEngine:
    """特征工程工具

    提供常用的股票特征计算方法。
    """

    @staticmethod
    def calculate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标特征

        Args:
            df: 股票数据，需包含close, high, low, volume等列

        Returns:
            包含技术特征的DataFrame
        """
        df = df.copy()

        # 收益率特征
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_20d'] = df['close'].pct_change(20)

        # 波动率特征
        df['volatility_20d'] = df['close'].pct_change().rolling(20).std()

        # 移动平均线
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()

        # 均线位置
        df['close_to_ma5'] = df['close'] / df['ma_5'] - 1
        df['close_to_ma20'] = df['close'] / df['ma_20'] - 1
        df['ma5_to_ma20'] = df['ma_5'] / df['ma_20'] - 1

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # 成交量特征
        df['volume_ma20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']

        # 振幅
        df['amplitude'] = (df['high'] - df['low']) / df['close']

        return df

    @staticmethod
    def calculate_fundamental_features(
        pe: Optional[float] = None,
        pb: Optional[float] = None,
        roe: Optional[float] = None,
        debt_ratio: Optional[float] = None
    ) -> Dict[str, float]:
        """计算基本面特征

        Args:
            pe: 市盈率
            pb: 市净率
            roe: 净资产收益率
            debt_ratio: 负债率

        Returns:
            基本面特征字典
        """
        features = {}

        # 估值特征
        if pe is not None:
            features['pe'] = pe
            features['pe_rank'] = 0.5  # 需要历史数据计算分位

        if pb is not None:
            features['pb'] = pb
            features['pb_rank'] = 0.5

        # 质量特征
        if roe is not None:
            features['roe'] = roe

        if debt_ratio is not None:
            features['debt_ratio'] = debt_ratio

        return features


class ExampleMLStrategy(MLStrategy):
    """示例ML策略

    展示如何实现具体的ML策略。
    使用简单的技术指标作为特征。
    """

    def __init__(self, model_path: Optional[str] = None):
        """初始化示例策略"""
        super().__init__(model_path, name="ExampleMLStrategy")
        self.feature_engine = FeatureEngine()
        self.feature_cols = [
            'return_1d', 'return_5d', 'return_20d', 'volatility_20d',
            'close_to_ma5', 'close_to_ma20', 'rsi', 'volume_ratio'
        ]

    def _extract_features(
        self,
        df: pd.DataFrame,
        current_date: datetime
    ) -> Optional[pd.Series]:
        """提取技术指标特征

        Args:
            df: 股票历史数据
            current_date: 当前日期

        Returns:
            特征向量
        """
        # 计算技术指标
        df_features = self.feature_engine.calculate_technical_features(df)

        # 获取最新数据
        current_data = df_features[df_features.index <= current_date]

        if len(current_data) < 60:  # 需要足够的历史数据
            return None

        latest = current_data.iloc[-1]

        try:
            features = latest[self.feature_cols]
            return features.fillna(0)
        except KeyError:
            return None

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, **kwargs) -> None:
        """训练示例模型（使用RandomForest）

        Args:
            X_train: 训练特征
            y_train: 训练标签
            **kwargs: 其他参数
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler

            # 标准化
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X_train)

            # 训练模型
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                **kwargs
            )
            self.model.fit(X_scaled, y_train)

            logger.info("模型训练完成")

        except ImportError:
            logger.error("scikit-learn未安装，无法训练模型")
            raise


class DeepLearningStrategy(MLStrategy):
    """深度学习策略（预留）

    展示如何集成深度学习模型（如LSTM、Transformer）。
    """

    def __init__(self, model_path: Optional[str] = None):
        """初始化深度学习策略"""
        super().__init__(model_path, name="DeepLearningStrategy")
        self.sequence_length = 60  # 序列长度

    def _extract_features(
        self,
        df: pd.DataFrame,
        current_date: datetime
    ) -> Optional[pd.Series]:
        """提取序列特征

        Args:
            df: 股票历史数据
            current_date: 当前日期

        Returns:
            特征向量（或序列）
        """
        # 筛选日期之前的数据
        current_data = df[df.index <= current_date]

        if len(current_data) < self.sequence_length:
            return None

        # 取最近N天的数据作为序列
        sequence = current_data.iloc[-self.sequence_length:]

        # 这里可以返回序列给LSTM等模型
        # 简化处理，返回最后一天的数据
        return sequence.iloc[-1][['close', 'volume', 'high', 'low']]

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, **kwargs) -> None:
        """训练深度学习模型（预留）

        Args:
            X_train: 训练特征（序列数据）
            y_train: 训练标签
            **kwargs: 其他参数
        """
        # 这里可以实现PyTorch/TensorFlow模型训练
        logger.info("深度学习模型训练（预留接口）")
        pass


def create_training_data(
    data_manager: DataManager,
    stock_list: List[str],
    start_date: datetime,
    end_date: datetime,
    label_days: int = 5
) -> pd.DataFrame:
    """创建训练数据

    Args:
        data_manager: 数据管理器
        stock_list: 股票列表
        start_date: 开始日期
        end_date: 结束日期
        label_days: 标签计算天数（未来N天收益）

    Returns:
        训练数据DataFrame
    """
    records = []
    feature_engine = FeatureEngine()

    for ts_code in stock_list:
        try:
            df = data_manager.get_stock_data(ts_code, start_date, end_date)

            if len(df) < 60:
                continue

            # 计算特征
            df_features = feature_engine.calculate_technical_features(df)

            # 计算标签（未来N天收益）
            df_features['future_return'] = df_features['close'].shift(-label_days) / df_features['close'] - 1
            df_features['label'] = (df_features['future_return'] > 0).astype(int)

            # 添加股票代码
            df_features['ts_code'] = ts_code

            # 删除NaN
            df_clean = df_features.dropna()

            records.append(df_clean)

        except Exception as e:
            logger.warning(f"处理 {ts_code} 失败: {e}")
            continue

    if not records:
        return pd.DataFrame()

    return pd.concat(records, ignore_index=True)


if __name__ == "__main__":
    # 测试ML策略
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("ML策略接口测试")
    print("=" * 60)

    # 创建示例策略
    strategy = ExampleMLStrategy()

    print(f"\n策略名称: {strategy.get_name()}")
    print(f"特征列: {strategy.feature_cols}")

    # 测试特征提取
    import pandas as pd
    import numpy as np

    # 生成测试数据
    dates = pd.date_range('2024-01-01', '2024-06-30', freq='B')
    test_df = pd.DataFrame({
        'open': 10 + np.random.randn(len(dates)).cumsum() * 0.5,
        'high': 10.5 + np.random.randn(len(dates)).cumsum() * 0.5,
        'low': 9.5 + np.random.randn(len(dates)).cumsum() * 0.5,
        'close': 10 + np.random.randn(len(dates)).cumsum() * 0.5,
        'volume': np.random.randint(100000, 1000000, len(dates))
    }, index=dates)

    features = strategy._extract_features(test_df, dates[-1])
    print(f"\n提取的特征: {features.to_dict() if features is not None else 'None'}")

    print("\n✅ ML策略接口测试完成")
    print("\n提示: 实际使用前需要:")
    print("  1. 准备历史数据进行模型训练")
    print("  2. 训练并保存模型文件")
    print("  3. 在策略初始化时加载模型")
