"""
信息系数(IC)分析模块

功能：
- IC计算（Pearson和Rank IC）
- IC统计（均值、标准差、IR）
- IC时间序列分析
- 分位数收益分析
- 因子相关性分析
- 因子衰减分析
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy import stats

from core.logger import get_logger

logger = get_logger(__name__)


class ICType(Enum):
    """IC类型"""
    PEARSON = "pearson"  # Pearson相关系数
    SPEARMAN = "spearman"  # Spearman秩相关系数


@dataclass
class ICStatistics:
    """IC统计结果"""

    # 基础统计
    ic_mean: float  # IC均值
    ic_std: float  # IC标准差
    ic_ir: float  # ICIR（信息比率）
    ic_tstat: float  # t统计量
    ic_pvalue: float  # p值

    # 胜率统计
    ic_win_rate: float  # IC胜率（IC>0的比例）
    ic_positive_count: int  # 正IC数量
    ic_total_count: int  # 总数量

    # 极值统计
    ic_max: float  # 最大IC
    ic_min: float  # 最小IC
    ic_skew: float  # IC偏度
    ic_kurt: float  # IC峰度

    # 稳定性
    ic_autocorr: float  # IC自相关性
    ic_stability: float  # IC稳定性（1 - 标准差/绝对均值）


@dataclass
class QuantileReturn:
    """分位数收益"""

    quantile: int  # 分位
    mean_return: float  # 平均收益
    std_return: float  # 收益标准差
    sharpe: float  # 夏普比率
    cum_return: float  # 累计收益
    win_rate: float  # 胜率

    # 与最低分位的对比
    spread: float = 0.0  # 与最低分位的收益差
    tstat_spread: float = 0.0  # 收益差的t统计量


class ICAnalyzer:
    """
    信息系数分析器

    评估因子的预测能力
    """

    def __init__(self, ic_type: ICType = ICType.SPEARMAN):
        self.ic_type = ic_type
        self.ic_history: pd.DataFrame = pd.DataFrame()

    def calculate_ic(
        self,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        method: Optional[ICType] = None,
    ) -> float:
        """
        计算单期IC

        Args:
            factor_values: 因子值
            forward_returns: 未来收益
            method: IC类型

        Returns:
            IC值
        """
        method = method or self.ic_type

        # 对齐数据
        common_idx = factor_values.index.intersection(forward_returns.index)
        x = factor_values.loc[common_idx]
        y = forward_returns.loc[common_idx]

        # 去除NaN
        valid = x.notna() & y.notna()
        x = x[valid]
        y = y[valid]

        if len(x) < 10:
            return np.nan

        if method == ICType.PEARSON:
            ic, _ = stats.pearsonr(x, y)
        else:
            ic, _ = stats.spearmanr(x, y)

        return ic

    def calculate_ic_series(
        self,
        factor_data: pd.DataFrame,
        returns_data: pd.DataFrame,
        periods: List[int] = [1, 5, 10, 20],
    ) -> pd.DataFrame:
        """
        计算IC时间序列

        Args:
            factor_data: 因子数据 (dates x stocks)
            returns_data: 收益数据 (dates x stocks)
            periods: 前瞻周期

        Returns:
            IC时间序列DataFrame
        """
        ic_results = []

        dates = factor_data.index

        for i, date in enumerate(dates[:-max(periods)]):
            factor_row = factor_data.loc[date]

            for period in periods:
                if i + period >= len(dates):
                    continue

                return_date = dates[i + period]
                return_row = returns_data.loc[return_date]

                ic = self.calculate_ic(factor_row, return_row)

                ic_results.append({
                    "date": date,
                    "period": period,
                    "ic": ic,
                })

        ic_df = pd.DataFrame(ic_results)
        self.ic_history = ic_df

        return ic_df

    def calculate_statistics(self, ic_series: pd.Series) -> ICStatistics:
        """
        计算IC统计量

        Args:
            ic_series: IC序列

        Returns:
            IC统计结果
        """
        ic_clean = ic_series.dropna()

        if len(ic_clean) == 0:
            return ICStatistics(
                ic_mean=0, ic_std=0, ic_ir=0, ic_tstat=0, ic_pvalue=1,
                ic_win_rate=0, ic_positive_count=0, ic_total_count=0,
                ic_max=0, ic_min=0, ic_skew=0, ic_kurt=0,
                ic_autocorr=0, ic_stability=0,
            )

        # 基础统计
        mean = ic_clean.mean()
        std = ic_clean.std()
        ir = mean / std if std > 0 else 0

        # t检验
        tstat, pvalue = stats.ttest_1samp(ic_clean, 0)

        # 胜率
        positive_count = (ic_clean > 0).sum()
        win_rate = positive_count / len(ic_clean)

        # 自相关
        autocorr = ic_clean.autocorr(lag=1) if len(ic_clean) > 1 else 0

        # 稳定性
        stability = 1 - std / abs(mean) if mean != 0 else 0

        return ICStatistics(
            ic_mean=mean,
            ic_std=std,
            ic_ir=ir,
            ic_tstat=tstat,
            ic_pvalue=pvalue,
            ic_win_rate=win_rate,
            ic_positive_count=positive_count,
            ic_total_count=len(ic_clean),
            ic_max=ic_clean.max(),
            ic_min=ic_clean.min(),
            ic_skew=ic_clean.skew(),
            ic_kurt=ic_clean.kurt(),
            ic_autocorr=autocorr,
            ic_stability=stability,
        )

    def analyze_factor_decay(
        self,
        factor_data: pd.DataFrame,
        returns_data: pd.DataFrame,
        max_period: int = 20,
    ) -> pd.DataFrame:
        """
        分析因子衰减

        Args:
            factor_data: 因子数据
            returns_data: 收益数据
            max_period: 最大前瞻周期

        Returns:
            衰减分析结果
        """
        periods = list(range(1, max_period + 1))
        results = []

        for period in periods:
            ic_series = []

            dates = factor_data.index
            for i, date in enumerate(dates[:-period]):
                factor_row = factor_data.loc[date]

                if i + period < len(dates):
                    return_date = dates[i + period]
                    return_row = returns_data.loc[return_date]

                    ic = self.calculate_ic(factor_row, return_row)
                    if not np.isnan(ic):
                        ic_series.append(ic)

            if ic_series:
                ic_arr = pd.Series(ic_series)
                stats = self.calculate_statistics(ic_arr)

                results.append({
                    "period": period,
                    "ic_mean": stats.ic_mean,
                    "ic_std": stats.ic_std,
                    "ic_ir": stats.ic_ir,
                    "ic_win_rate": stats.ic_win_rate,
                })

        return pd.DataFrame(results)

    def get_ic_report(self, ic_series: pd.Series) -> str:
        """生成IC分析报告"""
        stats = self.calculate_statistics(ic_series)

        lines = [
            "=" * 50,
            "IC Analysis Report",
            "=" * 50,
            f"Mean IC:         {stats.ic_mean:8.4f}",
            f"IC Std:          {stats.ic_std:8.4f}",
            f"ICIR:            {stats.ic_ir:8.4f}",
            f"t-statistic:     {stats.ic_tstat:8.4f}",
            f"p-value:         {stats.ic_pvalue:8.4f}",
            f"Win Rate:        {stats.ic_win_rate*100:7.2f}%",
            f"Positive/Total:  {stats.ic_positive_count}/{stats.ic_total_count}",
            f"Max IC:          {stats.ic_max:8.4f}",
            f"Min IC:          {stats.ic_min:8.4f}",
            f"Stability:       {stats.ic_stability:8.4f}",
            "=" * 50,
        ]

        return "\n".join(lines)


class QuantileAnalyzer:
    """
    分位数收益分析器

    分析因子分层的单调性
    """

    def __init__(self, n_quantiles: int = 5):
        self.n_quantiles = n_quantiles

    def analyze(
        self,
        factor_data: pd.DataFrame,
        returns_data: pd.DataFrame,
        period: int = 5,
    ) -> Tuple[List[QuantileReturn], pd.DataFrame]:
        """
        分位数收益分析

        Returns:
            (分位数收益列表, 详细数据)
        """
        all_results = []

        dates = factor_data.index

        for i, date in enumerate(dates[:-period]):
            factor_row = factor_data.loc[date]
            return_date = dates[i + period]
            return_row = returns_data.loc[return_date]

            # 计算分位数
            quantile_result = self._calculate_quantile_returns(
                factor_row, return_row
            )
            quantile_result["date"] = date
            all_results.append(quantile_result)

        # 合并结果
        combined_df = pd.concat(all_results, ignore_index=True)

        # 计算统计量
        quantile_stats = []
        for q in range(1, self.n_quantiles + 1):
            q_data = combined_df[combined_df["quantile"] == q]["return"]

            if len(q_data) > 0:
                quantile_stats.append(QuantileReturn(
                    quantile=q,
                    mean_return=q_data.mean(),
                    std_return=q_data.std(),
                    sharpe=q_data.mean() / q_data.std() if q_data.std() > 0 else 0,
                    cum_return=(1 + q_data).prod() - 1,
                    win_rate=(q_data > 0).mean(),
                ))

        # 计算spread
        if len(quantile_stats) >= 2:
            top = quantile_stats[-1]
            bottom = quantile_stats[0]

            top_data = combined_df[combined_df["quantile"] == self.n_quantiles]["return"]
            bottom_data = combined_df[combined_df["quantile"] == 1]["return"]

            spread_data = top_data.values - bottom_data.values

            top.spread = top.mean_return - bottom.mean_return
            top.tstat_spread = stats.ttest_1samp(spread_data, 0)[0] if len(spread_data) > 0 else 0

        return quantile_stats, combined_df

    def _calculate_quantile_returns(
        self, factor_row: pd.Series, return_row: pd.Series
    ) -> pd.DataFrame:
        """计算单期分位数收益"""
        # 对齐
        common_idx = factor_row.index.intersection(return_row.index)
        factor = factor_row.loc[common_idx]
        returns = return_row.loc[common_idx]

        # 去除NaN
        valid = factor.notna() & returns.notna()
        factor = factor[valid]
        returns = returns[valid]

        if len(factor) < self.n_quantiles * 2:
            return pd.DataFrame()

        # 计算分位数
        try:
            factor_quantiles = pd.qcut(factor, self.n_quantiles, labels=False) + 1
        except ValueError:
            # 分位数计算失败
            return pd.DataFrame()

        result = pd.DataFrame({
            "quantile": factor_quantiles,
            "return": returns,
        })

        return result

    def calculate_monotonicity(self, quantile_stats: List[QuantileReturn]) -> float:
        """计算单调性（Rank correlation）"""
        if len(quantile_stats) < 2:
            return 0.0

        quantiles = [q.quantile for q in quantile_stats]
        returns = [q.mean_return for q in quantile_stats]

        corr, _ = stats.spearmanr(quantiles, returns)
        return corr

    def get_quantile_report(self, quantile_stats: List[QuantileReturn]) -> str:
        """生成分位数收益报告"""
        mono = self.calculate_monotonicity(quantile_stats)

        lines = [
            "=" * 70,
            "Quantile Returns Analysis",
            "=" * 70,
            f"{'Quantile':<10} {'Mean Return':<15} {'Std':<12} {'Sharpe':<10} {'Win Rate':<10}",
            "-" * 70,
        ]

        for stat in quantile_stats:
            lines.append(
                f"{stat.quantile:<10} {stat.mean_return*100:14.4f}% "
                f"{stat.std_return*100:11.4f}% {stat.sharpe:10.2f} "
                f"{stat.win_rate*100:9.2f}%"
            )

        if len(quantile_stats) >= 2:
            lines.append("-" * 70)
            top = quantile_stats[-1]
            bottom = quantile_stats[0]
            lines.append(
                f"Top-Bottom Spread: {top.spread*100:.4f}% (t={top.tstat_spread:.2f})"
            )

        lines.extend([
            "=" * 70,
            f"Monotonicity (Rank Corr): {mono:.4f}",
            "=" * 70,
        ])

        return "\n".join(lines)


class FactorCorrelationAnalyzer:
    """因子相关性分析器"""

    def calculate_correlation_matrix(
        self, factor_data: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        计算因子间相关系数矩阵

        Args:
            factor_data: {factor_name: factor_df}

        Returns:
            相关系数矩阵
        """
        # 计算每个因子的IC时间序列
        ic_series = {}

        for name, df in factor_data.items():
            # 使用第一列作为代表
            if len(df.columns) > 0:
                ic_series[name] = df.iloc[:, 0]

        if not ic_series:
            return pd.DataFrame()

        ic_df = pd.DataFrame(ic_series)

        return ic_df.corr()

    def calculate_cross_sectional_correlation(
        self,
        factor1: pd.DataFrame,
        factor2: pd.DataFrame,
    ) -> pd.Series:
        """
        计算两个因子的横截面平均相关系数时间序列
        """
        corr_series = []
        dates = []

        common_dates = factor1.index.intersection(factor2.index)

        for date in common_dates:
            f1 = factor1.loc[date]
            f2 = factor2.loc[date]

            # 对齐
            common_stocks = f1.index.intersection(f2.index)
            f1 = f1.loc[common_stocks]
            f2 = f2.loc[common_stocks]

            # 去除NaN
            valid = f1.notna() & f2.notna()
            f1 = f1[valid]
            f2 = f2[valid]

            if len(f1) > 10:
                corr, _ = stats.spearmanr(f1, f2)
                corr_series.append(corr)
                dates.append(date)

        return pd.Series(corr_series, index=dates)


def analyze_factor_performance(
    factor_data: pd.DataFrame,
    returns_data: pd.DataFrame,
    factor_name: str = "",
) -> Dict[str, Any]:
    """
    综合分析因子表现

    Returns:
        包含IC分析和分位数分析的字典
    """
    logger.info(f"Analyzing factor: {factor_name}")

    # IC分析
    ic_analyzer = ICAnalyzer(ic_type=ICType.SPEARMAN)
    ic_series = ic_analyzer.calculate_ic_series(factor_data, returns_data)

    stats = None
    if not ic_series.empty:
        for period in ic_series["period"].unique():
            period_ic = ic_series[ic_series["period"] == period]["ic"]
            period_stats = ic_analyzer.calculate_statistics(period_ic)
            logger.info(f"\nPeriod {period}d IC Statistics:")
            logger.info(ic_analyzer.get_ic_report(period_ic))

        # 使用第一个周期作为代表
        first_period = ic_series["period"].unique()[0]
        stats = ic_analyzer.calculate_statistics(
            ic_series[ic_series["period"] == first_period]["ic"]
        )

    # 分位数分析
    quant_analyzer = QuantileAnalyzer(n_quantiles=5)
    quant_stats, quant_df = quant_analyzer.analyze(factor_data, returns_data, period=5)

    logger.info("\n" + quant_analyzer.get_quantile_report(quant_stats))

    # 衰减分析
    decay_df = ic_analyzer.analyze_factor_decay(factor_data, returns_data)

    return {
        "ic_series": ic_series,
        "ic_statistics": stats,
        "quantile_stats": quant_stats,
        "quantile_data": quant_df,
        "decay_analysis": decay_df,
    }
