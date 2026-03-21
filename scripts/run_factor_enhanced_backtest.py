"""
增强因子策略对比回测
===================
将6个新有效因子加入策略，与原策略对比：
  新增因子: bb_rsi_reversal, revenue_acceleration, momentum_diff,
            rd_ratio, rsi_reversal, price_vol_divergence

回测区间: 2024-01-01 → 2026-03-20
对比指标: 年化收益、Sharpe、最大回撤、IR

运行方式:
    python3 scripts/run_factor_enhanced_backtest.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.regime_aware_strategy import (
    RegimeAwareStrategy, RegimeAwareConfig, FACTOR_GROUPS, ALL_FACTORS
)
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedMarketRegime, REGIME_FACTOR_WEIGHTS
)

logger = get_logger(__name__)

START_DATE = '20240101'
END_DATE = '20260320'

# ============================================================
# 新增因子（已通过ICIR > 0.3筛选）
# ============================================================
NEW_FACTORS = [
    'bb_rsi_reversal',      # ICIR=1.356 布林带+RSI反转
    'revenue_acceleration', # ICIR=1.186 营收加速度
    'momentum_diff',        # ICIR=-1.122 长短期动量差（负向）
    'rd_ratio',             # ICIR=-0.611 研发占比（负向）
    'rsi_reversal',         # ICIR=0.493 RSI反转
    'price_vol_divergence', # ICIR=-0.401 价量背离（负向）
]

# 负向因子（对模型标签取负，等效于特征乘-1）
NEGATIVE_FACTORS = {'momentum_diff', 'rd_ratio', 'price_vol_divergence'}

# ============================================================
# 新因子计算函数（与compute_and_test_new_factors.py保持一致）
# ============================================================

def add_derived_factors(df: pd.DataFrame) -> pd.DataFrame:
    """添加技术反转类派生因子"""
    df = df.copy()
    if 'return_60d' in df.columns and 'return_5d' in df.columns:
        raw = df['return_60d'] - df['return_5d']
        df['momentum_diff'] = -raw  # 负向因子，取反后正向使用
    if 'rsi_14d' in df.columns:
        df['rsi_reversal'] = 100 - df['rsi_14d']
    if 'price_position_20d' in df.columns and 'volume_ratio' in df.columns:
        vol_norm = (df['volume_ratio'] - 1).clip(-1, 1)
        raw = df['price_position_20d'] - (vol_norm + 1) / 2
        df['price_vol_divergence'] = -raw  # 负向因子取反
    if 'bb_position' in df.columns and 'rsi_6d' in df.columns:
        df['bb_rsi_reversal'] = (1 - df['bb_position']) * (100 - df['rsi_6d']) / 100
    return df


def load_financial_factors_pit(start_date: str, end_date: str,
                                trade_dates_df: pd.DataFrame) -> pd.DataFrame:
    """加载财务因子并做PIT合并"""
    # 加载财务指标
    fin_sql = f"""
    SELECT ts_code, ann_date, end_date, q_sales_yoy
    FROM t_stock_fina_indicator
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
    ORDER BY ts_code, ann_date
    """
    # 加载现金流
    cf_sql = f"""
    SELECT ts_code, ann_date, end_date, n_cashflow_act
    FROM t_stock_cashflow
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """
    # 加载净利润+研发
    income_sql = f"""
    SELECT ts_code, ann_date, end_date, n_income_attr_p
    FROM t_stock_income
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """
    bs_sql = f"""
    SELECT ts_code, ann_date, end_date, total_assets, r_and_d
    FROM t_stock_balancesheet
    WHERE ann_date <= '{end_date}'
      AND ann_date >= '20220101'
      AND comp_type = '1'
    ORDER BY ts_code, ann_date
    """

    fin_df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', fin_sql))
    cf_df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', cf_sql))
    income_df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', income_sql))
    bs_df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', bs_sql))

    if fin_df.empty:
        logger.warning("Financial data empty")
        return pd.DataFrame()

    # 转换日期和数值
    for df, cols in [
        (fin_df, ['q_sales_yoy']),
        (cf_df, ['n_cashflow_act']),
        (income_df, ['n_income_attr_p']),
        (bs_df, ['total_assets', 'r_and_d']),
    ]:
        df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str))
        df['end_date'] = pd.to_datetime(df['end_date'].astype(str))
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    bs_df['r_and_d'] = bs_df['r_and_d'].fillna(0)

    # 计算营收加速度
    logger.info("Computing revenue_acceleration...")
    fin_df = fin_df.sort_values(['ts_code', 'end_date'])
    fin_df['q_sales_yoy_prev'] = fin_df.groupby('ts_code')['q_sales_yoy'].shift(1)
    fin_df['revenue_acceleration'] = fin_df['q_sales_yoy'] - fin_df['q_sales_yoy_prev']

    # 计算应计利润和研发比率
    logger.info("Computing accrual_ratio and rd_ratio...")
    merged_fin = income_df.merge(
        cf_df[['ts_code', 'end_date', 'n_cashflow_act']],
        on=['ts_code', 'end_date'], how='inner'
    ).merge(
        bs_df[['ts_code', 'end_date', 'total_assets', 'r_and_d']],
        on=['ts_code', 'end_date'], how='inner'
    )
    merged_fin['accrual_ratio'] = -(merged_fin['n_income_attr_p'] - merged_fin['n_cashflow_act']) / (
        merged_fin['total_assets'].abs() + 1e-10)
    merged_fin['rd_ratio'] = -merged_fin['r_and_d'] / (merged_fin['total_assets'].abs() + 1e-10)

    # 把accrual_ratio/rd_ratio合并到fin_df
    fin_df = fin_df.merge(
        merged_fin[['ts_code', 'end_date', 'accrual_ratio', 'rd_ratio']],
        on=['ts_code', 'end_date'], how='left'
    )

    # PIT合并到交易日
    logger.info("PIT merging financial factors to trade dates...")
    fin_cols = ['revenue_acceleration', 'accrual_ratio', 'rd_ratio']
    fin_cols_available = [c for c in fin_cols if c in fin_df.columns]

    result_parts = []
    for ts_code, fin_group in fin_df.groupby('ts_code'):
        stock_dates = trade_dates_df[trade_dates_df['ts_code'] == ts_code][['trade_date']].copy()
        if stock_dates.empty:
            continue
        fin_sorted = fin_group[['ann_date'] + fin_cols_available].sort_values('ann_date')
        stock_dates_sorted = stock_dates.sort_values('trade_date')
        merged = pd.merge_asof(
            stock_dates_sorted,
            fin_sorted,
            left_on='trade_date',
            right_on='ann_date',
            direction='backward'
        )
        merged['ts_code'] = ts_code
        result_parts.append(merged[['trade_date', 'ts_code'] + fin_cols_available])

    if not result_parts:
        return pd.DataFrame()

    result = pd.concat(result_parts, ignore_index=True)
    logger.info(f"Financial PIT factors: {len(result)} rows")
    return result


# ============================================================
# 增强版策略（继承RegimeAwareStrategy）
# ============================================================

class EnhancedFactorStrategy(RegimeAwareStrategy):
    """在原策略基础上增加6个新因子"""

    def __init__(self, config=None):
        super().__init__(config)
        self._financial_factors_cache = None

    def get_factor_cols(self) -> List[str]:
        """返回包含新因子的完整因子列表"""
        cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
        existing_cols = {c['Field'] for c in cols_info}
        base_cols = [f for f in ALL_FACTORS if f in existing_cols]
        # 添加新因子（通过load_factor_data在内存中计算）
        return base_cols + [f for f in NEW_FACTORS if f not in base_cols]

    def run_backtest_preparation(self, start_date: str, end_date: str) -> Dict:
        """重写：使用扩展的factor_cols"""
        logger.info(f"Loading data {start_date} -> {end_date}")

        factor_cols = self.get_factor_cols()
        logger.info(f"Enhanced factors: {len(factor_cols)} total ({len(NEW_FACTORS)} new)")

        train_start = (pd.Timestamp(start_date) - pd.Timedelta(
            days=self.config.train_lookback + 30)).strftime('%Y%m%d')

        factor_df = self.load_factor_data(train_start, end_date)
        logger.info(f"Factor data: {len(factor_df)} rows")

        returns_df = self.load_forward_returns(train_start, end_date, self.config.prediction_horizon)
        logger.info(f"Returns data: {len(returns_df)} rows")

        industry_df = self.load_industry_data()
        logger.info(f"Industry data: {len(industry_df)} stocks")

        regime_df = self.load_regime_data(start_date, end_date)
        logger.info(f"Regime data: {len(regime_df)} days")

        # 只保留实际有数据的因子列
        factor_cols = [f for f in factor_cols if f in factor_df.columns]
        logger.info(f"Available factors: {len(factor_cols)}")
        logger.info(f"New factors in dataset: {[f for f in NEW_FACTORS if f in factor_cols]}")

        backtest_dates = sorted(factor_df[
            (factor_df['trade_date'] >= start_date) &
            (factor_df['trade_date'] <= end_date)
        ]['trade_date'].unique())
        logger.info(f"Backtest dates: {len(backtest_dates)}")

        all_signals = []
        current_model = None
        last_regime = EnhancedMarketRegime.OSCILLATING

        for i, date in enumerate(backtest_dates):
            if not regime_df.empty:
                date_regime_row = regime_df[regime_df['trade_date'].astype(str) == date]
                if not date_regime_row.empty:
                    last_regime = EnhancedMarketRegime(date_regime_row.iloc[0]['regime'])
            regime = last_regime

            need_retrain = (
                current_model is None or
                self._last_train_date is None or
                i % self.config.retrain_freq == 0
            )

            if need_retrain:
                train_factor = factor_df[factor_df['trade_date'] < date].copy()
                train_returns = returns_df[returns_df['trade_date'] < date].copy()
                if len(train_factor) >= self.config.min_train_samples:
                    current_model = self.train_model(train_factor, train_returns, regime, factor_cols)
                    self._last_train_date = date
                    if current_model:
                        logger.info(f"[{date}] Retrained model (regime={regime.value})")

            signals = self.generate_signals(date, factor_df, current_model, regime, industry_df, factor_cols)
            if not signals.empty:
                all_signals.append(signals.head(self.config.top_n))

            if i % 20 == 0:
                logger.info(f"Progress: {i+1}/{len(backtest_dates)} [{date}] "
                           f"regime={regime.value}, stocks={len(signals) if not signals.empty else 0}")

        if not all_signals:
            return {'signals': pd.DataFrame(), 'regime_stats': {}}

        signals_df = pd.concat(all_signals, ignore_index=True)

        regime_stats = {}
        if not regime_df.empty:
            stats = regime_df['regime'].value_counts()
            for r in ['bull', 'bear', 'oscillating']:
                count = stats.get(r, 0)
                regime_stats[r] = {'days': int(count), 'pct': round(count / len(regime_df) * 100, 1)}

        factor_importance = {}
        if current_model is not None and hasattr(current_model, 'feature_importances_'):
            importance = current_model.feature_importances_
            factor_importance = dict(zip(factor_cols, importance.tolist()))
            factor_importance = dict(sorted(factor_importance.items(), key=lambda x: x[1], reverse=True))

        return {
            'signals': signals_df,
            'regime_stats': regime_stats,
            'factor_importance': factor_importance,
            'factor_cols': factor_cols,
        }

    def load_factor_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """重写：加载因子并添加新因子"""
        # 先加载原有因子（确保包含新因子依赖列）
        extra_cols = ['return_5d', 'return_60d', 'rsi_14d', 'rsi_6d',
                      'price_position_20d', 'volume_ratio', 'bb_position']

        cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
        existing_cols = {c['Field'] for c in cols_info}

        all_needed = list(set(ALL_FACTORS + extra_cols))
        available = [f for f in all_needed if f in existing_cols]
        factor_cols_str = ', '.join(available)

        sql = f"""
        SELECT trade_date, ts_code, log_mv, {factor_cols_str}
        FROM t_precomputed_factors
        WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date, ts_code
        """
        df = pd.DataFrame(DatabaseManager.fetchall('interface', sql))
        if df.empty:
            return df

        df['trade_date'] = df['trade_date'].astype(str)
        for f in available:
            if f in df.columns:
                df[f] = pd.to_numeric(df[f], errors='coerce')

        # 添加派生因子
        df = add_derived_factors(df)

        # 加载财务因子（只做一次）
        if self._financial_factors_cache is None:
            trade_dates = df[['trade_date', 'ts_code']].copy()
            trade_dates['trade_date'] = pd.to_datetime(trade_dates['trade_date'])
            fin_factors = load_financial_factors_pit(start_date, end_date, trade_dates)
            if not fin_factors.empty:
                fin_factors['trade_date'] = fin_factors['trade_date'].dt.strftime('%Y%m%d')
                self._financial_factors_cache = fin_factors
            else:
                self._financial_factors_cache = pd.DataFrame()

        if not self._financial_factors_cache.empty:
            df = df.merge(self._financial_factors_cache,
                          on=['trade_date', 'ts_code'], how='left')

        logger.info(f"Enhanced factor data loaded: {len(df)} rows, "
                   f"new factors present: {[f for f in NEW_FACTORS if f in df.columns]}")
        return df

    @property
    def factor_cols_with_new(self) -> List[str]:
        """返回包含新因子的完整因子列表"""
        return ALL_FACTORS + [f for f in NEW_FACTORS if f not in ALL_FACTORS]


# ============================================================
# 回测模拟函数（复用run_enhanced_backtest.py的逻辑）
# ============================================================

def load_price_data(start_date: str, end_date: str) -> pd.DataFrame:
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


def simulate_portfolio(signals_df: pd.DataFrame, price_df: pd.DataFrame,
                       top_n: int = 30, rebalance_freq: int = 5,
                       transaction_cost: float = 0.001) -> pd.DataFrame:
    signal_dates = sorted(signals_df['trade_date'].unique())
    price_dict = price_df.set_index(['trade_date', 'ts_code'])['pct_chg'].to_dict()
    all_dates = sorted(price_df['trade_date'].unique())

    portfolio_returns = []
    current_holdings = []
    last_rebalance_idx = -1

    for i, date in enumerate(all_dates):
        if not signal_dates or date < signal_dates[0]:
            continue
        need_rebalance = (not current_holdings or i - last_rebalance_idx >= rebalance_freq)
        if need_rebalance and date in signal_dates:
            date_signals = signals_df[signals_df['trade_date'] == date].nsmallest(top_n, 'rank')
            new_holdings = date_signals['ts_code'].tolist()
            cost = (len(set(new_holdings) - set(current_holdings)) / max(len(new_holdings), 1)
                    * transaction_cost * 2) if current_holdings else 0
            current_holdings = new_holdings
            last_rebalance_idx = i
        else:
            cost = 0

        if not current_holdings:
            continue

        daily_returns = [price_dict.get((date, s), np.nan) / 100
                         for s in current_holdings
                         if not np.isnan(price_dict.get((date, s), np.nan))]

        port_ret = np.mean(daily_returns) - cost if daily_returns else 0
        portfolio_returns.append({'trade_date': date, 'portfolio_return': port_ret,
                                  'n_stocks': len(daily_returns)})

    return pd.DataFrame(portfolio_returns)


def compute_metrics(port_df: pd.DataFrame, bench_df: pd.DataFrame) -> Dict:
    port_s = port_df.set_index('trade_date')['portfolio_return']
    bench_s = (bench_df.set_index('trade_date')['pct_chg'] / 100)
    common = port_s.index.intersection(bench_s.index)
    r, b = port_s.loc[common], bench_s.loc[common]

    cum_r = (1 + r).cumprod()
    cum_b = (1 + b).cumprod()
    n_years = len(r) / 252

    ann_ret = (cum_r.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0
    ann_vol = r.std() * np.sqrt(252)
    sharpe = (r.mean() - 0.025 / 252) * 252 / (ann_vol + 1e-10)

    cum_max = cum_r.cummax()
    max_dd = ((cum_r - cum_max) / cum_max).min()

    alpha = r - b
    ir = alpha.mean() * 252 / (alpha.std() * np.sqrt(252) + 1e-10)

    return {
        'cumulative': round(float(cum_r.iloc[-1] - 1), 4),
        'ann_return': round(float(ann_ret), 4),
        'ann_vol': round(float(ann_vol), 4),
        'sharpe': round(float(sharpe), 4),
        'max_drawdown': round(float(max_dd), 4),
        'ir': round(float(ir), 4),
        'bench_cumulative': round(float(cum_b.iloc[-1] - 1), 4),
        'bench_ann_return': round(float(cum_b.iloc[-1] ** (1 / n_years) - 1), 4),
    }


# ============================================================
# 可视化
# ============================================================

def plot_comparison(old_port: pd.DataFrame, new_port: pd.DataFrame,
                    bench_df: pd.DataFrame, output_dir: str):
    """绘制新旧策略对比图"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Enhanced Factor Strategy vs Original Strategy', fontsize=14)

    bench_s = bench_df.set_index('trade_date')['pct_chg'] / 100

    for port_df, label, color in [
        (old_port, 'Original', 'blue'),
        (new_port, 'Enhanced (+6 factors)', 'green'),
    ]:
        r = port_df.set_index('trade_date')['portfolio_return']
        common = r.index.intersection(bench_s.index)
        r_aligned = r.loc[common]

        cum = (1 + r_aligned).cumprod()
        dates = pd.to_datetime(cum.index)

        # Plot 1: Cumulative returns
        ax1 = axes[0, 0]
        ax1.plot(dates, cum.values - 1, label=label, color=color)

    bench_cum = (1 + bench_s).cumprod()
    bench_dates = pd.to_datetime(bench_cum.index)
    ax1.plot(bench_dates, bench_cum.values - 1, label='CSI300', color='gray', linestyle='--')
    ax1.set_title('Cumulative Returns')
    ax1.set_ylabel('Return')
    ax1.legend()
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))

    # Plot 2: Rolling Sharpe (60d)
    ax2 = axes[0, 1]
    for port_df, label, color in [
        (old_port, 'Original', 'blue'),
        (new_port, 'Enhanced', 'green'),
    ]:
        r = port_df.set_index('trade_date')['portfolio_return']
        common = r.index.intersection(bench_s.index)
        r_aligned = r.loc[common]
        rolling_sharpe = r_aligned.rolling(60).mean() / (r_aligned.rolling(60).std() + 1e-10) * np.sqrt(252)
        ax2.plot(pd.to_datetime(r_aligned.index), rolling_sharpe.values, label=label, color=color)
    ax2.axhline(0, color='black', linestyle='--', alpha=0.3)
    ax2.set_title('Rolling 60d Sharpe')
    ax2.legend()

    # Plot 3: Drawdown
    ax3 = axes[1, 0]
    for port_df, label, color in [
        (old_port, 'Original', 'blue'),
        (new_port, 'Enhanced', 'green'),
    ]:
        r = port_df.set_index('trade_date')['portfolio_return']
        common = r.index.intersection(bench_s.index)
        r_aligned = r.loc[common]
        cum = (1 + r_aligned).cumprod()
        dd = (cum - cum.cummax()) / cum.cummax()
        ax3.fill_between(pd.to_datetime(r_aligned.index), dd.values, 0,
                         alpha=0.3, color=color, label=label)
    ax3.set_title('Drawdown')
    ax3.set_ylabel('Drawdown')
    ax3.legend()

    # Plot 4: Performance summary table
    ax4 = axes[1, 1]
    ax4.axis('off')

    old_m = compute_metrics(old_port, bench_df)
    new_m = compute_metrics(new_port, bench_df)

    table_data = [
        ['Metric', 'Original', 'Enhanced', 'CSI300'],
        ['Cumulative', f"{old_m['cumulative']:.1%}", f"{new_m['cumulative']:.1%}", f"{old_m['bench_cumulative']:.1%}"],
        ['Ann Return', f"{old_m['ann_return']:.1%}", f"{new_m['ann_return']:.1%}", f"{old_m['bench_ann_return']:.1%}"],
        ['Sharpe', f"{old_m['sharpe']:.2f}", f"{new_m['sharpe']:.2f}", '-'],
        ['Max DD', f"{old_m['max_drawdown']:.1%}", f"{new_m['max_drawdown']:.1%}", '-'],
        ['IR', f"{old_m['ir']:.3f}", f"{new_m['ir']:.3f}", '-'],
    ]

    tbl = ax4.table(cellText=table_data[1:], colLabels=table_data[0],
                    loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.5)

    # Highlight improvements
    for row in range(1, len(table_data)):
        for col in range(1, 3):
            cell = tbl[row, col]
            if col == 2:  # Enhanced column
                orig_val = table_data[row][1]
                enh_val = table_data[row][2]
                if orig_val != enh_val:
                    cell.set_facecolor('#e8f5e9')  # light green

    ax4.set_title('Performance Summary')

    plt.tight_layout()
    path = os.path.join(output_dir, 'strategy_comparison.png')
    plt.savefig(path, dpi=120, bbox_inches='tight')
    plt.close()
    logger.info(f"Comparison chart saved: {path}")


# ============================================================
# 主流程
# ============================================================

def run_strategy(strategy: RegimeAwareStrategy, label: str) -> Dict:
    """运行策略并返回结果"""
    logger.info(f"\n{'='*50}")
    logger.info(f"Running strategy: {label}")
    logger.info(f"{'='*50}")

    result = strategy.run_backtest_preparation(START_DATE, END_DATE)
    return result


def main():
    os.makedirs('output', exist_ok=True)

    # ---- 运行原策略 ----
    logger.info("Running ORIGINAL strategy...")
    orig_config = RegimeAwareConfig(top_n=30, retrain_freq=21)
    orig_strategy = RegimeAwareStrategy(orig_config)
    orig_result = run_strategy(orig_strategy, 'Original')
    orig_signals = orig_result['signals']
    logger.info(f"Original signals: {len(orig_signals)}")

    # ---- 运行增强策略 ----
    logger.info("Running ENHANCED strategy (+6 new factors)...")
    enh_config = RegimeAwareConfig(top_n=30, retrain_freq=21)
    enh_strategy = EnhancedFactorStrategy(enh_config)
    enh_result = run_strategy(enh_strategy, 'Enhanced')
    enh_signals = enh_result['signals']
    logger.info(f"Enhanced signals: {len(enh_signals)}")

    # ---- 加载价格数据 ----
    logger.info("Loading price and benchmark data...")
    price_df = load_price_data(START_DATE, END_DATE)
    bench_df = load_benchmark(START_DATE, END_DATE)

    # ---- 模拟组合 ----
    logger.info("Simulating portfolios...")
    orig_port = simulate_portfolio(orig_signals, price_df, top_n=30, rebalance_freq=5)
    enh_port = simulate_portfolio(enh_signals, price_df, top_n=30, rebalance_freq=5)

    # ---- 计算绩效 ----
    orig_metrics = compute_metrics(orig_port, bench_df)
    enh_metrics = compute_metrics(enh_port, bench_df)

    # ---- 打印结果 ----
    print("\n" + "=" * 65)
    print("策略对比结果 (2024-01-01 → 2026-03-20)")
    print("=" * 65)
    print(f"{'指标':<20} {'原策略':>12} {'增强策略':>12} {'CSI300':>12}")
    print("-" * 65)

    metrics_map = [
        ('累计收益', 'cumulative', 'bench_cumulative'),
        ('年化收益', 'ann_return', 'bench_ann_return'),
        ('年化波动', 'ann_vol', None),
        ('Sharpe比率', 'sharpe', None),
        ('最大回撤', 'max_drawdown', None),
        ('信息比率(IR)', 'ir', None),
    ]

    for name, key, bench_key in metrics_map:
        orig_v = orig_metrics.get(key, np.nan)
        enh_v = enh_metrics.get(key, np.nan)
        bench_v = orig_metrics.get(bench_key, '-') if bench_key else '-'

        orig_str = f"{orig_v:.2%}" if key not in ['sharpe', 'ir'] else f"{orig_v:.3f}"
        enh_str = f"{enh_v:.2%}" if key not in ['sharpe', 'ir'] else f"{enh_v:.3f}"
        bench_str = f"{bench_v:.2%}" if bench_key and isinstance(bench_v, float) else str(bench_v)

        # 标记改善
        marker = ""
        if isinstance(orig_v, float) and isinstance(enh_v, float):
            if key in ['cumulative', 'ann_return', 'sharpe', 'ir'] and enh_v > orig_v:
                marker = " ↑"
            elif key in ['max_drawdown'] and enh_v > orig_v:
                marker = " ↑"  # drawdown closer to 0 is better

        print(f"{name:<20} {orig_str:>12} {enh_str + marker:>12} {bench_str:>12}")

    print("=" * 65)

    # 因子重要性对比
    if enh_result.get('factor_importance'):
        print("\n增强策略 - Top 15 因子重要性:")
        items = sorted(enh_result['factor_importance'].items(), key=lambda x: x[1], reverse=True)
        new_in_top15 = []
        for i, (f, imp) in enumerate(items[:15]):
            is_new = " [NEW]" if f in NEW_FACTORS else ""
            print(f"  {i+1:2d}. {f:<30} {imp:.4f}{is_new}")
            if f in NEW_FACTORS:
                new_in_top15.append(f)
        print(f"\n新因子进入Top15: {new_in_top15}")

    # 保存结果
    comparison = {
        'original': orig_metrics,
        'enhanced': enh_metrics,
        'new_factors': NEW_FACTORS,
        'regime_stats_original': orig_result.get('regime_stats', {}),
        'regime_stats_enhanced': enh_result.get('regime_stats', {}),
    }
    with open('output/strategy_comparison.json', 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    logger.info("Results saved to output/strategy_comparison.json")

    # 绘图
    try:
        plot_comparison(orig_port, enh_port, bench_df, 'output')
    except Exception as e:
        logger.warning(f"Plotting failed: {e}")

    return comparison


if __name__ == '__main__':
    result = main()
    print(f"\n完成！结果已保存到 output/ 目录")
