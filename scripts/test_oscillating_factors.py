"""
震荡市场专项因子测试
====================
测试目标：在震荡市场环境(82.2%的时间)中，
  使用 bb_rsi_reversal + revenue_acceleration 作为纯选股信号，
  绕过 sector_alpha/rs_20d_market 主导问题，评估新因子真实alpha贡献

策略：
  - 仅用 bb_rsi_reversal (ICIR=1.356) + revenue_acceleration (ICIR=1.186)
  - 等权组合，截面Z-score标准化后平均打分
  - 震荡期：使用新因子选股
  - 熊市期：使用原策略逻辑（暂退化为现金/空仓）
  - Top 30 等权持仓，5日调仓

对比基准：
  1. CSI300 (沪深300)
  2. 原RegimeAwareStrategy结果
  3. 仅bb_rsi_reversal单因子
  4. 双因子组合

运行方式:
    python3 scripts/test_oscillating_factors.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    load_and_detect_regimes
)

logger = get_logger(__name__)

START_DATE = '20240101'
END_DATE = '20260320'
OUTPUT_DIR = 'output/oscillating_factor_test'


# ============================================================
# 数据加载
# ============================================================

def load_base_factors(start_date: str, end_date: str) -> pd.DataFrame:
    """加载基础因子数据（包含新因子依赖列）"""
    cols = [
        'trade_date', 'ts_code',
        # bb_rsi_reversal 依赖
        'bb_position', 'rsi_6d', 'rsi_14d',
        # 其他辅助
        'return_5d', 'return_20d',
    ]
    cols_str = ', '.join(cols)
    sql = f"""
    SELECT {cols_str}
    FROM t_precomputed_factors
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('interface', sql))
    if df.empty:
        return df
    df['trade_date'] = df['trade_date'].astype(str)
    for c in cols[2:]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def load_financial_pit(start_date: str, end_date: str,
                       trade_dates: List[str]) -> pd.DataFrame:
    """加载营收加速度所需的季报数据（PIT join）"""
    # 需要3个季度的营收数据
    lookback_start = (pd.Timestamp(start_date) - pd.Timedelta(days=400)).strftime('%Y%m%d')

    # q_sales_yoy: 每季营收同比增速；revenue_acceleration = 本期q_sales_yoy - 上期q_sales_yoy
    sql = f"""
    SELECT ts_code, ann_date, end_date, q_sales_yoy
    FROM t_stock_fina_indicator
    WHERE ann_date >= '{lookback_start}'
      AND ann_date <= '{end_date}'
      AND q_sales_yoy IS NOT NULL
    ORDER BY ts_code, ann_date
    """
    fin_df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    if fin_df.empty:
        logger.warning("No financial data loaded")
        return pd.DataFrame()

    fin_df['ann_date'] = pd.to_datetime(fin_df['ann_date'].astype(str))
    fin_df['q_sales_yoy'] = pd.to_numeric(fin_df['q_sales_yoy'], errors='coerce')
    fin_df = fin_df.dropna(subset=['q_sales_yoy', 'ann_date'])
    fin_df = fin_df.sort_values(['ts_code', 'ann_date'])

    # revenue_acceleration = 本季销售增速 - 上季销售增速（正值=加速增长）
    def calc_rev_accel(grp):
        grp = grp.sort_values('ann_date').copy()
        grp['revenue_acceleration'] = grp['q_sales_yoy'].diff(1)
        return grp

    fin_df = fin_df.groupby('ts_code', group_keys=False).apply(calc_rev_accel)
    fin_df = fin_df.dropna(subset=['revenue_acceleration'])

    # PIT合并：对每个trade_date，取该日期之前最新的ann_date
    trade_dates_df = pd.DataFrame({'trade_date': trade_dates})
    trade_dates_df['trade_date_dt'] = pd.to_datetime(trade_dates_df['trade_date'])

    results = []
    for ts_code, fin_group in fin_df.groupby('ts_code'):
        fin_sorted = fin_group.sort_values('ann_date')
        merged = pd.merge_asof(
            trade_dates_df.sort_values('trade_date_dt'),
            fin_sorted[['ann_date', 'revenue_acceleration']].rename(
                columns={'ann_date': 'fin_date'}),
            left_on='trade_date_dt',
            right_on='fin_date',
            direction='backward'
        )
        merged = merged.dropna(subset=['revenue_acceleration'])
        if merged.empty:
            continue
        merged['ts_code'] = ts_code
        results.append(merged[['trade_date', 'ts_code', 'revenue_acceleration']])

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)


def load_price_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载价格数据"""
    sql = f"""
    SELECT trade_date, ts_code, pct_chg
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    return df


def load_benchmark(start_date: str, end_date: str) -> pd.DataFrame:
    """加载沪深300"""
    sql = f"""
    SELECT trade_date, pct_chg
    FROM t_index_daily
    WHERE ts_code = '000300.SH'
      AND trade_date >= '{start_date}'
      AND trade_date <= '{end_date}'
    ORDER BY trade_date
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    return df


# ============================================================
# 因子计算
# ============================================================

def compute_bb_rsi_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """bb_rsi_reversal = (1 - bb_position) * (100 - rsi_6d) / 100"""
    if 'bb_position' in df.columns and 'rsi_6d' in df.columns:
        df['bb_rsi_reversal'] = (1 - df['bb_position']) * (100 - df['rsi_6d']) / 100
    return df


# ============================================================
# 选股与组合模拟
# ============================================================

def zscore_normalize(series: pd.Series) -> pd.Series:
    """截面Z-score标准化，Winsorize at ±3"""
    mean = series.mean()
    std = series.std()
    if std < 1e-10:
        return pd.Series(0.0, index=series.index)
    return ((series - mean) / std).clip(-3, 3)


def generate_factor_signals(factor_df: pd.DataFrame, regime_map: Dict[str, str],
                              factor_cols: List[str], top_n: int = 30) -> pd.DataFrame:
    """
    基于因子打分生成选股信号

    factor_cols: 用于打分的因子列表（等权组合）
    """
    all_signals = []

    for date, group in factor_df.groupby('trade_date'):
        regime = regime_map.get(date, 'oscillating')

        # 仅在震荡期使用新因子（熊市期也使用，作为测试）
        available_cols = [c for c in factor_cols if c in group.columns and
                          group[c].notna().sum() > 30]
        if not available_cols:
            continue

        # 等权Z-score合并打分
        score = pd.Series(0.0, index=group.index)
        for f in available_cols:
            score += zscore_normalize(group[f])
        score /= len(available_cols)

        group = group.copy()
        group['score'] = score.values
        group['regime'] = regime
        group = group.sort_values('score', ascending=False)
        group['rank'] = range(1, len(group) + 1)

        all_signals.append(
            group[['trade_date', 'ts_code', 'score', 'rank', 'regime']].head(top_n * 3)
        )

    if not all_signals:
        return pd.DataFrame()
    return pd.concat(all_signals, ignore_index=True)


def simulate_portfolio(signals_df: pd.DataFrame, price_df: pd.DataFrame,
                        top_n: int = 30, rebalance_freq: int = 5,
                        transaction_cost: float = 0.001,
                        regime_map: Optional[Dict] = None,
                        only_regime: Optional[str] = None) -> pd.DataFrame:
    """
    模拟等权组合回测

    only_regime: 如果指定，仅在该regime持仓，其他时间空仓
    """
    signal_dates = sorted(signals_df['trade_date'].unique())
    price_dict = price_df.set_index(['trade_date', 'ts_code'])['pct_chg'].to_dict()
    all_dates = sorted(price_df['trade_date'].unique())

    portfolio_returns = []
    current_holdings = []
    last_rebalance_idx = -1

    for i, date in enumerate(all_dates):
        if date < signal_dates[0]:
            continue

        # 判断当日regime
        current_regime = regime_map.get(date, 'oscillating') if regime_map else None

        # 如果限定regime且不匹配，则空仓
        if only_regime and current_regime != only_regime:
            portfolio_returns.append({
                'trade_date': date,
                'portfolio_return': 0.0,
                'n_stocks': 0,
                'transaction_cost': 0.0,
                'regime': current_regime,
            })
            current_holdings = []
            last_rebalance_idx = i
            continue

        need_rebalance = (
            not current_holdings or
            i - last_rebalance_idx >= rebalance_freq
        )

        if need_rebalance and date in signal_dates:
            date_signals = signals_df[signals_df['trade_date'] == date].nsmallest(top_n, 'rank')
            new_holdings = date_signals['ts_code'].tolist()

            if current_holdings:
                turnover = len(set(new_holdings) - set(current_holdings)) / max(len(new_holdings), 1)
                cost = turnover * transaction_cost * 2
            else:
                cost = 0

            current_holdings = new_holdings
            last_rebalance_idx = i
        else:
            cost = 0

        if not current_holdings:
            portfolio_returns.append({
                'trade_date': date,
                'portfolio_return': 0.0,
                'n_stocks': 0,
                'transaction_cost': 0.0,
                'regime': current_regime,
            })
            continue

        daily_returns = []
        for ts_code in current_holdings:
            ret = price_dict.get((date, ts_code), np.nan)
            if not np.isnan(ret):
                daily_returns.append(ret / 100)

        port_ret = np.mean(daily_returns) - cost if daily_returns else 0.0

        portfolio_returns.append({
            'trade_date': date,
            'portfolio_return': port_ret,
            'n_stocks': len(daily_returns),
            'transaction_cost': cost,
            'regime': current_regime,
        })

    return pd.DataFrame(portfolio_returns)


# ============================================================
# 绩效指标
# ============================================================

def compute_metrics(port_returns: pd.Series, bench_returns: pd.Series) -> Dict:
    """计算绩效指标"""
    r = port_returns.fillna(0)
    b = bench_returns.fillna(0)

    common = r.index.intersection(b.index)
    r, b = r.loc[common], b.loc[common]

    cum_r = (1 + r).cumprod()
    cum_b = (1 + b).cumprod()

    n_years = len(r) / 252
    ann_r = (cum_r.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0
    ann_b = (cum_b.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0
    ann_vol = r.std() * np.sqrt(252)

    rf = 0.025 / 252
    sharpe = ((r - rf).mean() * 252) / (ann_vol + 1e-10)

    cum_max = cum_r.cummax()
    max_dd = ((cum_r - cum_max) / cum_max).min()

    alpha = r - b
    ir = (alpha.mean() * 252) / (alpha.std() * np.sqrt(252) + 1e-10)
    win_rate = (r > b).mean()

    return {
        'total_return': round(float(cum_r.iloc[-1] - 1), 4),
        'ann_return': round(float(ann_r), 4),
        'bench_ann_return': round(float(ann_b), 4),
        'ann_vol': round(float(ann_vol), 4),
        'sharpe': round(float(sharpe), 4),
        'max_drawdown': round(float(max_dd), 4),
        'ir': round(float(ir), 4),
        'win_rate': round(float(win_rate), 4),
        'calmar': round(float(ann_r / max(abs(max_dd), 1e-4)), 4),
    }


def compute_ic_for_factor(factor_df: pd.DataFrame, price_df: pd.DataFrame,
                           factor_col: str, horizon: int = 5) -> Dict:
    """计算因子IC/ICIR"""
    # 计算前瞻收益
    price_sorted = price_df.sort_values(['ts_code', 'trade_date'])
    fwd_list = []
    for ts_code, grp in price_sorted.groupby('ts_code'):
        grp = grp.copy().sort_values('trade_date')
        r = grp['pct_chg'].values / 100
        fwd = np.full(len(r), np.nan)
        for i in range(len(r) - horizon):
            fwd[i] = np.prod(1 + r[i+1:i+1+horizon]) - 1
        grp['fwd_return'] = fwd
        fwd_list.append(grp[['trade_date', 'ts_code', 'fwd_return']])

    fwd_df = pd.concat(fwd_list, ignore_index=True)

    merged = factor_df[['trade_date', 'ts_code', factor_col]].merge(
        fwd_df, on=['trade_date', 'ts_code'])
    merged = merged.dropna(subset=[factor_col, 'fwd_return'])

    ic_series = {}
    for date, group in merged.groupby('trade_date'):
        if len(group) < 30:
            continue
        try:
            ic, _ = spearmanr(group[factor_col], group['fwd_return'])
            if not np.isnan(ic):
                ic_series[date] = ic
        except Exception:
            pass

    ic_s = pd.Series(ic_series)
    if len(ic_s) < 5:
        return {'ic_mean': 0, 'ic_std': 0, 'icir': 0, 'n_obs': 0}

    ic_mean = ic_s.mean()
    ic_std = ic_s.std()
    icir = ic_mean / (ic_std + 1e-10) * np.sqrt(12)

    return {
        'ic_mean': round(float(ic_mean), 4),
        'ic_std': round(float(ic_std), 4),
        'icir': round(float(icir), 4),
        'n_obs': len(ic_s),
        'positive_pct': round(float((ic_s > 0).mean()), 4),
    }


# ============================================================
# 主流程
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger.info("=" * 60)
    logger.info("震荡市场专项因子测试: bb_rsi_reversal + revenue_acceleration")
    logger.info("=" * 60)

    # Step 1: 加载市场环境分类
    logger.info("\nStep 1: Loading regime classification...")
    regime_df, _ = load_and_detect_regimes(START_DATE, END_DATE)
    regime_map = dict(zip(
        regime_df['trade_date'].astype(str).values,
        regime_df['regime'].values
    ))

    oscillating_dates = [d for d, r in regime_map.items() if r == 'oscillating']
    bear_dates = [d for d, r in regime_map.items() if r == 'bear']
    logger.info(f"Oscillating: {len(oscillating_dates)} days, Bear: {len(bear_dates)} days")

    # Step 2: 加载基础因子
    logger.info("\nStep 2: Loading base factor data...")
    factor_df = load_base_factors(START_DATE, END_DATE)
    logger.info(f"Factor data: {len(factor_df)} rows, {factor_df['trade_date'].nunique()} dates")

    # 计算bb_rsi_reversal
    factor_df = compute_bb_rsi_reversal(factor_df)

    # Step 3: 加载财务因子 (revenue_acceleration)
    logger.info("\nStep 3: Loading financial factors (PIT)...")
    trade_dates = sorted(factor_df['trade_date'].unique().tolist())
    fin_df = load_financial_pit(START_DATE, END_DATE, trade_dates)
    if not fin_df.empty:
        logger.info(f"Financial factor data: {len(fin_df)} rows")
        factor_df = factor_df.merge(fin_df, on=['trade_date', 'ts_code'], how='left')
        rev_coverage = factor_df['revenue_acceleration'].notna().mean()
        logger.info(f"revenue_acceleration coverage: {rev_coverage:.1%}")
    else:
        logger.warning("No financial data available, using bb_rsi_reversal only")

    # Step 4: 加载价格数据
    logger.info("\nStep 4: Loading price data...")
    price_df = load_price_data(START_DATE, END_DATE)
    benchmark_df = load_benchmark(START_DATE, END_DATE)
    bench_series = benchmark_df.set_index('trade_date')['pct_chg'] / 100

    # Step 5: 计算各因子IC/ICIR（验证）
    logger.info("\nStep 5: Computing factor IC/ICIR...")
    ic_results = {}
    for factor in ['bb_rsi_reversal', 'revenue_acceleration', 'rsi_14d']:
        if factor in factor_df.columns and factor_df[factor].notna().sum() > 100:
            ic_res = compute_ic_for_factor(factor_df, price_df, factor)
            ic_results[factor] = ic_res
            logger.info(f"  {factor}: IC={ic_res['ic_mean']:.4f}, "
                       f"ICIR={ic_res['icir']:.4f}, n={ic_res['n_obs']}")

    # Step 6: 生成不同策略的选股信号
    logger.info("\nStep 6: Generating signals for different strategies...")

    # 策略A: 仅 bb_rsi_reversal
    logger.info("  Strategy A: bb_rsi_reversal only")
    signals_a = generate_factor_signals(factor_df, regime_map, ['bb_rsi_reversal'])

    # 策略B: bb_rsi_reversal + revenue_acceleration
    dual_cols = ['bb_rsi_reversal']
    if 'revenue_acceleration' in factor_df.columns and factor_df['revenue_acceleration'].notna().sum() > 1000:
        dual_cols.append('revenue_acceleration')
    logger.info(f"  Strategy B: {dual_cols}")
    signals_b = generate_factor_signals(factor_df, regime_map, dual_cols)

    # Step 7: 组合模拟（全时段）
    logger.info("\nStep 7: Simulating portfolios (full period)...")

    port_a = simulate_portfolio(signals_a, price_df, top_n=30, rebalance_freq=5,
                                 transaction_cost=0.001, regime_map=regime_map)
    port_b = simulate_portfolio(signals_b, price_df, top_n=30, rebalance_freq=5,
                                 transaction_cost=0.001, regime_map=regime_map)

    # 策略C: 仅震荡期持仓（非震荡期空仓）
    logger.info("\nStep 7b: Simulating oscillating-only portfolio...")
    port_c = simulate_portfolio(signals_b, price_df, top_n=30, rebalance_freq=5,
                                 transaction_cost=0.001, regime_map=regime_map,
                                 only_regime='oscillating')

    # Step 8: 计算绩效
    logger.info("\nStep 8: Computing performance metrics...")

    def get_port_series(port_df):
        return port_df.set_index('trade_date')['portfolio_return']

    port_a_r = get_port_series(port_a)
    port_b_r = get_port_series(port_b)
    port_c_r = get_port_series(port_c)

    common_dates = port_a_r.index.intersection(bench_series.index)

    metrics_a = compute_metrics(port_a_r, bench_series)
    metrics_b = compute_metrics(port_b_r, bench_series)
    metrics_c = compute_metrics(port_c_r, bench_series)

    # 原策略结果（从JSON加载）
    original_path = 'output/strategy_comparison.json'
    original_metrics = None
    if os.path.exists(original_path):
        with open(original_path) as f:
            orig_data = json.load(f)
            original_metrics = orig_data.get('original', {})

    # Step 9: 打印对比报告
    sep = "=" * 65
    report_lines = [
        sep,
        "  震荡市场专项因子测试报告",
        f"  测试区间: {START_DATE} → {END_DATE}",
        f"  市场环境: 震荡={len(oscillating_dates)}天(82.2%), 熊市={len(bear_dates)}天(17.8%)",
        sep,
        "",
        "📊 因子IC/ICIR验证",
        "-" * 50,
    ]
    for f, ic in ic_results.items():
        report_lines.append(f"  {f:30s}: IC={ic['ic_mean']:+.4f}, ICIR={ic['icir']:+.4f}, "
                           f"正IC率={ic['positive_pct']:.1%}")

    report_lines.extend([
        "",
        "🏆 策略绩效对比 (2024-01-01 to 2026-03-20)",
        "-" * 65,
        f"  {'指标':20s} {'A:bb_rsi':>12} {'B:双因子':>12} {'C:震荡专项':>12} {'原策略':>12}",
        f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*12}",
    ])

    orig_v = original_metrics or {}
    rows = [
        ("累计收益", "total_return", "{:.2%}"),
        ("年化收益", "ann_return", "{:.2%}"),
        ("年化波动", "ann_vol", "{:.2%}"),
        ("Sharpe", "sharpe", "{:.4f}"),
        ("最大回撤", "max_drawdown", "{:.2%}"),
        ("信息比率IR", "ir", "{:.4f}"),
        ("胜率", "win_rate", "{:.2%}"),
        ("Calmar", "calmar", "{:.4f}"),
    ]

    for label, key, fmt in rows:
        a_val = fmt.format(metrics_a.get(key, 0))
        b_val = fmt.format(metrics_b.get(key, 0))
        c_val = fmt.format(metrics_c.get(key, 0))
        o_val = fmt.format(orig_v.get(key, orig_v.get('ann_return' if key == 'ann_return' else key, 0)))
        report_lines.append(f"  {label:20s} {a_val:>12} {b_val:>12} {c_val:>12} {o_val:>12}")

    report_lines.extend([
        "",
        f"  基准CSI300年化: {metrics_a['bench_ann_return']:.2%}",
        "",
        "📋 诊断分析",
        "-" * 50,
    ])

    # 诊断
    if metrics_b['sharpe'] > metrics_a['sharpe']:
        report_lines.append("  ✅ 双因子 > 单因子: revenue_acceleration 提供增量信息")
    else:
        report_lines.append("  ⚠️  双因子 ≤ 单因子: revenue_acceleration 效果有限（可能覆盖率不足）")

    if metrics_b['ann_return'] > (orig_v.get('ann_return', 0.16)):
        report_lines.append("  ✅ 双因子策略优于原RegimeAwareStrategy")
    else:
        report_lines.append("  ⚠️  双因子策略未能超越原策略（原策略有sector_alpha优势）")

    if metrics_c['ir'] > 0.1:
        report_lines.append(f"  ✅ 震荡专项策略IR={metrics_c['ir']:.3f}: 新因子在震荡市有正alpha")
    elif metrics_c['ir'] > 0:
        report_lines.append(f"  ⚠️  震荡专项IR={metrics_c['ir']:.3f}: 轻微正alpha但不显著")
    else:
        report_lines.append(f"  ❌ 震荡专项IR={metrics_c['ir']:.3f}: 震荡期alpha为负")

    report_lines.extend([
        "",
        "💡 建议",
        "-" * 50,
        "  1. 将 bb_rsi_reversal 权重提升至0.3-0.4（目前被sector_alpha稀释）",
        "  2. revenue_acceleration 需要更多有效数据（季报发布滞后）",
        "  3. 考虑在震荡期单独使用 bb_rsi_reversal 替代原多因子模型",
        sep,
    ])

    report = "\n".join(report_lines)
    print("\n" + report)

    # Step 10: 保存结果
    report_path = os.path.join(OUTPUT_DIR, 'oscillating_factor_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"Report saved: {report_path}")

    results = {
        'ic_results': ic_results,
        'metrics_a_bb_rsi_only': metrics_a,
        'metrics_b_dual_factor': metrics_b,
        'metrics_c_oscillating_only': metrics_c,
        'original_metrics': orig_v,
        'regime_distribution': {
            'oscillating_days': len(oscillating_dates),
            'bear_days': len(bear_dates),
            'oscillating_pct': len(oscillating_dates) / len(regime_map) * 100 if regime_map else 0,
        },
        'factors_used': dual_cols,
    }
    with open(os.path.join(OUTPUT_DIR, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    # Step 11: 生成对比图表
    logger.info("\nStep 11: Generating charts...")
    try:
        _plot_comparison(port_a_r, port_b_r, port_c_r, bench_series,
                         regime_map, OUTPUT_DIR)
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")

    logger.info(f"\nAll outputs saved to {OUTPUT_DIR}/")
    return results


def _plot_comparison(port_a: pd.Series, port_b: pd.Series, port_c: pd.Series,
                     bench: pd.Series, regime_map: Dict, output_dir: str):
    """生成4图对比：累计收益/回撤/Rolling Alpha/因子IC"""
    common = port_a.index.intersection(bench.index)
    port_a = port_a.loc[common]
    port_b = port_b.loc[common]
    port_c = port_c.loc[common]
    bench_c = bench.loc[common]

    port_a.index = pd.to_datetime(port_a.index)
    port_b.index = pd.to_datetime(port_b.index)
    port_c.index = pd.to_datetime(port_c.index)
    bench_c.index = pd.to_datetime(bench_c.index)

    cum_a = (1 + port_a).cumprod()
    cum_b = (1 + port_b).cumprod()
    cum_c = (1 + port_c).cumprod()
    cum_bench = (1 + bench_c).cumprod()

    fig, axes = plt.subplots(3, 1, figsize=(14, 11))
    fig.suptitle('Oscillating Market Factor Test: bb_rsi_reversal + revenue_acceleration',
                 fontsize=13, fontweight='bold')

    # Shade oscillating periods
    colors_regime = {'bull': '#90EE90', 'bear': '#FFB6C1', 'oscillating': '#FFFACD'}
    ax = axes[0]
    ax.plot(cum_a.index, cum_a.values, label='A: bb_rsi_reversal', lw=2, color='royalblue')
    ax.plot(cum_b.index, cum_b.values, label='B: Dual Factor', lw=2, color='darkgreen')
    ax.plot(cum_c.index, cum_c.values, label='C: Oscillating Only', lw=1.5,
            color='purple', linestyle='-.')
    ax.plot(cum_bench.index, cum_bench.values, label='CSI300', lw=1.5,
            color='orange', linestyle='--')
    ax.set_title('Cumulative Returns')
    ax.set_ylabel('Cumulative Return')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Drawdown
    ax2 = axes[1]
    for series, label, color in [
        (cum_a, 'A: bb_rsi', 'royalblue'),
        (cum_b, 'B: Dual', 'darkgreen'),
        (cum_bench, 'CSI300', 'orange'),
    ]:
        cum_max = series.cummax()
        dd = (series - cum_max) / cum_max
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.3, color=color, label=label)
    ax2.set_title('Drawdown Comparison')
    ax2.set_ylabel('Drawdown')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Rolling 60-day alpha of Strategy B vs benchmark
    ax3 = axes[2]
    alpha_b = port_b - bench_c
    rolling_alpha = alpha_b.rolling(60).mean() * 252
    ax3.plot(rolling_alpha.index, rolling_alpha.values, color='darkgreen', lw=1.5)
    ax3.axhline(y=0, color='black', lw=0.8, linestyle='--')
    ax3.fill_between(rolling_alpha.index, rolling_alpha.values, 0,
                     where=rolling_alpha > 0, alpha=0.3, color='green', label='Positive Alpha')
    ax3.fill_between(rolling_alpha.index, rolling_alpha.values, 0,
                     where=rolling_alpha < 0, alpha=0.3, color='red', label='Negative Alpha')
    ax3.set_title('Strategy B (Dual Factor) Rolling 60-day Alpha (Annualized)')
    ax3.set_ylabel('Annualized Alpha')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'oscillating_factor_comparison.png')
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Chart saved: {chart_path}")


if __name__ == '__main__':
    main()
