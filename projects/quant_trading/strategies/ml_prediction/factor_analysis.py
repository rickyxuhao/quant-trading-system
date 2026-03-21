"""
因子有效性分析模块

基于《A股因子挖掘库构建指南》最佳实践实现：
- IC（信息系数）分析：因子与future returns的横截面相关系数
- ICIR（信息比率）：IC均值/IC标准差，评估稳定性
- 分层回测：十分组/五分组构建，检验单调性
- Fama-MacBeth回归：横截面+时间序列联合检验
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy import stats

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager
from projects.quant_trading.backtest.data_manager import DataManager
from projects.quant_trading.strategies.ml_prediction.precomputed_factors import (
    FactorPrecomputer, get_factor_precomputer
)

logger = get_logger(__name__)


class FactorDirection(Enum):
    """因子方向预期"""
    POSITIVE = 1   # 正向预期（如ROE越高越好）
    NEGATIVE = -1  # 负向预期（如PE越低越好）
    NEUTRAL = 0    # 中性（需数据检验）


@dataclass
class ICResult:
    """IC分析结果"""
    factor_name: str
    ic_mean: float
    ic_std: float
    icir: float
    ic_positive_ratio: float
    ic_significant_ratio: float
    t_statistic: float
    p_value: float
    ic_series: pd.Series
    dates: List[str]
    rolling_icir_63d: Optional[pd.Series] = None  # 63日滚动ICIR序列

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor_name': self.factor_name,
            'ic_mean': self.ic_mean,
            'ic_std': self.ic_std,
            'icir': self.icir,
            'ic_positive_ratio': self.ic_positive_ratio,
            'ic_significant_ratio': self.ic_significant_ratio,
            't_statistic': self.t_statistic,
            'p_value': self.p_value,
        }


@dataclass
class QuantileBacktestResult:
    """分层回测结果"""
    factor_name: str
    n_quantiles: int
    forward_period: int
    quantile_returns: pd.DataFrame  # 各分组的收益率时序
    long_short_returns: pd.Series   # 多空组合收益率
    long_short_cumulative: pd.Series  # 多空累计收益
    long_short_sharpe: float
    monotonicity_score: float  # 单调性得分
    quantile_stats: Dict[int, Dict[str, float]]  # 各分组的统计指标

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor_name': self.factor_name,
            'n_quantiles': self.n_quantiles,
            'forward_period': self.forward_period,
            'long_short_sharpe': self.long_short_sharpe,
            'monotonicity_score': self.monotonicity_score,
            'quantile_avg_returns': self.quantile_returns.mean().to_dict(),
        }


@dataclass
class FamaMacBethResult:
    """Fama-MacBeth回归结果"""
    factor_name: str
    factor_premia_mean: float
    factor_premia_std: float
    t_statistic: float
    p_value: float
    r_squared_avg: float
    annualized_premia: float
    premia_series: pd.Series
    dates: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor_name': self.factor_name,
            'factor_premia_mean': self.factor_premia_mean,
            'factor_premia_std': self.factor_premia_std,
            't_statistic': self.t_statistic,
            'p_value': self.p_value,
            'r_squared_avg': self.r_squared_avg,
            'annualized_premia': self.annualized_premia,
        }


class FactorAnalyzer:
    """
    因子有效性分析器

    主要功能：
    1. IC分析：计算因子与forward returns的横截面相关系数
    2. 分层回测：构建分位数组合检验因子单调性
    3. Fama-MacBeth回归：横截面+时间序列联合检验
    """

    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        stock_pool: Optional[List[str]] = None,
        min_stocks_per_day: int = 100
    ):
        """
        初始化因子分析器

        Args:
            start_date: 分析开始日期
            end_date: 分析结束日期
            stock_pool: 股票池（默认全市场）
            min_stocks_per_day: 每日最少股票数（过滤数据不足日期）
        """
        self.start_date = start_date or datetime(2019, 1, 1)
        self.end_date = end_date or datetime(2024, 12, 31)
        self.stock_pool = stock_pool
        self.min_stocks_per_day = min_stocks_per_day
        self.precomputer = get_factor_precomputer()
        self.data_manager = DataManager()

        # 缓存
        self._trade_dates: Optional[List[datetime]] = None
        self._forward_returns_cache: Dict[int, pd.DataFrame] = {}

    def _get_trade_dates(self) -> List[datetime]:
        """获取交易日列表"""
        if self._trade_dates is None:
            self._trade_dates = self.data_manager.get_trade_dates(
                self.start_date, self.end_date
            )
        return self._trade_dates

    def _fetch_forward_return_for_date(
        self,
        args: Tuple,
    ) -> Optional[pd.DataFrame]:
        """单日前瞻收益计算（供并行调用）"""
        i, date, trade_dates, all_stocks, forward_period, min_stocks = args
        if i + forward_period >= len(trade_dates):
            return None

        target_date = trade_dates[i + forward_period]
        date_str = date.strftime('%Y%m%d')

        try:
            df_current = self.data_manager.get_batch_stock_data(
                ts_codes=all_stocks, fields=['close'], trade_date=date
            )
            df_target = self.data_manager.get_batch_stock_data(
                ts_codes=all_stocks, fields=['close'], trade_date=target_date
            )

            if df_current.empty or df_target.empty:
                return None

            merged = df_current[['close']].join(
                df_target[['close']], rsuffix='_target', how='inner'
            )

            if len(merged) < min_stocks:
                return None

            merged['forward_return'] = merged['close_target'] / merged['close'] - 1
            merged['trade_date'] = date_str
            merged.reset_index(inplace=True)
            merged.set_index(['trade_date', 'ts_code'], inplace=True)
            return merged[['forward_return']]

        except Exception as e:
            logger.warning(f"Failed to compute forward return for {date_str}: {e}")
            return None

    def _get_forward_returns(
        self,
        forward_period: int = 20,
        refresh_cache: bool = False,
        max_workers: int = 4,
    ) -> pd.DataFrame:
        """
        获取前瞻收益率数据（并行批量拉取）

        Args:
            forward_period: 前瞻期（交易日）
            refresh_cache: 是否刷新缓存
            max_workers: 并行线程数

        Returns:
            DataFrame: index=[trade_date, ts_code], columns=[forward_return]
        """
        if not refresh_cache and forward_period in self._forward_returns_cache:
            return self._forward_returns_cache[forward_period]

        trade_dates = self._get_trade_dates()

        # 获取股票池
        if self.stock_pool is None:
            all_stocks = self.precomputer._get_all_stocks(trade_dates[-1])
        else:
            all_stocks = self.stock_pool

        logger.info(
            f"Computing {forward_period}d forward returns for {len(all_stocks)} stocks "
            f"(parallel, workers={max_workers})..."
        )

        # 构建任务列表
        tasks = [
            (i, date, trade_dates, all_stocks, forward_period, self.min_stocks_per_day)
            for i, date in enumerate(trade_dates)
            if i + forward_period < len(trade_dates)
        ]

        forward_returns_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._fetch_forward_return_for_date, task): task
                for task in tasks
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    forward_returns_list.append(result)

        if forward_returns_list:
            result = pd.concat(forward_returns_list).sort_index()
        else:
            result = pd.DataFrame(columns=['forward_return'])

        self._forward_returns_cache[forward_period] = result
        logger.info(f"Forward returns computed: {len(result)} records")

        return result

    def calculate_ic(
        self,
        factor_name: str,
        forward_period: int = 20,
        method: str = 'spearman'
    ) -> ICResult:
        """
        计算IC（信息系数）

        IC衡量因子对未来收益的预测能力。
        - IC均值：预测能力的方向和强度
        - ICIR：IC均值/IC标准差，评估IC稳定性
        - IC>0比例：因子方向一致性

        Args:
            factor_name: 因子名称
            forward_period: 前瞻期（交易日）
            method: 相关系数方法 ('spearman' 或 'pearson')

        Returns:
            ICResult: IC分析结果
        """
        trade_dates = self._get_trade_dates()

        # 获取因子数据
        factor_data_list = []
        for date in trade_dates:
            try:
                factors = self.precomputer.get_precomputed_factors(
                    trade_date=date,
                    stock_pool=self.stock_pool
                )

                if factors.empty or factor_name not in factors.columns:
                    continue

                if len(factors) < self.min_stocks_per_day:
                    continue

                factors['trade_date'] = date.strftime('%Y%m%d')
                factors.reset_index(inplace=True)
                factors.set_index(['trade_date', 'ts_code'], inplace=True)
                factor_data_list.append(factors[[factor_name]])

            except Exception as e:
                logger.warning(f"Failed to get factor data for {date}: {e}")
                continue

        if not factor_data_list:
            raise ValueError(f"No factor data available for {factor_name}")

        factor_df = pd.concat(factor_data_list)

        # 获取前瞻收益
        forward_returns = self._get_forward_returns(forward_period)

        # 对齐数据
        aligned = factor_df.join(forward_returns, how='inner')

        if aligned.empty:
            raise ValueError("No aligned data between factor and forward returns")

        # 向量化计算每日IC（使用 groupby + apply）
        def _calc_ic_for_group(group: pd.DataFrame) -> float:
            fv = group[factor_name].dropna()
            rv = group['forward_return'].dropna()
            common = fv.index.intersection(rv.index)
            if len(common) < 10:
                return np.nan
            fv, rv = fv.loc[common], rv.loc[common]
            if method == 'spearman':
                ic, _ = stats.spearmanr(fv, rv)
            else:
                ic, _ = stats.pearsonr(fv, rv)
            return ic if not np.isnan(ic) else np.nan

        # 过滤掉股票数量不足的日期
        date_counts = aligned.groupby(level=0).size()
        valid_dates = date_counts[date_counts >= self.min_stocks_per_day].index

        if len(valid_dates) == 0:
            raise ValueError("Could not calculate IC for any date")

        ic_raw = aligned.loc[valid_dates].groupby(level=0).apply(_calc_ic_for_group)
        ic_raw = ic_raw.dropna()

        if len(ic_raw) == 0:
            raise ValueError("Could not calculate IC for any date")

        ic_by_date = ic_raw.tolist()
        dates = ic_raw.index.tolist()

        ic_series = pd.Series(ic_by_date, index=dates)

        # 计算统计指标
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        ic_positive_ratio = (ic_series > 0).mean()

        # IC显著性检验（|IC| > 2/sqrt(N)）
        avg_n = aligned.groupby(level=0).size().mean()
        ic_threshold = 2 / np.sqrt(avg_n)
        ic_significant_ratio = (ic_series.abs() > ic_threshold).mean()

        # t检验
        t_stat, p_value = stats.ttest_1samp(ic_series, 0)

        # 63日滚动ICIR（季度窗口）
        rolling_window = 63
        rolling_ic_mean = ic_series.rolling(rolling_window, min_periods=rolling_window // 2).mean()
        rolling_ic_std = ic_series.rolling(rolling_window, min_periods=rolling_window // 2).std()
        rolling_icir_63d = rolling_ic_mean / rolling_ic_std.replace(0, np.nan)

        return ICResult(
            factor_name=factor_name,
            ic_mean=ic_mean,
            ic_std=ic_std,
            icir=icir,
            ic_positive_ratio=ic_positive_ratio,
            ic_significant_ratio=ic_significant_ratio,
            t_statistic=t_stat,
            p_value=p_value,
            ic_series=ic_series,
            dates=dates,
            rolling_icir_63d=rolling_icir_63d,
        )

    def quantile_backtest(
        self,
        factor_name: str,
        n_quantiles: int = 10,
        forward_period: int = 20
    ) -> QuantileBacktestResult:
        """
        分层回测

        将股票按因子值分n组，检验各组收益单调性。
        高分组应显著跑赢低分组（因子有效性的直观检验）。

        Args:
            factor_name: 因子名称
            n_quantiles: 分位数数量（5或10）
            forward_period: 前瞻期（交易日）

        Returns:
            QuantileBacktestResult: 分层回测结果
        """
        trade_dates = self._get_trade_dates()
        forward_returns = self._get_forward_returns(forward_period)

        quantile_returns = {i: [] for i in range(1, n_quantiles + 1)}
        long_short_returns = []
        dates = []

        for date in trade_dates:
            date_str = date.strftime('%Y%m%d')

            # 检查是否有前瞻收益数据
            if date_str not in forward_returns.index.get_level_values(0):
                continue

            try:
                # 获取因子数据
                factors = self.precomputer.get_precomputed_factors(
                    trade_date=date,
                    stock_pool=self.stock_pool
                )

                if factors.empty or factor_name not in factors.columns:
                    continue

                factor_vals = factors[factor_name].dropna()

                if len(factor_vals) < self.min_stocks_per_day:
                    continue

                # 获取当日的前瞻收益
                day_forward = forward_returns.loc[date_str]['forward_return']
                if isinstance(day_forward, pd.DataFrame):
                    day_forward = day_forward['forward_return']

                # 对齐
                common_idx = factor_vals.index.intersection(day_forward.index)
                factor_vals = factor_vals.loc[common_idx]
                day_forward = day_forward.loc[common_idx]

                if len(factor_vals) < n_quantiles * 10:  # 每组至少10只
                    continue

                # 分位数分组
                factor_vals = factor_vals.rank(pct=True)

                for q in range(1, n_quantiles + 1):
                    lower = (q - 1) / n_quantiles
                    upper = q / n_quantiles

                    if q == 1:
                        mask = factor_vals <= upper
                    elif q == n_quantiles:
                        mask = factor_vals > lower
                    else:
                        mask = (factor_vals > lower) & (factor_vals <= upper)

                    group_returns = day_forward[mask]
                    avg_return = group_returns.mean()
                    quantile_returns[q].append(avg_return)

                # 多空组合（最高分位 - 最低分位）
                top_mask = factor_vals > (n_quantiles - 1) / n_quantiles
                bottom_mask = factor_vals <= 1 / n_quantiles

                long_return = day_forward[top_mask].mean()
                short_return = day_forward[bottom_mask].mean()
                long_short = long_return - short_return

                long_short_returns.append(long_short)
                dates.append(date_str)

            except Exception as e:
                logger.warning(f"Failed to process {date_str}: {e}")
                continue

        if not dates:
            raise ValueError("No valid data for quantile backtest")

        # 构建结果DataFrame
        quantile_df = pd.DataFrame(quantile_returns, index=dates)
        long_short_series = pd.Series(long_short_returns, index=dates)

        # 计算统计指标
        quantile_stats = {}
        for q in range(1, n_quantiles + 1):
            returns = quantile_df[q]
            quantile_stats[q] = {
                'mean_return': returns.mean(),
                'std': returns.std(),
                'sharpe': returns.mean() / returns.std() * np.sqrt(252 / forward_period)
                if returns.std() > 0 else 0,
            }

        # 单调性得分：计算各组平均收益的秩相关系数
        avg_returns = [quantile_stats[q]['mean_return'] for q in range(1, n_quantiles + 1)]
        ranks = list(range(1, n_quantiles + 1))
        monotonicity, _ = stats.spearmanr(ranks, avg_returns)

        # 多空组合指标
        long_short_sharpe = (
            long_short_series.mean() / long_short_series.std() *
            np.sqrt(252 / forward_period)
            if long_short_series.std() > 0 else 0
        )

        # 累计收益
        long_short_cumulative = (1 + long_short_series).cumprod()

        return QuantileBacktestResult(
            factor_name=factor_name,
            n_quantiles=n_quantiles,
            forward_period=forward_period,
            quantile_returns=quantile_df,
            long_short_returns=long_short_series,
            long_short_cumulative=long_short_cumulative,
            long_short_sharpe=long_short_sharpe,
            monotonicity_score=monotonicity,
            quantile_stats=quantile_stats
        )

    def fama_macbeth_regression(
        self,
        factor_names: List[str],
        forward_period: int = 20,
        control_factors: Optional[List[str]] = None
    ) -> Dict[str, FamaMacBethResult]:
        """
        Fama-MacBeth回归

        两阶段估计方法：
        1. 第一阶段：每个截面做OLS回归，得到因子暴露的估计
        2. 第二阶段：对时序上的估计值取平均，进行t检验

        优点：同时考虑横截面和时间序列，处理异方差和自相关

        Args:
            factor_names: 要检验的因子列表
            forward_period: 前瞻期（交易日）
            control_factors: 控制变量（如市值、行业等）

        Returns:
            Dict[str, FamaMacBethResult]: 各因子的回归结果
        """
        import statsmodels.api as sm

        trade_dates = self._get_trade_dates()
        forward_returns = self._get_forward_returns(forward_period)

        all_factors = factor_names + (control_factors or [])

        # 收集每日回归系数
        daily_coeffs = {name: [] for name in all_factors}
        daily_r2 = []
        valid_dates = []

        for date in trade_dates:
            date_str = date.strftime('%Y%m%d')

            if date_str not in forward_returns.index.get_level_values(0):
                continue

            try:
                # 获取因子数据
                factors = self.precomputer.get_precomputed_factors(
                    trade_date=date,
                    stock_pool=self.stock_pool
                )

                if factors.empty:
                    continue

                # 检查所需因子是否都存在
                missing = set(all_factors) - set(factors.columns)
                if missing:
                    continue

                # 获取前瞻收益
                day_forward = forward_returns.loc[date_str]['forward_return']
                if isinstance(day_forward, pd.DataFrame):
                    day_forward = day_forward['forward_return']

                # 构建回归数据
                X = factors[all_factors].copy()
                y = day_forward.reindex(X.index)

                # 对齐并删除缺失值
                valid_idx = X.dropna().index.intersection(y.dropna().index)
                X = X.loc[valid_idx]
                y = y.loc[valid_idx]

                if len(X) < self.min_stocks_per_day:
                    continue

                # 标准化因子（横截面Z-score）
                X = (X - X.mean()) / X.std()
                X = X.fillna(0)

                # 添加常数项
                X = sm.add_constant(X)

                # OLS回归
                model = sm.OLS(y, X).fit()

                # 保存系数
                for name in all_factors:
                    if name in model.params:
                        daily_coeffs[name].append(model.params[name])
                    else:
                        daily_coeffs[name].append(0)

                daily_r2.append(model.rsquared)
                valid_dates.append(date_str)

            except Exception as e:
                logger.warning(f"Failed Fama-MacBeth for {date_str}: {e}")
                continue

        if not valid_dates:
            raise ValueError("No valid data for Fama-MacBeth regression")

        # 计算结果
        results = {}
        for name in factor_names:
            coeffs = pd.Series(daily_coeffs[name], index=valid_dates)

            mean_premia = coeffs.mean()
            std_premia = coeffs.std()
            t_stat, p_value = stats.ttest_1samp(coeffs, 0)

            # 年化因子溢价
            annualized = mean_premia * (252 / forward_period)

            results[name] = FamaMacBethResult(
                factor_name=name,
                factor_premia_mean=mean_premia,
                factor_premia_std=std_premia,
                t_statistic=t_stat,
                p_value=p_value,
                r_squared_avg=np.mean(daily_r2),
                annualized_premia=annualized,
                premia_series=coeffs,
                dates=valid_dates
            )

        return results

    def comprehensive_analysis(
        self,
        factor_names: List[str],
        forward_periods: List[int] = [5, 10, 20],
        quantile_period: int = 20
    ) -> pd.DataFrame:
        """
        综合因子分析

        对多个因子进行完整的有效性检验，返回汇总报告。

        Args:
            factor_names: 要分析的因子列表
            forward_periods: 前瞻期列表（用于IC分析）
            quantile_period: 分层回测的前瞻期

        Returns:
            DataFrame: 各因子的综合评估指标
        """
        results = []

        for factor in factor_names:
            logger.info(f"Analyzing factor: {factor}")
            factor_result = {'factor_name': factor}

            # IC分析（多个前瞻期）
            for period in forward_periods:
                try:
                    ic_result = self.calculate_ic(factor, forward_period=period)
                    factor_result[f'ic_mean_{period}d'] = ic_result.ic_mean
                    factor_result[f'icir_{period}d'] = ic_result.icir
                    factor_result[f'ic_significant_{period}d'] = ic_result.ic_significant_ratio
                except Exception as e:
                    logger.warning(f"IC analysis failed for {factor}@{period}d: {e}")
                    factor_result[f'ic_mean_{period}d'] = np.nan
                    factor_result[f'icir_{period}d'] = np.nan

            # 分层回测
            try:
                qb_result = self.quantile_backtest(
                    factor, n_quantiles=10, forward_period=quantile_period
                )
                factor_result['long_short_sharpe'] = qb_result.long_short_sharpe
                factor_result['monotonicity'] = qb_result.monotonicity_score
                factor_result['top_quantile_return'] = qb_result.quantile_stats[10]['mean_return']
                factor_result['bottom_quantile_return'] = qb_result.quantile_stats[1]['mean_return']
            except Exception as e:
                logger.warning(f"Quantile backtest failed for {factor}: {e}")
                factor_result['long_short_sharpe'] = np.nan
                factor_result['monotonicity'] = np.nan

            results.append(factor_result)

        return pd.DataFrame(results)


def quick_factor_screen(
    factor_names: Optional[List[str]] = None,
    min_icir: float = 0.5,
    min_significance: float = 0.1
) -> pd.DataFrame:
    """
    快速因子筛选

    基于默认参数批量筛选有效因子。

    Args:
        factor_names: 因子列表（默认所有预计算因子）
        min_icir: 最小ICIR阈值
        min_significance: 最小显著性比例阈值

    Returns:
        DataFrame: 通过筛选的因子及其指标
    """
    if factor_names is None:
        precomputer = get_factor_precomputer()
        factor_names = list(precomputer._schema.keys())

    analyzer = FactorAnalyzer()

    logger.info(f"Screening {len(factor_names)} factors...")

    results = []
    for factor in factor_names:
        try:
            ic_result = analyzer.calculate_ic(factor)

            if (abs(ic_result.icir) >= min_icir and
                ic_result.ic_significant_ratio >= min_significance):

                results.append({
                    'factor_name': factor,
                    'ic_mean': ic_result.ic_mean,
                    'icir': ic_result.icir,
                    'ic_positive_ratio': ic_result.ic_positive_ratio,
                    'ic_significant_ratio': ic_result.ic_significant_ratio,
                    't_statistic': ic_result.t_statistic,
                    'p_value': ic_result.p_value,
                })
        except Exception as e:
            logger.debug(f"Screening failed for {factor}: {e}")
            continue

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values('icir', key=abs, ascending=False)

    return df


if __name__ == "__main__":
    # 示例用法
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--screen":
        # 快速筛选模式
        print("Running quick factor screen...")
        results = quick_factor_screen()
        print(f"\nFound {len(results)} significant factors:")
        print(results.to_string())

    elif len(sys.argv) > 1 and sys.argv[1] == "--analyze":
        # 单因子详细分析
        factor = sys.argv[2] if len(sys.argv) > 2 else "roe"
        print(f"Running comprehensive analysis for {factor}...")

        analyzer = FactorAnalyzer()

        # IC分析
        ic = analyzer.calculate_ic(factor)
        print(f"\nIC Analysis:")
        print(f"  IC Mean: {ic.ic_mean:.4f}")
        print(f"  ICIR: {ic.icir:.4f}")
        print(f"  IC Significant Ratio: {ic.ic_significant_ratio:.4f}")
        print(f"  T-statistic: {ic.t_statistic:.4f}")
        print(f"  P-value: {ic.p_value:.4f}")

        # 分层回测
        qb = analyzer.quantile_backtest(factor, n_quantiles=10)
        print(f"\nQuantile Backtest:")
        print(f"  Long-Short Sharpe: {qb.long_short_sharpe:.4f}")
        print(f"  Monotonicity: {qb.monotonicity_score:.4f}")
        print(f"  Top Quantile Return: {qb.quantile_stats[10]['mean_return']:.4f}")
        print(f"  Bottom Quantile Return: {qb.quantile_stats[1]['mean_return']:.4f}")

    else:
        print("Usage:")
        print("  python factor_analysis.py --screen")
        print("  python factor_analysis.py --analyze <factor_name>")


# ============================================================================
# 新增功能：因子换手率分析、行业中性测试、事件研究
# ============================================================================

@dataclass
class FactorTurnoverResult:
    """因子换手率分析结果"""
    factor_name: str
    daily_turnover: pd.Series  # 每日换手率时序
    mean_turnover: float       # 平均换手率
    turnover_std: float        # 换手率标准差
    annual_turnover: float     # 年化换手率估计

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor_name': self.factor_name,
            'mean_turnover': self.mean_turnover,
            'turnover_std': self.turnover_std,
            'annual_turnover': self.annual_turnover,
        }


@dataclass
class IndustryNeutralResult:
    """行业中性分析结果"""
    factor_name: str
    ic_within_industry: Dict[str, float]  # 行业内IC
    ic_cross_industry: float              # 行业间IC
    quantile_returns_by_industry: Dict[str, pd.DataFrame]  # 各行业分位数收益
    industry_neutral_ic: float            # 行业中性化后的IC

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor_name': self.factor_name,
            'ic_cross_industry': self.ic_cross_industry,
            'industry_neutral_ic': self.industry_neutral_ic,
            'avg_within_industry_ic': np.mean(list(self.ic_within_industry.values())),
        }


@dataclass
class EventStudyResult:
    """事件研究结果"""
    event_name: str
    window_pre: int          # 事件前窗口（天数）
    window_post: int         # 事件后窗口（天数）
    event_dates: List[str]   # 事件日期列表
    avg_cumulative_return: pd.Series  # 平均累积收益
    significant_days: List[int]       # 显著异于0的天数
    t_stats: pd.Series       # 每日t统计量

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_name': self.event_name,
            'n_events': len(self.event_dates),
            'max_return': self.avg_cumulative_return.max(),
            'min_return': self.avg_cumulative_return.min(),
            'final_return': self.avg_cumulative_return.iloc[-1],
        }


def calculate_factor_turnover(
    factor_name: str,
    stock_pool: Optional[List[str]] = None,
    top_n: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> FactorTurnoverResult:
    """
    计算因子换手率

    衡量因子选股的稳定性。高换手率意味着频繁调仓，交易成本增加。

    Args:
        factor_name: 因子名称
        stock_pool: 股票池
        top_n: 选取前N只股票计算换手率
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        FactorTurnoverResult: 换手率分析结果

    Example:
        >>> result = calculate_factor_turnover("pe_ttm", top_n=50)
        >>> print(f"平均换手率: {result.mean_turnover:.2%}")
    """
    from .precomputed_factors import get_factor_precomputer

    precomputer = get_factor_precomputer()
    start_date = start_date or datetime(2020, 1, 1)
    end_date = end_date or datetime(2024, 12, 31)

    # 获取交易日
    from projects.quant_trading.backtest.data_manager import DataManager
    dm = DataManager()
    trade_dates = dm.get_trade_dates(start_date, end_date)

    turnovers = []
    dates = []
    prev_top_stocks = None

    for date in trade_dates:
        try:
            # 获取当日因子值
            factors = precomputer.get_precomputed_factors(
                trade_date=date,
                stock_pool=stock_pool
            )

            if factors.empty or factor_name not in factors.columns:
                continue

            # 获取前N只股票
            factor_vals = factors[factor_name].dropna()
            if len(factor_vals) < top_n:
                continue

            current_top_stocks = set(factor_vals.nlargest(top_n).index)

            if prev_top_stocks is not None:
                # 计算换手率 = 1 - 交集比例
                common = len(prev_top_stocks & current_top_stocks)
                turnover = 1 - common / top_n
                turnovers.append(turnover)
                dates.append(date.strftime('%Y%m%d'))

            prev_top_stocks = current_top_stocks

        except Exception as e:
            logger.debug(f"Failed to compute turnover for {date}: {e}")
            continue

    if not turnovers:
        raise ValueError(f"No turnover data computed for {factor_name}")

    turnover_series = pd.Series(turnovers, index=dates)

    return FactorTurnoverResult(
        factor_name=factor_name,
        daily_turnover=turnover_series,
        mean_turnover=turnover_series.mean(),
        turnover_std=turnover_series.std(),
        annual_turnover=turnover_series.mean() * 252,  # 年化估算
    )


def industry_neutral_quantile_analysis(
    factor_name: str,
    industry_field: str = "industry",
    n_quantiles: int = 5,
    forward_period: int = 20,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> IndustryNeutralResult:
    """
    行业中性分位数分析

    在每个行业内进行分位数测试，排除行业效应对因子的影响。

    Args:
        factor_name: 因子名称
        industry_field: 行业字段名（需要在预计算因子中）
        n_quantiles: 分位数数量
        forward_period: 前瞻期
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        IndustryNeutralResult: 行业中性分析结果

    Example:
        >>> result = industry_neutral_quantile_analysis("pe_ttm")
        >>> print(f"行业中性IC: {result.industry_neutral_ic:.4f}")
    """
    from .precomputed_factors import get_factor_precomputer
    from projects.quant_trading.backtest.data_manager import DataManager
    import statsmodels.api as sm

    precomputer = get_factor_precomputer()
    dm = DataManager()

    start_date = start_date or datetime(2020, 1, 1)
    end_date = end_date or datetime(2024, 12, 31)

    trade_dates = dm.get_trade_dates(start_date, end_date)

    # 存储行业内IC
    ic_within_industry = defaultdict(list)
    all_neutral_ics = []

    for date in trade_dates:
        date_str = date.strftime('%Y%m%d')

        try:
            # 获取因子数据
            factors = precomputer.get_precomputed_factors(trade_date=date)

            if factors.empty or factor_name not in factors.columns:
                continue

            if industry_field not in factors.columns:
                logger.warning(f"Industry field {industry_field} not found in factor data")
                continue

            # 获取前瞻收益
            if date + timedelta(days=forward_period) > end_date:
                continue

            future_date = trade_dates[min(
                trade_dates.index(date) + forward_period,
                len(trade_dates) - 1
            )]

            current_prices = dm.get_batch_stock_data(
                ts_codes=list(factors.index),
                fields=['close'],
                trade_date=date
            )
            future_prices = dm.get_batch_stock_data(
                ts_codes=list(factors.index),
                fields=['close'],
                trade_date=future_date
            )

            # 计算收益
            returns = future_prices['close'] / current_prices['close'] - 1

            # 合并数据
            data = factors[[factor_name, industry_field]].copy()
            data['returns'] = returns
            data = data.dropna()

            if len(data) < 100:
                continue

            # 行业中性化：在每个行业内计算IC
            for industry in data[industry_field].unique():
                industry_data = data[data[industry_field] == industry]
                if len(industry_data) < 20:
                    continue

                ic, _ = stats.spearmanr(
                    industry_data[factor_name],
                    industry_data['returns']
                )
                if not np.isnan(ic):
                    ic_within_industry[industry].append(ic)

            # 整体行业中性IC（回归去除行业效应）
            # 使用虚拟变量控制行业
            industry_dummies = pd.get_dummies(data[industry_field], prefix='ind')
            X = pd.concat([data[[factor_name]], industry_dummies], axis=1)
            X = sm.add_constant(X)
            y = data['returns']

            model = sm.OLS(y, X).fit()
            # 因子系数标准化后的相关性
            neutral_ic = model.params[factor_name] / model.bse[factor_name]
            all_neutral_ics.append(neutral_ic)

        except Exception as e:
            logger.debug(f"Failed industry neutral analysis for {date}: {e}")
            continue

    # 计算平均行业内IC
    avg_ic_within = {
        industry: np.mean(ics)
        for industry, ics in ic_within_industry.items()
    }

    # 计算行业间IC（原始IC）
    cross_industry_ic = np.mean(all_neutral_ics) if all_neutral_ics else 0

    return IndustryNeutralResult(
        factor_name=factor_name,
        ic_within_industry=avg_ic_within,
        ic_cross_industry=cross_industry_ic,
        quantile_returns_by_industry={},  # TODO: 实现各行业的分位数收益
        industry_neutral_ic=np.mean(all_neutral_ics) if all_neutral_ics else 0,
    )


def event_study(
    event_dates: List[str],
    returns_data: pd.DataFrame,
    window_pre: int = 10,
    window_post: int = 10,
    event_name: str = "Event",
) -> EventStudyResult:
    """
    事件研究分析

    分析特定事件前后的股票收益表现。

    Args:
        event_dates: 事件日期列表 (YYYYMMDD)
        returns_data: 收益率数据 DataFrame，index=date, columns=stocks
        window_pre: 事件前窗口天数
        window_post: 事件后窗口天数
        event_name: 事件名称

    Returns:
        EventStudyResult: 事件研究结果

    Example:
        >>> events = ["20240115", "20240220", "20240315"]
        >>> result = event_study(events, returns_df, window_pre=5, window_post=20)
        >>> result.plot_cumulative_return()
    """
    cumulative_returns = []

    for event_date in event_dates:
        try:
            # 找到事件日期在数据中的位置
            if event_date not in returns_data.index:
                continue

            event_idx = returns_data.index.get_loc(event_date)

            # 提取窗口内的收益
            start_idx = max(0, event_idx - window_pre)
            end_idx = min(len(returns_data), event_idx + window_post + 1)

            window_returns = returns_data.iloc[start_idx:end_idx]

            # 计算累积收益（等权平均）
            avg_returns = window_returns.mean(axis=1)
            cum_returns = (1 + avg_returns).cumprod() - 1

            # 对齐到事件日（事件日为第0天）
            event_day_idx = event_idx - start_idx
            aligned_returns = cum_returns - cum_returns.iloc[event_day_idx]

            # 保存结果
            day_indices = list(range(-event_day_idx, len(cum_returns) - event_day_idx))
            cumulative_returns.append((day_indices, aligned_returns.values))

        except Exception as e:
            logger.warning(f"Failed to process event {event_date}: {e}")
            continue

    if not cumulative_returns:
        raise ValueError("No valid event data")

    # 计算平均累积收益
    all_days = set()
    for days, _ in cumulative_returns:
        all_days.update(days)
    all_days = sorted(all_days)

    avg_cum_returns = []
    t_stats = []

    for day in all_days:
        day_returns = []
        for days, rets in cumulative_returns:
            if day in days:
                idx = days.index(day)
                day_returns.append(rets[idx])

        if len(day_returns) >= 3:  # 至少3个事件
            avg_ret = np.mean(day_returns)
            t_stat = np.mean(day_returns) / (np.std(day_returns) / np.sqrt(len(day_returns)) + 1e-8)
            avg_cum_returns.append((day, avg_ret, t_stat))

    avg_cum_series = pd.Series(
        [x[1] for x in avg_cum_returns],
        index=[x[0] for x in avg_cum_returns]
    )
    t_stat_series = pd.Series(
        [x[2] for x in avg_cum_returns],
        index=[x[0] for x in avg_cum_returns]
    )

    # 找出显著的天数（|t| > 2）
    significant_days = t_stat_series[abs(t_stat_series) > 2].index.tolist()

    return EventStudyResult(
        event_name=event_name,
        window_pre=window_pre,
        window_post=window_post,
        event_dates=event_dates,
        avg_cumulative_return=avg_cum_series,
        significant_days=significant_days,
        t_stats=t_stat_series,
    )


def plot_event_cumulative_return(
    result: EventStudyResult,
    save_path: Optional[str] = None,
    show_confidence: bool = True,
):
    """
    绘制事件累积收益图

    Args:
        result: 事件研究结果
        save_path: 保存路径
        show_confidence: 是否显示置信区间
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))

    # 绘制累积收益
    ax.plot(
        result.avg_cumulative_return.index,
        result.avg_cumulative_return.values * 100,
        marker='o',
        linewidth=2,
        label='Cumulative Return'
    )

    # 标记事件日
    ax.axvline(x=0, color='red', linestyle='--', alpha=0.5, label='Event Day')

    # 标记显著天数
    if result.significant_days:
        for day in result.significant_days:
            if day in result.avg_cumulative_return.index:
                ax.scatter(
                    [day],
                    [result.avg_cumulative_return[day] * 100],
                    color='red',
                    s=100,
                    zorder=5,
                )

    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax.set_xlabel('Days Relative to Event')
    ax.set_ylabel('Cumulative Return (%)')
    ax.set_title(f'Event Study: {result.event_name} (n={len(result.event_dates)})')
    ax.legend()
    ax.grid(True, alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    else:
        plt.show()


# 便捷函数
def analyze_factor_turnover(
    factor_names: List[str],
    top_n: int = 100,
) -> pd.DataFrame:
    """
    批量分析多个因子的换手率

    Args:
        factor_names: 因子列表
        top_n: 选取前N只股票

    Returns:
        DataFrame: 各因子的换手率指标
    """
    results = []
    for factor in factor_names:
        try:
            result = calculate_factor_turnover(factor, top_n=top_n)
            results.append({
                'factor_name': factor,
                'mean_turnover': result.mean_turnover,
                'turnover_std': result.turnover_std,
                'annual_turnover': result.annual_turnover,
            })
        except Exception as e:
            logger.warning(f"Failed to analyze turnover for {factor}: {e}")

    return pd.DataFrame(results)


def analyze_industry_neutrality(
    factor_names: List[str],
    industry_field: str = "industry",
) -> pd.DataFrame:
    """
    批量分析多个因子的行业中性

    Args:
        factor_names: 因子列表
        industry_field: 行业字段名

    Returns:
        DataFrame: 各因子的行业中性指标
    """
    results = []
    for factor in factor_names:
        try:
            result = industry_neutral_quantile_analysis(factor, industry_field=industry_field)
            results.append({
                'factor_name': factor,
                'cross_industry_ic': result.ic_cross_industry,
                'industry_neutral_ic': result.industry_neutral_ic,
                'avg_within_industry_ic': np.mean(list(result.ic_within_industry.values())),
            })
        except Exception as e:
            logger.warning(f"Failed to analyze industry neutrality for {factor}: {e}")

    return pd.DataFrame(results)
