"""
回测框架 - 可视化模块
生成回测结果图表
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from pathlib import Path
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class BacktestVisualizer:
    """回测结果可视化器
    
    用于生成回测报告的各类图表，包括：
    - 净值曲线
    - 回撤曲线
    - 月度收益热力图
    - 交易统计
    """

    def __init__(self, figsize: Tuple[int, int] = (14, 10), dpi: int = 150):
        """初始化可视化器
        
        Args:
            figsize: 图表尺寸
            dpi: 分辨率
        """
        self.figsize = figsize
        self.dpi = dpi
        logger.debug(f"可视化器初始化: figsize={figsize}, dpi={dpi}")

    def plot_report(
        self,
        nav_history: List[Tuple[datetime, float]],
        benchmark_nav: Optional[List[Tuple[datetime, float]]] = None,
        trades_df: Optional[pd.DataFrame] = None,
        title: str = "回测报告",
        save_path: Optional[str] = None
    ) -> None:
        """生成完整回测报告图表
        
        Args:
            nav_history: 净值历史 [(date, nav), ...]
            benchmark_nav: 基准净值历史 [(date, nav), ...]
            trades_df: 交易记录DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        try:
            fig = plt.figure(figsize=self.figsize)
            gs = GridSpec(3, 2, height_ratios=[2, 1, 1], hspace=0.3)

            ax1 = fig.add_subplot(gs[0, :])
            ax2 = fig.add_subplot(gs[1, :])
            ax3 = fig.add_subplot(gs[2, 0])
            ax4 = fig.add_subplot(gs[2, 1])

            self._plot_nav_curve(ax1, nav_history, benchmark_nav, title)
            self._plot_drawdown(ax2, nav_history, benchmark_nav)
            self._plot_monthly_returns(ax3, nav_history)
            self._plot_trade_stats(ax4, trades_df)

            if save_path:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
                logger.info(f"图表已保存: {save_path}")
            else:
                plt.show()

            plt.close()
        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            raise

    def _plot_nav_curve(
        self,
        ax: plt.Axes,
        nav_history: List[Tuple[datetime, float]],
        benchmark_nav: Optional[List[Tuple[datetime, float]]],
        title: str
    ) -> None:
        """绘制净值曲线"""
        df = pd.DataFrame(nav_history, columns=['date', 'nav'])
        df = df.sort_values('date')

        ax.plot(df['date'], df['nav'], label='Strategy', linewidth=1.5, color='blue')

        if benchmark_nav:
            bench_df = pd.DataFrame(benchmark_nav, columns=['date', 'nav'])
            bench_df = bench_df.sort_values('date')
            bench_df['nav'] = bench_df['nav'] / bench_df['nav'].iloc[0] * df['nav'].iloc[0]
            ax.plot(bench_df['date'], bench_df['nav'], label='CSI 300',
                   linewidth=1.5, color='orange', linestyle='--', alpha=0.7)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Net Value')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    def _plot_drawdown(
        self,
        ax: plt.Axes,
        nav_history: List[Tuple[datetime, float]],
        benchmark_nav: Optional[List[Tuple[datetime, float]]]
    ) -> None:
        """绘制回撤曲线"""
        df = pd.DataFrame(nav_history, columns=['date', 'nav'])
        df = df.sort_values('date')
        df['peak'] = df['nav'].cummax()
        df['drawdown'] = (df['nav'] - df['peak']) / df['peak'] * 100

        ax.fill_between(df['date'], df['drawdown'], 0, alpha=0.3, color='red')
        ax.plot(df['date'], df['drawdown'], color='red', linewidth=1)

        if benchmark_nav:
            bench_df = pd.DataFrame(benchmark_nav, columns=['date', 'nav'])
            bench_df = bench_df.sort_values('date')
            bench_df['peak'] = bench_df['nav'].cummax()
            bench_df['drawdown'] = (bench_df['nav'] - bench_df['peak']) / bench_df['peak'] * 100
            ax.plot(bench_df['date'], bench_df['drawdown'], color='orange',
                   linewidth=1, linestyle='--', alpha=0.7)

        ax.set_title('Drawdown (%)', fontsize=12)
        ax.set_ylabel('Drawdown %')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    def _plot_monthly_returns(self, ax: plt.Axes, nav_history: List[Tuple[datetime, float]]) -> None:
        """绘制月度收益热力图"""
        df = pd.DataFrame(nav_history, columns=['date', 'nav'])
        df['month'] = df['date'].dt.to_period('M')

        monthly = df.groupby('month').agg({'nav': ['first', 'last']}).reset_index()
        monthly.columns = ['month', 'start_nav', 'end_nav']
        monthly['return'] = (monthly['end_nav'] / monthly['start_nav'] - 1) * 100

        monthly['year'] = monthly['month'].dt.year
        monthly['mon'] = monthly['month'].dt.month

        pivot = monthly.pivot(index='year', columns='mon', values='return')
        pivot = pivot.fillna(0)

        im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto', vmin=-10, vmax=10)

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)

        ax.set_title('Monthly Returns (%)', fontsize=12)
        ax.set_xlabel('Month')
        ax.set_ylabel('Year')

        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.iloc[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f'{val:.1f}', ha="center", va="center",
                           color="black", fontsize=7)

        plt.colorbar(im, ax=ax)

    def _plot_trade_stats(self, ax: plt.Axes, trades_df: Optional[pd.DataFrame]) -> None:
        """绘制交易统计"""
        ax.axis('off')

        if trades_df is None or trades_df.empty:
            ax.text(0.5, 0.5, 'No trades', ha='center', va='center', fontsize=12)
            return

        buy_count = len(trades_df[trades_df['action'] == 'buy'])
        sell_count = len(trades_df[trades_df['action'] == 'sell'])
        total_commission = trades_df['commission'].sum() if 'commission' in trades_df.columns else 0
        total_slippage = trades_df['slippage'].sum() if 'slippage' in trades_df.columns else 0

        stats_text = f"""Trade Statistics:

Buy Orders: {buy_count}
Sell Orders: {sell_count}
Total Trades: {len(trades_df)}

Total Commission: ¥{total_commission:,.2f}
Total Slippage: ¥{total_slippage:,.2f}
Total Cost: ¥{total_commission + total_slippage:,.2f}
"""

        ax.text(0.1, 0.9, stats_text, ha='left', va='top', fontsize=10, family='monospace')

    def plot_simple_nav(
        self,
        nav_history: List[Tuple[datetime, float]],
        benchmark_nav: Optional[List[Tuple[datetime, float]]] = None,
        title: str = "Net Value Curve",
        save_path: Optional[str] = None
    ) -> None:
        """绘制简单净值曲线
        
        Args:
            nav_history: 净值历史
            benchmark_nav: 基准净值历史
            title: 标题
            save_path: 保存路径
        """
        try:
            fig, ax = plt.subplots(figsize=(12, 6))

            df = pd.DataFrame(nav_history, columns=['date', 'nav'])
            df = df.sort_values('date')
            ax.plot(df['date'], df['nav'], label='Strategy', linewidth=1.5, color='blue')

            if benchmark_nav:
                bench_df = pd.DataFrame(benchmark_nav, columns=['date', 'nav'])
                bench_df = bench_df.sort_values('date')
                bench_df['nav'] = bench_df['nav'] / bench_df['nav'].iloc[0] * df['nav'].iloc[0]
                ax.plot(bench_df['date'], bench_df['nav'], label='CSI 300',
                       linewidth=1.5, color='orange', linestyle='--', alpha=0.7)

            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('Net Value')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_path:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
                logger.info(f"图表已保存: {save_path}")
            else:
                plt.show()

            plt.close()
        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            raise


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    import random

    dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
    nav = 1.0
    nav_history = []

    for date in dates:
        ret = random.gauss(0.0005, 0.02)
        nav *= (1 + ret)
        nav_history.append((date, nav))

    bench_nav = 1.0
    benchmark_nav = []
    for date in dates:
        ret = random.gauss(0.0003, 0.015)
        bench_nav *= (1 + ret)
        benchmark_nav.append((date, bench_nav))

    viz = BacktestVisualizer()
    viz.plot_report(nav_history, benchmark_nav, title="Test Strategy",
                   save_path="/tmp/test_backtest.png")
    print("测试图表已生成")
