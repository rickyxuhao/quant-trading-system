"""
Phase 4 v4: strategy-researcher-001 熵驱动多因子策略（优化版）
=============================================================
v3→v4 修复与增强:
  [P0] 修复 regime detection 调用错误（单次 detect_regime → detect_regime_series 预计算）
  [P1] 新增 ma_ratio_5_20 因子（内存计算，MA5/MA20-1，反转信号）
  [P1] 流动性过滤（剔除成交额后20%股票）
  [P1] 方向感知排名（反转因子用 ascending=False）
  [P2] 分数加权持仓（softmax 代替等权）

因子权重（v4）:
  entropy_20d:    0.55  方向+1  高熵→分散→买入
  net_inflow_20d: 0.20  方向+1  正流入→买入
  bb_width:       0.15  方向+1  宽带→波动分化→买入
  ma_ratio_5_20:  0.10  方向-1  反转：MA5<MA20（跌深）→买入

输出:
  - output/backtest_nav.csv
  - output/backtest_metrics.json
  - output/multifactor/strategy_nav.png
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

START_DATE = '20250102'
END_DATE   = '20260320'
TOP_N = 30
REBALANCE_FREQ = 5
TRANSACTION_COST = 0.001
LIQUIDITY_PERCENTILE = 0.20   # 剔除成交额后 20% 的低流动性股票
SOFTMAX_TEMP = 5.0             # softmax 温度系数（越高越集中）

REGIME_POSITION = {
    EnhancedMarketRegime.BULL: 1.00,
    EnhancedMarketRegime.OSCILLATING: 0.70,
    EnhancedMarketRegime.BEAR: 0.40,
}

# 因子权重（sum=1.0）
FACTOR_WEIGHTS = {
    'entropy_20d':    0.55,
    'net_inflow_20d': 0.20,
    'bb_width':       0.15,
    'ma_ratio_5_20':  0.10,
}
# +1=值越高越好（高排名得高分），-1=值越低越好（低排名得高分，反转）
FACTOR_DIRECTIONS = {
    'entropy_20d':    +1,
    'net_inflow_20d': +1,
    'bb_width':       +1,
    'ma_ratio_5_20':  -1,
}

OUTPUT_DIR = 'output/multifactor'
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────

def load_factor_data() -> pd.DataFrame:
    """从 t_precomputed_factors 加载数据库存储的因子（不含 ma_ratio_5_20）。"""
    db_factors = [f for f in FACTOR_WEIGHTS if f != 'ma_ratio_5_20']
    cols = ', '.join(db_factors)
    rows = DatabaseManager.fetchall('interface', f'''
        SELECT trade_date, ts_code, {cols}
        FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    for f in db_factors:
        df[f] = pd.to_numeric(df[f], errors='coerce')
    logger.info(f"Factor data: {len(df)} rows, {df['trade_date'].nunique()} dates")
    return df


def load_market_data() -> pd.DataFrame:
    """加载行情数据，包含 close 和 amount，用于 MA 因子与流动性过滤。"""
    rows = DatabaseManager.fetchall('tushare_biz', f'''
        SELECT trade_date, ts_code, pct_chg, close, amount
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{START_DATE}' AND trade_date <= '{END_DATE}'
        ORDER BY trade_date, ts_code
    ''')
    df = pd.DataFrame(rows)
    df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['close']   = pd.to_numeric(df['close'],   errors='coerce')
    df['amount']  = pd.to_numeric(df['amount'],  errors='coerce')
    logger.info(f"Market data: {len(df)} rows")
    return df


def load_index_data() -> pd.DataFrame:
    """
    加载沪深300，包含 close（用于 MA 多头排列检测）。
    预取 90 日热身数据以保证 MA60 有效。
    """
    warmup = (pd.Timestamp(START_DATE) - pd.Timedelta(days=90)).strftime('%Y%m%d')
    try:
        rows = DatabaseManager.fetchall('tushare_biz', f'''
            SELECT trade_date, close, pct_chg FROM t_index_daily
            WHERE ts_code = '000300.SH'
              AND trade_date >= '{warmup}' AND trade_date <= '{END_DATE}'
            ORDER BY trade_date
        ''')
        df = pd.DataFrame(rows)
        df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
        df['close']   = pd.to_numeric(df['close'],   errors='coerce')
        logger.info(f"Index data: {len(df)} rows")
        return df
    except Exception as e:
        logger.warning(f"Failed to load index data: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# P0: 市场环境预计算（修复）
# ─────────────────────────────────────────────

def precompute_regimes(index_df: pd.DataFrame) -> Dict[str, EnhancedMarketRegime]:
    """
    [P0 修复] 使用 detect_regime_series() 批量预计算所有交易日的市场环境。
    返回: {date_isoformat: EnhancedMarketRegime}

    原错误: detect_regime(prev_date)  ← 需要3个参数，导致 TypeError 被静默吞掉，
            market regime 永远为 OSCILLATING，牛/熊择时仓位从未生效。
    """
    if index_df.empty:
        logger.warning("No index data; all dates will default to OSCILLATING")
        return {}

    detector = EnhancedRegimeDetector(use_ma_cross=True)
    regime_df = detector.detect_regime_series(index_df)

    regime_map: Dict[str, EnhancedMarketRegime] = {}
    for _, row in regime_df.iterrows():
        date_key = pd.Timestamp(row['trade_date']).date().isoformat()
        try:
            regime_map[date_key] = EnhancedMarketRegime(row['regime'])
        except ValueError:
            regime_map[date_key] = EnhancedMarketRegime.OSCILLATING

    # 统计分布（仅回测区间）
    start_ts = pd.Timestamp(START_DATE).date().isoformat()
    in_window = {k: v for k, v in regime_map.items() if k >= start_ts}
    counts: Dict[str, int] = {}
    for r in in_window.values():
        counts[r.value] = counts.get(r.value, 0) + 1
    total = len(in_window) or 1
    dist_str = ', '.join(f"{k}={v/total*100:.1f}%" for k, v in sorted(counts.items()))
    logger.info(f"Regime distribution ({START_DATE}~{END_DATE}): {dist_str}")

    return regime_map


# ─────────────────────────────────────────────
# P1: ma_ratio_5_20 因子（内存计算）
# ─────────────────────────────────────────────

def compute_ma_factor(market_df: pd.DataFrame) -> pd.DataFrame:
    """
    [P1] 计算 ma_ratio_5_20 = MA5/MA20 - 1。
    使用当日收盘价的滚动均线，需要至少 20 日历史。
    方向 = -1（反转）：MA5/MA20 越低，股票越可能处于超卖状态，买入信号越强。
    """
    logger.info("Computing ma_ratio_5_20 factor in-memory...")
    df = market_df[['trade_date', 'ts_code', 'close']].dropna(subset=['close']).copy()
    df = df.sort_values(['ts_code', 'trade_date'])

    def _compute(grp: pd.DataFrame) -> pd.DataFrame:
        grp = grp.sort_values('trade_date').copy()
        ma5  = grp['close'].rolling(5,  min_periods=5).mean()
        ma20 = grp['close'].rolling(20, min_periods=20).mean()
        grp['ma_ratio_5_20'] = np.where(ma20 > 0, ma5 / ma20 - 1, np.nan)
        return grp[['trade_date', 'ts_code', 'ma_ratio_5_20']]

    result = df.groupby('ts_code', group_keys=False).apply(_compute)
    result = result.dropna(subset=['ma_ratio_5_20'])
    result = result[result['trade_date'] >= pd.Timestamp(START_DATE)]
    logger.info(f"ma_ratio_5_20: {len(result)} rows, {result['trade_date'].nunique()} dates")
    return result.reset_index(drop=True)


# ─────────────────────────────────────────────
# P1: 流动性过滤
# ─────────────────────────────────────────────

def build_liquidity_filter(market_df: pd.DataFrame) -> Dict[pd.Timestamp, Optional[set]]:
    """
    [P1] 构建每日流动性白名单：剔除 20 日均成交额后 LIQUIDITY_PERCENTILE（20%）的股票。
    返回: {trade_date: set(ts_code) | None}
         None 表示该日数据不足，不过滤。
    """
    logger.info("Building liquidity filter (bottom 20% by 20d avg amount)...")
    df = market_df[['trade_date', 'ts_code', 'amount']].copy()
    df = df.sort_values(['ts_code', 'trade_date'])
    df['amount_20d'] = df.groupby('ts_code')['amount'].transform(
        lambda x: x.rolling(20, min_periods=5).mean()
    )

    liq_filter: Dict[pd.Timestamp, Optional[set]] = {}
    for date, grp in df.groupby('trade_date'):
        valid = grp.dropna(subset=['amount_20d'])
        if len(valid) < 50:
            liq_filter[date] = None
            continue
        threshold = valid['amount_20d'].quantile(LIQUIDITY_PERCENTILE)
        liq_filter[date] = set(valid[valid['amount_20d'] >= threshold]['ts_code'])

    logger.info(f"Liquidity filter built for {len(liq_filter)} dates")
    return liq_filter


# ─────────────────────────────────────────────
# 合成分数构建
# ─────────────────────────────────────────────

def build_composite_score(factor_df: pd.DataFrame,
                           ma_factor_df: pd.DataFrame) -> pd.DataFrame:
    """
    截面合成分数：每日对各因子进行方向感知排名 → 加权合成。
    - 正向因子（direction=+1）：ascending=True，高值得高分
    - 反转因子（direction=-1）：ascending=False，低值得高分
    """
    # 合并 ma_ratio_5_20
    if not ma_factor_df.empty:
        factor_df = factor_df.merge(
            ma_factor_df[['trade_date', 'ts_code', 'ma_ratio_5_20']],
            on=['trade_date', 'ts_code'],
            how='left'
        )
    else:
        factor_df = factor_df.copy()
        factor_df['ma_ratio_5_20'] = np.nan

    result_rows = []
    for date, grp in factor_df.groupby('trade_date'):
        grp = grp.copy()
        score = np.zeros(len(grp))
        for f, w in FACTOR_WEIGHTS.items():
            if f not in grp.columns:
                continue
            series = grp[f]
            if series.notna().sum() < 10:
                continue
            direction = FACTOR_DIRECTIONS.get(f, +1)
            # ascending=True  → 高值=高百分位=高分（正向因子）
            # ascending=False → 低值=高百分位=高分（反转因子）
            ascending = (direction != -1)
            ranks = series.rank(pct=True, ascending=ascending, na_option='keep')
            ranks = ranks.fillna(0.5)
            score += w * ranks.values
        grp['score'] = score
        result_rows.append(grp[['trade_date', 'ts_code', 'score']])

    if not result_rows:
        return pd.DataFrame(columns=['trade_date', 'ts_code', 'score'])
    return pd.concat(result_rows, ignore_index=True)


# ─────────────────────────────────────────────
# P2: softmax 工具函数
# ─────────────────────────────────────────────

def _softmax(x: np.ndarray, temp: float = SOFTMAX_TEMP) -> np.ndarray:
    """数值稳定的 softmax（带温度系数）。"""
    e = np.exp((x - x.max()) * temp)
    return e / e.sum()


# ─────────────────────────────────────────────
# 回测引擎
# ─────────────────────────────────────────────

def run_backtest(scores_df: pd.DataFrame,
                 market_df: pd.DataFrame,
                 regime_map: Dict[str, EnhancedMarketRegime],
                 liq_filter: Dict,
                 index_df: pd.DataFrame) -> Dict:
    all_dates = sorted(market_df['trade_date'].unique())
    rebalance_dates = set(all_dates[i] for i in range(0, len(all_dates), REBALANCE_FREQ))

    # 收益率查找表
    ret_map: Dict = {}
    for _, row in market_df.iterrows():
        ret_map.setdefault(row['trade_date'], {})[row['ts_code']] = row['pct_chg'] / 100

    # 指数收益查找表
    idx_map: Dict = {}
    if not index_df.empty:
        for _, row in index_df.iterrows():
            idx_map[row['trade_date']] = float(row['pct_chg']) / 100

    nav       = [1.0]
    bench_nav = [1.0]
    nav_dates = [all_dates[0]]
    current_holdings: Dict[str, float] = {}
    current_regime = EnhancedMarketRegime.OSCILLATING

    for i, date in enumerate(all_dates[1:], 1):
        prev_date = all_dates[i - 1]

        if prev_date in rebalance_dates:
            # ── P0 修复：直接查 regime_map，无需调用 detect_regime() ──
            date_key = prev_date.date().isoformat()
            current_regime = regime_map.get(date_key, EnhancedMarketRegime.OSCILLATING)

            # 候选池：按分数筛选
            scores_on_date = scores_df[scores_df['trade_date'] == prev_date]

            # ── P1：流动性过滤 ──
            liq_set = liq_filter.get(prev_date)
            if liq_set is not None:
                scores_on_date = scores_on_date[scores_on_date['ts_code'].isin(liq_set)]

            if len(scores_on_date) >= TOP_N:
                top = scores_on_date.nlargest(TOP_N, 'score')
                # ── P2：softmax 分数加权 ──
                raw = top['score'].values.astype(float)
                weights = _softmax(raw)
                current_holdings = dict(zip(top['ts_code'], weights))

        # 仓位系数（由市场环境决定）
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

    # 绩效指标
    daily_rets = pd.Series(nav).pct_change().dropna()
    bench_rets = pd.Series(bench_nav).pct_change().dropna()
    ann = 252
    n = len(daily_rets)

    def _ann_ret(nav_s: list) -> float:
        return float((nav_s[-1] / nav_s[0]) ** (ann / n) - 1)

    def _sharpe(r: pd.Series) -> float:
        return float(r.mean() / r.std() * np.sqrt(ann)) if r.std() > 1e-10 else 0.0

    def _max_dd(nav_s: list) -> float:
        s = pd.Series(nav_s)
        return float((s / s.cummax() - 1).min())

    strat_ann = _ann_ret(nav)
    bench_ann = _ann_ret(bench_nav)
    excess = daily_rets.values - bench_rets.values[:len(daily_rets)]
    ir = float(excess.mean() / (excess.std() + 1e-10) * np.sqrt(ann))

    metrics = {
        'start_date':              str(nav_dates[0].date()),
        'end_date':                str(nav_dates[-1].date()),
        'strategy_annual_return':  round(strat_ann, 4),
        'benchmark_annual_return': round(bench_ann, 4),
        'excess_annual_return':    round(strat_ann - bench_ann, 4),
        'strategy_sharpe':         round(_sharpe(daily_rets), 4),
        'max_drawdown':            round(_max_dd(nav), 4),
        'information_ratio':       round(ir, 4),
        'total_return':            round(float(nav[-1] - 1), 4),
        'benchmark_total_return':  round(float(bench_nav[-1] - 1), 4),
        'version':                 'v4',
    }
    return {'nav_df': nav_df, 'metrics': metrics}


# ─────────────────────────────────────────────
# 绘图
# ─────────────────────────────────────────────

def plot_nav(nav_df: pd.DataFrame, metrics: Dict):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    ax1.plot(nav_df['date'], nav_df['strategy'], 'b-', linewidth=1.5,
             label='Strategy (Entropy v4)')
    ax1.plot(nav_df['date'], nav_df['benchmark'], 'r--', linewidth=1.2,
             label='CSI300')
    ax1.set_title(
        f"Entropy-Driven Strategy v4  [P0:Regime ✓  P1:LiqFilter+MAFactor ✓  P2:SoftmaxW ✓]\n"
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


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main():
    logger.info("=== Phase 4 v4: Entropy-Driven Strategy (strategy-researcher-001) ===")
    logger.info("Enhancements: [P0] Regime fix  [P1] ma_ratio_5_20 + LiqFilter  [P2] Softmax weights")

    logger.info("Loading data...")
    factor_df = load_factor_data()
    market_df = load_market_data()
    index_df  = load_index_data()

    # [P0] 预计算市场环境（修复核心 bug）
    logger.info("Precomputing market regimes via detect_regime_series()...")
    regime_map = precompute_regimes(index_df)

    # [P1] 内存计算 ma_ratio_5_20
    logger.info("Computing ma_ratio_5_20 factor in-memory...")
    ma_factor_df = compute_ma_factor(market_df)

    # [P1] 构建流动性白名单
    logger.info("Building liquidity filter...")
    liq_filter = build_liquidity_filter(market_df)

    logger.info("Building composite score (direction-aware ranking)...")
    scores_df = build_composite_score(factor_df, ma_factor_df)
    logger.info(f"Scores: {len(scores_df)} rows, {scores_df['trade_date'].nunique()} dates")

    logger.info("Running backtest...")
    result = run_backtest(scores_df, market_df, regime_map, liq_filter, index_df)

    nav_df  = result['nav_df']
    metrics = result['metrics']

    # 保存输出
    nav_df.to_csv('output/backtest_nav.csv', index=False)
    with open('output/backtest_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info("Outputs saved to output/backtest_nav.csv + output/backtest_metrics.json")

    plot_nav(nav_df, metrics)

    # 汇总输出
    logger.info(f"\n{'='*60}")
    logger.info("STRATEGY PERFORMANCE SUMMARY (Entropy v4)")
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
