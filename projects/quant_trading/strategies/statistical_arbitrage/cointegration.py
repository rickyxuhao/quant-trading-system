"""
协整检验模块 - Engle-Granger两步法

功能：
- 协整检验
- ADF检验p值输出
- 半衰期估计（Half-life = ln(2)/θ）
- 对冲比例β计算
"""

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CointegrationResult:
    """协整检验结果"""

    is_cointegrated: bool
    hedge_ratio: float  # β值
    spread_mean: float
    spread_std: float
    adf_statistic: float
    adf_pvalue: float
    half_life: float
    confidence_level: float

    def __repr__(self) -> str:
        status = "协整" if self.is_cointegrated else "非协整"
        return (
            f"CointegrationResult({status}, "
            f"β={self.hedge_ratio:.3f}, "
            f"p-value={self.adf_pvalue:.4f}, "
            f"half-life={self.half_life:.1f}天)"
        )


class CointegrationTester:
    """协整检验器"""

    def __init__(self, significance_level: float = 0.05):
        """
        初始化

        Args:
            significance_level: 显著性水平，默认0.05
        """
        self.significance_level = significance_level

    def test_pair(
        self, price_a: pd.Series, price_b: pd.Series, method: str = "ols"
    ) -> CointegrationResult:
        """
        对两个价格序列进行协整检验

        Args:
            price_a: 股票A价格序列
            price_b: 股票B价格序列
            method: 回归方法，'ols'或'total_least_squares'

        Returns:
            协整检验结果
        """
        # 对齐数据
        data = pd.concat([price_a, price_b], axis=1).dropna()
        data.columns = ["a", "b"]

        if len(data) < 30:
            logger.warning(f"数据点过少: {len(data)}，无法进行可靠的协整检验")
            return CointegrationResult(
                is_cointegrated=False,
                hedge_ratio=0.0,
                spread_mean=0.0,
                spread_std=0.0,
                adf_statistic=0.0,
                adf_pvalue=1.0,
                half_life=np.inf,
                confidence_level=self.significance_level,
            )

        # 第一步：OLS回归计算对冲比例
        if method == "ols":
            beta = self._calculate_hedge_ratio_ols(data["a"], data["b"])
        else:
            beta = self._calculate_hedge_ratio_tls(data["a"], data["b"])

        # 计算价差序列
        spread = data["a"] - beta * data["b"]

        # 第二步：对价差进行ADF检验
        adf_stat, adf_pvalue, _, _, critical_values, _ = adfuller(spread, autolag="AIC")

        # 判断是否协整
        is_cointegrated = adf_pvalue < self.significance_level

        # 计算半衰期
        half_life = self._calculate_half_life(spread)

        result = CointegrationResult(
            is_cointegrated=is_cointegrated,
            hedge_ratio=beta,
            spread_mean=spread.mean(),
            spread_std=spread.std(),
            adf_statistic=adf_stat,
            adf_pvalue=adf_pvalue,
            half_life=half_life,
            confidence_level=self.significance_level,
        )

        logger.debug(
            f"协整检验: β={beta:.3f}, p-value={adf_pvalue:.4f}, " f"半衰期={half_life:.1f}天"
        )

        return result

    def _calculate_hedge_ratio_ols(self, price_a: pd.Series, price_b: pd.Series) -> float:
        """
        使用OLS回归计算对冲比例

        模型: price_a = α + β * price_b + ε
        """
        # 添加常数项
        X = sm.add_constant(price_b)
        model = sm.OLS(price_a, X).fit()

        beta = model.params.iloc[1]  # β系数

        return beta

    def _calculate_hedge_ratio_tls(self, price_a: pd.Series, price_b: pd.Series) -> float:
        """
        使用总体最小二乘法(TLS)计算对冲比例

        TLS对两个变量的误差都有考虑，更适合配对交易
        """
        # 使用PCA方法近似TLS
        data = np.column_stack([price_a.values, price_b.values])

        # 中心化
        data_mean = data.mean(axis=0)
        data_centered = data - data_mean

        # SVD分解
        _, _, Vt = np.linalg.svd(data_centered.T @ data_centered)

        # 最小特征值对应的特征向量
        beta = -Vt[0, 0] / Vt[0, 1] if Vt[0, 1] != 0 else 1.0

        return beta

    def _calculate_half_life(self, spread: pd.Series) -> float:
        """
        计算价差的半衰期

        使用Ornstein-Uhlenbeck过程估计:
        dS(t) = θ(μ - S(t))dt + σdW(t)
        Half-life = ln(2) / θ
        """
        # 一阶差分
        spread_lag = spread.shift(1).dropna()
        spread_diff = spread.diff().dropna()

        # 对齐数据
        aligned_data = pd.concat([spread_diff, spread_lag], axis=1).dropna()
        aligned_data.columns = ["diff", "lag"]

        if len(aligned_data) < 10:
            return np.inf

        # 回归: ΔS(t) = α + β*S(t-1) + ε
        # θ = -β
        X = sm.add_constant(aligned_data["lag"])
        model = sm.OLS(aligned_data["diff"], X).fit()

        theta = -model.params.iloc[1]

        if theta <= 0:
            # 非均值回归
            return np.inf

        half_life = np.log(2) / theta

        return half_life

    def calculate_zscore(self, spread: pd.Series, lookback: int = 20) -> pd.Series:
        """
        计算价差的Z-score

        Args:
            spread: 价差序列
            lookback: 回望窗口

        Returns:
            Z-score序列
        """
        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()

        zscore = (spread - rolling_mean) / rolling_std

        return zscore

    def calculate_dynamic_hedge_ratio(
        self, price_a: pd.Series, price_b: pd.Series, window: int = 60
    ) -> pd.Series:
        """
        计算动态对冲比例（滚动窗口Kalman Filter）

        Args:
            price_a: 股票A价格序列
            price_b: 股票B价格序列
            window: 滚动窗口

        Returns:
            动态β序列
        """
        from pykalman import KalmanFilter

        # 初始化Kalman Filter
        kf = KalmanFilter(
            n_dim_obs=1,
            n_dim_state=2,
            initial_state_mean=[0, 0],
            initial_state_covariance=np.eye(2),
            observation_matrices=np.expand_dims(
                np.vstack([price_b, np.ones(len(price_b))]).T, axis=1
            ),
        )

        # 使用Kalman Filter估计状态
        state_means, _ = kf.filter(price_a.values)

        # 提取β值
        beta_series = pd.Series(state_means[:, 0], index=price_a.index)

        return beta_series

    def get_cointegration_summary(self, result: CointegrationResult) -> dict:
        """
        获取协整检验结果摘要

        Args:
            result: 协整检验结果

        Returns:
            结果字典
        """
        return {
            "协整关系": "存在" if result.is_cointegrated else "不存在",
            "对冲比例β": f"{result.hedge_ratio:.4f}",
            "价差均值": f"{result.spread_mean:.4f}",
            "价差标准差": f"{result.spread_std:.4f}",
            "ADF统计量": f"{result.adf_statistic:.4f}",
            "p值": f"{result.adf_pvalue:.4f}",
            "半衰期(天)": f"{result.half_life:.1f}",
            "建议": self._get_recommendation(result),
        }

    def _get_recommendation(self, result: CointegrationResult) -> str:
        """根据结果给出建议"""
        if not result.is_cointegrated:
            return "p值过高，不建议使用此配对进行交易"

        if result.half_life < 1:
            return "半衰期过短，可能不适合统计套利"
        elif result.half_life > 30:
            return "半衰期较长，需要较长期持仓"
        else:
            return "协整关系良好，适合统计套利策略"


def quick_test(
    price_a: pd.Series, price_b: pd.Series, significance: float = 0.05
) -> Tuple[bool, float, float]:
    """
    快速协整检验

    Args:
        price_a: 股票A价格序列
        price_b: 股票B价格序列
        significance: 显著性水平

    Returns:
        (是否协整, 对冲比例, p值)
    """
    tester = CointegrationTester(significance_level=significance)
    result = tester.test_pair(price_a, price_b)

    return result.is_cointegrated, result.hedge_ratio, result.adf_pvalue
