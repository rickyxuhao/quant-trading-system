#!/usr/bin/env python3
"""
茅台-五粮液配对交易策略回测运行脚本

Usage:
    python run_pair_backtest.py [--start 2019-01-01] [--end 2024-12-31] [--capital 1000000]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import backtrader as bt
import pandas as pd

# Add project root to path
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
    """
    从Tushare获取股票数据

    Args:
        ts_code: 股票代码 (e.g., "600519.SH")
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data
    """
    client = TushareClient()

    # Convert dates to YYYYMMDD format
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    logger.info(f"Fetching data for {ts_code} from {start_date} to {end_date}")

    # Get daily price data
    df_price = client.get_daily(ts_code, start_fmt, end_fmt)

    if df_price.empty:
        raise ValueError(f"No data returned for {ts_code}")

    # Rename columns to match Backtrader format
    df_price = df_price.rename(columns={
        "trade_date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
    })

    # Convert date to datetime
    df_price["date"] = pd.to_datetime(df_price["date"])

    # Sort by date
    df_price = df_price.sort_values("date").set_index("date")

    # Select required columns for Backtrader
    df_price = df_price[["open", "high", "low", "close", "volume"]]

    logger.info(f"Fetched {len(df_price)} records for {ts_code}")

    return df_price


def create_data_feed(df: pd.DataFrame, name: str) -> bt.feeds.PandasData:
    """
    创建Backtrader数据feed

    Args:
        df: DataFrame with OHLCV data
        name: Data feed name

    Returns:
        Backtrader PandasData feed
    """
    return bt.feeds.PandasData(
        dataname=df,
        name=name,
        datetime=None,  # Use index as datetime
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,  # No open interest
    )


def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    verbose: bool = False
):
    """
    运行回测

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        initial_capital: 初始资金
        verbose: 是否输出详细日志
    """
    logger.info("=" * 60)
    logger.info("茅台-五粮液配对交易策略回测")
    logger.info("=" * 60)
    logger.info(f"回测区间: {start_date} 至 {end_date}")
    logger.info(f"初始资金: {initial_capital:,.2f}")

    # 获取数据
    try:
        maotai_df = fetch_stock_data("600519.SH", start_date, end_date)
        wuliang_df = fetch_stock_data("000858.SZ", start_date, end_date)
    except Exception as e:
        logger.error(f"数据获取失败: {e}")
        raise

    # 检查数据对齐
    common_dates = maotai_df.index.intersection(wuliang_df.index)
    if len(common_dates) < 60:
        raise ValueError(f"共同交易日太少: {len(common_dates)} 天")

    logger.info(f"共同交易日: {len(common_dates)} 天")

    # 创建数据feed
    maotai_feed = create_data_feed(maotai_df, "maotai")
    wuliang_feed = create_data_feed(wuliang_df, "wuliang")

    # 策略配置
    config = StrategyConfig(
        initial_capital=initial_capital,
        commission_rate=0.00025,  # 0.025%
        stamp_duty_rate=0.001,    # 0.1% (sell only)
        slippage=0.0005,          # 0.05%
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

    # 添加策略
    cerebro.addstrategy(
        MaotaiWuliangStrategy,
        config=config,
        verbose=verbose,
        lookback=60,
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_threshold=3.5,
        position_pct=0.1,
    )

    # 设置初始资金
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
    cerebro.addobserver(bt.observers.Trades)

    # 运行回测
    logger.info("开始回测...")
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

    logger.info("=" * 60)
    logger.info("回测结果")
    logger.info("=" * 60)
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

    logger.info("=" * 60)

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


def main():
    parser = argparse.ArgumentParser(description="茅台-五粮液配对交易策略回测")
    parser.add_argument(
        "--start",
        type=str,
        default="2019-01-01",
        help="开始日期 (YYYY-MM-DD)，默认 2019-01-01",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="结束日期 (YYYY-MM-DD)，默认 2024-12-31",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=1_000_000,
        help="初始资金，默认 1,000,000",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出详细日志",
    )

    args = parser.parse_args()

    # Validate dates
    try:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end, "%Y-%m-%d")
        if start >= end:
            raise ValueError("开始日期必须早于结束日期")
    except ValueError as e:
        logger.error(f"日期格式错误: {e}")
        sys.exit(1)

    try:
        results = run_backtest(
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            verbose=args.verbose,
        )

        # 保存结果
        result_df = pd.DataFrame([results])
        result_file = f"backtest_result_{args.start}_{args.end}.csv"
        result_df.to_csv(result_file, index=False)
        logger.info(f"结果已保存到: {result_file}")

    except Exception as e:
        logger.error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
