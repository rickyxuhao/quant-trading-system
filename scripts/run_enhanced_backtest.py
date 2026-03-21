"""
Phase 6: 回测验证
- 回测区间：2024-01-01 至 2026-03-20
- 使用市场环境感知策略信号
- 分市场环境统计表现
- 生成对比报告和可视化图表
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

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.regime_aware_strategy import (
    RegimeAwareStrategy, RegimeAwareConfig
)
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    load_and_detect_regimes
)

logger = get_logger(__name__)


def load_price_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载回测期间股票价格数据"""
    sql = f"""
    SELECT trade_date, ts_code, open, close, pct_chg, vol
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    return df


def load_benchmark(start_date: str, end_date: str, ts_code: str = '000300.SH') -> pd.DataFrame:
    """加载基准指数"""
    sql = f"""
    SELECT trade_date, close, pct_chg
    FROM t_index_daily
    WHERE ts_code = '{ts_code}'
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
    """
    模拟等权重持股组合

    Args:
        signals_df: 每日选股信号 (trade_date, ts_code, score, rank, regime)
        price_df: 价格数据
        top_n: 每期持股数
        rebalance_freq: 调仓频率（交易日）
        transaction_cost: 单边交易成本

    Returns:
        DataFrame with portfolio daily returns
    """
    # 获取信号日期
    signal_dates = sorted(signals_df['trade_date'].unique())

    price_dict = price_df.set_index(['trade_date', 'ts_code'])['pct_chg'].to_dict()
    all_dates = sorted(price_df['trade_date'].unique())

    portfolio_returns = []
    current_holdings = []
    last_rebalance_idx = -1

    for i, date in enumerate(all_dates):
        if date < signal_dates[0]:
            continue

        # 是否需要调仓
        need_rebalance = (
            not current_holdings or
            i - last_rebalance_idx >= rebalance_freq
        )

        if need_rebalance and date in signal_dates:
            # 获取当日Top N信号
            date_signals = signals_df[signals_df['trade_date'] == date].nsmallest(top_n, 'rank')
            new_holdings = date_signals['ts_code'].tolist()

            # 计算交易成本
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
            continue

        # 计算当日组合收益（等权）
        daily_returns = []
        for ts_code in current_holdings:
            ret = price_dict.get((date, ts_code), np.nan)
            if not np.isnan(ret):
                daily_returns.append(ret / 100)

        if daily_returns:
            port_ret = np.mean(daily_returns) - cost
        else:
            port_ret = 0

        portfolio_returns.append({
            'trade_date': date,
            'portfolio_return': port_ret,
            'n_stocks': len(daily_returns),
            'transaction_cost': cost,
        })

    return pd.DataFrame(portfolio_returns)


def compute_performance_metrics(returns: pd.Series, benchmark_returns: pd.Series,
                                  regime_map: pd.Series = None) -> Dict:
    """计算完整绩效指标"""
    # 转为小数格式
    r = returns.fillna(0)
    b = benchmark_returns.fillna(0)

    # 对齐
    common_idx = r.index.intersection(b.index)
    r = r.loc[common_idx]
    b = b.loc[common_idx]

    cum_r = (1 + r).cumprod()
    cum_b = (1 + b).cumprod()

    # 年化收益
    n_years = len(r) / 252
    ann_return = (cum_r.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0
    bench_ann_return = (cum_b.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0

    # 年化波动率
    ann_vol = r.std() * np.sqrt(252)

    # Sharpe Ratio（无风险利率2.5%）
    rf = 0.025 / 252
    excess_r = r - rf
    sharpe = (excess_r.mean() * 252) / (r.std() * np.sqrt(252) + 1e-10)

    # 最大回撤
    cum_max = cum_r.cummax()
    drawdown = (cum_r - cum_max) / cum_max
    max_dd = drawdown.min()

    # 信息比率
    alpha = r - b
    ir = (alpha.mean() * 252) / (alpha.std() * np.sqrt(252) + 1e-10)

    # 胜率
    win_rate = (r > b).mean()

    metrics = {
        'total_return': round(float(cum_r.iloc[-1] - 1), 4),
        'benchmark_total_return': round(float(cum_b.iloc[-1] - 1), 4),
        'annual_return': round(float(ann_return), 4),
        'benchmark_annual_return': round(float(bench_ann_return), 4),
        'annual_volatility': round(float(ann_vol), 4),
        'sharpe_ratio': round(float(sharpe), 4),
        'max_drawdown': round(float(max_dd), 4),
        'information_ratio': round(float(ir), 4),
        'win_rate': round(float(win_rate), 4),
        'calmar_ratio': round(float(ann_return / max(abs(max_dd), 1e-4)), 4),
    }

    # 分市场环境统计
    if regime_map is not None:
        for regime in ['bull', 'bear', 'oscillating']:
            regime_dates = regime_map[regime_map == regime].index
            regime_common = common_idx.intersection(regime_dates)
            if len(regime_common) > 5:
                r_reg = r.loc[regime_common]
                b_reg = b.loc[regime_common]
                excess = r_reg - b_reg
                metrics[f'{regime}_alpha'] = round(float(excess.mean() * 252), 4)
                metrics[f'{regime}_sharpe'] = round(
                    float(r_reg.mean() * 252 / max(r_reg.std() * np.sqrt(252), 1e-4)), 4)
                metrics[f'{regime}_days'] = len(regime_common)

    return metrics


def plot_results(portfolio_df: pd.DataFrame, benchmark_df: pd.DataFrame,
                  regime_df: pd.DataFrame, output_dir: str):
    """生成可视化图表"""
    os.makedirs(output_dir, exist_ok=True)

    # 合并数据
    bench = benchmark_df.set_index('trade_date')['pct_chg'] / 100
    port = portfolio_df.set_index('trade_date')['portfolio_return']

    # 转为datetime索引（用于绘图）
    bench.index = pd.to_datetime(bench.index)
    port.index = pd.to_datetime(port.index)

    common_idx = port.index.intersection(bench.index)
    port = port.loc[common_idx]
    bench = bench.loc[common_idx]

    cum_port = (1 + port).cumprod()
    cum_bench = (1 + bench).cumprod()

    # 制作regime背景颜色
    if not regime_df.empty:
        regime_df = regime_df.copy()
        regime_df['trade_date'] = pd.to_datetime(regime_df['trade_date'].astype(str))
        regime_df = regime_df.set_index('trade_date')

    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle('Enhanced Strategy Backtest Report (2024-2026)', fontsize=14, fontweight='bold')

    # Plot 1: Cumulative Returns
    ax1 = axes[0]
    ax1.plot(cum_port.index, cum_port.values, label='Strategy', linewidth=2, color='royalblue')
    ax1.plot(cum_bench.index, cum_bench.values, label='CSI300', linewidth=1.5,
             color='orange', linestyle='--')

    # Shade regimes
    if not regime_df.empty:
        colors = {'bull': '#90EE90', 'bear': '#FFB6C1', 'oscillating': '#FFFACD'}
        prev_regime = None
        start_x = None
        for date, row in regime_df.iterrows():
            if date not in cum_port.index:
                continue
            regime = row.get('regime', 'oscillating')
            if regime != prev_regime:
                if prev_regime is not None and start_x is not None:
                    ax1.axvspan(start_x, date, alpha=0.2,
                               color=colors.get(prev_regime, 'white'), label='')
                start_x = date
                prev_regime = regime

    ax1.set_title('Cumulative Returns')
    ax1.set_ylabel('Cumulative Return')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Plot 2: Drawdown
    ax2 = axes[1]
    cum_max = cum_port.cummax()
    drawdown = (cum_port - cum_max) / cum_max
    ax2.fill_between(drawdown.index, drawdown.values, 0, color='crimson', alpha=0.4, label='Strategy DD')

    bench_cum_max = cum_bench.cummax()
    bench_dd = (cum_bench - bench_cum_max) / bench_cum_max
    ax2.fill_between(bench_dd.index, bench_dd.values, 0, color='orange', alpha=0.2, label='CSI300 DD')

    ax2.set_title('Drawdown')
    ax2.set_ylabel('Drawdown')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Plot 3: Rolling Alpha (60-day)
    ax3 = axes[2]
    alpha = port - bench
    rolling_alpha = alpha.rolling(60).mean() * 252
    ax3.plot(rolling_alpha.index, rolling_alpha.values, color='darkgreen', linewidth=1.5)
    ax3.axhline(y=0, color='black', linewidth=0.8, linestyle='--')
    ax3.fill_between(rolling_alpha.index, rolling_alpha.values, 0,
                     where=rolling_alpha > 0, alpha=0.3, color='green', label='Positive Alpha')
    ax3.fill_between(rolling_alpha.index, rolling_alpha.values, 0,
                     where=rolling_alpha < 0, alpha=0.3, color='red', label='Negative Alpha')
    ax3.set_title('Rolling 60-Day Annualized Alpha')
    ax3.set_ylabel('Annualized Alpha')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'backtest_report.png')
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Chart saved to {chart_path}")
    return chart_path


def generate_report(metrics: Dict, regime_stats: Dict, factor_importance: Dict,
                     output_dir: str) -> str:
    """生成文字报告"""
    lines = [
        "=" * 60,
        "增强版策略回测报告",
        "回测区间: 2024-01-01 → 2026-03-20",
        "=" * 60,
        "",
        "📊 整体绩效",
        "-" * 40,
        f"  策略累计收益:    {metrics.get('total_return', 0)*100:.2f}%",
        f"  基准累计收益:    {metrics.get('benchmark_total_return', 0)*100:.2f}%",
        f"  策略年化收益:    {metrics.get('annual_return', 0)*100:.2f}%",
        f"  基准年化收益:    {metrics.get('benchmark_annual_return', 0)*100:.2f}%",
        f"  Sharpe Ratio:    {metrics.get('sharpe_ratio', 0):.4f}",
        f"  最大回撤:        {metrics.get('max_drawdown', 0)*100:.2f}%",
        f"  信息比率(IR):    {metrics.get('information_ratio', 0):.4f}",
        f"  胜率:           {metrics.get('win_rate', 0)*100:.2f}%",
        f"  Calmar Ratio:    {metrics.get('calmar_ratio', 0):.4f}",
        "",
        "🌍 市场环境分类统计",
        "-" * 40,
    ]

    for regime, info in regime_stats.items():
        if isinstance(info, dict):
            lines.append(f"  {regime:15s}: {info['days']}天 ({info['pct']}%)")

    lines.extend([
        "",
        "📈 各市场环境下策略表现",
        "-" * 40,
    ])
    for regime in ['bull', 'bear', 'oscillating']:
        alpha = metrics.get(f'{regime}_alpha')
        sharpe = metrics.get(f'{regime}_sharpe')
        days = metrics.get(f'{regime}_days')
        if alpha is not None:
            lines.append(f"  {regime:15s}: Alpha={alpha*100:.2f}%/年, "
                        f"Sharpe={sharpe:.2f}, Days={days}")

    if factor_importance:
        lines.extend([
            "",
            "🔑 Top 15 因子重要性",
            "-" * 40,
        ])
        for i, (f, imp) in enumerate(list(factor_importance.items())[:15]):
            lines.append(f"  {i+1:2d}. {f:30s}: {imp:.4f}")

    report = "\n".join(lines)

    report_path = os.path.join(output_dir, 'backtest_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return report


def main():
    OUTPUT_DIR = 'output/enhanced_backtest'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    START_DATE = '20240101'
    END_DATE = '20260320'

    logger.info("=" * 60)
    logger.info("Phase 6: Enhanced Backtest 2024-2026")
    logger.info("=" * 60)

    # Step 1: Generate signals with regime-aware strategy
    logger.info("\nStep 1: Generating regime-aware signals...")
    config = RegimeAwareConfig(
        top_n=30,
        train_lookback=252,
        min_train_samples=3000,
        retrain_freq=21,
        prediction_horizon=5,
        industry_neutral=True,
        use_regime_weights=True,
    )
    strategy = RegimeAwareStrategy(config)
    result = strategy.run_backtest_preparation(START_DATE, END_DATE)

    signals_df = result['signals']
    regime_stats = result['regime_stats']
    factor_importance = result['factor_importance']

    if signals_df.empty:
        logger.error("No signals generated!")
        return

    logger.info(f"Signals generated: {len(signals_df)} total, "
               f"{signals_df['trade_date'].nunique()} dates")

    # Step 2: Load price data
    logger.info("\nStep 2: Loading price data...")
    price_df = load_price_data(START_DATE, END_DATE)
    benchmark_df = load_benchmark(START_DATE, END_DATE)

    # Step 3: Simulate portfolio
    logger.info("\nStep 3: Simulating portfolio...")
    portfolio_df = simulate_portfolio(
        signals_df, price_df,
        top_n=30, rebalance_freq=5, transaction_cost=0.001
    )

    # Step 4: Load regime data for performance breakdown
    logger.info("\nStep 4: Loading regime classification...")
    regime_df, detector = load_and_detect_regimes(START_DATE, END_DATE)
    regime_map = regime_df.set_index('trade_date')['regime']

    # Step 5: Compute metrics
    logger.info("\nStep 5: Computing performance metrics...")
    port_returns = portfolio_df.set_index('trade_date')['portfolio_return']
    bench_returns = benchmark_df.set_index('trade_date')['pct_chg'] / 100

    metrics = compute_performance_metrics(port_returns, bench_returns, regime_map)

    # Step 6: Generate report
    logger.info("\nStep 6: Generating report and charts...")
    report = generate_report(metrics, regime_stats, factor_importance, OUTPUT_DIR)
    print("\n" + report)

    # Step 7: Generate charts
    try:
        chart_path = plot_results(portfolio_df, benchmark_df, regime_df, OUTPUT_DIR)
        logger.info(f"Charts saved to {chart_path}")
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")

    # Step 8: Save data
    signals_df.to_csv(os.path.join(OUTPUT_DIR, 'signals.csv'), index=False)
    portfolio_df.to_csv(os.path.join(OUTPUT_DIR, 'portfolio_returns.csv'), index=False)
    regime_df.to_csv(os.path.join(OUTPUT_DIR, 'regime_classification.csv'), index=False)

    with open(os.path.join(OUTPUT_DIR, 'metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"\nAll outputs saved to {OUTPUT_DIR}/")
    return metrics


if __name__ == '__main__':
    main()
