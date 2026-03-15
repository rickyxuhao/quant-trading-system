#!/usr/bin/env python3
"""
使用最优参数运行茅台-五粮液配对交易策略回测

最优参数（基于参数优化结果）:
- entry_threshold: 1.5
- exit_threshold: 0.0
- stop_threshold: 3.0
- lookback: 40
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

    logger.info(f"Fetching data for {ts_code} from {start_date} to {end_date}")

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

    logger.info(f"Fetched {len(df_price)} records for {ts_code}")
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


def run_optimal_backtest(
    start_date: str = "2019-01-01",
    end_date: str = "2024-12-31",
    initial_capital: float = 1_000_000,
):
    """使用最优参数运行回测"""

    # 最优参数
    OPTIMAL_PARAMS = {
        "entry_threshold": 1.5,
        "exit_threshold": 0.0,
        "stop_threshold": 3.0,
        "lookback": 40,
    }

    logger.info("=" * 80)
    logger.info("茅台-五粮液配对交易策略回测 - 最优参数")
    logger.info("=" * 80)
    logger.info(f"回测区间: {start_date} 至 {end_date}")
    logger.info(f"初始资金: {initial_capital:,.2f}")
    logger.info(f"\n最优参数配置:")
    logger.info(f"  Entry Threshold: {OPTIMAL_PARAMS['entry_threshold']}")
    logger.info(f"  Exit Threshold: {OPTIMAL_PARAMS['exit_threshold']}")
    logger.info(f"  Stop Threshold: {OPTIMAL_PARAMS['stop_threshold']}")
    logger.info(f"  Lookback Window: {OPTIMAL_PARAMS['lookback']}")

    # 获取数据
    maotai_df = fetch_stock_data("600519.SH", start_date, end_date)
    wuliang_df = fetch_stock_data("000858.SZ", start_date, end_date)

    common_dates = maotai_df.index.intersection(wuliang_df.index)
    logger.info(f"\n共同交易日: {len(common_dates)} 天")

    # 创建数据feed
    maotai_feed = create_data_feed(maotai_df, "maotai")
    wuliang_feed = create_data_feed(wuliang_df, "wuliang")

    # 策略配置
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

    # 创建Cerebro引擎
    cerebro = create_cerebro(config)

    # 添加数据
    cerebro.adddata(maotai_feed, name="maotai")
    cerebro.adddata(wuliang_feed, name="wuliang")

    # 添加策略（使用最优参数）
    cerebro.addstrategy(
        MaotaiWuliangStrategy,
        config=config,
        verbose=False,
        lookback=OPTIMAL_PARAMS["lookback"],
        entry_threshold=OPTIMAL_PARAMS["entry_threshold"],
        exit_threshold=OPTIMAL_PARAMS["exit_threshold"],
        stop_threshold=OPTIMAL_PARAMS["stop_threshold"],
        position_pct=0.1,
    )

    cerebro.broker.setcash(initial_capital)

    # 添加佣金方案
    comminfo = ChinaCommissionScheme(
        commission=config.commission_rate,
        stamp_duty=config.stamp_duty_rate,
    )
    cerebro.broker.addcommissioninfo(comminfo, name="maotai")
    cerebro.broker.addcommissioninfo(comminfo, name="wuliang")

    # 添加观察者
    cerebro.addobserver(bt.observers.Value)
    cerebro.addobserver(bt.observers.DrawDown)

    # 运行回测
    logger.info("\n开始回测...")
    results = cerebro.run()
    strategy = results[0]

    # 输出结果
    final_value = cerebro.broker.getvalue()
    pnl = final_value - initial_capital
    pnl_pct = pnl / initial_capital * 100

    # 获取分析器结果
    sharpe = strategy.analyzers.sharpe.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    returns = strategy.analyzers.returns.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()

    logger.info("=" * 80)
    logger.info("回测结果")
    logger.info("=" * 80)
    logger.info(f"初始资金: {initial_capital:,.2f}")
    logger.info(f"最终资金: {final_value:,.2f}")
    logger.info(f"总盈亏:   {pnl:,.2f} ({pnl_pct:+.2f}%)")
    logger.info(f"")
    logger.info(f"年化收益: {returns.get('rnorm100', 0):.2f}%")
    logger.info(f"夏普比率: {sharpe.get('sharperatio', 0):.3f}")
    logger.info(f"最大回撤: {drawdown.get('max', {}).get('drawdown', 0):.2f}%")
    logger.info(f"回撤金额: {drawdown.get('max', {}).get('moneydown', 0):,.2f}")
    logger.info(f"")

    # 交易统计
    if trades:
        total_trades = trades.get('total', {}).get('total', 0)
        won_trades = trades.get('won', {}).get('total', 0)
        lost_trades = trades.get('lost', {}).get('total', 0)

        if total_trades > 0:
            win_rate = won_trades / total_trades * 100
            logger.info(f"总交易次数: {total_trades}")
            logger.info(f"盈利交易: {won_trades}")
            logger.info(f"亏损交易: {lost_trades}")
            logger.info(f"胜率: {win_rate:.1f}%")

            if won_trades > 0:
                avg_win = trades.get('won', {}).get('pnl', {}).get('average', 0)
                logger.info(f"平均盈利: {avg_win:,.2f}")

            if lost_trades > 0:
                avg_loss = trades.get('lost', {}).get('pnl', {}).get('average', 0)
                logger.info(f"平均亏损: {avg_loss:,.2f}")

            # 盈亏比
            if won_trades > 0 and lost_trades > 0:
                profit_factor = abs(avg_win * won_trades / (avg_loss * lost_trades))
                logger.info(f"盈亏比: {profit_factor:.2f}")

    logger.info("=" * 80)

    # 绘图
    try:
        cerebro.plot(style="candlestick", barup="red", bardown="green")
    except Exception as e:
        logger.warning(f"绘图失败: {e}")

    return {
        "initial_capital": initial_capital,
        "final_value": final_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "sharpe_ratio": sharpe.get("sharperatio", 0),
        "max_drawdown": drawdown.get("max", {}).get("drawdown", 0),
        "annual_return": returns.get("rnorm100", 0),
        "total_trades": trades.get("total", {}).get("total", 0) if trades else 0,
    }


if __name__ == "__main__":
    results = run_optimal_backtest()

    # 保存结果
    result_df = pd.DataFrame([results])
    result_file = "optimal_backtest_result.csv"
    result_df.to_csv(result_file, index=False)
    logger.info(f"\n结果已保存到: {result_file}")
