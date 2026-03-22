"""
Phase 4: strategy-researcher-001 多因子 XGBoost 走势策略
=========================================================
Walk-forward cross-validation + regime-aware position sizing.

输入:
  - output/factor_icir_results.json (Phase 2 选出的因子)
  - t_precomputed_factors (因子数据)
  - t_stock_dailymarketdata (行情数据)

输出:
  - output/backtest_nav.csv     (策略净值序列)
  - output/backtest_metrics.json (详细指标)
  - output/multifactor/         (图表)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import xgboost as xgb
from sklearn.preprocessing import RobustScaler

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedRegimeDetector, EnhancedMarketRegime, FACTOR_MULTIPLIERS
)

logger = get_logger(__name__)

# ============================================================
# 配置
# ============================================================
START_DATE = '20240102'
END_DATE   = '20260320'
TRAIN_LOOKBACK_DAYS = 126   # 训练窗口（约6个月，v2迭代：扩大回测覆盖至2024下半年）
PREDICT_PERIOD_DAYS = 42    # 预测窗口（约2个月）
FORWARD_HORIZON = 5         # 预测未来5日收益
TOP_N = 30                  # 每期持仓数
REBALANCE_FREQ = 5          # 调仓频率
TRANSACTION_COST = 0.001

REGIME_POSITION = {
    EnhancedMarketRegime.BULL: 1.00,
    EnhancedMarketRegime.OSCILLATING: 0.70,
    EnhancedMarketRegime.BEAR: 0.40,
}

OUTPUT_DIR = 'output/multifactor'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_selected_factors() -> List[str]:
    path = 'output/factor_icir_results.json'
    if not os.path.exists(path):
        raise FileNotFoundError(f"Phase 2 results not found: {path}")
    with open(path) as f:
        data = json.load(f)
    selected = data.get('selected_factors', [])
    logger.info(f"Selected factors from Phase 2 ({len(selected)}): {selected}")
    return selected


def load_all_data(factors: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """加载因子数据和行情数据"""
    logger.info("Loading factor data...")
    cols = ', '.join(factors)
    rows = DatabaseManager.fetchall('interface', f'''
        SELECT trade_date, ts_code, {cols}
        FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    factor_df = pd.DataFrame(rows)
    factor_df['trade_date'] = pd.to_datetime(factor_df['trade_date'].astype(str))
    for f in factors:
        factor_df[f] = pd.to_numeric(factor_df[f], errors='coerce')
    logger.info(f"Factor data: {len(factor_df)} rows")

    logger.info("Loading market data...")
    rows2 = DatabaseManager.fetchall('tushare_biz', f'''
        SELECT trade_date, ts_code, pct_chg, close
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    market_df = pd.DataFrame(rows2)
    market_df['trade_date'] = pd.to_datetime(market_df['trade_date'].astype(str))
    market_df['pct_chg'] = pd.to_numeric(market_df['pct_chg'], errors='coerce').fillna(0)
    market_df['close']   = pd.to_numeric(market_df['close'],   errors='coerce')
    logger.info(f"Market data: {len(market_df)} rows")

    return factor_df, market_df


def compute_forward_returns(market_df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """计算未来N日收益率"""
    df = market_df.sort_values(['ts_code', 'trade_date'])
    def _fwd(g):
        g = g.sort_values('trade_date').copy()
        g['fwd'] = g['pct_chg'].shift(-1).rolling(horizon).sum().shift(-(horizon - 1)) / 100
        return g
    result = df.groupby('ts_code', group_keys=False).apply(_fwd)
    return result[['trade_date', 'ts_code', 'fwd']].dropna()


def cross_sectional_rank_normalize(df: pd.DataFrame, factors: List[str]) -> pd.DataFrame:
    """截面排名标准化（每日）"""
    def _rank_norm(group):
        for f in factors:
            if f in group.columns:
                series = group[f]
                valid = series.notna()
                if valid.sum() > 1:
                    group[f] = (series.rank(pct=True) - 0.5) * 2  # [-1, 1]
        return group
    return df.groupby('trade_date', group_keys=False).apply(_rank_norm)


def walk_forward_predict(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                         factors: List[str]) -> pd.DataFrame:
    """
    Walk-forward XGBoost预测
    Returns: DataFrame[trade_date, ts_code, score]
    """
    all_dates = sorted(factor_df['trade_date'].unique())
    predictions = []

    # 滚动窗口
    i = 0
    while i < len(all_dates):
        current_date = all_dates[i]

        # 训练集: current_date 之前 TRAIN_LOOKBACK_DAYS 天
        train_end = current_date - pd.Timedelta(days=1)
        train_start = current_date - pd.Timedelta(days=TRAIN_LOOKBACK_DAYS)
        train_dates = [d for d in all_dates if train_start <= d <= train_end]

        if len(train_dates) < 60:
            i += 1
            continue

        # 预测集: 从 current_date 开始的 PREDICT_PERIOD_DAYS 天
        predict_end = current_date + pd.Timedelta(days=PREDICT_PERIOD_DAYS * 2)
        predict_dates = [d for d in all_dates if current_date <= d <=
                         min(predict_end, all_dates[-1])][:PREDICT_PERIOD_DAYS]

        if not predict_dates:
            break

        # 构建训练数据
        train_factor = factor_df[factor_df['trade_date'].isin(train_dates)][
            ['trade_date', 'ts_code'] + factors]
        train_fwd = fwd_returns[fwd_returns['trade_date'].isin(train_dates)]
        train_data = train_factor.merge(train_fwd, on=['trade_date', 'ts_code'])
        train_data = train_data.dropna(subset=factors + ['fwd'])

        if len(train_data) < 500:
            i += PREDICT_PERIOD_DAYS
            continue

        X_train = train_data[factors].values
        y_train = train_data['fwd'].values

        # 标签: 未来5日收益排名 -> 截面标准化
        y_rank = pd.Series(y_train).rank(pct=True).values

        # XGBoost
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X_train)

        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            n_jobs=2,
            verbosity=0,
        )
        model.fit(X_scaled, y_rank)

        # 预测
        for pred_date in predict_dates:
            pred_factor = factor_df[factor_df['trade_date'] == pred_date][
                ['ts_code'] + factors].dropna(subset=factors)
            if len(pred_factor) < TOP_N:
                continue

            X_pred = scaler.transform(pred_factor[factors].values)
            scores = model.predict(X_pred)
            pred_factor = pred_factor.copy()
            pred_factor['score'] = scores
            pred_factor['trade_date'] = pred_date
            predictions.append(pred_factor[['trade_date', 'ts_code', 'score']])

        logger.info(f"  Walk-forward: trained up to {train_end.date()}, "
                    f"predicting {predict_dates[0].date()} ~ {predict_dates[-1].date()}")
        i += len(predict_dates)

    if not predictions:
        return pd.DataFrame(columns=['trade_date', 'ts_code', 'score'])

    return pd.concat(predictions, ignore_index=True)


def run_backtest(predictions: pd.DataFrame, market_df: pd.DataFrame,
                 regime_detector: EnhancedRegimeDetector,
                 index_data: Optional[pd.DataFrame] = None) -> Dict:
    """
    基于预测分数进行回测（每 REBALANCE_FREQ 天调仓 TOP_N 股票）
    """
    all_dates = sorted(market_df['trade_date'].unique())
    rebalance_dates = set(all_dates[i] for i in range(0, len(all_dates), REBALANCE_FREQ))

    nav = [1.0]
    nav_dates = [all_dates[0]]
    current_holdings = {}  # ts_code -> weight
    current_regime = EnhancedMarketRegime.OSCILLATING

    # CSI300 benchmark NAV
    bench_nav = [1.0]
    bench_prev_close = None

    ret_map_cache = {}
    for _, row in market_df.iterrows():
        d = row['trade_date']
        if d not in ret_map_cache:
            ret_map_cache[d] = {}
        ret_map_cache[d][row['ts_code']] = row['pct_chg'] / 100

    # Index return (if available)
    index_ret = {}
    if index_data is not None and not index_data.empty:
        for _, row in index_data.iterrows():
            index_ret[row['trade_date']] = float(row.get('pct_chg', 0)) / 100

    for i, date in enumerate(all_dates[1:], 1):
        prev_date = all_dates[i - 1]

        # Regime detection
        if prev_date in rebalance_dates:
            try:
                regime, confidence = regime_detector.detect_regime(prev_date)
                current_regime = regime
            except Exception:
                pass

            # Portfolio construction
            pred_on_date = predictions[predictions['trade_date'] == prev_date]
            if len(pred_on_date) >= TOP_N:
                top = pred_on_date.nlargest(TOP_N, 'score')['ts_code'].tolist()
                w = 1.0 / TOP_N
                current_holdings = {s: w for s in top}

        # Position multiplier from regime
        pos_mult = REGIME_POSITION.get(current_regime, 0.7)

        # Portfolio return
        day_ret_map = ret_map_cache.get(date, {})
        if current_holdings:
            port_ret = sum(w * day_ret_map.get(s, 0) for s, w in current_holdings.items())
            if prev_date in rebalance_dates:
                port_ret -= TRANSACTION_COST
            adj_ret = port_ret * pos_mult
        else:
            adj_ret = 0.0

        nav.append(nav[-1] * (1 + adj_ret))
        nav_dates.append(date)

        # Benchmark
        bench_r = index_ret.get(date, 0)
        bench_nav.append(bench_nav[-1] * (1 + bench_r))

    nav_df = pd.DataFrame({
        'date': nav_dates,
        'strategy': nav,
        'benchmark': bench_nav,
    })

    # Compute metrics
    daily_rets = pd.Series(nav).pct_change().dropna()
    bench_rets  = pd.Series(bench_nav).pct_change().dropna()
    n_days = len(daily_rets)
    ann = 252

    def _sharpe(r):
        if r.std() < 1e-10:
            return 0.0
        return r.mean() / r.std() * np.sqrt(ann)

    def _max_dd(nav_s):
        roll_max = pd.Series(nav_s).cummax()
        dd = (pd.Series(nav_s) - roll_max) / roll_max
        return float(dd.min())

    def _annual_ret(nav_s):
        total = nav_s[-1] / nav_s[0]
        return float(total ** (ann / n_days) - 1)

    strategy_annual = _annual_ret(nav)
    benchmark_annual = _annual_ret(bench_nav)
    excess_daily = daily_rets.values - bench_rets.values[:len(daily_rets)]
    ir = (excess_daily.mean() / (excess_daily.std() + 1e-10)) * np.sqrt(ann)

    metrics = {
        'start_date': str(nav_dates[0].date()),
        'end_date': str(nav_dates[-1].date()),
        'strategy_annual_return': round(strategy_annual, 4),
        'benchmark_annual_return': round(benchmark_annual, 4),
        'excess_annual_return': round(strategy_annual - benchmark_annual, 4),
        'strategy_sharpe': round(_sharpe(daily_rets), 4),
        'max_drawdown': round(_max_dd(nav), 4),
        'information_ratio': round(float(ir), 4),
        'total_return': round(float(nav[-1] - 1), 4),
        'benchmark_total_return': round(float(bench_nav[-1] - 1), 4),
    }

    return {'nav_df': nav_df, 'metrics': metrics}


def load_index_data() -> pd.DataFrame:
    """加载CSI300基准指数"""
    try:
        rows = DatabaseManager.fetchall('tushare_biz', f'''
            SELECT trade_date, pct_chg
            FROM t_index_daily
            WHERE ts_code = '000300.SH'
              AND trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
            ORDER BY trade_date
        ''')
        df = pd.DataFrame(rows)
        df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        logger.warning(f"Failed to load index data: {e}")
        return pd.DataFrame()


def plot_nav(nav_df: pd.DataFrame, metrics: Dict):
    """绘制净值曲线"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    ax1.plot(nav_df['date'], nav_df['strategy'],  'b-', linewidth=1.5, label='Strategy')
    ax1.plot(nav_df['date'], nav_df['benchmark'], 'r--', linewidth=1.2, label='CSI300')
    ax1.set_title(
        f"Multi-Factor XGBoost Strategy\n"
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

    # Drawdown
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
    logger.info("=== Phase 4: 多因子 XGBoost 策略 (strategy-researcher-001) ===")

    # Load factors
    factors = load_selected_factors()
    if not factors:
        logger.error("No factors from Phase 2. Run factor_icir_analysis.py first.")
        return

    # Load data
    factor_df, market_df = load_all_data(factors)

    # Normalize factors cross-sectionally
    logger.info("Cross-sectional normalization...")
    factor_df = cross_sectional_rank_normalize(factor_df, factors)

    # Compute forward returns
    logger.info("Computing forward returns...")
    fwd_returns = compute_forward_returns(market_df, FORWARD_HORIZON)
    logger.info(f"Forward returns: {len(fwd_returns)} rows")

    # Walk-forward predictions
    logger.info("Running walk-forward XGBoost...")
    predictions = walk_forward_predict(factor_df, fwd_returns, factors)
    logger.info(f"Predictions: {len(predictions)} rows, "
                f"{predictions['trade_date'].nunique() if not predictions.empty else 0} dates")

    if predictions.empty:
        logger.error("No predictions generated.")
        return

    # Load index
    index_data = load_index_data()

    # Initialize regime detector
    regime_detector = EnhancedRegimeDetector()

    # Run backtest
    logger.info("Running backtest...")
    result = run_backtest(predictions, market_df, regime_detector, index_data)

    nav_df  = result['nav_df']
    metrics = result['metrics']

    # Save outputs
    nav_df.to_csv('output/backtest_nav.csv', index=False)
    with open('output/backtest_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    plot_nav(nav_df, metrics)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"STRATEGY PERFORMANCE SUMMARY")
    logger.info(f"{'='*60}")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v}")

    # Phase 4 exit condition check
    sharpe = metrics['strategy_sharpe']
    max_dd = abs(metrics['max_drawdown'])
    if sharpe >= 1.0 and max_dd <= 0.20:
        logger.info(f"\n✅ Phase 4 PASS: Sharpe={sharpe:.2f} >= 1.0, MaxDD={max_dd*100:.1f}% <= 20%")
    else:
        warn_parts = []
        if sharpe < 1.0:
            warn_parts.append(f"Sharpe={sharpe:.2f} < 1.0")
        if max_dd > 0.20:
            warn_parts.append(f"MaxDD={max_dd*100:.1f}% > 20%")
        logger.warning(f"\n⚠️  Phase 4 NOT PASS: {'; '.join(warn_parts)}")

    return metrics


if __name__ == '__main__':
    main()
