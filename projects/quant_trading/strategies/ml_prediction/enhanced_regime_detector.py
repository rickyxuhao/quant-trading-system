"""
增强版市场环境分类器 - Phase 4
实现3类市场环境识别：
- 牛市 (BULL): 20日收益 > 10% 且 波动率 < 中位数
- 熊市 (BEAR): 20日收益 < -10% 或 波动率 > 80分位
- 震荡市 (OSCILLATING): 其他情况

不同市场环境使用不同因子权重:
- 牛市: 偏动量/成长因子
- 熊市: 偏质量/价值因子
- 震荡市: 偏反转/技术因子
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from core.logger import get_logger

logger = get_logger(__name__)


class EnhancedMarketRegime(Enum):
    BULL = "bull"           # 牛市
    BEAR = "bear"           # 熊市
    OSCILLATING = "oscillating"  # 震荡市


@dataclass
class RegimeWeights:
    """不同市场环境下的因子权重配置"""

    # 因子类别权重 (sum should be 1.0)
    category_weights: Dict[str, float]

    # 描述
    description: str = ""


# 预定义的市场环境因子权重
REGIME_FACTOR_WEIGHTS = {
    EnhancedMarketRegime.BULL: RegimeWeights(
        category_weights={
            'momentum': 0.35,    # 动量因子最重要
            'growth': 0.25,      # 成长因子
            'quality': 0.15,     # 质量因子
            'value': 0.10,       # 估值因子
            'technical': 0.10,   # 技术因子
            'liquidity': 0.05,   # 流动性因子
        },
        description="牛市：偏动量/成长因子"
    ),
    EnhancedMarketRegime.BEAR: RegimeWeights(
        category_weights={
            'quality': 0.30,     # 质量因子最重要
            'value': 0.25,       # 价值因子
            'volatility': 0.20,  # 波动率因子（低波动）
            'momentum': 0.10,    # 动量因子
            'technical': 0.10,   # 技术因子
            'liquidity': 0.05,   # 流动性因子
        },
        description="熊市：偏质量/价值因子"
    ),
    EnhancedMarketRegime.OSCILLATING: RegimeWeights(
        category_weights={
            'technical': 0.30,   # 技术/反转因子最重要
            'momentum': 0.20,    # 短期动量（反转）
            'quality': 0.20,     # 质量因子
            'value': 0.15,       # 估值因子
            'liquidity': 0.10,   # 流动性因子
            'growth': 0.05,      # 成长因子
        },
        description="震荡市：偏反转/技术因子"
    ),
}

# 各市场环境下因子组的具体因子权重乘数
FACTOR_MULTIPLIERS = {
    EnhancedMarketRegime.BULL: {
        # 动量因子强化
        'return_20d': 1.5, 'return_60d': 1.3, 'market_alpha_20d': 1.4,
        'rs_20d_market': 1.3, 'sector_alpha_20d': 1.2,
        # 成长因子强化
        'profit_yoy': 1.3, 'revenue_yoy': 1.2, 'roe_yoy': 1.2,
        # 技术因子弱化
        'rsi_6d': 0.7, 'kdj_k': 0.7, 'bb_position': 0.8,
    },
    EnhancedMarketRegime.BEAR: {
        # 质量因子强化
        'roe': 1.5, 'roa': 1.3, 'gross_margin': 1.3,
        'debt_to_assets': 1.4, 'current_ratio': 1.3,
        # 价值因子强化
        'ep_ttm': 1.4, 'bp': 1.3, 'dividend_yield': 1.5,
        # 动量因子弱化
        'return_20d': 0.5, 'return_60d': 0.6,
    },
    EnhancedMarketRegime.OSCILLATING: {
        # 反转因子强化（高RSI卖出信号）
        'rsi_6d': 1.4, 'rsi_12d': 1.3, 'kdj_j': 1.3,
        'bb_position': 1.2, 'macd_hist': 1.2,
        'obv_norm': 1.2, 'amihud': 1.1,
        # 短期动量（反转用负权重）
        'return_5d': 0.5, 'return_10d': 0.6,
    },
}


class EnhancedRegimeDetector:
    """
    增强版市场环境检测器

    使用沪深300或全市场平均收益+波动率来分类当前市场环境
    """

    def __init__(self, return_threshold_bull: float = 0.10,
                 return_threshold_bear: float = -0.10,
                 vol_bear_percentile: float = 0.80,
                 smooth_window: int = 3):
        self.return_threshold_bull = return_threshold_bull
        self.return_threshold_bear = return_threshold_bear
        self.vol_bear_percentile = vol_bear_percentile
        self.smooth_window = smooth_window
        self._regime_cache: Dict[str, EnhancedMarketRegime] = {}

    def detect_regime(self, date: str, index_returns: pd.Series,
                      vol_history: pd.Series) -> EnhancedMarketRegime:
        """
        检测指定日期的市场环境

        Args:
            date: 日期字符串 YYYYMMDD
            index_returns: 指数日收益率序列（已按日期排序）
            vol_history: 历史波动率序列

        Returns:
            EnhancedMarketRegime
        """
        if date in self._regime_cache:
            return self._regime_cache[date]

        # 计算20日累积收益
        if len(index_returns) < 20:
            regime = EnhancedMarketRegime.OSCILLATING
            self._regime_cache[date] = regime
            return regime

        return_20d = (1 + index_returns.tail(20)).prod() - 1

        # 计算当前波动率（20日年化）
        current_vol = index_returns.tail(20).std() * np.sqrt(252)

        # 计算历史波动率中位数和80分位
        if len(vol_history) >= 60:
            vol_median = vol_history.median()
            vol_p80 = vol_history.quantile(0.80)
        else:
            vol_median = current_vol
            vol_p80 = current_vol * 1.2

        # 市场环境分类
        is_bull_return = return_20d > self.return_threshold_bull
        is_low_vol = current_vol < vol_median
        is_bear_return = return_20d < self.return_threshold_bear
        is_high_vol = current_vol > vol_p80

        if is_bull_return and is_low_vol:
            regime = EnhancedMarketRegime.BULL
        elif is_bear_return or is_high_vol:
            regime = EnhancedMarketRegime.BEAR
        else:
            regime = EnhancedMarketRegime.OSCILLATING

        self._regime_cache[date] = regime
        return regime

    def detect_regime_series(self, index_df: pd.DataFrame,
                              date_col: str = 'trade_date',
                              return_col: str = 'pct_chg') -> pd.DataFrame:
        """
        批量检测历史市场环境序列

        Args:
            index_df: 包含日期和收益率的DataFrame
            date_col: 日期列名
            return_col: 收益率列名（百分比格式）

        Returns:
            DataFrame with columns: trade_date, regime, return_20d, vol_20d
        """
        df = index_df.sort_values(date_col).copy()
        df['return_pct'] = pd.to_numeric(df[return_col], errors='coerce') / 100
        df['return_pct'] = df['return_pct'].fillna(0)

        # 计算20日滚动收益和波动率
        df['return_20d'] = (1 + df['return_pct']).rolling(20).apply(
            lambda x: np.prod(x) - 1, raw=True
        )
        df['vol_20d'] = df['return_pct'].rolling(20).std() * np.sqrt(252)

        # 历史波动率（用于计算分位数，使用过去252天）
        vol_series = df['vol_20d'].dropna()

        regimes = []
        for idx, row in df.iterrows():
            if pd.isna(row['return_20d']) or pd.isna(row['vol_20d']):
                regimes.append(EnhancedMarketRegime.OSCILLATING.value)
                continue

            current_vol = row['vol_20d']
            current_return_20d = row['return_20d']

            # 获取截至当前的历史波动率
            hist_vol = vol_series.loc[:idx]
            if len(hist_vol) >= 60:
                vol_median = hist_vol.quantile(0.5)
                vol_p80 = hist_vol.quantile(0.80)
            else:
                vol_median = current_vol
                vol_p80 = current_vol * 1.2

            is_bull = current_return_20d > self.return_threshold_bull and current_vol < vol_median
            is_bear = current_return_20d < self.return_threshold_bear or current_vol > vol_p80

            if is_bull:
                regime = EnhancedMarketRegime.BULL.value
            elif is_bear:
                regime = EnhancedMarketRegime.BEAR.value
            else:
                regime = EnhancedMarketRegime.OSCILLATING.value

            regimes.append(regime)

        df['regime'] = regimes

        # 平滑处理（减少噪声切换）
        if self.smooth_window > 1:
            df['regime'] = self._smooth_regimes(df['regime'], self.smooth_window)

        return df[[date_col, 'regime', 'return_20d', 'vol_20d']]

    def _smooth_regimes(self, regime_series: pd.Series, window: int) -> pd.Series:
        """平滑市场环境（取滚动窗口众数）"""
        smoothed = regime_series.copy()
        for i in range(window - 1, len(regime_series)):
            window_data = regime_series.iloc[i - window + 1:i + 1]
            mode_val = window_data.value_counts().idxmax()
            smoothed.iloc[i] = mode_val
        return smoothed

    def get_factor_weights(self, regime: EnhancedMarketRegime,
                           factor_names: List[str],
                           factor_groups: Dict[str, List[str]]) -> Dict[str, float]:
        """
        获取指定市场环境下各因子的权重

        Args:
            regime: 市场环境
            factor_names: 因子列表
            factor_groups: 因子分组 {group_name: [factor_list]}

        Returns:
            {factor_name: weight} 字典
        """
        regime_weights = REGIME_FACTOR_WEIGHTS[regime]
        multipliers = FACTOR_MULTIPLIERS[regime]

        # 构建factor -> group 映射
        factor_to_group = {}
        for group, factors in factor_groups.items():
            for f in factors:
                factor_to_group[f] = group

        # 计算每个因子的基础权重
        weights = {}
        for factor in factor_names:
            group = factor_to_group.get(factor, 'other')
            group_weight = regime_weights.category_weights.get(group, 0.1)
            # 同组因子均分权重
            group_factor_count = sum(
                1 for f in factor_names
                if factor_to_group.get(f, 'other') == group
            )
            base_weight = group_weight / max(group_factor_count, 1)

            # 应用乘数
            multiplier = multipliers.get(factor, 1.0)
            weights[factor] = base_weight * multiplier

        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def get_regime_statistics(self, regime_df: pd.DataFrame) -> Dict:
        """统计各市场环境的时间分布"""
        stats = regime_df['regime'].value_counts()
        total = len(regime_df)

        result = {}
        for regime in [r.value for r in EnhancedMarketRegime]:
            count = stats.get(regime, 0)
            result[regime] = {
                'count': int(count),
                'pct': round(float(count / total * 100), 2) if total > 0 else 0,
            }

        # 连续段统计
        transitions = (regime_df['regime'] != regime_df['regime'].shift()).sum()
        result['transitions'] = int(transitions)
        result['avg_duration'] = round(total / max(transitions, 1), 1)

        return result


def load_and_detect_regimes(start_date: str = '20240101',
                             end_date: str = '20260320') -> pd.DataFrame:
    """
    从数据库加载沪深300数据并检测市场环境

    Returns:
        DataFrame with trade_date, regime, return_20d, vol_20d
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
    from core.storage.relational.connection import DatabaseManager

    # 加载沪深300指数数据（需要多加载历史数据用于热身）
    warmup_start = pd.Timestamp(start_date) - pd.Timedelta(days=60)
    sql = f"""
    SELECT trade_date, close, pct_chg
    FROM t_index_daily
    WHERE ts_code = '000300.SH'
      AND trade_date >= '{warmup_start.strftime('%Y%m%d')}'
      AND trade_date <= '{end_date}'
    ORDER BY trade_date
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))

    if df.empty:
        logger.warning("No index data found, using market average")
        # 回退：使用全市场平均收益
        sql2 = f"""
        SELECT trade_date, AVG(pct_chg) as pct_chg
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{warmup_start.strftime('%Y%m%d')}'
          AND trade_date <= '{end_date}'
        GROUP BY trade_date
        ORDER BY trade_date
        """
        df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql2))

    detector = EnhancedRegimeDetector()
    regime_df = detector.detect_regime_series(df)

    # 只保留目标日期范围
    regime_df = regime_df[regime_df['trade_date'].astype(str) >= start_date.replace('-', '')]

    return regime_df, detector


if __name__ == '__main__':
    from core.logger import get_logger

    regime_df, detector = load_and_detect_regimes('20240101', '20260320')

    stats = detector.get_regime_statistics(regime_df)
    print("\n市场环境统计 (2024-01-01 to 2026-03-20):")
    print("=" * 50)
    for regime, info in stats.items():
        if isinstance(info, dict):
            print(f"  {regime}: {info['count']}天 ({info['pct']}%)")
        else:
            print(f"  {regime}: {info}")

    # 保存结果
    regime_df.to_csv('output/regime_classification.csv', index=False)
    print("\n结果已保存到 output/regime_classification.csv")
