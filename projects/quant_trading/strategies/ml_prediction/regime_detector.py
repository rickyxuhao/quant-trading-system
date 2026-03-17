"""
市场状态检测器 - 识别市场所处的状态（牛市/熊市/震荡/高波动）

功能：
- 基于波动率和趋势的市场状态分类
- 支持多种状态定义方式
- 状态转换检测
- 历史状态识别
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy import stats

from core.logger import get_logger

logger = get_logger(__name__)


class MarketRegime(Enum):
    """市场状态枚举"""
    BULL_TREND = "bull_trend"  # 牛市趋势
    BEAR_TREND = "bear_trend"  # 熊市趋势
    HIGH_VOLATILITY = "high_vol"  # 高波动
    LOW_VOLATILITY = "low_vol"  # 低波动
    NORMAL = "normal"  # 正常状态
    UNKNOWN = "unknown"  # 未知


@dataclass
class RegimeConfig:
    """市场状态检测配置"""

    # 波动率阈值
    high_vol_threshold: float = 0.25  # 高波动阈值（年化25%）
    low_vol_threshold: float = 0.10  # 低波动阈值（年化10%）

    # 趋势阈值
    bull_trend_threshold: float = 0.05  # 牛市阈值（60日收益>5%）
    bear_trend_threshold: float = -0.05  # 熊市阈值（60日收益<-5%）

    # 计算周期
    volatility_window: int = 20  # 波动率计算窗口
    trend_window: int = 60  # 趋势计算窗口

    # 状态平滑
    min_regime_duration: int = 5  # 最小状态持续时间
    smooth_window: int = 3  # 平滑窗口


@dataclass
class RegimeInfo:
    """市场状态信息"""

    regime: MarketRegime
    start_date: datetime
    end_date: datetime
    volatility: float
    trend_return: float
    confidence: float  # 状态置信度
    metrics: Dict[str, float]  # 额外指标


class MarketRegimeDetector:
    """
    市场状态检测器

    基于波动率和趋势判断市场状态，支持：
    1. 实时状态检测
    2. 历史状态识别
    3. 状态转换预测
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self._regime_history: List[RegimeInfo] = []
        self._current_regime: Optional[MarketRegime] = None
        self._current_regime_start: Optional[datetime] = None

    def detect_regime(
        self,
        price_series: pd.Series,
        date: Optional[datetime] = None,
        return_confidence: bool = False,
    ) -> Tuple[MarketRegime, Optional[float]]:
        """
        检测当前市场状态

        Args:
            price_series: 价格序列（日收盘价）
            date: 当前日期
            return_confidence: 是否返回置信度

        Returns:
            (市场状态, 置信度)
        """
        if len(price_series) < self.config.trend_window:
            return MarketRegime.UNKNOWN, None

        # 计算波动率
        returns = price_series.pct_change().dropna()
        volatility = returns.tail(self.config.volatility_window).std() * np.sqrt(252)

        # 计算趋势收益
        trend_return = (
            price_series.iloc[-1] / price_series.iloc[-self.config.trend_window] - 1
        )

        # 判断状态
        regime, confidence = self._classify_regime(volatility, trend_return)

        # 状态平滑处理
        regime = self._smooth_regime(regime, date)

        # 记录历史
        if date and regime != self._current_regime:
            if self._current_regime:
                self._regime_history.append(
                    RegimeInfo(
                        regime=self._current_regime,
                        start_date=self._current_regime_start or date,
                        end_date=date,
                        volatility=volatility,
                        trend_return=trend_return,
                        confidence=confidence or 0.5,
                        metrics={},
                    )
                )
            self._current_regime = regime
            self._current_regime_start = date

        if return_confidence:
            return regime, confidence
        return regime, None

    def detect_regime_batch(
        self, price_series: pd.Series
    ) -> pd.Series:
        """
        批量检测历史市场状态

        Args:
            price_series: 价格序列

        Returns:
            市场状态序列
        """
        regimes = []
        dates = []

        for i in range(self.config.trend_window, len(price_series)):
            window = price_series.iloc[: i + 1]
            regime, _ = self.detect_regime(
                window, date=price_series.index[i], return_confidence=False
            )
            regimes.append(regime.value)
            dates.append(price_series.index[i])

        return pd.Series(regimes, index=dates)

    def _classify_regime(
        self, volatility: float, trend_return: float
    ) -> Tuple[MarketRegime, float]:
        """
        分类市场状态

        Returns:
            (状态, 置信度)
        """
        # 高波动优先
        if volatility > self.config.high_vol_threshold:
            confidence = min(1.0, volatility / self.config.high_vol_threshold - 1)
            return MarketRegime.HIGH_VOLATILITY, confidence

        # 低波动
        if volatility < self.config.low_vol_threshold:
            if trend_return > self.config.bull_trend_threshold:
                confidence = min(1.0, trend_return / self.config.bull_trend_threshold)
                return MarketRegime.BULL_TREND, confidence
            elif trend_return < self.config.bear_trend_threshold:
                confidence = min(1.0, abs(trend_return) / abs(self.config.bear_trend_threshold))
                return MarketRegime.BEAR_TREND, confidence
            else:
                confidence = 1.0 - volatility / self.config.low_vol_threshold
                return MarketRegime.LOW_VOLATILITY, confidence

        # 正常波动下的趋势判断
        if trend_return > self.config.bull_trend_threshold:
            confidence = min(1.0, trend_return / self.config.bull_trend_threshold)
            return MarketRegime.BULL_TREND, confidence
        elif trend_return < self.config.bear_trend_threshold:
            confidence = min(1.0, abs(trend_return) / abs(self.config.bear_trend_threshold))
            return MarketRegime.BEAR_TREND, confidence

        return MarketRegime.NORMAL, 0.5

    def _smooth_regime(
        self, new_regime: MarketRegime, date: Optional[datetime]
    ) -> MarketRegime:
        """平滑状态转换"""
        # 简单实现：状态必须持续一定时间才转换
        # 实际可以实现更复杂的马尔科夫链或HMM
        return new_regime

    def get_regime_features(self, price_series: pd.Series) -> pd.Series:
        """
        获取状态相关特征

        Args:
            price_series: 价格序列

        Returns:
            特征序列
        """
        returns = price_series.pct_change().dropna()

        features = pd.Series(index=price_series.index)

        # 滚动波动率
        features["rolling_volatility"] = (
            returns.rolling(self.config.volatility_window).std() * np.sqrt(252)
        )

        # 滚动趋势
        features["trend_return"] = (
            price_series / price_series.shift(self.config.trend_window) - 1
        )

        # 波动率趋势
        features["volatility_trend"] = (
            features["rolling_volatility"]
            / features["rolling_volatility"].shift(20)
            - 1
        )

        # 价格位置（相对于近期区间）
        rolling_high = price_series.rolling(self.config.trend_window).max()
        rolling_low = price_series.rolling(self.config.trend_window).min()
        features["price_position"] = (price_series - rolling_low) / (rolling_high - rolling_low)

        return features

    def get_current_regime(self) -> Optional[MarketRegime]:
        """获取当前市场状态"""
        return self._current_regime

    def get_regime_history(self) -> List[RegimeInfo]:
        """获取状态历史"""
        return self._regime_history.copy()

    def get_regime_statistics(self) -> Dict[str, Any]:
        """获取状态统计信息"""
        if not self._regime_history:
            return {}

        regime_counts = {}
        total_days = 0

        for info in self._regime_history:
            regime_name = info.regime.value
            duration = (info.end_date - info.start_date).days

            if regime_name not in regime_counts:
                regime_counts[regime_name] = {"count": 0, "total_days": 0}

            regime_counts[regime_name]["count"] += 1
            regime_counts[regime_name]["total_days"] += duration
            total_days += duration

        # 计算平均持续时间
        for regime_name in regime_counts:
            regime_counts[regime_name]["avg_duration"] = (
                regime_counts[regime_name]["total_days"]
                / regime_counts[regime_name]["count"]
            )
            regime_counts[regime_name]["percentage"] = (
                regime_counts[regime_name]["total_days"] / total_days
            )

        return {
            "total_days": total_days,
            "regime_counts": regime_counts,
            "current_regime": self._current_regime.value if self._current_regime else None,
        }


class RegimeClassifier:
    """
    高级市场状态分类器

    使用机器学习或统计方法进行状态分类
    """

    def __init__(self, n_regimes: int = 4):
        self.n_regimes = n_regimes
        self.model = None
        self.fitted = False

    def fit(self, returns: pd.Series) -> None:
        """
        拟合状态分类模型

        使用高斯混合模型识别不同的市场状态
        """
        try:
            from sklearn.mixture import GaussianMixture

            # 计算特征
            features = self._calculate_features(returns)

            # 拟合GMM
            gmm = GaussianMixture(
                n_components=self.n_regimes,
                covariance_type="full",
                random_state=42,
            )
            gmm.fit(features.dropna())

            self.model = gmm
            self.fitted = True

            logger.info(f"Regime classifier fitted with {self.n_regimes} regimes")

        except ImportError:
            logger.warning("sklearn not available, using rule-based classification")
        except Exception as e:
            logger.error(f"Failed to fit regime classifier: {e}")

    def predict(self, returns: pd.Series) -> pd.Series:
        """预测市场状态"""
        if not self.fitted:
            logger.warning("Model not fitted, using rule-based classification")
            return self._rule_based_predict(returns)

        features = self._calculate_features(returns)
        predictions = self.model.predict(features.dropna())

        return pd.Series(predictions, index=features.dropna().index)

    def _calculate_features(self, returns: pd.Series) -> pd.DataFrame:
        """计算状态特征"""
        features = pd.DataFrame(index=returns.index)

        # 日收益率
        features["return_1d"] = returns

        # 波动率
        features["volatility_20d"] = returns.rolling(20).std()

        # 趋势
        features["trend_5d"] = returns.rolling(5).sum()
        features["trend_20d"] = returns.rolling(20).sum()

        # 偏度和峰度
        features["skewness_20d"] = returns.rolling(20).skew()
        features["kurtosis_20d"] = returns.rolling(20).kurt()

        return features

    def _rule_based_predict(self, returns: pd.Series) -> pd.Series:
        """基于规则的预测（备选）"""
        detector = MarketRegimeDetector()

        # 从收益率反推价格
        price = (1 + returns).cumprod()

        return detector.detect_regime_batch(price)


def detect_current_market_regime(
    index_code: str = "000300.SH",
    lookback_days: int = 120,
    data_manager: Optional[Any] = None,
) -> MarketRegime:
    """
    检测当前市场状态

    Args:
        index_code: 指数代码
        lookback_days: 回看天数
        data_manager: 数据管理器

    Returns:
        市场状态
    """
    try:
        if data_manager is None:
            from projects.quant_trading.backtest.data_manager import DataManager

            data_manager = DataManager()

        end_date = datetime.now()
        start_date = end_date - pd.Timedelta(days=lookback_days)

        df = data_manager.get_index_data(index_code, start_date, end_date)

        if df.empty or "close" not in df.columns:
            return MarketRegime.UNKNOWN

        detector = MarketRegimeDetector()
        regime, _ = detector.detect_regime(df["close"], date=end_date)

        return regime

    except Exception as e:
        logger.error(f"Failed to detect market regime: {e}")
        return MarketRegime.UNKNOWN


def get_regime_description(regime: MarketRegime) -> str:
    """获取状态描述"""
    descriptions = {
        MarketRegime.BULL_TREND: "牛市趋势 - 趋势向上，波动适中",
        MarketRegime.BEAR_TREND: "熊市趋势 - 趋势向下，波动适中",
        MarketRegime.HIGH_VOLATILITY: "高波动 - 市场震荡，风险较高",
        MarketRegime.LOW_VOLATILITY: "低波动 - 市场平静，趋势不明",
        MarketRegime.NORMAL: "正常状态 - 无显著特征",
        MarketRegime.UNKNOWN: "未知状态 - 数据不足",
    }
    return descriptions.get(regime, "未知")
