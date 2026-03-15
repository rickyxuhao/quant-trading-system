#!/usr/bin/env python3
"""
茅台-五粮液配对交易策略 - 参数优化回测

测试不同的Z-score阈值组合，寻找最优参数
"""

import sys
from datetime import datetime
from pathlib import Path

import backtrader as bt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from core.data_access.tushare.client import TushareClient
from core.logger import init_logging, get_logger
from projects.quant_trading.strategies.base_strategy import (
    StrategyConfig, create_cerebro, ChinaCommissionScheme
)
from projects.quant_trading.strategies.statistical_arbitrage import MaotaiWuliangStrategy

init_logging()
logger = get_logger(__name__)


def fetch_stock_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从Tushare获取股票数据"""
    client = TushareClient()
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    df_price = client.get_daily(ts_code, start_fmt, end_fmt)

    df_price = df_price.rename(columns={
        "trade_date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
    })
    df_price["date"] = pd.to_datetime(df_price["date"])
    df_price = df_price.sort_values("date").set_index("date")
    df_price = df_price[["open", "high", "low", "close", "volume"]]

    return df_price


def create_data_feed(df: pd.DataFrame, name: str) -> bt.feeds.PandasData:
    """创建Backtrader数据feed"""
    return bt.feeds.PandasData(
        dataname=df,
        name=name,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,
    )


def run_single_backtest(
    maotai_df: pd.DataFrame,
    wuliang_df: pd.DataFrame,
    entry_threshold: float,
    exit_threshold: float,
    stop_threshold: float,
    lookback: int = 60,
    initial_capital: float = 1_000_000,
) -> dict:
    """运行单次回测"""

    config = StrategyConfig(
        initial_capital=initial_capital,
        commission_rate=0.00025,
        stamp_duty_rate=0.001,
        slippage=0.0005,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        max_drawdown_pct=0.15,
        rebalance_frequency="daily",
    )

    cerebro = create_cerebro(config)

    maotai_feed = create_data_feed(maotai_df, "maotai")
    wuliang_feed = create_data_feed(wuliang_df, "wuliang")

    cerebro.adddata(maotai_feed, name="maotai")
    cerebro.adddata(wuliang_feed, name="wuliang")

    cerebro.addstrategy(
        MaotaiWuliangStrategy,
        config=config,
        verbose=False,
        lookback=lookback,
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        stop_threshold=stop_threshold,
        position_pct=0.1,
    )

    cerebro.broker.setcash(initial_capital)
    comminfo = ChinaCommissionScheme(
        commission=config.commission_rate,
        stamp_duty=config.stamp_duty_rate,
    )
    cerebro.broker.addcommissioninfo(comminfo, name="maotai")
    cerebro.broker.addcommissioninfo(comminfo, name="wuliang")

    results = cerebro.run()
    strategy = results[0]

    final_value = cerebro.broker.getvalue()
    pnl = final_value - initial_capital
    pnl_pct = pnl / initial_capital * 100

    sharpe = strategy.analyzers.sharpe.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    returns = strategy.analyzers.returns.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()

    total_trades = trades.get("total", {}).get("total", 0) if trades else 0
    won_trades = trades.get("won", {}).get("total", 0) if trades else 0
    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0

    return {
        "entry_threshold": entry_threshold,
        "exit_threshold": exit_threshold,
        "stop_threshold": stop_threshold,
        "lookback": lookback,
        "final_value": final_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "sharpe_ratio": sharpe.get("sharperatio", 0) or 0,
        "max_drawdown": drawdown.get("max", {}).get("drawdown", 0) or 0,
        "annual_return": returns.get("rnorm100", 0) or 0,
        "total_trades": total_trades,
        "won_trades": won_trades,
        "win_rate": win_rate,
    }


def main():
    start_date = "2019-01-01"
    end_date = "2024-12-31"
    initial_capital = 1_000_000

    logger.info("=" * 80)
    logger.info("茅台-五粮液配对交易策略 - 参数优化")
    logger.info("=" * 80)

    # 获取数据
    logger.info("获取数据...")
    maotai_df = fetch_stock_data("600519.SH", start_date, end_date)
    wuliang_df = fetch_stock_data("000858.SZ", start_date, end_date)

    # 测试不同的参数组合
    param_combinations = [
        # 更激进的阈值 (更早入场，更晚出场)
        {"entry": 1.5, "exit": 0.0, "stop": 3.0, "lookback": 60},
        {"entry": 1.5, "exit": 0.3, "stop": 3.0, "lookback": 60},
        {"entry": 1.8, "exit": 0.0, "stop": 3.0, "lookback": 60},
        {"entry": 1.8, "exit": 0.3, "stop": 3.0, "lookback": 60},
        # 不同的回望窗口
        {"entry": 1.5, "exit": 0.0, "stop": 3.0, "lookback": 40},
        {"entry": 1.5, "exit": 0.0, "stop": 3.0, "lookback": 80},
        # 更保守的止损
        {"entry": 1.5, "exit": 0.0, "stop": 2.5, "lookback": 60},
        # 原参数对比
        {"entry": 2.0, "exit": 0.5, "stop": 3.5, "lookback": 60},
    ]

    results = []

    for i, params in enumerate(param_combinations, 1):
        logger.info(f"\n测试参数组合 {i}/{len(param_combinations)}: "
                   f"entry={params['entry']}, exit={params['exit']}, "
                   f"stop={params['stop']}, lookback={params['lookback']}")

        result = run_single_backtest(
            maotai_df, wuliang_df,
            entry_threshold=params["entry"],
            exit_threshold=params["exit"],
            stop_threshold=params["stop"],
            lookback=params["lookback"],
            initial_capital=initial_capital,
        )
        results.append(result)

        logger.info(f"  盈亏: {result['pnl_pct']:.2f}%, 夏普: {result['sharpe_ratio']:.3f}, "
                   f"交易: {result['total_trades']}, 胜率: {result['win_rate']:.1f}%")

    # 结果汇总
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("pnl_pct", ascending=False)

    logger.info("\n" + "=" * 80)
    logger.info("参数优化结果排名（按收益率）")
    logger.info("=" * 80)

    for idx, row in results_df.iterrows():
        logger.info(
            f"参数: entry={row['entry_threshold']:.1f}, exit={row['exit_threshold']:.1f}, "
            f"stop={row['stop_threshold']:.1f}, lookback={row['lookback']} | "
            f"收益: {row['pnl_pct']:+.2f}%, 夏普: {row['sharpe_ratio']:.3f}, "
            f"回撤: {row['max_drawdown']:.2f}%, 交易: {row['total_trades']}, "
            f"胜率: {row['win_rate']:.1f}%"
        )

    # 选择最优参数重新运行并绘图
    best_params = results_df.iloc[0]
    logger.info("\n" + "=" * 80)
    logger.info("最优参数详细结果")
    logger.info("=" * 80)
    logger.info(f"Entry Threshold: {best_params['entry_threshold']}")
    logger.info(f"Exit Threshold: {best_params['exit_threshold']}")
    logger.info(f"Stop Threshold: {best_params['stop_threshold']}")
    logger.info(f"Lookback Window: {best_params['lookback']}")
    logger.info(f"Total PnL: {best_params['pnl_pct']:+.2f}%")
    logger.info(f"Sharpe Ratio: {best_params['sharpe_ratio']:.3f}")
    logger.info(f"Max Drawdown: {best_params['max_drawdown']:.2f}%")
    logger.info(f"Total Trades: {best_params['total_trades']}")
    logger.info(f"Win Rate: {best_params['win_rate']:.1f}%")

    # 保存结果
    results_df.to_csv("pair_trading_optimization_results.csv", index=False)
    logger.info("\n结果已保存到: pair_trading_optimization_results.csv")

    return results_df


if __name__ == "__main__":
    main()
