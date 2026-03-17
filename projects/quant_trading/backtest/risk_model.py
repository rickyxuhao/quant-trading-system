"""
BARRA风格多因子风险模型

功能：
- 因子暴露度计算（市场/行业/风格）
- 因子协方差矩阵估计
- 个股特异性风险计算
- 组合风险分解
- 风险归因分析
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy import linalg
from scipy.optimize import minimize

from core.logger import get_logger

logger = get_logger(__name__)


class FactorType(Enum):
    """因子类型"""
    MARKET = "market"  # 市场因子
    INDUSTRY = "industry"  # 行业因子
    STYLE = "style"  # 风格因子
    MACRO = "macro"  # 宏观因子


@dataclass
class FactorDefinition:
    """因子定义"""
    name: str
    factor_type: FactorType
    description: str = ""
    category: Optional[str] = None


# 申万一级行业（28个）
SHENWAN_INDUSTRIES = [
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子", "家用电器",
    "食品饮料", "纺织服饰", "轻工制造", "医药生物", "公用事业",
    "交通运输", "房地产", "商贸零售", "社会服务", "银行", "非银金融",
    "综合", "建筑材料", "建筑装饰", "电力设备", "机械设备", "国防军工",
    "计算机", "传媒", "通信", "煤炭", "石油石化", "环保", "汽车",
]

# BARRA风格因子
BARRA_STYLE_FACTORS = [
    FactorDefinition("size", FactorType.STYLE, "市值因子", "规模"),
    FactorDefinition("beta", FactorType.STYLE, "Beta因子", "系统性风险"),
    FactorDefinition("momentum", FactorType.STYLE, "动量因子", "趋势"),
    FactorDefinition("residual_volatility", FactorType.STYLE, "残差波动率", "波动"),
    FactorDefinition("non_linear_size", FactorType.STYLE, "非线性市值", "规模"),
    FactorDefinition("book_to_price", FactorType.STYLE, "账面市值比", "价值"),
    FactorDefinition("liquidity", FactorType.STYLE, "流动性因子", "交易"),
    FactorDefinition("earnings_yield", FactorType.STYLE, "盈利收益率", "盈利"),
    FactorDefinition("growth", FactorType.STYLE, "成长因子", "成长"),
    FactorDefinition("leverage", FactorType.STYLE, "杠杆因子", "财务"),
]


@dataclass
class RiskDecomposition:
    """风险分解结果"""
    total_risk: float  # 总风险（方差）
    systematic_risk: float  # 系统性风险
    idiosyncratic_risk: float  # 特质性风险
    factor_risks: Dict[str, float]  # 各因子风险贡献
    factor_exposures: Dict[str, float]  # 各因子暴露度


class FactorRiskModel:
    """
    因子风险模型

    实现BARRA风格的多因子风险模型
    """

    def __init__(
        self,
        industry_factors: Optional[List[str]] = None,
        style_factors: Optional[List[FactorDefinition]] = None,
        lookback_window: int = 252,
    ):
        self.industry_factors = industry_factors or SHENWAN_INDUSTRIES
        self.style_factors = style_factors or BARRA_STYLE_FACTORS
        self.lookback_window = lookback_window

        # 因子数据
        self.factor_exposures: Optional[pd.DataFrame] = None
        self.factor_covariance: Optional[pd.DataFrame] = None
        self.idiosyncratic_variance: Optional[pd.Series] = None

        # 股票池
        self.stock_universe: List[str] = []

    def calibrate(
        self,
        returns: pd.DataFrame,
        factor_data: pd.DataFrame,
        date: datetime,
    ) -> None:
        """
        校准风险模型

        Args:
            returns: 股票收益矩阵 (dates x stocks)
            factor_data: 因子暴露度矩阵 (stocks x factors)
            date: 校准日期
        """
        self.stock_universe = returns.columns.tolist()

        # 对齐数据
        common_stocks = returns.columns.intersection(factor_data.index)
        returns = returns[common_stocks]
        factor_data = factor_data.loc[common_stocks]

        if len(common_stocks) == 0:
            logger.error("No common stocks between returns and factor data")
            return

        # 估计因子协方差矩阵
        self._estimate_factor_covariance(returns, factor_data)

        # 估计特质性方差
        self._estimate_idiosyncratic_variance(returns, factor_data)

        # 保存因子暴露度
        self.factor_exposures = factor_data

        logger.info(f"Risk model calibrated on {len(common_stocks)} stocks")

    def _estimate_factor_covariance(
        self, returns: pd.DataFrame, factor_data: pd.DataFrame
    ) -> None:
        """估计因子协方差矩阵（使用指数加权移动平均EWMA）"""
        # 使用最近数据
        recent_returns = returns.tail(self.lookback_window)

        # 横截面回归获取因子收益
        factor_returns = self._estimate_factor_returns(recent_returns, factor_data)

        # EWMA协方差估计
        decay_factor = 0.94  # 标准EWMA衰减因子
        n = len(factor_returns)

        weights = np.array([decay_factor ** (n - 1 - i) for i in range(n)])
        weights /= weights.sum()

        # 加权协方差
        mean_returns = factor_returns.mul(weights, axis=0).sum()
        centered = factor_returns - mean_returns

        cov_matrix = pd.DataFrame(
            index=factor_returns.columns, columns=factor_returns.columns, dtype=float
        )

        for i, factor_i in enumerate(factor_returns.columns):
            for j, factor_j in enumerate(factor_returns.columns):
                cov_matrix.iloc[i, j] = (
                    centered[factor_i] * centered[factor_j] * weights
                ).sum()

        self.factor_covariance = cov_matrix

    def _estimate_factor_returns(
        self, returns: pd.DataFrame, factor_data: pd.DataFrame
    ) -> pd.DataFrame:
        """估计因子收益（加权最小二乘）"""
        factor_returns_list = []

        for date in returns.index:
            day_returns = returns.loc[date]
            day_exposures = factor_data.reindex(day_returns.index)

            # 去除NaN
            valid_idx = day_returns.notna() & day_exposures.notna().all(axis=1)
            if valid_idx.sum() < 10:  # 至少需要10只股票
                continue

            y = day_returns[valid_idx].values
            X = day_exposures[valid_idx].values

            # WLS估计（以市值平方根为权重）
            try:
                # 简单OLS（后续可加入权重）
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                factor_returns_list.append(
                    pd.Series(beta, index=factor_data.columns, name=date)
                )
            except Exception as e:
                logger.debug(f"Factor return estimation failed on {date}: {e}")
                continue

        return pd.DataFrame(factor_returns_list)

    def _estimate_idiosyncratic_variance(
        self, returns: pd.DataFrame, factor_data: pd.DataFrame
    ) -> None:
        """估计特质性方差"""
        # 获取因子收益
        factor_returns = self._estimate_factor_returns(returns, factor_data)

        idio_var = pd.Series(index=returns.columns, dtype=float)

        for stock in returns.columns:
            stock_returns = returns[stock]

            # 使用因子收益预测收益
            if stock in factor_data.index:
                exposures = factor_data.loc[stock].values
                predicted = factor_returns.dot(exposures)

                # 计算残差
                residuals = stock_returns - predicted.reindex(stock_returns.index)

                # 估计方差（使用EWMA）
                decay_factor = 0.94
                n = len(residuals.dropna())

                if n > 30:  # 至少需要30个观测
                    weights = np.array([decay_factor ** (n - 1 - i) for i in range(n)])
                    weights /= weights.sum()

                    residual_sq = residuals.dropna() ** 2
                    variance = (residual_sq * weights).sum()

                    # 压缩估计（向均值收缩）
                    mean_var = residual_sq.mean()
                    shrinkage = 0.5  # 压缩系数
                    idio_var[stock] = shrinkage * mean_var + (1 - shrinkage) * variance

        self.idiosyncratic_variance = idio_var.fillna(idio_var.mean())

    def calculate_portfolio_risk(
        self, weights: pd.Series
    ) -> RiskDecomposition:
        """
        计算组合风险分解

        Args:
            weights: 组合权重

        Returns:
            风险分解结果
        """
        if self.factor_exposures is None or self.factor_covariance is None:
            raise ValueError("Risk model not calibrated")

        # 对齐权重
        weights = weights.reindex(self.factor_exposures.index).fillna(0)

        # 计算组合因子暴露
        portfolio_exposure = self.factor_exposures.T.dot(weights)

        # 系统性风险 = w' * X * V * X' * w
        systematic_var = (
            portfolio_exposure.T
            @ self.factor_covariance
            @ portfolio_exposure
        )

        # 特质性风险 = sum(w_i^2 * sigma_i^2)
        if self.idiosyncratic_variance is not None:
            idio_var_aligned = self.idiosyncratic_variance.reindex(weights.index).fillna(
                self.idiosyncratic_variance.mean()
            )
            idiosyncratic_var = (weights ** 2 * idio_var_aligned).sum()
        else:
            idiosyncratic_var = 0

        # 总风险
        total_var = systematic_var + idiosyncratic_var

        # 各因子风险贡献
        factor_risks = {}
        for factor in self.factor_covariance.columns:
            factor_contrib = (
                portfolio_exposure[factor]
                * self.factor_covariance.loc[factor]
                @ portfolio_exposure
            )
            factor_risks[factor] = factor_contrib

        return RiskDecomposition(
            total_risk=total_var,
            systematic_risk=systematic_var,
            idiosyncratic_risk=idiosyncratic_var,
            factor_risks=factor_risks,
            factor_exposures=portfolio_exposure.to_dict(),
        )

    def calculate_tracking_error(
        self, active_weights: pd.Series
    ) -> float:
        """计算主动风险（跟踪误差）"""
        risk_decomp = self.calculate_portfolio_risk(active_weights)
        return np.sqrt(risk_decomp.total_risk)

    def get_factor_exposures(self, weights: pd.Series) -> pd.Series:
        """获取组合因子暴露"""
        if self.factor_exposures is None:
            return pd.Series()

        weights = weights.reindex(self.factor_exposures.index).fillna(0)
        return self.factor_exposures.T.dot(weights)


class FactorExposureCalculator:
    """
    因子暴露度计算器

    计算个股在各类因子上的暴露度
    """

    def __init__(self, data_manager: Any):
        self.data_manager = data_manager

    def calculate_exposures(
        self,
        date: datetime,
        stock_pool: List[str],
        market_index: str = "000300.SH",
    ) -> pd.DataFrame:
        """
        计算因子暴露度

        Returns:
            DataFrame (stocks x factors)
        """
        exposures = pd.DataFrame(index=stock_pool)

        # 1. 行业因子（哑变量）
        industry_exposure = self._calculate_industry_exposure(date, stock_pool)
        exposures = exposures.join(industry_exposure)

        # 2. 风格因子
        style_exposure = self._calculate_style_exposure(date, stock_pool, market_index)
        exposures = exposures.join(style_exposure)

        # 3. Beta因子
        beta_exposure = self._calculate_beta_exposure(date, stock_pool, market_index)
        exposures["beta"] = beta_exposure

        return exposures.fillna(0)

    def _calculate_industry_exposure(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """计算行业因子暴露（行业哑变量）"""
        exposure = pd.DataFrame(index=stock_pool, columns=SHENWAN_INDUSTRIES)
        exposure = exposure.fillna(0)

        try:
            stock_info = self.data_manager.get_batch_stock_info(stock_pool)

            for ts_code in stock_pool:
                if ts_code in stock_info:
                    industry = stock_info[ts_code].get("industry", "")
                    if industry in SHENWAN_INDUSTRIES:
                        exposure.loc[ts_code, industry] = 1

        except Exception as e:
            logger.error(f"Error calculating industry exposure: {e}")

        return exposure

    def _calculate_style_exposure(
        self, date: datetime, stock_pool: List[str], market_index: str
    ) -> pd.DataFrame:
        """计算风格因子暴露"""
        exposure = pd.DataFrame(index=stock_pool)

        try:
            # 获取基础数据
            lookback_start = date - pd.Timedelta(days=60)

            # Size因子（对数市值）
            size_data = self._get_market_data(date, stock_pool)
            if "total_mv" in size_data.columns:
                log_mv = np.log(size_data["total_mv"].replace(0, np.nan))
                exposure["size"] = self._standardize(log_mv)

            # Book-to-Price（PB倒数）
            if "pb" in size_data.columns:
                bp = 1 / size_data["pb"].replace(0, np.nan)
                exposure["book_to_price"] = self._standardize(bp)

            # Momentum（20日收益）
            returns = self._get_returns(lookback_start, date, stock_pool)
            if "return_20d" in returns.columns:
                exposure["momentum"] = self._standardize(returns["return_20d"])

            # Volatility
            if "volatility_20d" in returns.columns:
                exposure["residual_volatility"] = self._standardize(
                    returns["volatility_20d"]
                )

            # Liquidity（换手率）
            if "turnover_rate" in size_data.columns:
                exposure["liquidity"] = self._standardize(size_data["turnover_rate"])

            # Earnings Yield（EP）
            if "pe_ttm" in size_data.columns:
                ep = 1 / size_data["pe_ttm"].replace(0, np.nan)
                exposure["earnings_yield"] = self._standardize(ep)

        except Exception as e:
            logger.error(f"Error calculating style exposure: {e}")

        return exposure

    def _calculate_beta_exposure(
        self, date: datetime, stock_pool: List[str], market_index: str
    ) -> pd.Series:
        """计算Beta因子暴露"""
        betas = pd.Series(index=stock_pool, dtype=float)

        try:
            lookback_start = date - pd.Timedelta(days=252)

            # 获取市场收益
            market_df = self.data_manager.get_index_data(
                market_index, lookback_start, date
            )
            market_returns = market_df["close"].pct_change().dropna()

            # 获取个股收益
            for ts_code in stock_pool:
                try:
                    stock_df = self.data_manager.get_stock_data(
                        ts_code, lookback_start, date
                    )
                    stock_returns = stock_df["adj_close"].pct_change().dropna()

                    # 对齐
                    common_idx = stock_returns.index.intersection(market_returns.index)
                    if len(common_idx) < 60:  # 至少需要60个交易日
                        continue

                    # 计算Beta
                    X = market_returns[common_idx].values
                    y = stock_returns[common_idx].values

                    beta = np.cov(y, X)[0, 1] / np.var(X) if np.var(X) > 0 else 1.0
                    betas[ts_code] = beta

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error calculating beta: {e}")

        return betas.fillna(1.0)

    def _get_market_data(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取市场数据"""
        try:
            df = self.data_manager.get_market_data_for_date(
                date, ["ts_code", "total_mv", "pb", "pe_ttm", "turnover_rate"]
            )
            return df[df["ts_code"].isin(stock_pool)].set_index("ts_code")
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return pd.DataFrame(index=stock_pool)

    def _get_returns(
        self, start_date: datetime, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取收益数据"""
        returns_df = pd.DataFrame(index=stock_pool)

        try:
            batch_data = self.data_manager.get_batch_stock_data(
                stock_pool, start_date, end_date, adjust=True
            )

            for ts_code, df in batch_data.items():
                if df.empty or "adj_close" not in df.columns:
                    continue

                closes = df["adj_close"]

                if len(closes) >= 20:
                    returns_df.loc[ts_code, "return_20d"] = (
                        closes.iloc[-1] / closes.iloc[-20] - 1
                    )
                    returns_df.loc[ts_code, "volatility_20d"] = (
                        closes.pct_change().std() * np.sqrt(252)
                    )

        except Exception as e:
            logger.error(f"Error getting returns: {e}")

        return returns_df

    def _standardize(self, series: pd.Series) -> pd.Series:
        """标准化（Z-score）"""
        mean = series.mean()
        std = series.std()
        if std > 0:
            return (series - mean) / std
        return series - mean


def create_factor_risk_model(
    data_manager: Any,
    date: datetime,
    stock_pool: List[str],
    lookback_days: int = 252,
) -> FactorRiskModel:
    """
    创建并校准因子风险模型

    Args:
        data_manager: 数据管理器
        date: 校准日期
        stock_pool: 股票池
        lookback_days: 回看天数

    Returns:
        校准后的风险模型
    """
    # 计算因子暴露
    calculator = FactorExposureCalculator(data_manager)
    exposures = calculator.calculate_exposures(date, stock_pool)

    # 获取历史收益
    start_date = date - pd.Timedelta(days=lookback_days + 30)
    returns_df = pd.DataFrame(index=pd.date_range(start_date, date, freq="B"))

    batch_data = data_manager.get_batch_stock_data(
        stock_pool, start_date, date, adjust=True
    )

    for ts_code, df in batch_data.items():
        if not df.empty and "adj_close" in df.columns:
            returns = df["adj_close"].pct_change()
            returns_df[ts_code] = returns

    returns_df = returns_df.dropna(how="all")

    # 创建并校准模型
    model = FactorRiskModel(lookback_window=lookback_days)
    model.calibrate(returns_df, exposures, date)

    return model
