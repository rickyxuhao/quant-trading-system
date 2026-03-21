"""
择时增强策略完整回测
===================
Phase 2: 择时机制（牛市满仓/震荡减仓/熊市防御）
Phase 3: Qlib因子复刻（PSY, VWAP偏差, MA比率, 对数收益动量）
Phase 4: IC测试筛选有效因子
Phase 5: 构建择时增强策略
Phase 6: 回测对比（原策略 vs 择时增强）
Phase 7: 报告生成

回测区间: 2024-01-01 ~ 2026-03-20
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

import xgboost as xgb
from sklearn.preprocessing import RobustScaler

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedRegimeDetector, EnhancedMarketRegime, FACTOR_MULTIPLIERS
)

logger = get_logger(__name__)

# ==============================
# 配置
# ==============================
START_DATE = '20240101'
END_DATE = '20260320'
TRAIN_START = '20230101'  # 训练数据从更早开始
TOP_N = 30
REBALANCE_FREQ = 5  # 每5个交易日调仓
TRANSACTION_COST = 0.001  # 双边0.1%

# 择时仓位配置
REGIME_POSITION = {
    EnhancedMarketRegime.BULL: 1.00,        # 牛市满仓
    EnhancedMarketRegime.OSCILLATING: 0.70, # 震荡减仓至70%
    EnhancedMarketRegime.BEAR: 0.40,        # 熊市防御仓位40%
}

# 原有因子（t_precomputed_factors 中已有）
BASE_FACTORS = [
    'ep_ttm', 'bp', 'dividend_yield', 'pb', 'ps_ttm',
    'roe', 'roa', 'gross_margin', 'net_margin',
    'revenue_yoy', 'profit_yoy',
    'return_5d', 'return_10d', 'return_20d', 'return_60d',
    'market_alpha_20d', 'rs_20d_market', 'sector_alpha_20d',
    'volatility_20d', 'atr_14d',
    'turnover_rate', 'amount_norm',
    'large_order_net_ratio', 'main_net_inflow',
    'macd_hist', 'rsi_14d', 'rsi_6d', 'rsi_12d',
    'bb_width', 'bb_position', 'kdj_k', 'kdj_j',
    'obv_norm', 'amihud',
]

FACTOR_GROUPS = {
    'value': ['ep_ttm', 'bp', 'dividend_yield', 'pb', 'ps_ttm'],
    'quality': ['roe', 'roa', 'gross_margin', 'net_margin'],
    'growth': ['revenue_yoy', 'profit_yoy'],
    'momentum': ['return_5d', 'return_10d', 'return_20d', 'return_60d',
                 'market_alpha_20d', 'rs_20d_market', 'sector_alpha_20d'],
    'volatility': ['volatility_20d', 'atr_14d'],
    'liquidity': ['turnover_rate', 'amount_norm'],
    'moneyflow': ['large_order_net_ratio', 'main_net_inflow'],
    'technical': ['macd_hist', 'rsi_14d', 'rsi_6d', 'rsi_12d',
                  'bb_width', 'bb_position', 'kdj_k', 'kdj_j', 'obv_norm', 'amihud'],
    # 新增 Qlib 因子组
    'qlib': ['psy_12', 'psy_24', 'vwap_dev_20d', 'ma_ratio_5_20', 'ma_ratio_5_60', 'log_mom_20d'],
}


# ==============================
# Phase 3: Qlib因子计算函数
# ==============================

def compute_qlib_factors(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    在价格数据上计算Qlib风格因子：
    - psy_12: 12日心理线（上涨天数/12）
    - psy_24: 24日心理线
    - vwap_dev_20d: 收盘价偏离20日VWAP的程度
    - ma_ratio_5_20: MA5/MA20 - 1 (短/长均线比值)
    - ma_ratio_5_60: MA5/MA60 - 1
    - log_mom_20d: 20日对数收益动量 (与return_20d差异在于对数)
    """
    df = price_df.copy()
    df = df.sort_values(['ts_code', 'trade_date'])
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['vol'] = pd.to_numeric(df['vol'], errors='coerce').fillna(0)

    results = []

    for ts_code, grp in df.groupby('ts_code'):
        grp = grp.sort_values('trade_date').copy()
        close = grp['close'].values
        pct_chg = grp['pct_chg'].values
        vol = grp['vol'].values
        n = len(grp)

        psy_12 = np.full(n, np.nan)
        psy_24 = np.full(n, np.nan)
        vwap_dev = np.full(n, np.nan)
        ma_ratio_5_20 = np.full(n, np.nan)
        ma_ratio_5_60 = np.full(n, np.nan)
        log_mom_20d = np.full(n, np.nan)

        for i in range(n):
            # PSY_12: 过去12日上涨天数占比
            if i >= 12:
                up_days_12 = np.sum(pct_chg[i-12:i] > 0)
                psy_12[i] = up_days_12 / 12.0 * 100

            # PSY_24
            if i >= 24:
                up_days_24 = np.sum(pct_chg[i-24:i] > 0)
                psy_24[i] = up_days_24 / 24.0 * 100

            # VWAP deviation (20日量价均线偏差)
            if i >= 20 and np.sum(vol[i-20:i]) > 0:
                vwap = np.sum(close[i-20:i] * vol[i-20:i]) / np.sum(vol[i-20:i])
                if vwap > 0:
                    vwap_dev[i] = (close[i] - vwap) / vwap

            # MA ratio
            if i >= 20:
                ma5 = np.mean(close[i-5:i]) if i >= 5 else np.nan
                ma20 = np.mean(close[i-20:i])
                if not np.isnan(ma5) and ma20 > 0:
                    ma_ratio_5_20[i] = ma5 / ma20 - 1

            if i >= 60:
                ma5 = np.mean(close[i-5:i]) if i >= 5 else np.nan
                ma60 = np.mean(close[i-60:i])
                if not np.isnan(ma5) and ma60 > 0:
                    ma_ratio_5_60[i] = ma5 / ma60 - 1

            # Log momentum (20日)
            if i >= 20 and close[i-20] > 0:
                log_mom_20d[i] = np.log(close[i] / close[i-20])

        grp = grp.copy()
        grp['psy_12'] = psy_12
        grp['psy_24'] = psy_24
        grp['vwap_dev_20d'] = vwap_dev
        grp['ma_ratio_5_20'] = ma_ratio_5_20
        grp['ma_ratio_5_60'] = ma_ratio_5_60
        grp['log_mom_20d'] = log_mom_20d

        results.append(grp[['trade_date', 'ts_code',
                              'psy_12', 'psy_24', 'vwap_dev_20d',
                              'ma_ratio_5_20', 'ma_ratio_5_60', 'log_mom_20d']])

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


# ==============================
# Phase 4: 因子IC测试
# ==============================

def compute_ic_icir(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                    factor_cols: List[str], test_dates: List[str]) -> pd.DataFrame:
    """计算因子IC和ICIR（仅测试新增Qlib因子）"""
    # 合并因子和前瞻收益
    merged = factor_df.merge(fwd_returns, on=['trade_date', 'ts_code'])
    merged = merged[merged['trade_date'].isin(test_dates)]
    merged = merged.dropna(subset=['fwd_return'])

    ic_results = []
    for factor in factor_cols:
        if factor not in merged.columns:
            continue
        ic_list = []
        for date, grp in merged.groupby('trade_date'):
            grp_clean = grp[['ts_code', factor, 'fwd_return']].dropna()
            if len(grp_clean) < 50:
                continue
            ic = grp_clean[factor].rank().corr(grp_clean['fwd_return'].rank(), method='spearman')
            ic_list.append(ic)

        if ic_list:
            ic_arr = np.array(ic_list)
            ic_mean = np.mean(ic_arr)
            ic_std = np.std(ic_arr) if np.std(ic_arr) > 0 else 1e-6
            icir = ic_mean / ic_std * np.sqrt(252 / 5)  # annualize assuming 5d horizon
            ic_results.append({
                'factor': factor,
                'ic_mean': round(ic_mean, 4),
                'ic_std': round(ic_std, 4),
                'icir': round(icir, 3),
                'ic_positive_pct': round(np.mean(ic_arr > 0) * 100, 1),
            })

    return pd.DataFrame(ic_results).sort_values('icir', key=abs, ascending=False)


# ==============================
# 数据加载
# ==============================

def load_factor_data(start_date: str, end_date: str) -> pd.DataFrame:
    cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
    existing_cols = {c['Field'] for c in cols_info}
    available = [f for f in BASE_FACTORS if f in existing_cols]
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
    return df, available


def load_price_data(start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, ts_code, open, close, pct_chg, vol
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    for col in ['open', 'close', 'pct_chg', 'vol']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def load_index_data(start_date: str, end_date: str) -> pd.DataFrame:
    warmup = (pd.Timestamp(start_date) - pd.Timedelta(days=90)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, close, pct_chg
    FROM t_index_daily
    WHERE ts_code = '000300.SH'
      AND trade_date >= '{warmup}'
      AND trade_date <= '{end_date}'
    ORDER BY trade_date
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    return df


def load_forward_returns(start_date: str, end_date: str, horizon: int = 5) -> pd.DataFrame:
    extended_end = (pd.Timestamp(end_date) + pd.Timedelta(days=horizon * 3)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, ts_code, pct_chg
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{extended_end}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df = df.sort_values(['ts_code', 'trade_date'])

    def calc_fwd(grp):
        grp = grp.copy()
        r = grp['pct_chg'].values / 100
        fwd = np.full(len(r), np.nan)
        for i in range(len(r) - horizon):
            fwd[i] = np.prod(1 + r[i+1:i+1+horizon]) - 1
        grp['fwd_return'] = fwd
        return grp

    df = df.groupby('ts_code', group_keys=False).apply(calc_fwd)
    return df[['trade_date', 'ts_code', 'fwd_return']]


def load_industry_data() -> pd.DataFrame:
    sql = "SELECT ts_code, industry FROM t_stock_basic WHERE list_status = 'L'"
    try:
        return pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))[['ts_code', 'industry']].dropna()
    except Exception:
        return pd.DataFrame()


# ==============================
# Phase 5: 信号生成（择时增强）
# ==============================

def prepare_features(factor_df: pd.DataFrame, regime: EnhancedMarketRegime,
                     factor_cols: List[str]) -> pd.DataFrame:
    X = factor_df[factor_cols].copy()
    multipliers = FACTOR_MULTIPLIERS.get(regime, {})
    for f in factor_cols:
        if f not in X.columns:
            X[f] = 0.0
            continue
        vals = X[f]
        std = vals.std()
        if std > 1e-10:
            X[f] = ((vals - vals.mean()) / std).clip(-3, 3)
        if f in multipliers:
            X[f] *= multipliers[f]
    return X.fillna(0)


def train_xgboost(train_factor: pd.DataFrame, train_returns: pd.DataFrame,
                   regime: EnhancedMarketRegime, factor_cols: List[str],
                   min_samples: int = 5000):
    merged = train_factor.merge(train_returns, on=['trade_date', 'ts_code']).dropna(subset=['fwd_return'])
    if len(merged) < min_samples:
        return None
    X = prepare_features(merged, regime, factor_cols)
    y = merged['fwd_return']
    split = int(len(merged) * 0.85)
    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.7, min_child_weight=5,
        reg_alpha=0.1, reg_lambda=1.0, tree_method='hist',
        random_state=42, n_jobs=-1, early_stopping_rounds=20,
        eval_metric='rmse',
    )
    model.fit(X.iloc[:split], y.iloc[:split],
              eval_set=[(X.iloc[split:], y.iloc[split:])], verbose=False)
    return model


def generate_signals(date: str, factor_df: pd.DataFrame, model,
                     regime: EnhancedMarketRegime, industry_df: pd.DataFrame,
                     factor_cols: List[str], top_n: int = 30) -> pd.DataFrame:
    date_df = factor_df[factor_df['trade_date'] == date].copy()
    if len(date_df) < 200:
        return pd.DataFrame()

    # 行业中性化
    if not industry_df.empty:
        merged = date_df.merge(industry_df, on='ts_code', how='left')
        merged['industry'] = merged['industry'].fillna('未知')
        for f in factor_cols:
            if f in merged.columns:
                try:
                    ind_mean = merged.groupby('industry')[f].transform('mean')
                    merged[f] = merged[f] - ind_mean
                except Exception:
                    pass
        date_df = merged.drop(columns=['industry'], errors='ignore')

    X = prepare_features(date_df, regime, factor_cols)

    if model is not None:
        try:
            score = model.predict(X)
        except Exception:
            score = X[factor_cols].mean(axis=1).values if factor_cols else np.zeros(len(date_df))
    else:
        # 简单等权综合分
        score_df = pd.DataFrame(index=date_df.index)
        for f in factor_cols:
            if f in X.columns:
                score_df[f] = X[f]
        score = score_df.mean(axis=1).fillna(0).values

    date_df = date_df.copy()
    date_df['score'] = score
    date_df['regime'] = regime.value
    date_df = date_df.sort_values('score', ascending=False)
    date_df['rank'] = range(1, len(date_df) + 1)
    return date_df[['trade_date', 'ts_code', 'score', 'rank', 'regime']].head(top_n)


# ==============================
# Phase 6: 回测模拟
# ==============================

def simulate_portfolio(signals_df: pd.DataFrame, price_df: pd.DataFrame,
                        regime_df: pd.DataFrame, use_timing: bool = True,
                        top_n: int = 30, rebalance_freq: int = 5,
                        cost: float = 0.001) -> pd.DataFrame:
    """
    等权重持股组合模拟
    use_timing=True 时按市场环境调整仓位
    """
    signal_dates = sorted(signals_df['trade_date'].unique())
    price_dict = price_df.set_index(['trade_date', 'ts_code'])['pct_chg'].to_dict()
    all_dates = sorted(price_df['trade_date'].unique())

    # regime lookup
    regime_map = {}
    if not regime_df.empty:
        for _, row in regime_df.iterrows():
            regime_map[str(row['trade_date'])] = row['regime']

    portfolio_returns = []
    current_holdings = []
    last_rebalance_idx = -1

    for i, date in enumerate(all_dates):
        if date < signal_dates[0]:
            continue

        # 市场环境 & 仓位
        regime_str = regime_map.get(date, 'oscillating')
        try:
            regime = EnhancedMarketRegime(regime_str)
        except ValueError:
            regime = EnhancedMarketRegime.OSCILLATING
        position_ratio = REGIME_POSITION[regime] if use_timing else 1.0

        # 是否调仓
        signal_idx = [j for j, sd in enumerate(signal_dates) if sd <= date]
        latest_signal_date = signal_dates[signal_idx[-1]] if signal_idx else None
        need_rebalance = (
            not current_holdings or
            i - last_rebalance_idx >= rebalance_freq
        ) and latest_signal_date is not None

        if need_rebalance:
            new_holdings = signals_df[
                signals_df['trade_date'] == latest_signal_date
            ]['ts_code'].tolist()[:top_n]

            if new_holdings:
                # 换仓成本
                added = set(new_holdings) - set(current_holdings)
                removed = set(current_holdings) - set(new_holdings)
                turnover = (len(added) + len(removed)) / max(len(new_holdings), 1)
                cost_drag = turnover * cost
                current_holdings = new_holdings
                last_rebalance_idx = i
            else:
                cost_drag = 0.0
        else:
            cost_drag = 0.0

        if not current_holdings:
            portfolio_returns.append({'trade_date': date, 'portfolio_return': 0.0,
                                      'regime': regime_str, 'position_ratio': position_ratio})
            continue

        # 计算当日组合收益
        daily_rets = []
        for code in current_holdings:
            ret = price_dict.get((date, code), 0) / 100
            daily_rets.append(ret)

        avg_ret = np.mean(daily_rets) if daily_rets else 0.0
        # 应用仓位比例（剩余现金收益为0）
        net_ret = avg_ret * position_ratio - cost_drag

        portfolio_returns.append({
            'trade_date': date,
            'portfolio_return': net_ret,
            'regime': regime_str,
            'position_ratio': position_ratio,
            'n_holdings': len(current_holdings),
        })

    return pd.DataFrame(portfolio_returns)


def compute_metrics(returns: pd.Series, benchmark_returns: pd.Series = None) -> Dict:
    r = returns.fillna(0)
    cum = (1 + r).cumprod()
    total_return = float(cum.iloc[-1] - 1)
    n_years = len(r) / 252
    annual_return = float((1 + total_return) ** (1 / max(n_years, 0.01)) - 1)
    vol = float(r.std() * np.sqrt(252))
    sharpe = annual_return / vol if vol > 0 else 0.0
    drawdown = (cum / cum.cummax() - 1)
    max_dd = float(drawdown.min())

    metrics = {
        'total_return': round(total_return * 100, 2),
        'annual_return': round(annual_return * 100, 2),
        'volatility': round(vol * 100, 2),
        'sharpe': round(sharpe, 3),
        'max_drawdown': round(max_dd * 100, 2),
    }

    if benchmark_returns is not None:
        bm = benchmark_returns.fillna(0).reindex(r.index).fillna(0)
        alpha = r - bm
        alpha_annual = float(alpha.mean() * 252)
        te = float(alpha.std() * np.sqrt(252))
        ir = alpha_annual / te if te > 0 else 0.0
        metrics['alpha_annual'] = round(alpha_annual * 100, 2)
        metrics['tracking_error'] = round(te * 100, 2)
        metrics['ir'] = round(ir, 3)

    return metrics


# ==============================
# 可视化
# ==============================

def plot_results(original_df: pd.DataFrame, enhanced_df: pd.DataFrame,
                 bm_df: pd.DataFrame, regime_df: pd.DataFrame,
                 output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(16, 18))
    fig.suptitle('择时增强策略 vs 原策略对比', fontsize=16, fontweight='bold')

    # --- 图1: 净值曲线 ---
    ax1 = axes[0]
    orig_cum = (1 + original_df['portfolio_return']).cumprod()
    enh_cum = (1 + enhanced_df['portfolio_return']).cumprod()

    bm_cum = None
    if not bm_df.empty:
        bm_ret = bm_df.set_index('trade_date')['pct_chg'] / 100
        bm_ret = bm_ret.reindex(original_df['trade_date'])
        bm_cum = (1 + bm_ret.fillna(0)).cumprod().values

    dates_str = original_df['trade_date'].values
    dates = pd.to_datetime(dates_str)

    ax1.plot(dates, orig_cum.values, label='原策略（无择时）', color='steelblue', linewidth=1.5)
    ax1.plot(dates, enh_cum.values, label='择时增强策略', color='coral', linewidth=2.0)
    if bm_cum is not None:
        ax1.plot(dates, bm_cum, label='沪深300', color='gray', linewidth=1.2, linestyle='--')

    # 背景色标注市场环境
    if not regime_df.empty:
        regime_map = dict(zip(regime_df['trade_date'].astype(str), regime_df['regime']))
        colors = {'bull': 'lightgreen', 'bear': 'lightcoral', 'oscillating': 'lightyellow'}
        prev_regime = None
        start_x = None
        for d_str in dates_str:
            r = regime_map.get(d_str, 'oscillating')
            if r != prev_regime:
                if prev_regime is not None and start_x is not None:
                    ax1.axvspan(pd.Timestamp(start_x), pd.Timestamp(d_str),
                                alpha=0.15, color=colors.get(prev_regime, 'white'))
                prev_regime = r
                start_x = d_str
        if start_x:
            ax1.axvspan(pd.Timestamp(start_x), dates[-1],
                        alpha=0.15, color=colors.get(prev_regime, 'white'))

    ax1.set_title('净值曲线（绿=牛市，红=熊市，黄=震荡）')
    ax1.legend(loc='upper left')
    ax1.set_ylabel('累计净值')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30)

    # --- 图2: 仓位与市场环境 ---
    ax2 = axes[1]
    enh_pos = enhanced_df.set_index('trade_date')['position_ratio'].reindex(dates_str).fillna(method='ffill')
    ax2.fill_between(dates, enh_pos.values, alpha=0.6, color='steelblue', label='仓位比例')
    ax2.set_ylim(0, 1.2)
    ax2.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='满仓线')
    ax2.axhline(y=0.7, color='orange', linestyle='--', alpha=0.5, label='震荡仓位')
    ax2.axhline(y=0.4, color='green', linestyle='--', alpha=0.5, label='防御仓位')
    ax2.set_title('择时仓位变化')
    ax2.legend(loc='upper right')
    ax2.set_ylabel('仓位比例')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30)

    # --- 图3: 超额收益 ---
    ax3 = axes[2]
    enh_vs_orig = (1 + enhanced_df['portfolio_return']).cumprod() / (1 + original_df['portfolio_return']).cumprod()
    ax3.plot(dates, enh_vs_orig.values, color='purple', linewidth=1.5)
    ax3.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
    ax3.fill_between(dates, enh_vs_orig.values, 1.0,
                     where=enh_vs_orig.values > 1.0, alpha=0.3, color='green', label='超额正')
    ax3.fill_between(dates, enh_vs_orig.values, 1.0,
                     where=enh_vs_orig.values <= 1.0, alpha=0.3, color='red', label='超额负')
    ax3.set_title('择时增强 vs 原策略（超额净值）')
    ax3.legend()
    ax3.set_ylabel('相对净值')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30)

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'timing_enhanced_backtest.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"图表已保存: {out_path}")


def plot_regime_analysis(portfolio_df: pd.DataFrame, output_dir: str):
    """分市场环境表现分析"""
    os.makedirs(output_dir, exist_ok=True)

    regime_perf = {}
    for regime in ['bull', 'bear', 'oscillating']:
        sub = portfolio_df[portfolio_df['regime'] == regime]['portfolio_return']
        if len(sub) < 5:
            continue
        cum = (1 + sub).prod() - 1
        ann = (1 + cum) ** (252 / max(len(sub), 1)) - 1
        sharpe = sub.mean() / sub.std() * np.sqrt(252) if sub.std() > 0 else 0
        regime_perf[regime] = {
            'days': len(sub),
            'total_return': round(cum * 100, 2),
            'annual_return': round(ann * 100, 2),
            'sharpe': round(sharpe, 3),
            'avg_daily': round(sub.mean() * 100, 4),
        }

    # Bar chart
    if regime_perf:
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle('分市场环境表现（择时增强策略）', fontsize=14)

        regimes = list(regime_perf.keys())
        name_map = {'bull': '牛市', 'bear': '熊市', 'oscillating': '震荡市'}
        color_map = {'bull': 'green', 'bear': 'red', 'oscillating': 'orange'}

        ann_rets = [regime_perf[r]['annual_return'] for r in regimes]
        sharpes = [regime_perf[r]['sharpe'] for r in regimes]
        days = [regime_perf[r]['days'] for r in regimes]

        axes[0].bar([name_map.get(r, r) for r in regimes], ann_rets,
                    color=[color_map.get(r, 'gray') for r in regimes])
        axes[0].set_title('年化收益率(%)')
        axes[0].axhline(0, color='black', linewidth=0.5)

        axes[1].bar([name_map.get(r, r) for r in regimes], sharpes,
                    color=[color_map.get(r, 'gray') for r in regimes])
        axes[1].set_title('夏普比率')
        axes[1].axhline(0, color='black', linewidth=0.5)

        axes[2].bar([name_map.get(r, r) for r in regimes], days,
                    color=[color_map.get(r, 'gray') for r in regimes])
        axes[2].set_title('天数分布')

        plt.tight_layout()
        out_path = os.path.join(output_dir, 'regime_analysis.png')
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"环境分析图已保存: {out_path}")

    return regime_perf


# ==============================
# Main
# ==============================

def main():
    os.makedirs('output/timing_enhanced', exist_ok=True)
    logger.info("=" * 60)
    logger.info("择时增强策略回测开始")
    logger.info("=" * 60)

    # ---- 加载数据 ----
    logger.info("1. 加载数据...")
    result = load_factor_data(TRAIN_START, END_DATE)
    if isinstance(result, tuple):
        factor_df, available_factors = result
    else:
        factor_df = result
        available_factors = BASE_FACTORS

    logger.info(f"   因子数据: {len(factor_df)} 行, {len(available_factors)} 个基础因子")

    price_df = load_price_data(TRAIN_START, END_DATE)
    logger.info(f"   价格数据: {len(price_df)} 行")

    index_df = load_index_data(START_DATE, END_DATE)
    logger.info(f"   指数数据: {len(index_df)} 行")

    fwd_returns = load_forward_returns(TRAIN_START, END_DATE, horizon=5)
    logger.info(f"   前瞻收益: {len(fwd_returns)} 行")

    industry_df = load_industry_data()
    logger.info(f"   行业数据: {len(industry_df)} 只股票")

    # ---- Phase 3: 计算Qlib因子 ----
    logger.info("\n2. 计算Qlib风格因子 (PSY/VWAP/MA ratio)...")
    qlib_df = compute_qlib_factors(price_df)
    if not qlib_df.empty:
        logger.info(f"   Qlib因子: {len(qlib_df)} 行")
        factor_df = factor_df.merge(qlib_df, on=['trade_date', 'ts_code'], how='left')
        qlib_factor_names = ['psy_12', 'psy_24', 'vwap_dev_20d',
                             'ma_ratio_5_20', 'ma_ratio_5_60', 'log_mom_20d']
        available_factors = available_factors + qlib_factor_names
        logger.info(f"   合并后总因子数: {len(available_factors)}")

    # ---- Phase 4: IC测试（仅对新增Qlib因子）----
    logger.info("\n3. 新增Qlib因子IC测试...")
    backtest_dates = sorted(factor_df[
        (factor_df['trade_date'] >= START_DATE) &
        (factor_df['trade_date'] <= END_DATE)
    ]['trade_date'].unique())

    qlib_ic = compute_ic_icir(factor_df, fwd_returns, qlib_factor_names, backtest_dates)
    print("\n=== Qlib因子IC测试结果 ===")
    print(qlib_ic.to_string(index=False))

    # 筛选有效Qlib因子（|ICIR| > 0.3）
    valid_qlib = qlib_ic[qlib_ic['icir'].abs() > 0.3]['factor'].tolist()
    logger.info(f"   有效Qlib因子 (|ICIR|>0.3): {valid_qlib}")

    # 最终因子列表
    final_factors = [f for f in available_factors if f in factor_df.columns]
    logger.info(f"   最终使用因子数: {len(final_factors)}")

    # ---- Phase 1修正验证: 市场环境分类 ----
    logger.info("\n4. 市场环境分类（修正后）...")
    detector = EnhancedRegimeDetector(use_ma_cross=True)
    regime_df = detector.detect_regime_series(index_df)
    regime_df = regime_df[regime_df['trade_date'].astype(str) >= START_DATE]

    regime_stats = regime_df['regime'].value_counts()
    total_days = len(regime_df)
    print("\n=== 修正后市场环境分布 ===")
    for r, cnt in regime_stats.items():
        print(f"  {r:12s}: {cnt:4d}天 ({cnt/total_days*100:.1f}%)")

    # 按月显示环境分类
    regime_df_copy = regime_df.copy()
    regime_df_copy['ym'] = regime_df_copy['trade_date'].astype(str).str[:6]
    monthly_regime = regime_df_copy.groupby('ym')['regime'].apply(
        lambda x: x.value_counts().idxmax()
    )
    print("\n月度市场环境（主要环境）:")
    for ym, r in monthly_regime.items():
        emoji = {'bull': '🐂', 'bear': '🐻', 'oscillating': '↔️'}.get(r, '?')
        print(f"  {ym}: {emoji} {r}")

    # ---- Phase 5: 生成选股信号 ----
    logger.info("\n5. 生成选股信号（含择时）...")
    regime_map = dict(zip(regime_df['trade_date'].astype(str), regime_df['regime']))

    backtest_factor_df = factor_df[
        (factor_df['trade_date'] >= START_DATE) &
        (factor_df['trade_date'] <= END_DATE)
    ]

    all_signals = []
    current_model = None
    last_train_date = None
    last_regime = EnhancedMarketRegime.OSCILLATING
    retrain_freq = 21  # 每21个交易日重训练

    for i, date in enumerate(backtest_dates):
        regime_str = regime_map.get(date, 'oscillating')
        try:
            regime = EnhancedMarketRegime(regime_str)
        except ValueError:
            regime = EnhancedMarketRegime.OSCILLATING
        last_regime = regime

        # 是否重训练
        need_retrain = (current_model is None or i % retrain_freq == 0)
        if need_retrain:
            train_factor = factor_df[factor_df['trade_date'] < date].copy()
            train_ret = fwd_returns[fwd_returns['trade_date'] < date].copy()
            if len(train_factor) >= 5000:
                current_model = train_xgboost(train_factor, train_ret, regime, final_factors)
                last_train_date = date
                if current_model and i % 60 == 0:
                    logger.info(f"  [{date}] 重训练完成 (regime={regime_str}, samples={len(train_factor)})")

        signals = generate_signals(date, backtest_factor_df, current_model,
                                   regime, industry_df, final_factors, TOP_N)
        if not signals.empty:
            all_signals.append(signals)

        if i % 50 == 0:
            logger.info(f"  进度: {i+1}/{len(backtest_dates)} [{date}] regime={regime_str}")

    signals_df = pd.concat(all_signals, ignore_index=True) if all_signals else pd.DataFrame()
    logger.info(f"   总信号数: {len(signals_df)}, 覆盖日期: {signals_df['trade_date'].nunique() if not signals_df.empty else 0}")

    # ---- Phase 6: 回测 ----
    logger.info("\n6. 运行回测对比...")
    backtest_price = price_df[
        (price_df['trade_date'] >= START_DATE) &
        (price_df['trade_date'] <= END_DATE)
    ]

    # 策略A: 择时增强
    logger.info("   运行择时增强策略...")
    enhanced_portfolio = simulate_portfolio(
        signals_df, backtest_price, regime_df,
        use_timing=True, top_n=TOP_N, rebalance_freq=REBALANCE_FREQ, cost=TRANSACTION_COST
    )

    # 策略B: 原策略（无择时，满仓）
    logger.info("   运行原策略（无择时）...")
    original_portfolio = simulate_portfolio(
        signals_df, backtest_price, regime_df,
        use_timing=False, top_n=TOP_N, rebalance_freq=REBALANCE_FREQ, cost=TRANSACTION_COST
    )

    # 基准数据
    bm_df = index_df[index_df['trade_date'] >= START_DATE].copy()
    bm_returns = bm_df.set_index('trade_date')['pct_chg'] / 100

    # 指标计算
    orig_ret = original_portfolio.set_index('trade_date')['portfolio_return']
    enh_ret = enhanced_portfolio.set_index('trade_date')['portfolio_return']
    bm_aligned = bm_returns.reindex(orig_ret.index).fillna(0)

    orig_metrics = compute_metrics(orig_ret, bm_aligned)
    enh_metrics = compute_metrics(enh_ret, bm_aligned)
    bm_metrics = compute_metrics(bm_aligned)

    # ---- Phase 7: 报告 ----
    logger.info("\n7. 生成报告...")

    print("\n" + "=" * 65)
    print("                  回测结果汇总报告")
    print("=" * 65)
    print(f"回测区间: {START_DATE} ~ {END_DATE}")
    print(f"{'指标':<20} {'原策略(无择时)':>16} {'择时增强策略':>16} {'沪深300':>12}")
    print("-" * 65)
    metrics_map = {
        'total_return': ('总收益率(%)', ),
        'annual_return': ('年化收益率(%)', ),
        'volatility': ('年化波动率(%)', ),
        'sharpe': ('夏普比率', ),
        'max_drawdown': ('最大回撤(%)', ),
        'alpha_annual': ('年化Alpha(%)', ),
        'ir': ('信息比率', ),
    }
    for key, (label,) in metrics_map.items():
        o = orig_metrics.get(key, '-')
        e = enh_metrics.get(key, '-')
        b = bm_metrics.get(key, '-')
        print(f"  {label:<18} {str(o):>16} {str(e):>16} {str(b):>12}")

    print("\n市场环境分布:")
    for r, cnt in regime_stats.items():
        print(f"  {r:12s}: {cnt:4d}天 ({cnt/total_days*100:.1f}%)")

    # 分环境统计（择时增强策略）
    print("\n分市场环境表现（择时增强策略）:")
    regime_perf = {}
    for regime_name in ['bull', 'bear', 'oscillating']:
        sub = enhanced_portfolio[enhanced_portfolio['regime'] == regime_name]['portfolio_return']
        if len(sub) < 5:
            continue
        cum = (1 + sub).prod() - 1
        ann = (1 + cum) ** (252 / max(len(sub), 1)) - 1
        sr = sub.mean() / sub.std() * np.sqrt(252) if sub.std() > 0 else 0
        regime_perf[regime_name] = {'days': len(sub), 'annual_return': ann, 'sharpe': sr}
        name_cn = {'bull': '牛市  ', 'bear': '熊市  ', 'oscillating': '震荡市'}[regime_name]
        print(f"  {name_cn}: {len(sub)}天, 年化={ann*100:.2f}%, Sharpe={sr:.3f}")

    print("=" * 65)

    # 保存结果
    enhanced_portfolio.to_csv('output/timing_enhanced/portfolio_enhanced.csv', index=False)
    original_portfolio.to_csv('output/timing_enhanced/portfolio_original.csv', index=False)
    regime_df.to_csv('output/timing_enhanced/regime_classification.csv', index=False)
    signals_df.to_csv('output/timing_enhanced/signals.csv', index=False)
    qlib_ic.to_csv('output/timing_enhanced/qlib_ic_results.csv', index=False)

    # 保存指标
    summary = {
        'original': orig_metrics,
        'enhanced': enh_metrics,
        'benchmark': bm_metrics,
        'regime_stats': {r: {'days': int(c), 'pct': round(c/total_days*100, 1)}
                         for r, c in regime_stats.items()},
        'regime_performance': {r: {k: round(v, 4) for k, v in d.items()}
                                for r, d in regime_perf.items()},
    }
    with open('output/timing_enhanced/metrics_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 绘图
    plot_results(original_portfolio, enhanced_portfolio, bm_df, regime_df,
                 'output/timing_enhanced')
    plot_regime_analysis(enhanced_portfolio, 'output/timing_enhanced')

    logger.info("\n所有结果已保存到 output/timing_enhanced/")
    logger.info("=" * 60)
    logger.info("回测完成！")

    return summary


if __name__ == '__main__':
    main()
