"""
Plotly 图表组件

提供持仓分析所需的各类可视化图表。

Example:
    >>> from projects.portfolio_analysis.visualization.charts import create_nav_chart
    >>> fig = create_nav_chart(nav_df, benchmark_df)
    >>> fig.show()
"""

from typing import Optional, List, Dict, Any
import logging

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from projects.portfolio_analysis.core.analyzer import PositionPnl

logger = logging.getLogger(__name__)


def create_nav_chart(
    nav_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    title: str = "净值曲线"
) -> go.Figure:
    """净值曲线对比图

    Args:
        nav_df: 策略净值DataFrame，需包含date和nav列
        benchmark_df: 基准净值DataFrame（可选）
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    fig = go.Figure()

    # 策略净值
    fig.add_trace(go.Scatter(
        x=nav_df['date'],
        y=nav_df['nav'],
        mode='lines',
        name='策略净值',
        line=dict(color='#1f77b4', width=2)
    ))

    # 基准净值
    if benchmark_df is not None and not benchmark_df.empty:
        fig.add_trace(go.Scatter(
            x=benchmark_df['date'],
            y=benchmark_df['nav'],
            mode='lines',
            name='基准净值',
            line=dict(color='#ff7f0e', width=1.5, dash='dash')
        ))

    fig.update_layout(
        title=title,
        xaxis_title='日期',
        yaxis_title='净值',
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def create_sector_pie(
    sector_df: pd.DataFrame,
    title: str = "行业分布"
) -> go.Figure:
    """行业分布环形图

    Args:
        sector_df: 行业分布DataFrame，需包含sector和weight列
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    if sector_df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (无数据)")
        return fig

    # 限制显示数量，合并小项
    if len(sector_df) > 8:
        top_sectors = sector_df.head(7)
        others_weight = sector_df.iloc[7:]['weight'].sum()
        others_row = pd.DataFrame([{'sector': '其他', 'weight': others_weight}])
        plot_df = pd.concat([top_sectors, others_row], ignore_index=True)
    else:
        plot_df = sector_df

    fig = go.Figure(data=[go.Pie(
        labels=plot_df['sector'],
        values=plot_df['weight'],
        hole=0.5,
        textinfo='label+percent',
        textposition='outside',
        marker=dict(
            colors=px.colors.qualitative.Set3[:len(plot_df)]
        )
    )])

    fig.update_layout(
        title=title,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )

    return fig


def create_pnl_waterfall(
    positions: List[PositionPnl],
    title: str = "个股盈亏"
) -> go.Figure:
    """盈亏瀑布图（盈利绿、亏损红）

    Args:
        positions: 持仓列表
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    if not positions:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (无数据)")
        return fig

    # 按盈亏排序
    sorted_positions = sorted(positions, key=lambda x: x.pnl, reverse=True)

    # 限制显示数量
    if len(sorted_positions) > 20:
        sorted_positions = sorted_positions[:20]

    names = [f"{p.name}\n({p.code})" for p in sorted_positions]
    pnls = [p.pnl for p in sorted_positions]

    # 颜色：盈利绿色，亏损红色
    colors = ['#2ecc71' if pnl >= 0 else '#e74c3c' for pnl in pnls]

    fig = go.Figure(data=[go.Bar(
        x=names,
        y=pnls,
        marker_color=colors,
        text=[f"{pnl:+,.0f}" for pnl in pnls],
        textposition='auto',
    )])

    fig.update_layout(
        title=title,
        xaxis_title='股票',
        yaxis_title='盈亏（元）',
        showlegend=False,
        xaxis_tickangle=-45
    )

    return fig


def create_drawdown_gauge(
    current_drawdown: float,
    title: str = "当前回撤"
) -> go.Figure:
    """回撤仪表盘

    Args:
        current_drawdown: 当前回撤比例（负数表示回撤）
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    # 将回撤转换为绝对值用于显示
    dd_pct = abs(current_drawdown) * 100

    # 颜色区间
    if dd_pct < 5:
        color = "green"
    elif dd_pct < 10:
        color = "yellow"
    elif dd_pct < 20:
        color = "orange"
    else:
        color = "red"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=dd_pct,
        title={'text': title},
        delta={'reference': 10, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
        gauge={
            'axis': {'range': [0, 50], 'tickwidth': 1},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 10], 'color': '#d5f5e3'},
                {'range': [10, 20], 'color': '#fef9e7'},
                {'range': [20, 30], 'color': '#fadbd8'},
                {'range': [30, 50], 'color': '#f5b7b1'},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 20
            }
        }
    ))

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


def create_returns_bar(
    metrics_dict: Dict[str, float],
    title: str = "收益指标"
) -> go.Figure:
    """收益指标柱状图

    Args:
        metrics_dict: 指标字典，如{'总收益': 0.15, '年化收益': 0.20}
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    categories = list(metrics_dict.keys())
    values = [v * 100 for v in metrics_dict.values()]  # 转换为百分比

    colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in values]

    fig = go.Figure(data=[go.Bar(
        x=categories,
        y=values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in values],
        textposition='auto',
    )])

    fig.update_layout(
        title=title,
        yaxis_title='收益率 (%)',
        showlegend=False,
        yaxis=dict(ticksuffix='%')
    )

    return fig


def create_risk_radar(
    metrics: Dict[str, float],
    title: str = "风险指标雷达图"
) -> go.Figure:
    """风险指标雷达图

    Args:
        metrics: 指标字典，如{'波动率': 0.15, '最大回撤': 0.10}
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    categories = list(metrics.keys())
    values = list(metrics.values())

    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],  # 闭合图形
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(31, 119, 180, 0.3)',
        line=dict(color='#1f77b4', width=2)
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(values) * 1.2]
            )
        ),
        title=title,
        showlegend=False
    )

    return fig


def create_position_treemap(
    positions: List[PositionPnl],
    title: str = "持仓权重分布"
) -> go.Figure:
    """持仓权重树状图

    Args:
        positions: 持仓列表
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    if not positions:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (无数据)")
        return fig

    df = pd.DataFrame([
        {
            'code': p.code,
            'name': p.name,
            'weight': p.weight * 100,  # 转换为百分比
            'sector': p.sector or '未知',
            'pnl': p.pnl,
        }
        for p in positions
    ])

    fig = px.treemap(
        df,
        path=[px.Constant("全部持仓"), 'sector', 'name'],
        values='weight',
        color='pnl',
        color_continuous_scale=['#e74c3c', '#f39c12', '#2ecc71'],
        color_continuous_midpoint=0,
        title=title
    )

    fig.update_traces(
        texttemplate='<b>%{label}</b><br>%{value:.1f}%',
        textfont=dict(size=12)
    )

    return fig


def create_rolling_metrics_chart(
    rolling_df: pd.DataFrame,
    title: str = "滚动指标"
) -> go.Figure:
    """滚动指标图表

    Args:
        rolling_df: 滚动指标DataFrame
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    if rolling_df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (无数据)")
        return fig

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=('滚动收益率', '滚动波动率', '滚动夏普比率')
    )

    # 滚动收益率
    if 'rolling_return' in rolling_df.columns:
        fig.add_trace(
            go.Scatter(x=rolling_df['date'], y=rolling_df['rolling_return'] * 100,
                      mode='lines', name='收益率', line=dict(color='blue')),
            row=1, col=1
        )

    # 滚动波动率
    if 'rolling_volatility' in rolling_df.columns:
        fig.add_trace(
            go.Scatter(x=rolling_df['date'], y=rolling_df['rolling_volatility'] * 100,
                      mode='lines', name='波动率', line=dict(color='orange')),
            row=2, col=1
        )

    # 滚动夏普
    if 'rolling_sharpe' in rolling_df.columns:
        fig.add_trace(
            go.Scatter(x=rolling_df['date'], y=rolling_df['rolling_sharpe'],
                      mode='lines', name='夏普比率', line=dict(color='green')),
            row=3, col=1
        )

    fig.update_layout(
        title=title,
        showlegend=False,
        height=600
    )

    return fig


def create_trade_history_table(
    trades_df: pd.DataFrame
) -> go.Figure:
    """交易历史表格

    Args:
        trades_df: 交易记录DataFrame

    Returns:
        Plotly表格对象
    """
    if trades_df.empty:
        fig = go.Figure()
        fig.update_layout(title="交易历史 (无数据)")
        return fig

    # 格式化数据
    display_df = trades_df.copy()
    if 'date' in display_df.columns:
        display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%Y-%m-%d')

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(display_df.columns),
            fill_color='#1f77b4',
            align='left',
            font=dict(color='white', size=12)
        ),
        cells=dict(
            values=[display_df[col] for col in display_df.columns],
            align='left',
            font=dict(size=11)
        )
    )])

    fig.update_layout(
        title="交易历史",
        height=min(400, 50 + len(display_df) * 30)
    )

    return fig


def create_market_cap_distribution(
    positions: List[PositionPnl],
    title: str = "市值分布"
) -> go.Figure:
    """市值分布柱状图

    Args:
        positions: 持仓列表
        title: 图表标题

    Returns:
        Plotly图表对象
    """
    if not positions:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (无数据)")
        return fig

    # 简化处理：根据代码数量估算（实际应从数据库获取市值）
    large_cap = sum(1 for p in positions if p.weight > 0.1)
    mid_cap = sum(1 for p in positions if 0.05 < p.weight <= 0.1)
    small_cap = len(positions) - large_cap - mid_cap

    categories = ['大盘 (>10%)', '中盘 (5-10%)', '小盘 (<5%)']
    values = [large_cap, mid_cap, small_cap]

    fig = go.Figure(data=[go.Bar(
        x=categories,
        y=values,
        marker_color=['#3498db', '#2ecc71', '#f39c12'],
        text=values,
        textposition='auto',
    )])

    fig.update_layout(
        title=title,
        yaxis_title='股票数量',
        showlegend=False
    )

    return fig


if __name__ == "__main__":
    # 测试图表
    print("测试图表组件...")

    # 测试净值曲线
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
    nav = 1.0
    nav_data = []
    for d in dates:
        nav *= (1 + np.random.normal(0.0005, 0.02))
        nav_data.append({'date': d, 'nav': nav})

    nav_df = pd.DataFrame(nav_data)
    fig = create_nav_chart(nav_df, title="测试净值曲线")
    fig.write_html("/tmp/test_nav.html")
    print("✅ 净值曲线图已保存到 /tmp/test_nav.html")

    # 测试行业分布
    sector_df = pd.DataFrame({
        'sector': ['银行', '医药', '科技', '消费', '能源'],
        'weight': [0.25, 0.20, 0.30, 0.15, 0.10]
    })
    fig = create_sector_pie(sector_df)
    fig.write_html("/tmp/test_sector.html")
    print("✅ 行业分布图已保存到 /tmp/test_sector.html")

    # 测试回撤仪表盘
    fig = create_drawdown_gauge(-0.15)
    fig.write_html("/tmp/test_drawdown.html")
    print("✅ 回撤仪表盘已保存到 /tmp/test_drawdown.html")
