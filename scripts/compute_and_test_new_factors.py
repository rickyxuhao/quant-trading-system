"""
新因子复刻与IC测试 - Phase 2-3
=================================
复刻以下因子类别并测试ICIR:

类别1: 技术反转因子 (from existing precomputed)
  - momentum_diff: return_60d - return_5d (长短期动量差)
  - rsi_reversal: 100 - rsi_14d (RSI超买反转信号)
  - price_vol_divergence: 价格位置与量能比背离

类别2: 质量因子 (from t_stock_fina_indicator)
  - roe_change: ROE同比变化率 (roe_yoy直接可用)
  - gross_margin_stability: 8季度毛利率稳定性(1/std)
  - accrual_ratio: (净利润 - 经营现金流) / 总资产

类别3: 成长因子 (from financial statements)
  - revenue_acceleration: 营收增速加速度(当季yoy - 上季yoy)
  - rd_ratio: 研发费用/总资产 (from balance sheet)

运行方式:
    python3 scripts/compute_and_test_new_factors.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from typing import Dict, List, Tuple, Optional
import json
import logging

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# 配置
# ============================================================
START_DATE = '20240101'
END_DATE = '20260320'
FWD_HORIZON = 5          # 预测未来5日收益
ICIR_THRESHOLD = 0.3     # 有效因子ICIR阈值
CORR_THRESHOLD = 0.7     # 高相关去重阈值


# ============================================================
# 1. 加载现有precomputed因子
# ============================================================

EXISTING_FACTORS_NEEDED = [
    'return_5d', 'return_10d', 'return_20d', 'return_60d',
    'rsi_14d', 'rsi_6d', 'rsi_12d',
    'price_position_20d', 'volume_ratio',
    'volatility_20d', 'volatility_60d',
    'turnover_rate', 'bb_position', 'bb_width',
    'macd', 'macd_hist',
    'roe', 'roe_yoy', 'gross_margin', 'profit_yoy',
    'large_order_net_ratio', 'net_inflow_20d',
    'amihud',
]


def load_precomputed_factors(start_date: str, end_date: str) -> pd.DataFrame:
    """加载现有precomputed因子"""
    cols = ', '.join(EXISTING_FACTORS_NEEDED)
    sql = f"""
    SELECT trade_date, ts_code, {cols}
    FROM t_precomputed_factors
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    rows = DatabaseManager.fetchall('interface', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    for col in EXISTING_FACTORS_NEEDED:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# ============================================================
# 2. 派生新因子 (从existing precomputed计算)
# ============================================================

def compute_derived_factors(df: pd.DataFrame) -> pd.DataFrame:
    """计算从现有因子派生的新因子"""
    df = df.copy()

    # 长短期动量差: 捕捉短期反转与中期趋势背离
    if 'return_60d' in df.columns and 'return_5d' in df.columns:
        df['momentum_diff'] = df['return_60d'] - df['return_5d']

    # RSI反转因子: RSI越高越超买，预期下跌
    if 'rsi_14d' in df.columns:
        df['rsi_reversal'] = 100 - df['rsi_14d']  # 越低越好

    # 价格-成交量背离: 价格在高位但成交量相对低(缩量) → 看跌
    # 公式: price_position - (volume_ratio - 1) 越小越好（高位缩量）
    if 'price_position_20d' in df.columns and 'volume_ratio' in df.columns:
        # volume_ratio = 5日均量/20日均量
        # vol_norm = clamp(volume_ratio - 1, -1, 1)
        vol_norm = (df['volume_ratio'] - 1).clip(-1, 1)
        # 价量背离: 价格高但成交量低 → 负信号
        df['price_vol_divergence'] = df['price_position_20d'] - (vol_norm + 1) / 2
        # 负值表示高位缩量 (看跌因子，取负使ICIR为正)
        df['price_vol_divergence'] = -df['price_vol_divergence']

    # 布林带反转: 接近下轨+低RSI → 看涨
    if 'bb_position' in df.columns and 'rsi_6d' in df.columns:
        # bb_position接近0表示接近下轨，rsi_6d低表示超卖 → 反转机会
        df['bb_rsi_reversal'] = (1 - df['bb_position']) * (100 - df['rsi_6d']) / 100

    # 资金流向加速: 净流入占比（已有）
    # large_order_net_ratio 已有

    logger.info(f"Derived factors computed: momentum_diff, rsi_reversal, price_vol_divergence, bb_rsi_reversal")
    return df


# ============================================================
# 3. 财务报表质量因子
# ============================================================

def load_financial_data_pit(start_date: str, end_date: str) -> pd.DataFrame:
    """
    加载财务报表数据，做PIT (Point-in-Time) 处理。
    使用 ann_date (披露日期) 确保无前视偏差。
    """
    # 加载所有股票的财务指标（ann_date在结束日期前的）
    sql = f"""
    SELECT ts_code, ann_date, end_date,
           roe, gross_profit_margin,
           or_yoy, q_sales_yoy,
           netprofit_yoy, roe_yoy
    FROM t_stock_fina_indicator
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
    ORDER BY ts_code, ann_date
    """
    rows = DatabaseManager.fetchall('tushare_biz', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("No financial data loaded")
        return df
    df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str))
    df['end_date'] = pd.to_datetime(df['end_date'].astype(str))
    for col in ['roe', 'gross_profit_margin', 'or_yoy', 'q_sales_yoy',
                'netprofit_yoy', 'roe_yoy']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    logger.info(f"Financial indicator data: {len(df)} rows, {df['ts_code'].nunique()} stocks")
    return df


def load_cashflow_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载经营现金流数据 (PIT)"""
    sql = f"""
    SELECT ts_code, ann_date, end_date, n_cashflow_act
    FROM t_stock_cashflow
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """
    rows = DatabaseManager.fetchall('tushare_biz', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str))
    df['n_cashflow_act'] = pd.to_numeric(df['n_cashflow_act'], errors='coerce')
    return df


def load_income_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载净利润数据 (PIT)"""
    sql = f"""
    SELECT ts_code, ann_date, end_date, n_income_attr_p
    FROM t_stock_income
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """
    rows = DatabaseManager.fetchall('tushare_biz', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str))
    df['n_income_attr_p'] = pd.to_numeric(df['n_income_attr_p'], errors='coerce')
    return df


def load_balance_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载总资产和研发费用数据 (PIT)"""
    sql = f"""
    SELECT ts_code, ann_date, end_date, total_assets, r_and_d
    FROM t_stock_balancesheet
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """
    rows = DatabaseManager.fetchall('tushare_biz', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str))
    df['total_assets'] = pd.to_numeric(df['total_assets'], errors='coerce')
    df['r_and_d'] = pd.to_numeric(df['r_and_d'], errors='coerce').fillna(0)
    return df


def pit_merge_financial(trade_dates_df: pd.DataFrame,
                        fin_df: pd.DataFrame,
                        value_cols: List[str],
                        date_col: str = 'ann_date') -> pd.DataFrame:
    """
    PIT合并：对每个(ts_code, trade_date)找最近的财务报告。
    采用 merge_asof 方法，效率较高。
    """
    # trade_dates_df: [trade_date, ts_code]
    all_results = []

    for ts_code, fin_group in fin_df.groupby('ts_code'):
        stock_dates = trade_dates_df[trade_dates_df['ts_code'] == ts_code][
            ['trade_date']].copy()
        if stock_dates.empty:
            continue
        fin_sorted = fin_group.sort_values(date_col)
        stock_dates_sorted = stock_dates.sort_values('trade_date')

        # merge_asof: 对每个trade_date找最近的ann_date
        merged = pd.merge_asof(
            stock_dates_sorted,
            fin_sorted[['ann_date'] + value_cols].rename(columns={'ann_date': date_col}),
            left_on='trade_date',
            right_on=date_col,
            direction='backward'
        )
        merged['ts_code'] = ts_code
        all_results.append(merged[['trade_date', 'ts_code'] + value_cols])

    if not all_results:
        return pd.DataFrame()
    return pd.concat(all_results, ignore_index=True)


def compute_gross_margin_stability(fin_df: pd.DataFrame,
                                   n_quarters: int = 8) -> pd.DataFrame:
    """
    计算毛利率稳定性: 过去8季度毛利率标准差的倒数
    返回: [ts_code, ann_date, gross_margin_stability]
    """
    results = []
    for ts_code, group in fin_df.groupby('ts_code'):
        group = group.sort_values('end_date').copy()
        gm = group['gross_profit_margin'].values
        stability = np.full(len(gm), np.nan)
        for i in range(n_quarters - 1, len(gm)):
            window = gm[max(0, i - n_quarters + 1):i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) >= 4:
                std = np.std(valid, ddof=1)
                stability[i] = 1.0 / (std + 1e-6)
        group['gross_margin_stability'] = stability
        results.append(group[['ts_code', 'ann_date', 'gross_margin_stability']])

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


def compute_revenue_acceleration(fin_df: pd.DataFrame) -> pd.DataFrame:
    """
    营收增速加速度: 当季同比增速 - 上季同比增速
    (q_sales_yoy_t - q_sales_yoy_{t-1})
    返回: [ts_code, ann_date, revenue_acceleration]
    """
    results = []
    for ts_code, group in fin_df.groupby('ts_code'):
        group = group.sort_values('end_date').copy()
        group['q_sales_yoy_prev'] = group['q_sales_yoy'].shift(1)
        group['revenue_acceleration'] = group['q_sales_yoy'] - group['q_sales_yoy_prev']
        results.append(group[['ts_code', 'ann_date', 'revenue_acceleration']])
    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


def compute_accrual_ratio(income_df: pd.DataFrame, cashflow_df: pd.DataFrame,
                          balance_df: pd.DataFrame) -> pd.DataFrame:
    """
    应计利润比率: (净利润 - 经营现金流) / 总资产
    负值表示现金质量好（好因子），需取负使ICIR方向一致
    返回: [ts_code, ann_date, accrual_ratio]
    """
    # 合并三张表（按ts_code, end_date匹配）
    merged = income_df.merge(
        cashflow_df[['ts_code', 'end_date', 'n_cashflow_act']],
        on=['ts_code', 'end_date'], how='inner'
    ).merge(
        balance_df[['ts_code', 'end_date', 'total_assets', 'r_and_d']],
        on=['ts_code', 'end_date'], how='inner'
    )
    merged['accrual_ratio'] = (
        merged['n_income_attr_p'] - merged['n_cashflow_act']
    ) / (merged['total_assets'] + 1e-10)
    # 取负值：应计利润越低（现金质量越好）→ 因子越高
    merged['accrual_ratio'] = -merged['accrual_ratio']
    # 研发占比（来自资产负债表，存量指标）
    merged['rd_ratio'] = merged['r_and_d'] / (merged['total_assets'] + 1e-10)
    return merged[['ts_code', 'ann_date', 'accrual_ratio', 'rd_ratio']]


# ============================================================
# 4. 合并所有新因子到交易日截面
# ============================================================

NEW_FINANCIAL_FACTORS = [
    'gross_margin_stability',
    'revenue_acceleration',
    'accrual_ratio',
    'rd_ratio',
]

NEW_DERIVED_FACTORS = [
    'momentum_diff',
    'rsi_reversal',
    'price_vol_divergence',
    'bb_rsi_reversal',
]


def build_new_factor_dataset(start_date: str, end_date: str) -> pd.DataFrame:
    """
    构建完整的新因子数据集。
    返回: [trade_date, ts_code, factor1, factor2, ...]
    """
    logger.info("Step 1: Loading existing precomputed factors...")
    base_df = load_precomputed_factors(start_date, end_date)
    if base_df.empty:
        raise ValueError("No precomputed factor data found")
    logger.info(f"  Loaded {len(base_df)} rows, {base_df['ts_code'].nunique()} stocks")

    # Step 2: 派生因子
    logger.info("Step 2: Computing derived factors...")
    base_df = compute_derived_factors(base_df)

    # Step 3: 加载财务报表数据
    logger.info("Step 3: Loading financial statement data...")
    fin_df = load_financial_data_pit(start_date, end_date)
    cashflow_df = load_cashflow_data(start_date, end_date)
    income_df = load_income_data(start_date, end_date)
    balance_df = load_balance_data(start_date, end_date)

    # 获取需要PIT合并的(trade_date, ts_code)组合
    trade_dates_df = base_df[['trade_date', 'ts_code']].drop_duplicates()

    # Step 4: 计算毛利率稳定性
    logger.info("Step 4: Computing gross margin stability...")
    if not fin_df.empty:
        gm_stability_df = compute_gross_margin_stability(fin_df)
        # PIT合并到交易日
        gm_pit = pit_merge_financial(trade_dates_df, gm_stability_df,
                                     ['gross_margin_stability'],
                                     date_col='ann_date')
        if not gm_pit.empty:
            base_df = base_df.merge(gm_pit, on=['trade_date', 'ts_code'], how='left')
            logger.info(f"  gross_margin_stability: {base_df['gross_margin_stability'].notna().sum()} valid values")

    # Step 5: 计算营收加速度
    logger.info("Step 5: Computing revenue acceleration...")
    if not fin_df.empty:
        rev_acc_df = compute_revenue_acceleration(fin_df)
        rev_pit = pit_merge_financial(trade_dates_df, rev_acc_df,
                                      ['revenue_acceleration'],
                                      date_col='ann_date')
        if not rev_pit.empty:
            base_df = base_df.merge(rev_pit, on=['trade_date', 'ts_code'], how='left')
            logger.info(f"  revenue_acceleration: {base_df['revenue_acceleration'].notna().sum()} valid values")

    # Step 6: 计算应计利润比率和研发比率
    logger.info("Step 6: Computing accrual ratio and R&D ratio...")
    if not income_df.empty and not cashflow_df.empty and not balance_df.empty:
        accrual_df = compute_accrual_ratio(income_df, cashflow_df, balance_df)
        accrual_pit = pit_merge_financial(trade_dates_df, accrual_df,
                                          ['accrual_ratio', 'rd_ratio'],
                                          date_col='ann_date')
        if not accrual_pit.empty:
            base_df = base_df.merge(accrual_pit, on=['trade_date', 'ts_code'], how='left')
            logger.info(f"  accrual_ratio: {base_df['accrual_ratio'].notna().sum()} valid values")
            logger.info(f"  rd_ratio: {base_df['rd_ratio'].notna().sum()} valid values")

    # roe_yoy 已在precomputed中，直接用作roe_change代理
    # 用roe_yoy就是ROE同比变化率

    logger.info(f"Final dataset: {len(base_df)} rows, {base_df.columns.tolist()}")
    return base_df


# ============================================================
# 5. IC/ICIR 计算
# ============================================================

def load_forward_returns(start_date: str, end_date: str,
                         horizon: int = 5) -> pd.DataFrame:
    """加载未来N日累积收益率"""
    extended_end = (pd.Timestamp(end_date) + pd.Timedelta(days=horizon * 2)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, ts_code, pct_chg
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{extended_end}'
    ORDER BY ts_code, trade_date
    """
    rows = DatabaseManager.fetchall('tushare_biz', sql)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce') / 100

    # 计算未来N日累积收益
    fwd_results = []
    for ts_code, group in df.groupby('ts_code'):
        group = group.sort_values('trade_date').copy()
        group[f'fwd_{horizon}d'] = group['pct_chg'].shift(-1).rolling(horizon).sum().shift(-(horizon - 1))
        fwd_results.append(group[['trade_date', 'ts_code', f'fwd_{horizon}d']])

    fwd_df = pd.concat(fwd_results, ignore_index=True)
    return fwd_df


def compute_icir(factor_df: pd.DataFrame, fwd_df: pd.DataFrame,
                 factor_col: str, horizon: int = 5) -> Dict:
    """计算单因子ICIR"""
    fwd_col = f'fwd_{horizon}d'
    merged = factor_df[['trade_date', 'ts_code', factor_col]].merge(
        fwd_df[['trade_date', 'ts_code', fwd_col]],
        on=['trade_date', 'ts_code']
    ).dropna(subset=[factor_col, fwd_col])

    if len(merged) < 100:
        return {'factor': factor_col, 'ic_mean': np.nan, 'ic_std': np.nan,
                'icir': np.nan, 'ic_positive_pct': np.nan, 'n_obs': 0}

    ic_series = {}
    for date, group in merged.groupby('trade_date'):
        if len(group) < 30:
            continue
        try:
            ic, _ = spearmanr(group[factor_col], group[fwd_col])
            if not np.isnan(ic):
                ic_series[date] = ic
        except Exception:
            pass

    if not ic_series:
        return {'factor': factor_col, 'ic_mean': np.nan, 'ic_std': np.nan,
                'icir': np.nan, 'ic_positive_pct': np.nan, 'n_obs': 0}

    ic_s = pd.Series(ic_series)
    ic_mean = ic_s.mean()
    ic_std = ic_s.std()
    icir = ic_mean / (ic_std + 1e-10) * np.sqrt(12)  # 月化ICIR
    ic_positive_pct = (ic_s > 0).mean()

    return {
        'factor': factor_col,
        'ic_mean': round(float(ic_mean), 4),
        'ic_std': round(float(ic_std), 4),
        'icir': round(float(icir), 4),
        'ic_positive_pct': round(float(ic_positive_pct), 4),
        'n_obs': len(ic_s),
    }


# ============================================================
# 6. 主流程
# ============================================================

# 所有新因子（含用作对比的roe_yoy）
ALL_NEW_FACTORS = [
    # 技术反转
    'momentum_diff',
    'rsi_reversal',
    'price_vol_divergence',
    'bb_rsi_reversal',
    # 质量
    'roe_yoy',            # ROE变化率（现有，作为对比基准）
    'gross_margin_stability',
    'accrual_ratio',
    # 成长
    'revenue_acceleration',
    'rd_ratio',
]


def run_ic_analysis(factor_df: pd.DataFrame) -> pd.DataFrame:
    """对所有新因子运行IC分析"""
    logger.info(f"\nLoading forward returns ({FWD_HORIZON}d)...")
    fwd_df = load_forward_returns(START_DATE, END_DATE, FWD_HORIZON)
    logger.info(f"Forward returns: {len(fwd_df)} rows")

    results = []
    available = [f for f in ALL_NEW_FACTORS if f in factor_df.columns]
    logger.info(f"\nComputing ICIR for {len(available)} new factors: {available}")

    for i, factor in enumerate(available):
        logger.info(f"  [{i+1}/{len(available)}] {factor}...")
        result = compute_icir(factor_df, fwd_df, factor, FWD_HORIZON)
        results.append(result)
        if not np.isnan(result['icir']):
            logger.info(f"    IC={result['ic_mean']:.4f}, ICIR={result['icir']:.4f}, "
                       f"positive%={result['ic_positive_pct']:.1%}")

    results_df = pd.DataFrame(results).sort_values('icir', key=abs, ascending=False)
    return results_df


def print_summary(results_df: pd.DataFrame):
    """打印分析摘要"""
    print("\n" + "=" * 70)
    print("新因子 ICIR 分析结果 (2024-01-01 to 2026-03-20, Fwd=5d)")
    print("=" * 70)
    print(f"{'因子':<30} {'IC均值':>8} {'IC标准差':>8} {'ICIR':>8} {'正IC%':>8} {'观测数':>6}")
    print("-" * 70)
    for _, row in results_df.iterrows():
        if np.isnan(row['icir']):
            continue
        marker = "✓" if abs(row['icir']) > ICIR_THRESHOLD else " "
        print(f"{marker} {row['factor']:<28} {row['ic_mean']:>8.4f} {row['ic_std']:>8.4f} "
              f"{row['icir']:>8.4f} {row['ic_positive_pct']:>8.1%} {row['n_obs']:>6}")
    print("=" * 70)

    valid = results_df[results_df['icir'].abs() > ICIR_THRESHOLD]
    print(f"\n有效因子 (|ICIR| > {ICIR_THRESHOLD}): {len(valid)}/{len(results_df)}")
    if not valid.empty:
        print("  " + ", ".join(valid['factor'].tolist()))

    print(f"\n建议加入模型的新因子:")
    top_factors = results_df[results_df['icir'].abs() > ICIR_THRESHOLD]['factor'].tolist()
    if top_factors:
        for f in top_factors:
            row = results_df[results_df['factor'] == f].iloc[0]
            direction = "负向" if row['icir'] < 0 else "正向"
            print(f"  - {f}: ICIR={row['icir']:.3f} ({direction})")
    else:
        print("  无新因子达到ICIR阈值")


def main():
    logger.info("=" * 60)
    logger.info("新因子复刻与IC测试")
    logger.info("=" * 60)

    # 构建新因子数据集
    try:
        factor_df = build_new_factor_dataset(START_DATE, END_DATE)
    except Exception as e:
        logger.error(f"Failed to build factor dataset: {e}")
        raise

    # 运行IC分析
    results_df = run_ic_analysis(factor_df)

    # 打印结果
    print_summary(results_df)

    # 保存结果
    os.makedirs('output', exist_ok=True)
    results_df.to_csv('output/new_factor_icir_results.csv', index=False)
    logger.info("Results saved to output/new_factor_icir_results.csv")

    # 返回有效因子列表供后续使用
    valid = results_df[results_df['icir'].abs() > ICIR_THRESHOLD]['factor'].tolist()
    return valid, results_df


if __name__ == '__main__':
    valid_factors, results = main()
    print(f"\n供模型使用的新有效因子: {valid_factors}")
