"""
横截面机器学习策略 - 多股票预测和选股

功能：
- 批量预测股票池收益
- 横截面排名选股
- 多模型集成（XGBoost + LSTM）
- 市场状态自适应
- 多horizon预测
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from core.logger import get_logger
from projects.quant_trading.backtest.data_manager import DataManager

# ML模型
from .xgboost_model import XGBoostModel, XGBoostConfig

# LSTM模型使用延迟导入以避免TensorFlow加载问题
LSTMModel = None
LSTMConfig = None

def _import_lstm():
    global LSTMModel, LSTMConfig
    if LSTMModel is None:
        from .lstm_model import LSTMModel as _LSTMModel, LSTMConfig as _LSTMConfig
        LSTMModel = _LSTMModel
        LSTMConfig = _LSTMConfig
    return LSTMModel, LSTMConfig

# 特征工程
from .cross_sectional_features import (
    CrossSectionalFeatureEngineer,
    CrossSectionalFeatureConfig,
    FactorPipeline,
    create_standard_pipeline,
)

# 股票池选择
from .universe_selector import (
    UniverseConfig,
    DynamicUniverseSelector,
    create_all_a_share_universe,
)

# 市场状态
from .regime_detector import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeConfig,
)

logger = get_logger(__name__)


@dataclass
class CrossSectionalConfig:
    """横截面策略配置"""

    # 股票池配置
    universe_config: UniverseConfig = field(
        default_factory=lambda: create_all_a_share_universe()
    )

    # 特征配置
    feature_config: CrossSectionalFeatureConfig = field(
        default_factory=CrossSectionalFeatureConfig
    )

    # 模型配置
    use_xgboost: bool = True
    use_lstm: bool = False  # 默认禁用LSTM以避免TensorFlow加载
    use_ensemble: bool = True

    # XGBoost配置
    xgboost_config: XGBoostConfig = field(default_factory=XGBoostConfig)

    # LSTM配置 (延迟加载)
    lstm_config: Optional[Any] = None

    # 集成权重
    xgboost_weight: float = 0.6
    lstm_weight: float = 0.4

    # 预测horizon（多周期）
    prediction_horizons: List[int] = field(default_factory=lambda: [1, 5, 10])
    horizon_weights: List[float] = field(default_factory=lambda: [0.5, 0.3, 0.2])

    # 选股配置
    top_n_stocks: int = 30  # 选股数量
    min_prediction_confidence: float = 0.1

    # 训练配置
    train_lookback_days: int = 252 * 2  # 2年训练数据
    retrain_frequency: int = 63  # 季度重训练
    min_train_samples: int = 252  # 最少训练样本

    # 市场状态配置
    use_regime_switching: bool = True
    regime_config: RegimeConfig = field(default_factory=RegimeConfig)


@dataclass
class PredictionResult:
    """预测结果"""

    ts_code: str
    predicted_return: float
    confidence: float
    model_type: str
    horizon: int
    features: Optional[Dict[str, float]] = None


class RegimeSpecificModel:
    """
    状态特定模型

    为不同市场状态训练独立的模型
    """

    def __init__(self, base_config: CrossSectionalConfig):
        self.base_config = base_config
        self.models: Dict[MarketRegime, Dict[str, Any]] = {}
        self.regime_detector = MarketRegimeDetector(base_config.regime_config)

    def train_for_regime(
        self,
        regime: MarketRegime,
        features: pd.DataFrame,
        targets: pd.Series,
    ) -> None:
        """为特定状态训练模型"""
        if len(features) < self.base_config.min_train_samples:
            logger.warning(f"Insufficient samples for {regime.value} regime")
            return

        models = {}

        # 训练XGBoost
        if self.base_config.use_xgboost:
            xgb_model = XGBoostModel(config=self.base_config.xgboost_config)
            split_point = int(len(features) * 0.8)

            xgb_model.fit(
                features.iloc[:split_point],
                targets.iloc[:split_point],
                features.iloc[split_point:],
                targets.iloc[split_point:],
                verbose=False,
            )
            models["xgboost"] = xgb_model

        # 训练LSTM
        if self.base_config.use_lstm:
            LSTMModelClass, LSTMConfigClass = _import_lstm()
            lstm_config = self.base_config.lstm_config or LSTMConfigClass()
            lstm_model = LSTMModelClass(config=lstm_config)
            split_point = int(len(features) * 0.8)

            lstm_model.fit(
                features.iloc[:split_point],
                targets.iloc[:split_point],
                features.iloc[split_point:],
                targets.iloc[split_point:],
                verbose=0,
            )
            models["lstm"] = lstm_model

        self.models[regime] = models
        logger.info(f"Trained models for {regime.value} regime")

    def predict(
        self,
        regime: MarketRegime,
        features: pd.DataFrame,
    ) -> Optional[np.ndarray]:
        """使用状态特定模型预测"""
        if regime not in self.models:
            # 使用正常状态模型或最近的状态模型
            regime = MarketRegime.NORMAL

        if regime not in self.models:
            return None

        models = self.models[regime]
        predictions = []
        weights = []

        # XGBoost预测
        if "xgboost" in models:
            pred = models["xgboost"].predict(features)
            predictions.append(pred)
            weights.append(self.base_config.xgboost_weight)

        # LSTM预测
        if "lstm" in models:
            pred = models["lstm"].predict(features)
            predictions.append(pred)
            weights.append(self.base_config.lstm_weight)

        if not predictions:
            return None

        # 加权平均
        weights = np.array(weights) / sum(weights)
        ensemble_pred = sum(w * p for w, p in zip(weights, predictions))

        return ensemble_pred

    def save(self, path: str) -> None:
        """保存模型"""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        for regime, models in self.models.items():
            regime_path = save_path / regime.value
            regime_path.mkdir(exist_ok=True)

            for model_name, model in models.items():
                model_path = regime_path / f"{model_name}.pkl"
                model.save(str(model_path))

    def load(self, path: str) -> None:
        """加载模型"""
        load_path = Path(path)

        for regime in MarketRegime:
            regime_path = load_path / regime.value
            if not regime_path.exists():
                continue

            models = {}

            # 加载XGBoost
            xgb_path = regime_path / "xgboost.pkl"
            if xgb_path.exists() and self.base_config.use_xgboost:
                models["xgboost"] = XGBoostModel(model_path=str(xgb_path))

            # 加载LSTM
            lstm_path = regime_path / "lstm.keras"
            if lstm_path.exists() and self.base_config.use_lstm:
                LSTMModelClass, _ = _import_lstm()
                models["lstm"] = LSTMModelClass(model_path=str(lstm_path))

            if models:
                self.models[regime] = models


class CrossSectionalMLStrategy:
    """
    横截面机器学习策略

    对股票池进行批量预测，选股并生成权重
    """

    def __init__(
        self,
        config: Optional[CrossSectionalConfig] = None,
        data_manager: Optional[DataManager] = None,
    ):
        self.config = config or CrossSectionalConfig()
        self.data_manager = data_manager or DataManager()

        # 组件初始化
        self.feature_engineer = CrossSectionalFeatureEngineer(
            config=self.config.feature_config,
            data_manager=self.data_manager,
        )

        self.universe_selector = DynamicUniverseSelector(
            config=self.config.universe_config,
            data_manager=self.data_manager,
            rebalance_frequency=self.config.universe_config.rebalance_frequency,
        )

        self.regime_detector = MarketRegimeDetector(self.config.regime_config)

        # 模型
        self.regime_model: Optional[RegimeSpecificModel] = None
        self.global_xgboost: Optional[XGBoostModel] = None
        self.global_lstm: Optional[Any] = None

        # 数据处理
        self.scaler = StandardScaler()
        self.pipeline: FactorPipeline = create_standard_pipeline()

        # 状态
        self._last_train_date: Optional[datetime] = None
        self._prediction_cache: Dict[str, pd.DataFrame] = {}

        logger.info("CrossSectionalMLStrategy initialized")

    def train(
        self,
        start_date: datetime,
        end_date: datetime,
        use_regime_specific: bool = True,
    ) -> None:
        """
        训练模型

        Args:
            start_date: 训练开始日期
            end_date: 训练结束日期
            use_regime_specific: 是否训练状态特定模型
        """
        logger.info(f"Training models from {start_date} to {end_date}")

        # 准备训练数据
        training_data = self._prepare_training_data(start_date, end_date)

        if training_data is None or len(training_data) < self.config.min_train_samples:
            logger.error("Insufficient training data")
            return

        features = training_data["features"]
        targets = training_data["targets"]
        regimes = training_data.get("regimes")

        if use_regime_specific and self.config.use_regime_switching:
            # 训练状态特定模型
            self.regime_model = RegimeSpecificModel(self.config)

            for regime in MarketRegime:
                if regime == MarketRegime.UNKNOWN:
                    continue

                # 筛选该状态下的数据
                if regimes is not None:
                    mask = regimes == regime
                    regime_features = features[mask]
                    regime_targets = targets[mask]

                    if len(regime_features) > self.config.min_train_samples:
                        self.regime_model.train_for_regime(
                            regime, regime_features, regime_targets
                        )
        else:
            # 训练全局模型
            self._train_global_models(features, targets)

        self._last_train_date = end_date
        logger.info("Model training completed")

    def predict(
        self,
        date: datetime,
        stock_pool: Optional[List[str]] = None,
        return_features: bool = False,
    ) -> pd.DataFrame:
        """
        预测股票池收益

        Args:
            date: 预测日期
            stock_pool: 股票池（None则使用配置的股票池）
            return_features: 是否返回特征

        Returns:
            预测结果DataFrame
        """
        # 获取股票池
        if stock_pool is None:
            stock_pool = self.universe_selector.get_universe(date)

        if not stock_pool:
            logger.warning(f"Empty stock pool on {date}")
            return pd.DataFrame()

        # 生成特征
        features_df = self.feature_engineer.create_features_for_universe(
            date, stock_pool
        )

        if features_df.empty:
            logger.warning(f"No features generated for {date}")
            return pd.DataFrame()

        # 预处理特征
        processed_features = self.pipeline.process(features_df)

        # 检测市场状态
        current_regime = self._detect_current_regime(date)

        # 预测
        predictions = self._make_prediction(
            processed_features, current_regime, date
        )

        if predictions is None:
            return pd.DataFrame()

        # 构建结果
        results = pd.DataFrame(
            {
                "ts_code": processed_features.index,
                "predicted_return": predictions,
                "prediction_date": date,
                "regime": current_regime.value,
            }
        )

        # 计算置信度（基于历史预测准确率）
        results["confidence"] = self._calculate_confidence(predictions)

        # 添加特征（可选）
        if return_features:
            for col in processed_features.columns:
                results[f"feature_{col}"] = processed_features[col].values

        return results.sort_values("predicted_return", ascending=False)

    def select_stocks(
        self,
        date: datetime,
        top_n: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> List[str]:
        """
        选股

        Args:
            date: 选股日期
            top_n: 选股数量
            min_confidence: 最小置信度

        Returns:
            选中的股票代码列表
        """
        top_n = top_n or self.config.top_n_stocks
        min_confidence = min_confidence or self.config.min_prediction_confidence

        # 预测
        predictions = self.predict(date)

        if predictions.empty:
            return []

        # 过滤低置信度
        predictions = predictions[predictions["confidence"] >= min_confidence]

        # 选择Top N
        selected = predictions.head(top_n)["ts_code"].tolist()

        logger.info(f"Selected {len(selected)} stocks on {date.strftime('%Y%m%d')}")

        return selected

    def generate_portfolio_weights(
        self,
        date: datetime,
        selected_stocks: List[str],
        method: str = "score_weighted",
    ) -> Dict[str, float]:
        """
        生成组合权重

        Args:
            date: 日期
            selected_stocks: 选中的股票
            method: 权重方法（equal, score_weighted, risk_parity）

        Returns:
            权重字典
        """
        if not selected_stocks:
            return {}

        predictions = self.predict(date, selected_stocks)

        if predictions.empty:
            return {stock: 1.0 / len(selected_stocks) for stock in selected_stocks}

        # 转换为字典
        pred_dict = predictions.set_index("ts_code")["predicted_return"].to_dict()

        if method == "equal":
            weights = {stock: 1.0 / len(selected_stocks) for stock in selected_stocks}

        elif method == "score_weighted":
            # 基于预测分数加权
            scores = np.array([max(0, pred_dict.get(stock, 0)) for stock in selected_stocks])

            if scores.sum() > 0:
                weights_array = scores / scores.sum()
            else:
                weights_array = np.ones(len(selected_stocks)) / len(selected_stocks)

            weights = {stock: weights_array[i] for i, stock in enumerate(selected_stocks)}

        elif method == "rank_weighted":
            # 基于排名加权（降序排名）
            sorted_stocks = sorted(
                selected_stocks,
                key=lambda s: pred_dict.get(s, 0),
                reverse=True,
            )

            # 使用倒数排名加权
            ranks = np.arange(len(sorted_stocks), 0, -1)
            weights_array = ranks / ranks.sum()

            weights = {stock: weights_array[i] for i, stock in enumerate(sorted_stocks)}

        else:
            weights = {stock: 1.0 / len(selected_stocks) for stock in selected_stocks}

        return weights

    def _prepare_training_data(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """准备训练数据"""
        # 获取交易日历
        try:
            trade_dates = self.data_manager.get_trade_dates(start_date, end_date)
        except Exception as e:
            logger.error(f"Failed to get trade dates: {e}")
            return None

        if len(trade_dates) < self.config.min_train_samples:
            logger.error(f"Insufficient trade dates: {len(trade_dates)}")
            return None

        all_features = []
        all_targets = []
        all_regimes = []

        # 采样训练日期（每周一次以减少计算量）
        sample_dates = trade_dates[::5]  # 每5个交易日采样一次

        for date in sample_dates:
            try:
                # 获取股票池
                stock_pool = self.universe_selector.get_universe(date)

                if not stock_pool:
                    continue

                # 生成特征
                features_df = self.feature_engineer.create_features_for_universe(
                    date, stock_pool
                )

                if features_df.empty:
                    continue

                # 生成目标（未来收益）
                targets = self._generate_targets(
                    date, features_df.index.tolist()
                )

                if targets.empty:
                    continue

                # 对齐特征和目标
                common_idx = features_df.index.intersection(targets.index)
                features_df = features_df.loc[common_idx]
                targets = targets.loc[common_idx]

                if len(features_df) < 10:  # 最少需要10只股票
                    continue

                # 预处理
                processed_features = self.pipeline.process(features_df)

                # 检测市场状态
                regime = self._detect_current_regime(date)

                all_features.append(processed_features)
                all_targets.append(targets)
                all_regimes.extend([regime] * len(processed_features))

            except Exception as e:
                logger.debug(f"Error preparing data for {date}: {e}")
                continue

        if not all_features:
            return None

        # 合并数据
        combined_features = pd.concat(all_features, ignore_index=True)
        combined_targets = pd.concat(all_targets, ignore_index=True)

        return {
            "features": combined_features,
            "targets": combined_targets,
            "regimes": pd.Series(all_regimes) if all_regimes else None,
        }

    def _generate_targets(
        self, date: datetime, stock_pool: List[str], horizon: int = 5
    ) -> pd.Series:
        """生成训练目标（未来收益）

        使用次日开盘价作为基准价格，避免T+0执行偏差。
        计算公式：future_close[horizon] / open[1] - 1
        """
        try:
            # 获取未来价格，留出足够时间
            future_date = date + pd.Timedelta(days=horizon * 2)

            batch_data = self.data_manager.get_batch_stock_data(
                stock_pool, date, future_date, adjust=True
            )

            targets = pd.Series(index=stock_pool, dtype=float)

            for ts_code, df in batch_data.items():
                if df.empty:
                    continue

                # 确定基准价格：优先使用次日开盘价（index 1），避免T+0偏差
                current_price = None
                if "adj_open" in df.columns and len(df) > 1:
                    open_val = df["adj_open"].iloc[1]
                    if open_val > 0:
                        current_price = open_val
                elif "open" in df.columns and len(df) > 1:
                    open_val = df["open"].iloc[1]
                    if open_val > 0:
                        current_price = open_val

                # 回退到当日收盘价
                if current_price is None:
                    if "adj_close" in df.columns and len(df) > 0:
                        current_price = df["adj_close"].iloc[0]
                    elif "close" in df.columns and len(df) > 0:
                        current_price = df["close"].iloc[0]

                if current_price is None or current_price <= 0:
                    continue

                # 计算horizon日后的收益（基于收盘价）
                close_col = "adj_close" if "adj_close" in df.columns else "close"
                if close_col not in df.columns or len(df) <= 1:
                    continue

                closes = df[close_col]
                future_idx = min(horizon, len(closes) - 1)
                future_price = closes.iloc[future_idx]

                targets[ts_code] = future_price / current_price - 1

            return targets.dropna()

        except Exception as e:
            logger.error(f"Error generating targets: {e}")
            return pd.Series()

    def _detect_current_regime(self, date: datetime) -> MarketRegime:
        """检测当前市场状态"""
        try:
            # 获取市场指数数据
            lookback_start = date - pd.Timedelta(days=120)
            df = self.data_manager.get_index_data("000300.SH", lookback_start, date)

            if df.empty or "close" not in df.columns:
                return MarketRegime.NORMAL

            regime, _ = self.regime_detector.detect_regime(df["close"], date)
            return regime

        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return MarketRegime.NORMAL

    def _train_global_models(
        self, features: pd.DataFrame, targets: pd.Series
    ) -> None:
        """训练全局模型"""
        split_point = int(len(features) * 0.8)

        # 训练XGBoost
        if self.config.use_xgboost:
            logger.info("Training global XGBoost model")
            self.global_xgboost = XGBoostModel(config=self.config.xgboost_config)
            self.global_xgboost.fit(
                features.iloc[:split_point],
                targets.iloc[:split_point],
                features.iloc[split_point:],
                targets.iloc[split_point:],
                verbose=False,
            )

        # 训练LSTM
        if self.config.use_lstm:
            logger.info("Training global LSTM model")
            LSTMModelClass, LSTMConfigClass = _import_lstm()
            lstm_config = self.config.lstm_config or LSTMConfigClass()
            self.global_lstm = LSTMModelClass(config=lstm_config)
            self.global_lstm.fit(
                features.iloc[:split_point],
                targets.iloc[:split_point],
                features.iloc[split_point:],
                targets.iloc[split_point:],
                verbose=0,
            )

    def _make_prediction(
        self,
        features: pd.DataFrame,
        regime: MarketRegime,
        date: datetime,
    ) -> Optional[np.ndarray]:
        """执行预测"""
        predictions = []
        weights = []

        # 尝试使用状态特定模型
        if self.regime_model and self.config.use_regime_switching:
            pred = self.regime_model.predict(regime, features)
            if pred is not None:
                return pred

        # 使用全局模型
        if self.global_xgboost and self.config.use_xgboost:
            try:
                pred = self.global_xgboost.predict(features)
                predictions.append(pred)
                weights.append(self.config.xgboost_weight)
            except Exception as e:
                logger.warning(f"XGBoost prediction error: {e}")

        if self.global_lstm and self.config.use_lstm:
            try:
                pred = self.global_lstm.predict(features)
                predictions.append(pred)
                weights.append(self.config.lstm_weight)
            except Exception as e:
                logger.warning(f"LSTM prediction error: {e}")

        if not predictions:
            return None

        # 加权集成
        weights = np.array(weights) / sum(weights)
        ensemble_pred = sum(w * p for w, p in zip(weights, predictions))

        return ensemble_pred

    def _calculate_confidence(self, predictions: np.ndarray) -> np.ndarray:
        """计算预测置信度"""
        # 简单实现：基于预测值的绝对值
        # 预测值越大（绝对值），置信度越高
        abs_pred = np.abs(predictions)
        confidence = np.minimum(abs_pred / abs_pred.std(), 1.0)
        return confidence

    def should_retrain(self, current_date: datetime) -> bool:
        """判断是否需要重训练"""
        if self._last_train_date is None:
            return True

        days_since_train = (current_date - self._last_train_date).days
        return days_since_train >= self.config.retrain_frequency

    def save(self, path: str) -> None:
        """保存模型"""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        if self.regime_model:
            self.regime_model.save(str(save_path / "regime_models"))

        logger.info(f"Models saved to {path}")

    def load(self, path: str) -> None:
        """加载模型"""
        load_path = Path(path)

        if (load_path / "regime_models").exists():
            self.regime_model = RegimeSpecificModel(self.config)
            self.regime_model.load(str(load_path / "regime_models"))

        logger.info(f"Models loaded from {path}")
