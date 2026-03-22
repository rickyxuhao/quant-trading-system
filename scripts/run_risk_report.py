"""
Phase 5: risk-manager-001 风险审查
===================================
基于 Phase 4 策略净值，生成全面风险评估报告。

输入:
  - output/backtest_nav.csv
  - output/backtest_metrics.json
  - output/layered_stats.json

输出:
  - output/risk_report.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from typing import Dict

from core.logger import get_logger

logger = get_logger(__name__)


def check_lookahead_bias(nav_df: pd.DataFrame) -> Dict:
    """
    简单的 lookahead 检测：
    - 如果 Sharpe > 3.0 AND strategy 在所有月份均为正，高度疑似泄漏
    """
    daily_rets = nav_df['strategy'].pct_change().dropna()
    sharpe = daily_rets.mean() / daily_rets.std() * np.sqrt(252)

    nav_df2 = nav_df.copy()
    nav_df2['month'] = pd.to_datetime(nav_df2['date']).dt.to_period('M')
    monthly_ret = nav_df2.groupby('month')['strategy'].apply(
        lambda x: x.iloc[-1] / x.iloc[0] - 1 if len(x) > 1 else 0
    )
    positive_months_pct = (monthly_ret > 0).mean()

    suspicious = bool(sharpe > 3.0 and positive_months_pct > 0.9)
    return {
        'sharpe': round(float(sharpe), 4),
        'positive_months_pct': round(float(positive_months_pct), 4),
        'lookahead_suspicious': suspicious,
        'note': ('⚠️ Sharpe > 3.0 and >90% positive months — possible lookahead bias'
                 if suspicious else '✅ No obvious lookahead indicators')
    }


def compute_drawdown_analysis(nav: pd.Series) -> Dict:
    """详细回撤分析"""
    roll_max = nav.cummax()
    dd = (nav - roll_max) / roll_max

    max_dd = float(dd.min())
    max_dd_date = str(dd.idxmin())

    # Find drawdown periods
    in_dd = dd < -0.01
    dd_periods = []
    start = None
    nav_idx = pd.to_datetime(nav.index) if not pd.api.types.is_datetime64_any_dtype(nav.index) else nav.index
    dd_dates = list(zip(nav_idx, dd.values))
    for d, v in dd_dates:
        if v < -0.01 and start is None:
            start = d
        elif v >= -0.005 and start is not None:
            mask = (nav_idx >= start) & (nav_idx <= d)
            dd_periods.append({
                'start': str(start.date()) if hasattr(start, 'date') else str(start),
                'end': str(d.date()) if hasattr(d, 'date') else str(d),
                'depth': round(float(dd.values[mask].min()), 4),
                'length_days': (d - start).days if hasattr(d, 'days') or hasattr(start, 'days') else int((d - start) / np.timedelta64(1, 'D'))
            })
            start = None

    # Sort by depth
    dd_periods = sorted(dd_periods, key=lambda x: x['depth'])[:5]

    return {
        'max_drawdown': round(max_dd, 4),
        'max_drawdown_date': max_dd_date,
        'top_5_drawdowns': dd_periods,
        'avg_drawdown': round(float(dd[dd < 0].mean()), 4) if (dd < 0).any() else 0.0,
    }


def compute_regime_performance(nav_df: pd.DataFrame) -> Dict:
    """按年度拆解绩效"""
    nav_df = nav_df.copy()
    nav_df['year'] = pd.to_datetime(nav_df['date']).dt.year

    yearly = {}
    for year, g in nav_df.groupby('year'):
        if len(g) < 2:
            continue
        rets = g['strategy'].pct_change().dropna()
        total = g['strategy'].iloc[-1] / g['strategy'].iloc[0] - 1
        sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
        dd = ((g['strategy'] / g['strategy'].cummax()) - 1).min()
        yearly[str(year)] = {
            'total_return': round(float(total), 4),
            'sharpe': round(float(sharpe), 4),
            'max_drawdown': round(float(dd), 4),
        }
    return yearly


def compute_risk_metrics(nav_df: pd.DataFrame) -> Dict:
    """VaR, CVaR, Calmar, Sortino"""
    daily_rets = nav_df['strategy'].pct_change().dropna()
    ann = 252

    annual_ret = float((nav_df['strategy'].iloc[-1] / nav_df['strategy'].iloc[0]) **
                       (ann / len(daily_rets)) - 1)

    # VaR & CVaR (95%, 99%)
    var_95 = float(np.percentile(daily_rets, 5))
    var_99 = float(np.percentile(daily_rets, 1))
    cvar_95 = float(daily_rets[daily_rets <= var_95].mean())
    cvar_99 = float(daily_rets[daily_rets <= var_99].mean())

    # Sortino
    downside = daily_rets[daily_rets < 0]
    sortino = (daily_rets.mean() / (downside.std() + 1e-10)) * np.sqrt(ann)

    # Calmar
    max_dd = abs((nav_df['strategy'] / nav_df['strategy'].cummax() - 1).min())
    calmar = annual_ret / (max_dd + 1e-10)

    return {
        'var_95': round(var_95, 5),
        'var_99': round(var_99, 5),
        'cvar_95': round(cvar_95, 5),
        'cvar_99': round(cvar_99, 5),
        'sortino_ratio': round(float(sortino), 4),
        'calmar_ratio': round(float(calmar), 4),
        'annual_volatility': round(float(daily_rets.std() * np.sqrt(ann)), 4),
        'skewness': round(float(daily_rets.skew()), 4),
        'kurtosis': round(float(daily_rets.kurtosis()), 4),
    }


def risk_approval_gate(metrics: Dict, la: Dict) -> Dict:
    """风控审核门禁"""
    sharpe = metrics.get('strategy_sharpe', 0)
    max_dd = abs(metrics.get('max_drawdown', -1))
    ir     = metrics.get('information_ratio', 0)

    checks = [
        ('Sharpe >= 1.0',       sharpe >= 1.0,   f"Sharpe={sharpe:.2f}"),
        ('MaxDD <= 20%',        max_dd <= 0.20,  f"MaxDD={max_dd*100:.1f}%"),
        ('IR >= 0.3',           ir >= 0.3,       f"IR={ir:.2f}"),
        ('No lookahead (Sharpe<=3 or <90% positive months)',
                                not la['lookahead_suspicious'],
                                la['note']),
    ]

    all_pass = all(c[1] for c in checks)
    return {
        'approved': all_pass,
        'verdict': '✅ APPROVED' if all_pass else '⛔ REJECTED',
        'checks': [{'rule': c[0], 'pass': c[1], 'detail': c[2]} for c in checks],
    }


def main():
    logger.info("=== Phase 5: 风险审查 (risk-manager-001) ===")

    # Load inputs
    nav_path = 'output/backtest_nav.csv'
    metrics_path = 'output/backtest_metrics.json'

    if not os.path.exists(nav_path) or not os.path.exists(metrics_path):
        logger.error("Phase 4 outputs not found. Run run_multifactor_strategy.py first.")
        return

    nav_df = pd.read_csv(nav_path, parse_dates=['date'])
    with open(metrics_path) as f:
        metrics = json.load(f)

    # Analyses
    logger.info("Running lookahead bias check...")
    la = check_lookahead_bias(nav_df)

    logger.info("Computing drawdown analysis...")
    dd_analysis = compute_drawdown_analysis(nav_df['strategy'])

    logger.info("Computing yearly breakdown...")
    yearly = compute_regime_performance(nav_df)

    logger.info("Computing risk metrics...")
    risk = compute_risk_metrics(nav_df)

    logger.info("Running approval gate...")
    gate = risk_approval_gate(metrics, la)

    # Assemble report
    report = {
        'generated_at': pd.Timestamp.now().isoformat(),
        'strategy_metrics': metrics,
        'lookahead_check': la,
        'drawdown_analysis': dd_analysis,
        'yearly_performance': yearly,
        'risk_metrics': risk,
        'approval': gate,
    }

    with open('output/risk_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Risk report saved to output/risk_report.json")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("RISK REVIEW SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Verdict: {gate['verdict']}")
    for c in gate['checks']:
        status = '✅' if c['pass'] else '❌'
        logger.info(f"  {status} {c['rule']}: {c['detail']}")
    logger.info(f"\nAdditional metrics:")
    logger.info(f"  Sortino:  {risk['sortino_ratio']:.2f}")
    logger.info(f"  Calmar:   {risk['calmar_ratio']:.2f}")
    logger.info(f"  VaR(99%): {risk['var_99']*100:.2f}%/day")
    logger.info(f"  MaxDD:    {dd_analysis['max_drawdown']*100:.1f}%")
    if yearly:
        logger.info("\nYearly performance:")
        for yr, ym in sorted(yearly.items()):
            logger.info(f"  {yr}: return={ym['total_return']*100:.1f}%  "
                        f"Sharpe={ym['sharpe']:.2f}  MaxDD={ym['max_drawdown']*100:.1f}%")

    return report


if __name__ == '__main__':
    main()
