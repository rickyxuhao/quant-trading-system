"""
Phase 3: backtest-engineer-001 分层回测验证
==========================================
对 Phase 2 筛选出的有效因子进行5分位分层回测，验证因子单调性。

输入: output/factor_icir_results.json (Phase 2 输出)
输出:
  - output/layered_returns.csv  (每个因子的5组分位净值序列)
  - output/layered_stats.json   (单调性得分、分层收益统计)
  - output/layered_backtest/    (各因子分层收益图)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from typing import List, Dict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)

START_DATE = '20240102'
END_DATE   = '20260320'
N_QUINTILES = 5
TOP_N = 30              # 每组股票数
REBALANCE_FREQ = 5      # 调仓频率（交易日）
TRANSACTION_COST = 0.001

OUTPUT_DIR = 'output/layered_backtest'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_selected_factors() -> List[str]:
    """从 Phase 2 结果加载筛选后的因子列表"""
    results_path = 'output/factor_icir_results.json'
    if not os.path.exists(results_path):
        raise FileNotFoundError(f"Phase 2 results not found: {results_path}")
    with open(results_path) as f:
        data = json.load(f)
    selected = data.get('selected_factors', [])
    logger.info(f"Loaded {len(selected)} selected factors from Phase 2: {selected}")
    return selected


def load_factor_data(factors: List[str]) -> pd.DataFrame:
    """加载指定因子数据"""
    cols = ', '.join(factors)
    rows = DatabaseManager.fetchall('interface', f'''
        SELECT trade_date, ts_code, {cols}
        FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No factor data loaded")
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    for f in factors:
        df[f] = pd.to_numeric(df[f], errors='coerce')
    logger.info(f"Factor data: {len(df)} rows, {df['trade_date'].nunique()} dates")
    return df


def load_returns() -> pd.DataFrame:
    """加载每日收益率"""
    rows = DatabaseManager.fetchall('tushare_biz', f'''
        SELECT trade_date, ts_code, pct_chg, open, close
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['open']    = pd.to_numeric(df['open'], errors='coerce')
    df['close']   = pd.to_numeric(df['close'], errors='coerce')
    logger.info(f"Returns data: {len(df)} rows")
    return df


def get_rebalance_dates(all_dates: pd.DatetimeIndex) -> List[pd.Timestamp]:
    """每 REBALANCE_FREQ 个交易日取一个调仓日"""
    dates = sorted(all_dates.unique())
    return [dates[i] for i in range(0, len(dates), REBALANCE_FREQ)]


def run_quintile_backtest(factor_df: pd.DataFrame, returns_df: pd.DataFrame,
                          factor_name: str) -> Dict:
    """
    对单个因子做5分位回测
    Returns dict with:
        nav_df: DataFrame columns=[date, Q1..Q5, LS]
        stats: monotonicity, spreads, sharpe per quintile
    """
    dates = sorted(factor_df['trade_date'].unique())
    rebalance_dates = get_rebalance_dates(pd.DatetimeIndex(dates))

    # 持仓字典: quintile -> {ts_code: weight}
    holdings = {q: {} for q in range(1, N_QUINTILES + 1)}

    nav = {q: [1.0] for q in range(1, N_QUINTILES + 1)}
    nav['LS'] = [1.0]  # Long Q1, Short Q5 (反转策略)
    nav_dates = [dates[0]]

    current_holdings = {q: {} for q in range(1, N_QUINTILES + 1)}

    for i, date in enumerate(dates[1:], 1):
        # 是否调仓
        prev_date = dates[i - 1]
        if prev_date in rebalance_dates:
            factor_on_date = factor_df[factor_df['trade_date'] == prev_date][
                ['ts_code', factor_name]].dropna()
            if len(factor_on_date) >= N_QUINTILES * 10:
                factor_on_date = factor_on_date.sort_values(factor_name)
                n = len(factor_on_date)
                q_size = n // N_QUINTILES
                for q in range(1, N_QUINTILES + 1):
                    start_idx = (q - 1) * q_size
                    end_idx = q * q_size if q < N_QUINTILES else n
                    group_stocks = factor_on_date.iloc[start_idx:end_idx]['ts_code'].tolist()
                    w = 1.0 / len(group_stocks)
                    current_holdings[q] = {s: w for s in group_stocks}

        # 当日收益
        day_ret = returns_df[returns_df['trade_date'] == date][['ts_code', 'pct_chg']]
        ret_map = dict(zip(day_ret['ts_code'], day_ret['pct_chg'] / 100))

        for q in range(1, N_QUINTILES + 1):
            if not current_holdings[q]:
                nav[q].append(nav[q][-1])
                continue
            port_ret = sum(w * ret_map.get(s, 0) for s, w in current_holdings[q].items())
            # transaction cost on turnover (approx 5d turnover ~ 100% turnover per rebalance)
            if i > 0 and dates[i - 1] in rebalance_dates:
                port_ret -= TRANSACTION_COST
            nav[q].append(nav[q][-1] * (1 + port_ret))

        # Long-Short: buy Q1, sell Q5 (low factor = reversal buy)
        ls_ret = (sum(w * ret_map.get(s, 0) for s, w in current_holdings[1].items()) -
                  sum(w * ret_map.get(s, 0) for s, w in current_holdings[5].items()))
        if i > 0 and dates[i - 1] in rebalance_dates:
            ls_ret -= 2 * TRANSACTION_COST
        nav['LS'].append(nav['LS'][-1] * (1 + ls_ret))

        nav_dates.append(date)

    nav_df = pd.DataFrame({'date': nav_dates})
    for q in range(1, N_QUINTILES + 1):
        nav_df[f'Q{q}'] = nav[q]
    nav_df['LS'] = nav['LS']

    # Compute stats
    ann_factor = 252
    final_navs = [nav_df[f'Q{q}'].iloc[-1] for q in range(1, N_QUINTILES + 1)]
    n_days = len(nav_df)

    def annualized_ret(nav_series):
        if nav_series.iloc[0] <= 0:
            return 0
        total = nav_series.iloc[-1] / nav_series.iloc[0]
        return total ** (ann_factor / n_days) - 1

    def sharpe(nav_series):
        daily_rets = nav_series.pct_change().dropna()
        if daily_rets.std() < 1e-10:
            return 0
        return daily_rets.mean() / daily_rets.std() * np.sqrt(ann_factor)

    q_rets = [annualized_ret(nav_df[f'Q{q}']) for q in range(1, N_QUINTILES + 1)]
    q_sharpe = [sharpe(nav_df[f'Q{q}']) for q in range(1, N_QUINTILES + 1)]

    # Monotonicity: check if returns are monotonically increasing from Q1 to Q5 or decreasing
    from scipy.stats import spearmanr
    mono_corr, _ = spearmanr(range(1, N_QUINTILES + 1), q_rets)
    monotonicity = abs(mono_corr)

    ls_annual = annualized_ret(nav_df['LS'])
    ls_sharpe = sharpe(nav_df['LS'])

    stats = {
        'factor': factor_name,
        'monotonicity': round(float(monotonicity), 4),
        'q_annual_returns': [round(float(r), 4) for r in q_rets],
        'q_sharpe': [round(float(s), 4) for q, s in enumerate(q_sharpe)],
        'spread_q1_q5': round(float(q_rets[0] - q_rets[4]), 4),
        'ls_annual': round(float(ls_annual), 4),
        'ls_sharpe': round(float(ls_sharpe), 4),
        'final_navs': [round(float(v), 4) for v in final_navs],
    }

    return {'nav_df': nav_df, 'stats': stats}


def plot_quintile(nav_df: pd.DataFrame, factor_name: str, stats: Dict):
    """绘制5分位净值图"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    colors = ['#d73027', '#fc8d59', '#fee090', '#91bfdb', '#4575b4']
    for q, color in enumerate(colors, 1):
        ax1.plot(nav_df['date'], nav_df[f'Q{q}'], color=color,
                 label=f'Q{q} ({stats["q_annual_returns"][q-1]*100:.1f}%/yr)',
                 linewidth=1.5)
    ax1.plot(nav_df['date'], nav_df['LS'], 'k--', linewidth=2,
             label=f'L-S ({stats["ls_annual"]*100:.1f}%/yr)')
    ax1.set_title(f'{factor_name} — 5分位净值\n'
                  f'单调性={stats["monotonicity"]:.3f}  L-S Sharpe={stats["ls_sharpe"]:.2f}',
                  fontsize=12)
    ax1.legend(loc='upper left', fontsize=8)
    ax1.set_ylabel('净值')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Bar chart of annualized returns
    q_labels = [f'Q{i}' for i in range(1, N_QUINTILES + 1)]
    q_vals = [r * 100 for r in stats['q_annual_returns']]
    bar_colors = ['green' if v > 0 else 'red' for v in q_vals]
    ax2.bar(q_labels, q_vals, color=bar_colors, alpha=0.7, edgecolor='black')
    ax2.axhline(0, color='black', linewidth=0.8)
    ax2.set_title(f'各分组年化收益率 (单调性: {stats["monotonicity"]:.3f})')
    ax2.set_ylabel('年化收益率 (%)')
    ax2.grid(True, alpha=0.3, axis='y')
    for i, v in enumerate(q_vals):
        ax2.text(i, v + 0.5, f'{v:.1f}%', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/{factor_name}_quintile.png', dpi=100, bbox_inches='tight')
    plt.close()


def main():
    logger.info("=== Phase 3: 分层回测 (backtest-engineer-001) ===")

    # 加载因子列表
    selected_factors = load_selected_factors()

    if not selected_factors:
        logger.warning("No selected factors found from Phase 2. Exiting.")
        return

    # 加载数据
    logger.info("Loading factor data...")
    factor_df = load_factor_data(selected_factors)
    logger.info("Loading returns data...")
    returns_df = load_returns()

    all_stats = []
    all_nav_dfs = []

    for i, factor in enumerate(selected_factors):
        logger.info(f"[{i+1}/{len(selected_factors)}] Quintile backtest for {factor}")
        try:
            result = run_quintile_backtest(factor_df, returns_df, factor)
            stats = result['stats']
            all_stats.append(stats)

            nav_df = result['nav_df'].copy()
            nav_df['factor'] = factor
            all_nav_dfs.append(nav_df)

            logger.info(f"  Monotonicity={stats['monotonicity']:.3f}, "
                        f"L-S={stats['ls_annual']*100:.1f}%/yr, "
                        f"L-S Sharpe={stats['ls_sharpe']:.2f}")

            plot_quintile(result['nav_df'], factor, stats)
        except Exception as e:
            logger.warning(f"  Failed for {factor}: {e}")

    # Save results
    stats_path = 'output/layered_stats.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump({'results': all_stats}, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Stats saved to {stats_path}")

    if all_nav_dfs:
        combined = pd.concat(all_nav_dfs, ignore_index=True)
        combined.to_csv('output/layered_returns.csv', index=False)
        logger.info("NAV data saved to output/layered_returns.csv")

    # Summary
    stats_df = pd.DataFrame(all_stats).sort_values('monotonicity', ascending=False)
    logger.info(f"\n{'='*60}")
    logger.info("LAYERED BACKTEST SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"\n{stats_df[['factor','monotonicity','spread_q1_q5','ls_annual','ls_sharpe']].to_string(index=False)}")

    valid_mono = stats_df[stats_df['monotonicity'] > 0.7]
    logger.info(f"\n单调性 > 0.7 的因子: {len(valid_mono)}/{len(stats_df)}")
    if not valid_mono.empty:
        logger.info(valid_mono[['factor', 'monotonicity', 'ls_sharpe']].to_string(index=False))

    return stats_df


if __name__ == '__main__':
    main()
