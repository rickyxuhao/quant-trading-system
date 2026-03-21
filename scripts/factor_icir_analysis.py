"""
Phase 3: 因子ICIR分析
- 计算所有因子的滚动IC和ICIR（2024-2026）
- 筛选ICIR > 0.3的有效因子
- 分析因子相关性，去除高相关冗余因子
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from scipy.stats import spearmanr, rankdata
from typing import List, Dict, Optional, Tuple
import json

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


# 所有待测试因子列表（按类别）
FACTOR_GROUPS = {
    'value': [
        'pe_ttm', 'pb', 'ps_ttm', 'dividend_yield', 'ep_ttm', 'bp',
    ],
    'quality': [
        'roe', 'roa', 'gross_margin', 'net_margin', 'operating_margin',
        'debt_to_assets', 'current_ratio', 'asset_turnover',
    ],
    'growth': [
        'revenue_yoy', 'profit_yoy', 'roe_yoy', 'asset_growth',
    ],
    'momentum': [
        'return_5d', 'return_10d', 'return_20d', 'return_60d',
        'return_120d', 'return_250d', 'sector_alpha_20d', 'sector_alpha_60d',
        'market_alpha_20d', 'market_alpha_60d', 'rs_20d_market', 'rs_60d_market',
    ],
    'volatility': [
        'volatility_5d', 'volatility_10d', 'volatility_20d', 'volatility_60d',
        'volatility_120d', 'downside_vol_20d', 'max_drawdown_20d', 'max_drawdown_60d',
        'atr_14d',
    ],
    'liquidity': [
        'turnover_rate', 'turnover_rate_f', 'turnover_20d', 'volume_ratio',
        'amount_norm',
    ],
    'moneyflow': [
        'large_order_net_ratio', 'main_net_inflow', 'retail_net_inflow',
        'net_inflow_5d', 'net_inflow_20d',
    ],
    'technical': [
        'macd', 'macd_signal', 'macd_hist',
        'rsi_14d', 'rsi_6d', 'rsi_12d', 'rsi_24d',
        'bb_width', 'bb_position',
        'kdj_k', 'kdj_d', 'kdj_j',
        'obv_norm',
        'amihud',
    ],
    'risk': [
        'turnover_volatility_20d', 'price_position_20d',
    ],
}

ALL_FACTORS = [f for factors in FACTOR_GROUPS.values() for f in factors]


def load_factor_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载因子数据"""
    factor_cols = ', '.join(ALL_FACTORS)
    sql = f"""
    SELECT trade_date, ts_code, {factor_cols}
    FROM t_precomputed_factors
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('interface', sql))
    if df.empty:
        return df
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    return df


def load_returns(start_date: str, end_date: str, horizon: int = 5) -> pd.DataFrame:
    """加载未来N日收益率（用于IC计算）"""
    # 需要加载到end_date + horizon天后
    extended_end = pd.Timestamp(end_date) + pd.Timedelta(days=horizon * 2)
    ext_end_str = extended_end.strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, ts_code, pct_chg
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{ext_end_str}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    if df.empty:
        return df
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce')
    return df


def compute_forward_returns(returns_df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """计算未来N日累积收益率"""
    returns_df = returns_df.sort_values(['ts_code', 'trade_date'])

    # 计算未来N日收益
    returns_df['return_1d'] = returns_df.groupby('ts_code')['pct_chg'].transform(lambda x: x / 100)

    # 累积收益
    def calc_forward(group):
        group = group.sort_values('trade_date').copy()
        group[f'fwd_{horizon}d'] = group['return_1d'].shift(-1).rolling(horizon).sum().shift(-(horizon-1))
        return group

    result = returns_df.groupby('ts_code', group_keys=False).apply(calc_forward)
    return result[['trade_date', 'ts_code', f'fwd_{horizon}d']]


def compute_ic_series(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                      factor: str, horizon: int = 5) -> pd.Series:
    """计算单因子的IC时间序列（rank IC / Spearman）"""
    fwd_col = f'fwd_{horizon}d'
    merged = factor_df[['trade_date', 'ts_code', factor]].merge(
        fwd_returns[['trade_date', 'ts_code', fwd_col]],
        on=['trade_date', 'ts_code']
    )
    merged = merged.dropna(subset=[factor, fwd_col])

    ic_series = {}
    for date, group in merged.groupby('trade_date'):
        if len(group) < 30:
            continue
        try:
            ic, _ = spearmanr(group[factor], group[fwd_col])
            if not np.isnan(ic):
                ic_series[date] = ic
        except Exception:
            pass

    return pd.Series(ic_series).sort_index()


def analyze_factors(start_date: str = '20240101', end_date: str = '20260320',
                    horizon: int = 5, icir_threshold: float = 0.3,
                    corr_threshold: float = 0.7) -> Dict:
    """
    主分析函数

    Returns:
        包含IC、ICIR统计和有效因子列表的字典
    """
    logger.info(f"Loading factor data {start_date} -> {end_date}")
    factor_df = load_factor_data(start_date, end_date)
    logger.info(f"Factor data loaded: {len(factor_df)} rows")

    logger.info("Loading returns data")
    returns_df = load_returns(start_date, end_date, horizon)
    fwd_returns = compute_forward_returns(returns_df, horizon)
    logger.info(f"Forward returns computed: {len(fwd_returns)} rows")

    # 计算每个因子的IC序列
    results = []
    ic_data = {}

    available_factors = [f for f in ALL_FACTORS if f in factor_df.columns]
    logger.info(f"Computing IC for {len(available_factors)} factors")

    for i, factor in enumerate(available_factors):
        logger.info(f"  [{i+1}/{len(available_factors)}] {factor}")
        ic_series = compute_ic_series(factor_df, fwd_returns, factor, horizon)

        if len(ic_series) < 10:
            logger.warning(f"  Insufficient IC data for {factor}")
            continue

        ic_data[factor] = ic_series
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / (ic_std + 1e-10) * np.sqrt(12)  # 年化
        ic_positive_pct = (ic_series > 0).mean()

        # 找出该因子属于哪个类别
        group = next((g for g, fs in FACTOR_GROUPS.items() if factor in fs), 'other')

        results.append({
            'factor': factor,
            'group': group,
            'ic_mean': round(float(ic_mean), 4),
            'ic_std': round(float(ic_std), 4),
            'icir': round(float(icir), 4),
            'ic_positive_pct': round(float(ic_positive_pct), 4),
            'n_obs': len(ic_series),
        })

    results_df = pd.DataFrame(results).sort_values('icir', ascending=False)
    logger.info(f"\n{'='*60}")
    logger.info(f"FACTOR ICIR ANALYSIS RESULTS ({start_date} - {end_date})")
    logger.info(f"{'='*60}")
    logger.info(f"\n{results_df.to_string(index=False)}")

    # 筛选有效因子（ICIR > threshold）
    valid_factors = results_df[results_df['icir'].abs() > icir_threshold]
    logger.info(f"\nValid factors (|ICIR| > {icir_threshold}): {len(valid_factors)}")
    logger.info(valid_factors[['factor', 'group', 'ic_mean', 'icir']].to_string(index=False))

    # 因子相关性分析
    if len(valid_factors) > 1:
        valid_factor_names = valid_factors['factor'].tolist()
        ic_matrix = pd.DataFrame({f: ic_data[f] for f in valid_factor_names
                                   if f in ic_data})
        corr_matrix = ic_matrix.corr()

        # 去除高相关因子
        selected_factors = remove_redundant_factors(valid_factor_names, corr_matrix,
                                                     corr_threshold)
        logger.info(f"\nAfter deduplication (corr>{corr_threshold}): {len(selected_factors)} factors")
        logger.info(f"Selected: {selected_factors}")
    else:
        selected_factors = valid_factors['factor'].tolist()
        corr_matrix = pd.DataFrame()

    return {
        'all_results': results_df.to_dict('records'),
        'valid_factors': valid_factors.to_dict('records'),
        'selected_factors': selected_factors,
        'ic_data': {f: ic_data[f].to_dict() for f in ic_data},
        'corr_matrix': corr_matrix.to_dict() if not corr_matrix.empty else {},
    }


def remove_redundant_factors(factors: List[str], corr_matrix: pd.DataFrame,
                               threshold: float = 0.7) -> List[str]:
    """贪心去除高相关冗余因子（保留ICIR更高的）"""
    selected = []
    for factor in factors:  # factors已按ICIR降序排列
        redundant = False
        for sel in selected:
            if sel in corr_matrix.columns and factor in corr_matrix.columns:
                if abs(corr_matrix.loc[sel, factor]) > threshold:
                    redundant = True
                    break
        if not redundant:
            selected.append(factor)
    return selected


def save_results(results: Dict, output_path: str):
    """保存分析结果"""
    # 只保存可序列化的部分
    save_data = {
        'all_results': results['all_results'],
        'valid_factors': results['valid_factors'],
        'selected_factors': results['selected_factors'],
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Results saved to {output_path}")


if __name__ == '__main__':
    OUTPUT_DIR = 'output'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = analyze_factors(
        start_date='20240101',
        end_date='20260320',
        horizon=5,
        icir_threshold=0.3,
        corr_threshold=0.7,
    )

    save_results(results, f'{OUTPUT_DIR}/factor_icir_results.json')
    print(f"\nSelected factors for model: {results['selected_factors']}")
