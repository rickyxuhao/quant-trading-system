"""
多策略并行回测模块

支持多种策略的并行回测与对比分析：
- 多进程并行回测
- 统一格式结果输出
- 策略对比可视化
- 结果持久化到数据库

Example:
    >>> from projects.quant_trading.backtest.multi_strategy import run_multiple_strategies
    >>>
    >>> strategies = [
    ...     ('momentum', MomentumStrategy()),
    ...     ('mean_reversion', MeanReversionStrategy()),
    ... ]
    >>> results = run_multiple_strategies(
    ...     strategies=strategies,
    ...     start_date=datetime(2024, 1, 1),
    ...     end_date=datetime(2024, 12, 31),
    ...     symbols=['000001.SZ']
    ... )
"""

import os
import multiprocessing as mp
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Callable, Union
from pathlib import Path
import json
import hashlib

import pandas as pd
import numpy as np
import backtrader as bt
import matplotlib.pyplot as plt

from core.logger import get_logger
from projects.quant_trading.backtest.data_feed import MySQLDataFeed, MultiSymbolDataFeed
from projects.quant_trading.backtest.comminfo import setup_china_stock_commission
from projects.quant_trading.backtest.analyzers import add_all_analyzers, get_analyzer_results
from projects.quant_trading.backtest.risk_config import EnhancedRiskConfig

logger = get_logger(__name__)


@dataclass
class BacktestResult:
    """
    回测结果数据类

    统一的回测结果格式，便于对比分析。
    """
    strategy_name: str
    run_id: str
    start_date: datetime
    end_date: datetime

    # 收益指标
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0

    # 风险指标
    volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # 风险调整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_holding_days: float = 0.0

    # 成本统计
    total_commission: float = 0.0
    total_slippage: float = 0.0
    cost_pct: float = 0.0

    # 净值曲线
    nav_history: List[Tuple[datetime, float]] = field(default_factory=list)

    # 交易记录
    trades: Optional[pd.DataFrame] = None

    # 详细分析结果
    analyzer_results: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        result = {
            'strategy_name': self.strategy_name,
            'run_id': self.run_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'benchmark_return': self.benchmark_return,
            'alpha': self.alpha,
            'volatility': self.volatility,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_profit': self.avg_profit,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'avg_holding_days': self.avg_holding_days,
            'total_commission': self.total_commission,
            'total_slippage': self.total_slippage,
            'cost_pct': self.cost_pct,
        }

        # 添加元数据
        result.update(self.metadata)

        return result

    def to_series(self) -> pd.Series:
        """转换为Series"""
        return pd.Series(self.to_dict())

    def calculate_score(self, risk_free_rate: float = 0.03) -> float:
        """
        计算综合评分

        综合考量收益、风险、稳定性。

        Args:
            risk_free_rate: 无风险利率

        Returns:
            综合评分
        """
        # 收益得分 (0-40)
        return_score = min(self.annual_return * 100, 40) if self.annual_return > 0 else 0

        # 风险调整收益得分 (0-30)
        sharpe_score = min(self.sharpe_ratio * 10, 30) if self.sharpe_ratio > 0 else 0

        # 回撤控制得分 (0-20)
        drawdown_score = max(0, 20 - self.max_drawdown * 100)

        # 胜率得分 (0-10)
        win_rate_score = self.win_rate * 10

        return return_score + sharpe_score + drawdown_score + win_rate_score


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: datetime
    end_date: datetime
    symbols: List[str]
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.00025
    slippage_pct: float = 0.0005
    adj_type: str = 'qfq'
    risk_config: Optional[EnhancedRiskConfig] = None
    benchmark: str = '000300.SH'


def _run_single_backtest(
    strategy_info: Tuple[str, bt.Strategy],
    config: BacktestConfig,
    data_feeds: List[MySQLDataFeed]
) -> BacktestResult:
    """
    执行单次回测（用于多进程）

    Args:
        strategy_info: (策略名称, 策略类) 元组
        config: 回测配置
        data_feeds: 数据列表

    Returns:
        BacktestResult
    """
    strategy_name, strategy_class = strategy_info

    logger.info(f"[_run_single_backtest] 开始回测: {strategy_name}")

    # 创建Cerebro
    cerebro = bt.Cerebro()

    # 添加数据
    for data_feed in data_feeds:
        cerebro.adddata(data_feed)

    # 添加策略
    cerebro.addstrategy(strategy_class)

    # 设置佣金
    setup_china_stock_commission(
        cerebro,
        initial_cash=config.initial_cash,
        commission_rate=config.commission_rate,
        slippage_pct=config.slippage_pct
    )

    # 添加分析器
    add_all_analyzers(cerebro)

    try:
        # 运行回测
        results = cerebro.run()
        result = results[0]

        # 提取结果
        backtest_result = _extract_result(
            result, strategy_name, config
        )

        logger.info(f"[_run_single_backtest] 完成回测: {strategy_name}, "
                   f"收益率={backtest_result.total_return*100:.2f}%")

        return backtest_result

    except Exception as e:
        logger.error(f"[_run_single_backtest] 回测失败 {strategy_name}: {e}")
        # 返回空结果
        return BacktestResult(
            strategy_name=strategy_name,
            run_id=_generate_run_id(strategy_name, config),
            start_date=config.start_date,
            end_date=config.end_date,
            metadata={'error': str(e)}
        )


def _extract_result(
    result,
    strategy_name: str,
    config: BacktestConfig
) -> BacktestResult:
    """
    从Backtrader结果中提取数据

    Args:
        result: Backtrader回测结果
        strategy_name: 策略名称
        config: 回测配置

    Returns:
        BacktestResult
    """
    run_id = _generate_run_id(strategy_name, config)

    # 获取分析器结果
    analyzer_results = get_analyzer_results(result)

    # 基础结果
    backtest_result = BacktestResult(
        strategy_name=strategy_name,
        run_id=run_id,
        start_date=config.start_date,
        end_date=config.end_date,
        analyzer_results=analyzer_results
    )

    # 提取收益指标
    if 'returns' in analyzer_results:
        ret = analyzer_results['returns']
        backtest_result.total_return = ret.get('rtot', 0)
        backtest_result.annual_return = ret.get('rnorm', 0)

    # 提取风险指标
    if 'drawdown' in analyzer_results:
        dd = analyzer_results['drawdown']
        backtest_result.max_drawdown = dd.get('max', {}).get('drawdown', 0)
        backtest_result.max_drawdown_duration = dd.get('max', {}).get('len', 0)

    # 提取风险调整收益
    if 'sharpe' in analyzer_results:
        backtest_result.sharpe_ratio = analyzer_results['sharpe'].get('sharperatio', 0)

    if 'sortino' in analyzer_results:
        backtest_result.sortino_ratio = analyzer_results['sortino'].get('sortino_ratio', 0)

    if 'calmar' in analyzer_results:
        backtest_result.calmar_ratio = analyzer_results['calmar'].get('calmar_ratio', 0)

    # 提取交易统计
    if 'trades' in analyzer_results:
        trades = analyzer_results['trades']
        total = trades.get('total', {})
        backtest_result.total_trades = total.get('total', 0)
        backtest_result.winning_trades = total.get('won', 0)
        backtest_result.losing_trades = total.get('lost', 0)

        if backtest_result.total_trades > 0:
            backtest_result.win_rate = backtest_result.winning_trades / backtest_result.total_trades

    # 提取详细交易记录
    if 'trade_details' in analyzer_results:
        trade_df = analyzer_results['trade_details']
        if isinstance(trade_df, pd.DataFrame) and not trade_df.empty:
            backtest_result.trades = trade_df
            backtest_result.avg_holding_days = trade_df['holding_days'].mean()

    # 提取增强交易分析
    if 'enhanced_trades' in analyzer_results:
        et = analyzer_results['enhanced_trades']
        backtest_result.profit_factor = et.get('profit_factor', 0)

    return backtest_result


def _generate_run_id(strategy_name: str, config: BacktestConfig) -> str:
    """生成运行ID"""
    unique_str = f"{strategy_name}_{config.start_date}_{config.end_date}_{config.symbols}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:12]


def run_multiple_strategies(
    strategies: List[Tuple[str, bt.Strategy]],
    config: BacktestConfig,
    parallel: bool = True,
    max_workers: Optional[int] = None
) -> List[BacktestResult]:
    """
    运行多策略回测

    Args:
        strategies: (策略名称, 策略类) 列表
        config: 回测配置
        parallel: 是否并行执行
        max_workers: 最大并行进程数，None使用CPU核心数

    Returns:
        BacktestResult列表
    """
    logger.info(f"[run_multiple_strategies] 开始回测 {len(strategies)} 个策略")

    # 加载数据（所有策略共用）
    data_manager = MultiSymbolDataFeed(
        symbols=config.symbols,
        fromdate=config.start_date,
        todate=config.end_date,
        adj_type=config.adj_type
    )
    data_feeds = data_manager.load_all()

    if not data_feeds:
        logger.error("[run_multiple_strategies] 无可用数据")
        return []

    logger.info(f"[run_multiple_strategies] 加载数据完成: {len(data_feeds)} 个标的")

    results = []

    if parallel and len(strategies) > 1:
        # 并行执行
        max_workers = max_workers or min(mp.cpu_count(), len(strategies))
        logger.info(f"[run_multiple_strategies] 使用 {max_workers} 个进程并行执行")

        with mp.Pool(processes=max_workers) as pool:
            tasks = [
                (strategy_info, config, data_feeds)
                for strategy_info in strategies
            ]
            results = pool.starmap(_run_single_backtest, tasks)
    else:
        # 串行执行
        for strategy_info in strategies:
            result = _run_single_backtest(strategy_info, config, data_feeds)
            results.append(result)

    logger.info(f"[run_multiple_strategies] 完成 {len(results)} 个策略回测")
    return results


def compare_strategies(
    results: List[BacktestResult],
    sort_by: str = 'sharpe_ratio',
    ascending: bool = False
) -> pd.DataFrame:
    """
    对比多个策略结果

    Args:
        results: BacktestResult列表
        sort_by: 排序字段
        ascending: 是否升序

    Returns:
        对比DataFrame
    """
    if not results:
        return pd.DataFrame()

    # 转换为DataFrame
    records = [r.to_dict() for r in results]
    df = pd.DataFrame(records)

    # 添加综合评分
    df['composite_score'] = [r.calculate_score() for r in results]

    # 排序
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)

    return df


def plot_comparison(
    results: List[BacktestResult],
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
):
    """
    可视化策略对比

    Args:
        results: BacktestResult列表
        save_path: 保存路径，None则显示
        figsize: 图大小
    """
    if not results:
        logger.warning("[plot_comparison] 无结果可绘制")
        return

    fig, axes = plt.subplots(2, 2, figsize=figsize)

    # 1. 净值曲线对比
    ax1 = axes[0, 0]
    for result in results:
        if result.nav_history:
            dates = [d for d, _ in result.nav_history]
            navs = [nav for _, nav in result.nav_history]
            ax1.plot(dates, navs, label=result.strategy_name, linewidth=1.5)
    ax1.set_title('NAV Comparison')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('NAV')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. 风险收益散点图
    ax2 = axes[0, 1]
    for result in results:
        ax2.scatter(result.volatility, result.annual_return,
                   s=100, label=result.strategy_name, alpha=0.7)
    ax2.set_title('Risk-Return Profile')
    ax2.set_xlabel('Volatility')
    ax2.set_ylabel('Annual Return')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax2.axvline(x=0, color='gray', linestyle='--', alpha=0.5)

    # 3. 风险调整收益对比
    ax3 = axes[1, 0]
    metrics = ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio']
    x = np.arange(len(results))
    width = 0.25

    for i, metric in enumerate(metrics):
        values = [r.to_dict().get(metric, 0) for r in results]
        ax3.bar(x + i * width, values, width, label=metric)

    ax3.set_title('Risk-Adjusted Returns')
    ax3.set_xlabel('Strategy')
    ax3.set_ylabel('Ratio')
    ax3.set_xticks(x + width)
    ax3.set_xticklabels([r.strategy_name for r in results], rotation=45)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    # 4. 交易统计对比
    ax4 = axes[1, 1]
    win_rates = [r.win_rate for r in results]
    total_trades = [r.total_trades for r in results]

    x = np.arange(len(results))
    ax4_twin = ax4.twinx()

    bars = ax4.bar(x - 0.2, win_rates, 0.4, label='Win Rate', color='steelblue')
    bars2 = ax4_twin.bar(x + 0.2, total_trades, 0.4, label='Total Trades', color='coral')

    ax4.set_title('Trading Statistics')
    ax4.set_xlabel('Strategy')
    ax4.set_ylabel('Win Rate', color='steelblue')
    ax4_twin.set_ylabel('Total Trades', color='coral')
    ax4.set_xticks(x)
    ax4.set_xticklabels([r.strategy_name for r in results], rotation=45)

    # 添加图例
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4_twin.get_legend_handles_labels()
    ax4.legend(lines1 + lines2, labels1 + labels2)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"[plot_comparison] 图表已保存: {save_path}")
    else:
        plt.show()


def save_results_to_csv(
    results: List[BacktestResult],
    output_dir: str,
    prefix: str = "backtest"
):
    """
    保存回测结果到CSV

    Args:
        results: BacktestResult列表
        output_dir: 输出目录
        prefix: 文件名前缀
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 保存汇总结果
    summary_df = compare_strategies(results)
    summary_file = output_path / f"{prefix}_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"[save_results_to_csv] 汇总结果已保存: {summary_file}")

    # 保存每个策略的详细结果
    for result in results:
        # 净值曲线
        if result.nav_history:
            nav_df = pd.DataFrame(result.nav_history, columns=['date', 'nav'])
            nav_file = output_path / f"{prefix}_{result.strategy_name}_nav.csv"
            nav_df.to_csv(nav_file, index=False)

        # 交易记录
        if result.trades is not None and not result.trades.empty:
            trades_file = output_path / f"{prefix}_{result.strategy_name}_trades.csv"
            result.trades.to_csv(trades_file, index=False)


def save_results_to_database(
    results: List[BacktestResult],
    db_connection: Any,
    table_name: str = 'backtest_results'
):
    """
    保存回测结果到数据库

    Args:
        results: BacktestResult列表
        db_connection: 数据库连接
        table_name: 表名
    """
    # 转换为DataFrame
    records = []
    for result in results:
        record = result.to_dict()
        record['created_at'] = datetime.now().isoformat()
        records.append(record)

    df = pd.DataFrame(records)

    # 写入数据库（这里使用通用的pandas方法，实际使用时可能需要适配）
    try:
        df.to_sql(table_name, db_connection, if_exists='append', index=False)
        logger.info(f"[save_results_to_database] 已保存 {len(results)} 条结果到 {table_name}")
    except Exception as e:
        logger.error(f"[save_results_to_database] 保存失败: {e}")


# 便捷函数
def quick_backtest_comparison(
    strategies: List[Tuple[str, bt.Strategy]],
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    output_dir: Optional[str] = None
) -> pd.DataFrame:
    """
    快速策略对比

    Args:
        strategies: (策略名称, 策略类) 列表
        symbols: 标的列表
        start_date: 开始日期
        end_date: 结束日期
        output_dir: 输出目录，None不保存

    Returns:
        对比DataFrame
    """
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols
    )

    # 运行回测
    results = run_multiple_strategies(strategies, config)

    # 对比结果
    comparison_df = compare_strategies(results)

    # 保存结果
    if output_dir:
        save_results_to_csv(results, output_dir)
        plot_comparison(results, save_path=f"{output_dir}/comparison.png")

    return comparison_df


if __name__ == "__main__":
    print("=== 多策略并行回测模块 ===\n")
    print("主要功能:")
    print("  - run_multiple_strategies: 多策略并行回测")
    print("  - compare_strategies: 策略结果对比")
    print("  - plot_comparison: 可视化对比")
    print("  - save_results_to_csv: 保存CSV结果")
    print("  - save_results_to_database: 保存到数据库")
