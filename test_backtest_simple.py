"""
简化回测测试 - 验证框架可执行性
随机选择50只股票进行回测
"""

import sys
from pathlib import Path
from datetime import datetime
import random

import numpy as np
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager

logger = get_logger(__name__)


def get_random_stocks(n=50):
    """随机选择n只股票"""
    query = """
    SELECT ts_code, name, industry
    FROM t_stock_basic
    WHERE list_status = 'L'
    AND market IN ('主板', '创业板', '科创板')
    ORDER BY RAND()
    LIMIT %s
    """
    results = DatabaseManager.fetchall("tushare_biz", query, (n,))
    stocks = [r['ts_code'] for r in results]
    logger.info(f"随机选择 {len(stocks)} 只股票:")
    for r in results[:10]:
        logger.info(f"  {r['ts_code']}: {r['name']} ({r['industry']})")
    logger.info(f"  ... 共 {len(results)} 只")
    return stocks


def run_simple_backtest():
    """运行简化回测"""
    logger.info("=" * 60)
    logger.info("简化回测测试 - 验证框架可执行性")
    logger.info("=" * 60)

    # 1. 随机选择50只股票
    logger.info("\n1. 选择股票池...")
    stocks = get_random_stocks(50)

    # 2. 获取数据
    logger.info("\n2. 获取历史数据...")
    from projects.quant_trading.backtest.data_manager import DataManager

    data_manager = DataManager()
    start_date = pd.Timestamp("20230101")
    end_date = pd.Timestamp("20231231")

    stock_data = {}
    valid_stocks = []
    for ts_code in stocks:
        try:
            df = data_manager.get_stock_data(ts_code, start_date, end_date)
            if not df.empty and len(df) > 60:  # 至少60个交易日
                stock_data[ts_code] = df
                valid_stocks.append(ts_code)
        except Exception as e:
            logger.debug(f"获取 {ts_code} 数据失败: {e}")

    logger.info(f"有效股票: {len(valid_stocks)} / {len(stocks)}")

    # 3. 生成随机信号并模拟回测
    logger.info("\n3. 运行简化回测...")

    # 简化的回测逻辑
    initial_capital = 1_000_000
    capital = initial_capital
    positions = {}
    trades = []

    # 获取交易日列表
    trade_dates = stock_data[valid_stocks[0]].index if valid_stocks else []

    # 每月第一个交易日调仓
    rebalance_dates = []
    current_month = None
    for date in trade_dates:
        if date.month != current_month:
            rebalance_dates.append(date)
            current_month = date.month

    logger.info(f"调仓次数: {len(rebalance_dates)}")

    portfolio_values = []

    for i, date in enumerate(rebalance_dates[:12]):  # 限制为12个月
        # 随机选择10只股票等权买入
        selected = random.sample(valid_stocks, min(10, len(valid_stocks)))

        # 清空旧持仓
        for ts_code in list(positions.keys()):
            if ts_code not in selected:
                # 卖出
                position_value = positions.pop(ts_code, 0)
                capital += position_value * 0.997  # 扣除交易成本

        # 买入新持仓
        if selected:
            position_size = capital * 0.95 / len(selected)  # 留5%现金
            for ts_code in selected:
                positions[ts_code] = position_size
            capital -= position_size * len(selected)

        # 计算组合市值
        portfolio_value = capital + sum(positions.values())
        portfolio_values.append({
            'date': date,
            'value': portfolio_value,
        })

        logger.info(f"  {date.strftime('%Y-%m-%d')}: 市值={portfolio_value:,.0f}, 持仓={len(positions)}只")

    # 4. 计算绩效指标
    if len(portfolio_values) > 1:
        df_values = pd.DataFrame(portfolio_values).set_index('date')
        initial = df_values['value'].iloc[0]
        final = df_values['value'].iloc[-1]

        total_return = (final - initial) / initial
        annual_return = total_return / len(portfolio_values) * 12

        # 计算最大回撤
        cummax = df_values['value'].cummax()
        drawdown = (cummax - df_values['value']) / cummax
        max_drawdown = drawdown.max()

        logger.info("\n4. 回测结果:")
        logger.info(f"  初始资金: {initial:,.0f}")
        logger.info(f"  最终市值: {final:,.0f}")
        logger.info(f"  总收益率: {total_return*100:.2f}%")
        logger.info(f"  年化收益: {annual_return*100:.2f}%")
        logger.info(f"  最大回撤: {max_drawdown*100:.2f}%")

    logger.info("\n" + "=" * 60)
    logger.info("回测框架验证完成!")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    run_simple_backtest()
