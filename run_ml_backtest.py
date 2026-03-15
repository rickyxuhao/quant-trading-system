#!/usr/bin/env python3
"""
机器学习策略回测运行脚本

Usage:
    python run_ml_backtest.py --symbol 000001.SH --model xgboost [--start 2019-01-01] [--end 2024-12-31]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import backtrader as bt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from core.data_access.tushare.client import TushareClient
from core.logger import init_logging, get_logger
from projects.quant_trading.strategies.ml_prediction import (
    FeatureEngineer, TechnicalFeatureConfig, MLStrategy, MLStrategyConfig
)

init_logging()
logger = get_logger(__name__)


def fetch_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取股票数据"""
    client = TushareClient()
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    logger.info(f"获取数据: {ts_code} [{start_date} 至 {end_date}]")
    df = client.get_daily(ts_code, start_fmt, end_fmt)

    df = df.rename(columns={
        "trade_date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    df = df[["open", "high", "low", "close", "volume"]]

    logger.info(f"获取到 {len(df)} 条数据")
    return df


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


def run_ml_backtest(
    symbol: str,
    model_type: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    train_first: bool = True,
):
    """运行ML策略回测"""
    logger.info("=" * 80)
    logger.info(f"机器学习策略回测 - {model_type.upper()}")
    logger.info("=" * 80)
    logger.info(f"标的: {symbol}")
    logger.info(f"区间: {start_date} 至 {end_date}")
    logger.info(f"初始资金: {initial_capital:,.2f}")

    # 获取数据
    df = fetch_data(symbol, start_date, end_date)

    if len(df) < 500:
        raise ValueError(f"数据不足: {len(df)} 条")

    # 预训练模型（可选）
    model_path = None
    if train_first:
        logger.info("\n预训练模型...")
        feature_eng = FeatureEngineer(TechnicalFeatureConfig())
        features = feature_eng.create_features(df)
        target = feature_eng.create_target(features, horizon=1, target_type='direction')

        # 数据划分
        train_size = int(len(features) * 0.6)
        val_size = int(len(features) * 0.2)

        X_train = features.iloc[:train_size]
        y_train = target.iloc[:train_size]
        X_val = features.iloc[train_size:train_size+val_size]
        y_val = target.iloc[train_size:train_size+val_size]

        # 移除NaN
        train_mask = y_train.notna()
        X_train, y_train = X_train[train_mask], y_train[train_mask]
        val_mask = y_val.notna()
        X_val, y_val = X_val[val_mask], y_val[val_mask]

        # 映射标签: -1->0, 0->1, 1->2 (XGBoost需要非负整数标签)
        label_map = {-1: 0, 0: 1, 1: 2}
        y_train = y_train.map(label_map)
        y_val = y_val.map(label_map)

        logger.info(f"训练集: {len(X_train)}, 验证集: {len(X_val)}")

        if model_type == 'xgboost':
            from projects.quant_trading.strategies.ml_prediction import XGBoostModel, XGBoostConfig
            model = XGBoostModel(XGBoostConfig(
                objective='multi:softprob',
                num_class=3,
                eval_metric='mlogloss'
            ))
        else:
            from projects.quant_trading.strategies.ml_prediction import LSTMModel, LSTMConfig
            model = LSTMModel(LSTMConfig())

        model.fit(X_train, y_train, X_val, y_val, verbose=True)

        # 保存模型
        if model_type == 'xgboost':
            model_path = f"ml_model_{symbol.replace('.', '_')}_{model_type}.json"
        else:
            model_path = f"ml_model_{symbol.replace('.', '_')}_{model_type}.keras"
        model.save(model_path)
        logger.info(f"模型已保存: {model_path}")

        # 评估
        X_test = features.iloc[train_size+val_size:]
        y_test = target.iloc[train_size+val_size:]
        test_mask = y_test.notna()
        X_test, y_test = X_test[test_mask], y_test[test_mask]

        if len(X_test) > 0:
            # 同样映射测试集标签
            y_test = y_test.map(label_map)
            metrics = model.evaluate(X_test, y_test)
            logger.info(f"测试集指标: {metrics}")

    # 创建Backtrader回测
    from projects.quant_trading.strategies.base_strategy import create_cerebro, ChinaCommissionScheme

    config = MLStrategyConfig(
        initial_capital=initial_capital,
        confidence_threshold=0.55,
        retrain_frequency=63 if not train_first else 9999,  # 如果预训练了就不在回测中重新训练
    )

    cerebro = create_cerebro(config)

    # 添加数据
    data_feed = create_data_feed(df, symbol)
    cerebro.adddata(data_feed)

    # 添加策略
    cerebro.addstrategy(
        MLStrategy,
        config=config,
        model_type=model_type,
        model_path=model_path,
        verbose=False,
    )

    # 设置佣金
    cerebro.broker.setcash(initial_capital)
    comminfo = ChinaCommissionScheme()
    cerebro.broker.addcommissioninfo(comminfo)

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

    sharpe = strategy.analyzers.sharpe.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    returns = strategy.analyzers.returns.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()

    logger.info("=" * 80)
    logger.info("回测结果")
    logger.info("=" * 80)
    logger.info(f"初始资金: {initial_capital:,.2f}")
    logger.info(f"最终资金: {final_value:,.2f}")
    logger.info(f"总盈亏: {pnl:,.2f} ({pnl_pct:+.2f}%)")
    logger.info(f"年化收益: {returns.get('rnorm100', 0):.2f}%")
    logger.info(f"夏普比率: {sharpe.get('sharperatio', 0):.3f}")
    logger.info(f"最大回撤: {drawdown.get('max', {}).get('drawdown', 0):.2f}%")

    if trades:
        total_trades = trades.get('total', {}).get('total', 0)
        if total_trades > 0:
            won_trades = trades.get('won', {}).get('total', 0)
            win_rate = won_trades / total_trades * 100
            logger.info(f"总交易次数: {total_trades}")
            logger.info(f"胜率: {win_rate:.1f}%")

    logger.info("=" * 80)

    # 绘图
    try:
        cerebro.plot(style="candlestick")
    except Exception as e:
        logger.warning(f"绘图失败: {e}")

    return {
        'final_value': final_value,
        'pnl_pct': pnl_pct,
        'sharpe': sharpe.get('sharperatio', 0),
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0),
    }


def main():
    parser = argparse.ArgumentParser(description="机器学习策略回测")
    parser.add_argument("--symbol", type=str, default="000001.SH", help="股票代码")
    parser.add_argument("--model", type=str, default="xgboost", choices=["xgboost", "lstm"])
    parser.add_argument("--start", type=str, default="2019-01-01", help="开始日期")
    parser.add_argument("--end", type=str, default="2024-12-31", help="结束日期")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--no-pretrain", action="store_true", help="禁用预训练")

    args = parser.parse_args()

    try:
        results = run_ml_backtest(
            symbol=args.symbol,
            model_type=args.model,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            train_first=not args.no_pretrain,
        )

        # 保存结果
        result_df = pd.DataFrame([results])
        result_file = f"ml_backtest_{args.symbol}_{args.model}.csv"
        result_df.to_csv(result_file, index=False)
        logger.info(f"结果已保存: {result_file}")

    except Exception as e:
        logger.error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
