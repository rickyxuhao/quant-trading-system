"""
横截面特征工程模块 - 支持多股票截面特征计算

功能：
- 横截面Z-score和百分位排名
- 行业中性化（去除行业因子暴露）
- 基本面因子计算（PE/PB/ROE等）
- 资金流向因子
- 行业/市场相对强弱
- SQL批量计算引擎集成（高性能版本）

性能优化：
- 支持 SQLFactorEngine 批量计算（6-10x 性能提升）
- 单例模式重用数据库连接
- 自动回退到 Python 计算（当 SQL 引擎不可用时）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set, Union
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy import stats

from core.logger import get_logger

logger = get_logger(__name__)


class NeutralizationMethod(Enum):
    """中性化方法"""
    INDUSTRY_MEAN = "industry_mean"  # 减去行业均值
    INDUSTRY_ZSCORE = "industry_zscore"  # 行业内Z-score
    MARKET_CAP = "market_cap"  # 对市值回归取残差
    INDUSTRY_CAP = "industry_cap"  # 行业+市值双中性化


@dataclass
class CrossSectionalFeatureConfig:
    """横截面特征配置"""

    # 基本面因子
    use_valuation_factors: bool = True  # 估值因子
    use_profitability_factors: bool = True  # 盈利因子
    use_growth_factors: bool = True  # 成长因子

    # 资金流因子
    use_moneyflow_factors: bool = True  # 资金流向

    # 横截面特征
    use_cross_sectional_ranks: bool = True  # 横截面排名
    use_sector_relative: bool = True  # 行业相对强弱
    use_market_relative: bool = True  # 市场相对强弱

    # 中性化配置
    neutralization: NeutralizationMethod = NeutralizationMethod.INDUSTRY_MEAN

    # 回看周期
    lookback_days: int = 20

    # 估值因子参数
    pe_percentiles: List[int] = field(default_factory=lambda: [10, 25, 50, 75, 90])

    # 性能优化选项
    use_sql_engine: bool = True  # 使用 SQL 批量计算引擎
    sql_engine_fallback: bool = True  # SQL 引擎失败时回退到 Python


@dataclass
class FactorCategory:
    """因子类别定义"""

    name: str
    factors: List[str]
    description: str = ""


# 预定义因子类别
VALUATION_FACTORS = FactorCategory(
    name="valuation",
    factors=["pe_ttm", "pb", "ps_ttm", "pcf", "dividend_yield"],
    description="估值因子：PE/PB/PS/PCF/股息率",
)

PROFITABILITY_FACTORS = FactorCategory(
    name="profitability",
    factors=["roe", "roa", "gross_margin", "net_margin", "operating_margin"],
    description="盈利因子：ROE/ROA/毛利率/净利率",
)

GROWTH_FACTORS = FactorCategory(
    name="growth",
    factors=["revenue_yoy", "profit_yoy", "roe_yoy", "asset_growth"],
    description="成长因子：营收/利润同比增长",
)

MONEYFLOW_FACTORS = FactorCategory(
    name="moneyflow",
    factors=[
        "large_order_net_ratio",
        "main_net_inflow",
        "retail_net_inflow",
        "net_inflow_5d",
        "northbound_flow_5d",
    ],
    description="资金流因子：大单净流入/北向资金",
)

TECHNICAL_FACTORS = FactorCategory(
    name="technical",
    factors=["rs_20d_sector", "rs_60d_market", "volatility_percentile", "volume_percentile"],
    description="技术因子：相对强弱/波动率分位",
)


class CrossSectionalFeatureEngineer:
    """
    横截面特征工程器

    为股票池计算横截面特征，包括：
    1. 基本面Z-score（行业中性化）
    2. 资金流向因子
    3. 行业/市场相对强弱
    4. 横截面排名和百分位

    性能优化：
    - 支持 SQLFactorEngine 批量计算（单次查询 ~2秒/天）
    - 自动回退到 Python 计算（兼容模式）
    """

    def __init__(
        self,
        config: Optional[CrossSectionalFeatureConfig] = None,
        data_manager: Optional[Any] = None,
    ):
        self.config = config or CrossSectionalFeatureConfig()
        self.data_manager = data_manager

        # 缓存
        self._industry_cache: Dict[str, str] = {}
        self._market_data_cache: Dict[datetime, pd.DataFrame] = {}

        # SQL 引擎（延迟初始化）
        self._sql_engine: Optional[Any] = None

        logger.info("CrossSectionalFeatureEngineer initialized")

    def _get_sql_engine(self) -> Optional[Any]:
        """获取 SQLFactorEngine 实例（延迟初始化）"""
        if self._sql_engine is None and self.config.use_sql_engine:
            try:
                from .sql_factor_engine import SQLFactorEngine
                self._sql_engine = SQLFactorEngine()
            except Exception as e:
                logger.warning(f"Failed to initialize SQLFactorEngine: {e}")
                self._sql_engine = None
        return self._sql_engine

    def create_features_for_universe(
        self,
        date: datetime,
        stock_pool: List[str],
        market_index: str = "000300.SH",
    ) -> pd.DataFrame:
        """
        为股票池计算横截面特征

        Args:
            date: 计算日期
            stock_pool: 股票代码列表
            market_index: 市场指数代码（默认沪深300）

        Returns:
            特征DataFrame，每行一只股票
        """
        # 尝试使用 SQL 引擎批量计算
        if self.config.use_sql_engine:
            try:
                return self._create_features_with_sql_engine(date, stock_pool, market_index)
            except Exception as e:
                if self.config.sql_engine_fallback:
                    logger.warning(f"SQL engine failed, falling back to Python: {e}")
                else:
                    raise

        # 使用传统 Python 方法计算
        return self._create_features_with_python(date, stock_pool, market_index)

    def _create_features_with_sql_engine(
        self, date: datetime, stock_pool: List[str], market_index: str
    ) -> pd.DataFrame:
        """使用 SQLFactorEngine 批量计算特征"""
        engine = self._get_sql_engine()
        if engine is None:
            raise RuntimeError("SQLFactorEngine not available")

        # 批量计算基础因子
        features_df = engine.calculate_factors_for_date(
            trade_date=date,
            stock_pool=stock_pool,
            include_sectors=self.config.use_sector_relative,
        )

        if features_df.empty:
            return pd.DataFrame(index=stock_pool)

        # 计算行业相对因子（如果 SQL 引擎未包含）
        if self.config.use_sector_relative:
            missing_sector_cols = [
                col for col in ["sector_alpha_20d", "sector_alpha_60d", "sector_rank_20d"]
                if col not in features_df.columns
            ]
            if missing_sector_cols:
                try:
                    sector_factors = engine.calculate_sector_relative_factors(
                        trade_date=date, stock_pool=stock_pool, base_factors=features_df
                    )
                    if not sector_factors.empty:
                        features_df = features_df.join(
                            sector_factors[[c for c in sector_factors.columns
                                          if c not in features_df.columns]],
                            how="left"
                        )
                except Exception as e:
                    logger.warning(f"Failed to calculate sector factors: {e}")

        # 计算额外的横截面排名
        if self.config.use_cross_sectional_ranks:
            rank_features = self._calculate_cross_sectional_ranks(features_df)
            features_df = features_df.join(
                rank_features[[c for c in rank_features.columns
                              if c not in features_df.columns]],
                how="left"
            )

        # 行业中性化（如果需要）
        if self.config.neutralization != NeutralizationMethod.INDUSTRY_MEAN:
            neutralized_df = self._neutralize_factors(features_df, date, stock_pool)
            features_df = features_df.join(neutralized_df, rsuffix="_neutral")

        features_df.index.name = "ts_code"
        return features_df

    def _create_features_with_python(
        self, date: datetime, stock_pool: List[str], market_index: str
    ) -> pd.DataFrame:
        """使用传统 Python 方法计算特征"""
        features_list = []

        # 1. 获取基本面数据
        if self.config.use_valuation_factors:
            valuation_features = self._get_valuation_features(date, stock_pool)
            features_list.append(valuation_features)

        # 2. 获取盈利能力数据
        if self.config.use_profitability_factors:
            profitability_features = self._get_profitability_features(date, stock_pool)
            features_list.append(profitability_features)

        # 3. 获取成长数据
        if self.config.use_growth_factors:
            growth_features = self._get_growth_features(date, stock_pool)
            features_list.append(growth_features)

        # 4. 获取资金流向数据
        if self.config.use_moneyflow_factors:
            moneyflow_features = self._get_moneyflow_features(date, stock_pool)
            features_list.append(moneyflow_features)

        # 合并所有特征
        if not features_list:
            return pd.DataFrame(index=stock_pool)

        features_df = features_list[0]
        for df in features_list[1:]:
            features_df = features_df.join(df, how="outer")

        # 5. 计算横截面Z-score
        if self.config.use_cross_sectional_ranks:
            zscore_df = self._calculate_cross_sectional_zscores(features_df)
            features_df = features_df.join(zscore_df, rsuffix="_zscore")

        # 6. 计算行业中性化特征
        if self.config.neutralization != NeutralizationMethod.INDUSTRY_MEAN:
            neutralized_df = self._neutralize_factors(features_df, date, stock_pool)
            features_df = features_df.join(neutralized_df, rsuffix="_neutral")

        # 7. 计算行业相对强弱
        if self.config.use_sector_relative:
            sector_relative = self._calculate_sector_relative_features(date, stock_pool)
            features_df = features_df.join(sector_relative)

        # 8. 计算市场相对强弱
        if self.config.use_market_relative:
            market_relative = self._calculate_market_relative_features(
                date, stock_pool, market_index
            )
            features_df = features_df.join(market_relative)

        # 9. 计算横截面排名
        if self.config.use_cross_sectional_ranks:
            rank_features = self._calculate_cross_sectional_ranks(features_df)
            features_df = features_df.join(rank_features, rsuffix="_rank")

        features_df.index.name = "ts_code"
        return features_df

    def _get_valuation_features(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取估值特征（PE/PB/PS等）"""
        features = pd.DataFrame(index=stock_pool)

        try:
            # 从数据库获取每日指标数据
            daily_basic = self._fetch_daily_basic(date, stock_pool)

            if daily_basic.empty:
                logger.warning(f"No daily basic data for {date.strftime('%Y%m%d')}")
                return features

            # 估值因子
            features["pe_ttm"] = daily_basic.get("pe_ttm", np.nan)
            features["pb"] = daily_basic.get("pb", np.nan)
            features["ps_ttm"] = daily_basic.get("ps_ttm", np.nan)
            features["pcf"] = daily_basic.get("pcf_ncf_ttm", np.nan)

            # 股息率（如有）
            if "dv_ttm" in daily_basic.columns:
                features["dividend_yield"] = daily_basic["dv_ttm"]

            # 市值
            features["total_mv"] = daily_basic.get("total_mv", np.nan) * 10000  # 转换为元
            features["circ_mv"] = daily_basic.get("circ_mv", np.nan) * 10000

            # 对数市值（用于中性化）
            features["log_mv"] = np.log(features["total_mv"].replace(0, np.nan))

            # 估值Z-score（原始值，后续中性化）
            features["pe_ttm_raw"] = features["pe_ttm"]
            features["pb_raw"] = features["pb"]

        except Exception as e:
            logger.error(f"Error getting valuation features: {e}")

        return features

    def _get_profitability_features(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取盈利能力特征（ROE/ROA等）"""
        features = pd.DataFrame(index=stock_pool)

        try:
            fina_data = self._fetch_fina_indicator(date, stock_pool)

            if fina_data.empty:
                return features

            # 盈利能力
            features["roe"] = fina_data.get("roe", np.nan)
            features["roa"] = fina_data.get("roa", np.nan)
            features["gross_margin"] = fina_data.get("grossprofit_margin", np.nan)
            features["net_margin"] = fina_data.get("netprofit_margin", np.nan)
            features["operating_margin"] = fina_data.get("op_yoy", np.nan)

        except Exception as e:
            logger.error(f"Error getting profitability features: {e}")

        return features

    def _get_growth_features(self, date: datetime, stock_pool: List[str]) -> pd.DataFrame:
        """获取成长性特征"""
        features = pd.DataFrame(index=stock_pool)

        try:
            fina_data = self._fetch_fina_indicator(date, stock_pool)

            if fina_data.empty:
                return features

            # 成长性
            features["revenue_yoy"] = fina_data.get("or_yoy", np.nan)  # 营业收入同比增长
            features["profit_yoy"] = fina_data.get("netprofit_yoy", np.nan)  # 净利润同比增长
            features["roe_yoy"] = fina_data.get("roe_yoy", np.nan)
            features["asset_growth"] = fina_data.get("assets_yoy", np.nan)

        except Exception as e:
            logger.error(f"Error getting growth features: {e}")

        return features

    def _get_moneyflow_features(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取资金流向特征"""
        features = pd.DataFrame(index=stock_pool)

        try:
            # 当日资金流向
            moneyflow_today = self._fetch_moneyflow(date, stock_pool)

            if not moneyflow_today.empty:
                features["large_order_net_ratio"] = moneyflow_today.get(
                    "large_order_net_ratio", np.nan
                )
                features["main_net_inflow"] = moneyflow_today.get("main_net_inflow", np.nan)
                features["retail_net_inflow"] = moneyflow_today.get("retail_net_inflow", np.nan)

            # 5日累计资金流向
            start_date = date - pd.Timedelta(days=10)  # 获取稍多数据以确保5个交易日
            moneyflow_5d = self._fetch_moneyflow_window(start_date, date, stock_pool)

            if not moneyflow_5d.empty:
                # 按股票聚合5日净流入
                net_inflow_5d = (
                    moneyflow_5d.groupby("ts_code")["net_mf_amount"].sum()
                    if "net_mf_amount" in moneyflow_5d.columns
                    else pd.Series(index=stock_pool, dtype=float)
                )
                features["net_inflow_5d"] = net_inflow_5d

        except Exception as e:
            logger.error(f"Error getting moneyflow features: {e}")

        return features

    def _calculate_cross_sectional_zscores(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """计算横截面Z-score"""
        zscore_df = pd.DataFrame(index=features_df.index)

        numeric_cols = features_df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if col.endswith(("_zscore", "_rank", "_neutral")):
                continue

            values = features_df[col]

            # 去除极端异常值（Winsorize）
            lower = values.quantile(0.01)
            upper = values.quantile(0.99)
            values = values.clip(lower, upper)

            # 计算Z-score
            mean = values.mean()
            std = values.std()

            if std > 0:
                zscore_df[f"{col}_zscore"] = (values - mean) / std
            else:
                zscore_df[f"{col}_zscore"] = 0.0

        return zscore_df

    def _calculate_cross_sectional_ranks(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """计算横截面排名和百分位"""
        rank_df = pd.DataFrame(index=features_df.index)

        numeric_cols = features_df.select_dtypes(include=[np.number]).columns
        n = len(features_df)

        if n == 0:
            return rank_df

        for col in numeric_cols:
            if col.endswith(("_zscore", "_rank", "_neutral", "_pct")):
                continue

            values = features_df[col]

            # 排名（1=最小）
            rank = values.rank(method="average", na_option="keep")
            rank_df[f"{col}_rank"] = rank

            # 百分位（0-1）
            percentile = (rank - 1) / (n - 1) if n > 1 else 0.5
            rank_df[f"{col}_pct"] = percentile

        return rank_df

    def _neutralize_factors(
        self, features_df: pd.DataFrame, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """因子中性化"""
        neutral_df = pd.DataFrame(index=features_df.index)

        # 获取行业信息
        industries = self._get_industries(stock_pool)

        # 需要中性化的因子
        factor_cols = [c for c in features_df.columns if c in VALUATION_FACTORS.factors]

        for col in factor_cols:
            values = features_df[col].copy()

            if self.config.neutralization == NeutralizationMethod.INDUSTRY_MEAN:
                # 减去行业均值
                for industry in set(industries.values()):
                    industry_stocks = [s for s, ind in industries.items() if ind == industry]
                    if len(industry_stocks) > 0:
                        industry_mean = values[industry_stocks].mean()
                        values[industry_stocks] -= industry_mean

                neutral_df[f"{col}_neutral"] = values

            elif self.config.neutralization == NeutralizationMethod.INDUSTRY_ZSCORE:
                # 行业内Z-score
                for industry in set(industries.values()):
                    industry_stocks = [s for s, ind in industries.items() if ind == industry]
                    if len(industry_stocks) > 3:  # 至少需要3只股票
                        industry_values = values[industry_stocks]
                        mean = industry_values.mean()
                        std = industry_values.std()
                        if std > 0:
                            values[industry_stocks] = (industry_values - mean) / std
                        else:
                            values[industry_stocks] = 0

                neutral_df[f"{col}_neutral"] = values

            elif self.config.neutralization == NeutralizationMethod.MARKET_CAP:
                # 对市值回归取残差
                log_mv = features_df.get("log_mv", pd.Series(index=features_df.index))
                neutral_df[f"{col}_neutral"] = self._regress_residual(values, log_mv)

            elif self.config.neutralization == NeutralizationMethod.INDUSTRY_CAP:
                # 行业+市值双中性化
                log_mv = features_df.get("log_mv", pd.Series(index=features_df.index))

                # 先行业中性化
                industry_neutral = values.copy()
                for industry in set(industries.values()):
                    industry_stocks = [s for s, ind in industries.items() if ind == industry]
                    if len(industry_stocks) > 0:
                        industry_mean = industry_neutral[industry_stocks].mean()
                        industry_neutral[industry_stocks] -= industry_mean

                # 再市值中性化
                neutral_df[f"{col}_neutral"] = self._regress_residual(industry_neutral, log_mv)

        return neutral_df

    def _calculate_sector_relative_features(
        self, date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """计算行业相对强弱特征"""
        features = pd.DataFrame(index=stock_pool)

        try:
            # 获取历史价格数据
            lookback_start = date - pd.Timedelta(days=60)

            # 获取股票收益
            stock_returns = self._get_returns(lookback_start, date, stock_pool)

            # 获取行业分类
            industries = self._get_industries(stock_pool)

            # 计算各行业平均收益
            sector_returns = {}
            for period in [20, 60]:
                col_name = f"return_{period}d"
                if col_name not in stock_returns.columns:
                    continue

                sector_returns[period] = {}

                for industry in set(industries.values()):
                    industry_stocks = [s for s, ind in industries.items() if ind == industry]
                    if len(industry_stocks) > 0:
                        avg_return = stock_returns.loc[industry_stocks, col_name].mean()
                        sector_returns[period][industry] = avg_return

            # 计算个股相对行业超额收益
            for stock in stock_pool:
                industry = industries.get(stock)
                if not industry:
                    continue

                for period in [20, 60]:
                    col_name = f"return_{period}d"
                    if col_name not in stock_returns.columns:
                        continue

                    stock_ret = stock_returns.loc[stock, col_name]
                    sector_ret = sector_returns.get(period, {}).get(industry, 0)
                    features.loc[stock, f"sector_alpha_{period}d"] = stock_ret - sector_ret

                    # 行业内排名
                    industry_stocks = [s for s, ind in industries.items() if ind == industry]
                    if len(industry_stocks) > 1:
                        industry_returns = stock_returns.loc[industry_stocks, col_name]
                        rank = (industry_returns > stock_ret).sum() + 1
                        features.loc[stock, f"sector_rank_{period}d"] = rank / len(industry_stocks)

        except Exception as e:
            logger.error(f"Error calculating sector relative features: {e}")

        return features

    def _calculate_market_relative_features(
        self, date: datetime, stock_pool: List[str], market_index: str
    ) -> pd.DataFrame:
        """计算市场相对强弱特征"""
        features = pd.DataFrame(index=stock_pool)

        try:
            lookback_start = date - pd.Timedelta(days=60)

            # 获取股票收益
            stock_returns = self._get_returns(lookback_start, date, stock_pool)

            # 获取市场指数收益
            market_returns = self._get_index_returns(lookback_start, date, market_index)

            # 计算相对强弱
            for period in [20, 60]:
                col_name = f"return_{period}d"
                if col_name not in stock_returns.columns:
                    continue

                market_ret = market_returns.get(f"return_{period}d", 0)

                # 超额收益
                features[f"market_alpha_{period}d"] = (
                    stock_returns[col_name] - market_ret
                )

                # 相对强弱（比率）
                features[f"rs_{period}d_market"] = (
                    1 + stock_returns[col_name]
                ) / (1 + market_ret) - 1

            # 波动率百分位
            if "volatility_20d" in stock_returns.columns:
                features["volatility_percentile"] = stock_returns["volatility_20d"].rank(
                    pct=True
                )

            # 成交量百分位
            if "volume_ratio" in stock_returns.columns:
                features["volume_percentile"] = stock_returns["volume_ratio"].rank(pct=True)

        except Exception as e:
            logger.error(f"Error calculating market relative features: {e}")

        return features

    def _regress_residual(
        self, y: pd.Series, x: pd.Series, add_constant: bool = True
    ) -> pd.Series:
        """计算回归残差"""
        from scipy.stats import linregress

        # 去除NaN
        valid_idx = y.notna() & x.notna()
        y_valid = y[valid_idx]
        x_valid = x[valid_idx]

        if len(y_valid) < 3:
            return pd.Series(index=y.index, dtype=float)

        # 简单线性回归
        slope, intercept, _, _, _ = linregress(x_valid, y_valid)

        # 预测值
        predicted = intercept + slope * x

        # 残差
        residual = y - predicted

        return residual

    def _get_returns(
        self, start_date: datetime, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取股票收益数据"""
        returns_df = pd.DataFrame(index=stock_pool)

        try:
            if self.data_manager is None:
                return returns_df

            # 批量获取数据
            batch_data = self.data_manager.get_batch_stock_data(
                stock_pool, start_date, end_date, adjust=True
            )

            for ts_code, df in batch_data.items():
                if df.empty or "adj_close" not in df.columns:
                    continue

                # Convert to float to handle MySQL DECIMAL types
                closes = df["adj_close"].astype(float)

                # 计算各周期收益
                if len(closes) >= 20:
                    returns_df.loc[ts_code, "return_20d"] = float(closes.iloc[-1] / closes.iloc[-20] - 1)
                    returns_df.loc[ts_code, "volatility_20d"] = float(closes.pct_change().std() * np.sqrt(252))

                if len(closes) >= 60:
                    returns_df.loc[ts_code, "return_60d"] = float(closes.iloc[-1] / closes.iloc[-60] - 1)

                # 成交量比率
                if "vol" in df.columns and len(df) >= 20:
                    vol = df["vol"].astype(float)
                    returns_df.loc[ts_code, "volume_ratio"] = float(vol.iloc[-5:].mean() / vol.iloc[-20:].mean())

        except Exception as e:
            logger.error(f"Error getting returns: {e}")

        return returns_df.fillna(0)

    def _get_industries(self, stock_pool: List[str]) -> Dict[str, str]:
        """获取股票行业分类"""
        if not self._industry_cache:
            try:
                if self.data_manager:
                    info = self.data_manager.get_batch_stock_info(stock_pool)
                    self._industry_cache = {
                        code: data.get("industry", "未知")
                        for code, data in info.items()
                    }
            except Exception as e:
                logger.error(f"Error getting industries: {e}")

        return {s: self._industry_cache.get(s, "未知") for s in stock_pool}

    def _get_index_returns(
        self, start_date: datetime, end_date: datetime, index_code: str
    ) -> Dict[str, float]:
        """获取指数收益"""
        returns = {}

        try:
            if self.data_manager is None:
                return returns

            df = self.data_manager.get_index_data(index_code, start_date, end_date)

            if df.empty or "close" not in df.columns:
                return returns

            closes = df["close"]

            if len(closes) >= 20:
                returns["return_20d"] = float(closes.iloc[-1] / closes.iloc[-20] - 1)

            if len(closes) >= 60:
                returns["return_60d"] = float(closes.iloc[-1] / closes.iloc[-60] - 1)

        except Exception as e:
            logger.debug(f"Error getting index returns: {e}")

        return returns

    # 数据库查询方法（需要根据实际数据库结构调整）
    def _fetch_daily_basic(self, date: datetime, stock_pool: List[str]) -> pd.DataFrame:
        """获取每日指标数据"""
        try:
            from core.storage.relational.connection import DatabaseManager

            date_str = date.strftime("%Y%m%d")
            placeholders = ",".join(["%s"] * len(stock_pool))

            sql = f"""
                SELECT ts_code, pe_ttm, pb, ps_ttm, pcf_ncf_ttm, dv_ttm,
                       total_mv, circ_mv
                FROM t_stock_daily_basic
                WHERE trade_date = %s AND ts_code IN ({placeholders})
            """

            results = DatabaseManager.fetchall(
                "tushare_biz", sql, (date_str,) + tuple(stock_pool)
            )

            if results:
                return pd.DataFrame(results).set_index("ts_code")

        except Exception as e:
            logger.debug(f"Fetch daily basic error: {e}")

        return pd.DataFrame()

    def _fetch_fina_indicator(self, date: datetime, stock_pool: List[str]) -> pd.DataFrame:
        """获取财务指标数据"""
        try:
            from core.storage.relational.connection import DatabaseManager

            # 获取最近的财报日期
            date_str = date.strftime("%Y%m%d")
            placeholders = ",".join(["%s"] * len(stock_pool))

            sql = f"""
                SELECT ts_code, end_date as ann_date,
                       roe, roa, grossprofit_margin, netprofit_margin,
                       op_yoy, or_yoy, netprofit_yoy, roe_yoy, assets_yoy
                FROM t_stock_fina_indicator
                WHERE ts_code IN ({placeholders})
                  AND end_date <= %s
                ORDER BY ts_code, end_date DESC
            """

            results = DatabaseManager.fetchall(
                "tushare_biz", sql, tuple(stock_pool) + (date_str,)
            )

            if results:
                df = pd.DataFrame(results)
                # 取每只股票的最新数据
                df = df.drop_duplicates(subset=["ts_code"], keep="first")
                return df.set_index("ts_code")

        except Exception as e:
            logger.debug(f"Fetch fina indicator error: {e}")

        return pd.DataFrame()

    def _fetch_moneyflow(self, date: datetime, stock_pool: List[str]) -> pd.DataFrame:
        """获取当日资金流向数据"""
        try:
            from core.storage.relational.connection import DatabaseManager

            date_str = date.strftime("%Y%m%d")
            placeholders = ",".join(["%s"] * len(stock_pool))

            sql = f"""
                SELECT ts_code, large_order_net_ratio, main_net_inflow,
                       retail_net_inflow
                FROM t_stock_moneyflow
                WHERE trade_date = %s AND ts_code IN ({placeholders})
            """

            results = DatabaseManager.fetchall(
                "tushare_biz", sql, (date_str,) + tuple(stock_pool)
            )

            if results:
                return pd.DataFrame(results).set_index("ts_code")

        except Exception as e:
            logger.debug(f"Fetch moneyflow error: {e}")

        return pd.DataFrame()

    def _fetch_moneyflow_window(
        self, start_date: datetime, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """获取一段时间内的资金流向数据"""
        try:
            from core.storage.relational.connection import DatabaseManager

            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            placeholders = ",".join(["%s"] * len(stock_pool))

            sql = f"""
                SELECT ts_code, trade_date, net_mf_amount
                FROM t_stock_moneyflow
                WHERE trade_date BETWEEN %s AND %s
                  AND ts_code IN ({placeholders})
            """

            results = DatabaseManager.fetchall(
                "tushare_biz", sql, (start_str, end_str) + tuple(stock_pool)
            )

            if results:
                return pd.DataFrame(results)

        except Exception as e:
            logger.debug(f"Fetch moneyflow window error: {e}")

        return pd.DataFrame()


class FactorPipeline:
    """
    因子处理流水线

    整合多个因子处理步骤：
    1. 缺失值处理
    2. 异常值处理（Winsorize）
    3. 标准化（Z-score/Rank）
    4. 中性化
    """

    def __init__(self, methods: Optional[List[str]] = None):
        self.methods = methods or ["winsorize", "zscore"]

    def process(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """处理特征矩阵"""
        df = features_df.copy()

        for method in self.methods:
            if method == "winsorize":
                df = self._winsorize(df)
            elif method == "zscore":
                df = self._zscore(df)
            elif method == "rank":
                df = self._rank(df)
            elif method == "fillna":
                df = df.fillna(df.median())

        return df

    def _winsorize(self, df: pd.DataFrame, limits: Tuple[float, float] = (0.01, 0.01)) -> pd.DataFrame:
        """缩尾处理"""
        result = df.copy()
        for col in result.select_dtypes(include=[np.number]).columns:
            lower = result[col].quantile(limits[0])
            upper = result[col].quantile(1 - limits[1])
            result[col] = result[col].clip(lower, upper)
        return result

    def _zscore(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化"""
        result = df.copy()
        for col in result.select_dtypes(include=[np.number]).columns:
            mean = result[col].mean()
            std = result[col].std()
            if std > 0:
                result[col] = (result[col] - mean) / std
        return result

    def _rank(self, df: pd.DataFrame) -> pd.DataFrame:
        """排名标准化"""
        result = df.copy()
        n = len(result)
        for col in result.select_dtypes(include=[np.number]).columns:
            result[col] = result[col].rank(pct=True) * 2 - 1  # 映射到[-1, 1]
        return result


def create_standard_pipeline() -> FactorPipeline:
    """创建标准因子处理流水线"""
    return FactorPipeline(methods=["fillna", "winsorize", "zscore"])


def create_rank_pipeline() -> FactorPipeline:
    """创建排名因子处理流水线"""
    return FactorPipeline(methods=["fillna", "rank"])
