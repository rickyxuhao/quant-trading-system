"""
Phase 4 v3: strategy-researcher-001 熵驱动多因子策略
=====================================================
基于 entropy_20d（ICIR=+3.95，单调性=1.0）主信号 + 副信号排名。

设计原理:
  - 高熵 = 成交分散 = 市场分歧 = 多头信号（不是少数人在出货）
  - 低熵 = 成交集中 = 顶部出货 = 卖出信号
  - 只使用无需历史积累的因子（entropy_20d, turnover_20d, volume_ratio等）

策略逻辑:
  1. 按截面排名对 entropy_20d 排名（高熵↑= 买入信号）
  2. 二次信号: net_inflow_20d（正流入↑）、bb_width（宽布林带=波动分化）
  3. 合成分数 = 0.6 * entropy_rank + 0.2 * inflow_rank + 0.2 * bb_rank
  4. 每5个交易日，买入合成分数最高的 TOP_N 只股票
  5. 择时仓位（牛市100%/震荡70%/熊市40%）

输出:
  - output/backtest_nav.csv     (覆盖前版本)
  - output/backtest_metrics.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from typing import Dict, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedRegimeDetector, EnhancedMarketRegime
)

logger = get_logger(__name__)

START_DATE = '20240102'
END_DATE   = '20260320'
TOP_N = 30
REBALANCE_FREQ = 5
TRANSACTION_COST = 0.001

REGIME_POSITION = {
    EnhancedMarketRegime.BULL: 1.00,
    EnhancedMarketRegime.OSCILLATING: 0.70,
    EnhancedMarketRegime.BEAR: 0.40,
}

# Factor weights (sum=1.0)
FACTOR_WEIGHTS = {
    'entropy_20d':    0.60,
    'net_inflow_20d': 0.20,
    'bb_width':       0.20,
}

OUTPUT_DIR = 'output/multifactor'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_factor_data() -> pd.DataFrame:
    factors = list(FACTOR_WEIGHTS.keys())
    cols = ', '.join(factors)
    rows = DatabaseManager.fetchall('interface', f'''
        SELECT trade_date, ts_code, {cols}
        FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    for f in factors:
        df[f] = pd.to_numeric(df[f], errors='coerce')
    logger.info(f"Factor data: {len(df)} rows, {df['trade_date'].nunique()} dates")
    return df


def load_market_data() -> pd.DataFrame:
    rows = DatabaseManager.fetchall('tushare_biz', f'''
        SELECT trade_date, ts_code, pct_chg
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    logger.info(f"Market data: {len(df)} rows")
    return df


def load_index_data() -> pd.DataFrame:
    try:
        rows = DatabaseManager.fetchall('tushare_biz', f'''
            SELECT trade_date, pct_chg FROM t_index_daily
            WHERE ts_code = '000300.SH'
              AND trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
            ORDER BY trade_date
        ''')
        df = pd.DataFrame(rows)
        df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()


def build_composite_score(factor_df: pd.DataFrame) -> pd.DataFrame:
    """截面合成分数：每日对各因子排名 → 加权合成"""
    result_rows = []
    for date, grp in factor_df.groupby('trade_date'):
        grp = grp.copy()
        score = np.zeros(len(grp))
        valid_count = 0
        for f, w in FACTOR_WEIGHTS.items():
            series = grp[f]
            n_valid = series.notna().sum()
            if n_valid < 10:
                continue
            # 截面排名 [0, 1]
            ranks = series.rank(pct=True, na_option='keep')
            ranks = ranks.fillna(0.5)  # 缺失值给中间排名
            score += w * ranks.values
            valid_count += 1
        if valid_count == 0:
            continue
        grp['score'] = score
        result_rows.append(grp[['trade_date', 'ts_code', 'score']])
    if not result_rows:
        return pd.DataFrame(columns=['trade_date', 'ts_code', 'score'])
    return pd.concat(result_rows, ignore_index=True)


def run_backtest(scores_df: pd.DataFrame, market_df: pd.DataFrame,
                 regime_detector: EnhancedRegimeDetector,
                 index_df: pd.DataFrame) -> Dict:
    all_dates = sorted(market_df['trade_date'].unique())
    rebalance_dates = set(all_dates[i] for i in range(0, len(all_dates), REBALANCE_FREQ))

    # Precompute return lookup
    ret_map = {}
    for _, row in market_df.iterrows():
        ret_map.setdefault(row['trade_date'], {})[row['ts_code']] = row['pct_chg'] / 100

    # Index return lookup
    idx_map = {}
    if not index_df.empty:
        for _, row in index_df.iterrows():
            idx_map[row['trade_date']] = float(row['pct_chg']) / 100

    nav        = [1.0]
    bench_nav  = [1.0]
    nav_dates  = [all_dates[0]]
    current_holdings = {}
    current_regime = EnhancedMarketRegime.OSCILLATING

    for i, date in enumerate(all_dates[1:], 1):
        prev_date = all_dates[i - 1]

        if prev_date in rebalance_dates:
            # Regime detection
            try:
                current_regime, _ = regime_detector.detect_regime(prev_date)
            except Exception:
                pass

            # Build holdings from scores
            scores_on_date = scores_df[scores_df['trade_date'] == prev_date]
            if len(scores_on_date) >= TOP_N:
                top = scores_on_date.nlargest(TOP_N, 'score')['ts_code'].tolist()
                w = 1.0 / TOP_N
                current_holdings = {s: w for s in top}

        # Position multiplier
        pos_mult = REGIME_POSITION.get(current_regime, 0.7)

        day_ret_map = ret_map.get(date, {})
        if current_holdings:
            port_ret = sum(w * day_ret_map.get(s, 0) for s, w in current_holdings.items())
            if prev_date in rebalance_dates:
                port_ret -= TRANSACTION_COST
            adj_ret = port_ret * pos_mult
        else:
            adj_ret = 0.0

        nav.append(nav[-1] * (1 + adj_ret))
        bench_nav.append(bench_nav[-1] * (1 + idx_map.get(date, 0)))
        nav_dates.append(date)

    nav_df = pd.DataFrame({'date': nav_dates, 'strategy': nav, 'benchmark': bench_nav})

    # Metrics
    daily_rets = pd.Series(nav).pct_change().dropna()
    bench_rets = pd.Series(bench_nav).pct_change().dropna()
    ann = 252
    n = len(daily_rets)

    def ann_ret(nav_s):
        return float((nav_s[-1] / nav_s[0]) ** (ann / n) - 1)

    def sharpe(r):
        return float(r.mean() / r.std() * np.sqrt(ann)) if r.std() > 1e-10 else 0.0

    def max_dd(nav_s):
        s = pd.Series(nav_s)
        return float((s / s.cummax() - 1).min())

    strat_ann = ann_ret(nav)
    bench_ann = ann_ret(bench_nav)
    excess = daily_rets.values - bench_rets.values[:len(daily_rets)]
    ir = float(excess.mean() / (excess.std() + 1e-10) * np.sqrt(ann))

    metrics = {
        'start_date': str(nav_dates[0].date()),
        'end_date': str(nav_dates[-1].date()),
        'strategy_annual_return': round(strat_ann, 4),
        'benchmark_annual_return': round(bench_ann, 4),
        'excess_annual_return': round(strat_ann - bench_ann, 4),
        'strategy_sharpe': round(sharpe(daily_rets), 4),
        'max_drawdown': round(max_dd(nav), 4),
        'information_ratio': round(ir, 4),
        'total_return': round(float(nav[-1] - 1), 4),
        'benchmark_total_return': round(float(bench_nav[-1] - 1), 4),
    }
    return {'nav_df': nav_df, 'metrics': metrics}


def plot_nav(nav_df: pd.DataFrame, metrics: Dict):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    ax1.plot(nav_df['date'], nav_df['strategy'], 'b-', linewidth=1.5, label='Strategy (Entropy)')
    ax1.plot(nav_df['date'], nav_df['benchmark'], 'r--', linewidth=1.2, label='CSI300')
    ax1.set_title(
        f"Entropy-Driven Multi-Factor Strategy\n"
        f"Annual={metrics['strategy_annual_return']*100:.1f}%  "
        f"Sharpe={metrics['strategy_sharpe']:.2f}  "
        f"MaxDD={metrics['max_drawdown']*100:.1f}%  "
        f"IR={metrics['information_ratio']:.2f}",
        fontsize=11
    )
    ax1.legend()
    ax1.set_ylabel('净值')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    dd = (nav_df['strategy'] / nav_df['strategy'].cummax() - 1) * 100
    ax2.fill_between(nav_df['date'], dd, 0, color='red', alpha=0.4, label='Drawdown')
    ax2.set_ylabel('回撤 (%)')
    ax2.set_xlabel('日期')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.legend()

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/strategy_nav.png', dpi=100, bbox_inches='tight')
    plt.close()
    logger.info(f"NAV chart saved to {OUTPUT_DIR}/strategy_nav.png")


def main():
    logger.info("=== Phase 4 v3: Entropy-Driven Strategy (strategy-researcher-001) ===")

    logger.info("Loading data...")
    factor_df = load_factor_data()
    market_df = load_market_data()
    index_df  = load_index_data()

    logger.info("Building composite score (entropy_20d × 0.6 + net_inflow_20d × 0.2 + bb_width × 0.2)...")
    scores_df = build_composite_score(factor_df)
    logger.info(f"Scores: {len(scores_df)} rows, {scores_df['trade_date'].nunique()} dates")

    regime_detector = EnhancedRegimeDetector()

    logger.info("Running backtest...")
    result = run_backtest(scores_df, market_df, regime_detector, index_df)

    nav_df  = result['nav_df']
    metrics = result['metrics']

    # Save outputs
    nav_df.to_csv('output/backtest_nav.csv', index=False)
    with open('output/backtest_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info("Outputs saved.")

    plot_nav(nav_df, metrics)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("STRATEGY PERFORMANCE SUMMARY (Entropy-Driven)")
    logger.info(f"{'='*60}")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v}")

    sharpe = metrics['strategy_sharpe']
    max_dd = abs(metrics['max_drawdown'])
    if sharpe >= 1.0 and max_dd <= 0.20:
        logger.info(f"\n✅ Phase 4 PASS: Sharpe={sharpe:.2f} >= 1.0, MaxDD={max_dd*100:.1f}% <= 20%")
    else:
        warns = []
        if sharpe < 1.0:
            warns.append(f"Sharpe={sharpe:.2f} < 1.0")
        if max_dd > 0.20:
            warns.append(f"MaxDD={max_dd*100:.1f}% > 20%")
        logger.warning(f"\n⚠️  Phase 4 NOT PASS: {'; '.join(warns)}")

    return metrics


if __name__ == '__main__':
    main()
