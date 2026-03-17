"""Plotly图表封装组件"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from datetime import datetime


def create_cumulative_return_chart(
    nav_history: List[Tuple[datetime, float]],
    benchmark_nav: Optional[List[Tuple[datetime, float]]] = None,
    log_scale: bool = False,
    title: str = "累计收益曲线",
    height: int = 500,
) -> go.Figure:
    """
    创建累计收益曲线

    Args:
        nav_history: 策略净值历史 [(date, nav), ...]
        benchmark_nav: 基准净值历史 [(date, nav), ...]
        log_scale: 是否使用对数刻度
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    fig = go.Figure()

    # 策略曲线
    df = pd.DataFrame(nav_history, columns=["date", "nav"])
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["nav"],
            mode="lines",
            name="策略",
            line=dict(color="#1f77b4", width=2),
            hovertemplate="日期: %{x}<br>净值: %{y:.4f}<extra>策略</extra>",
        )
    )

    # 基准曲线
    if benchmark_nav:
        bench_df = pd.DataFrame(benchmark_nav, columns=["date", "nav"])
        # 对齐起始点
        if not bench_df.empty and not df.empty:
            bench_df["nav"] = bench_df["nav"] / bench_df["nav"].iloc[0] * df["nav"].iloc[0]
            fig.add_trace(
                go.Scatter(
                    x=bench_df["date"],
                    y=bench_df["nav"],
                    mode="lines",
                    name="基准",
                    line=dict(color="#ffa502", width=2, dash="dash"),
                    hovertemplate="日期: %{x}<br>净值: %{y:.4f}<extra>基准</extra>",
                )
            )

    # 添加1.0基准线
    fig.add_hline(
        y=1.0, line_dash="dot", line_color="gray", opacity=0.5, annotation_text="初始净值"
    )

    fig.update_layout(
        title=title,
        xaxis_title="日期",
        yaxis_title="净值",
        yaxis_type="log" if log_scale else "linear",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=height,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig


def create_drawdown_chart(
    nav_history: List[Tuple[datetime, float]],
    highlight_max: bool = True,
    title: str = "回撤曲线",
    height: int = 400,
) -> go.Figure:
    """
    创建回撤曲线

    Args:
        nav_history: 净值历史
        highlight_max: 是否高亮最大回撤区间
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    df = pd.DataFrame(nav_history, columns=["date", "nav"])
    df["peak"] = df["nav"].cummax()
    df["drawdown"] = (df["nav"] - df["peak"]) / df["peak"] * 100

    fig = go.Figure()

    # 填充回撤区域
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["drawdown"],
            fill="tozeroy",
            fillcolor="rgba(231, 76, 60, 0.3)",
            line=dict(color="#e74c3c", width=1),
            name="回撤",
            hovertemplate="日期: %{x}<br>回撤: %{y:.2f}%<extra></extra>",
        )
    )

    # 高亮最大回撤
    if highlight_max and not df.empty:
        max_dd_idx = df["drawdown"].idxmin()
        max_dd_start = df.loc[:max_dd_idx, "peak"].idxmax()

        fig.add_vrect(
            x0=df.loc[max_dd_start, "date"],
            x1=df.loc[max_dd_idx, "date"],
            fillcolor="red",
            opacity=0.2,
            annotation_text="最大回撤区间",
            annotation_position="top left",
        )

        # 标注最大回撤值
        max_dd_value = df["drawdown"].min()
        fig.add_annotation(
            x=df.loc[max_dd_idx, "date"],
            y=max_dd_value,
            text=f"最大回撤: {max_dd_value:.2f}%",
            showarrow=True,
            arrowhead=2,
            ax=40,
            ay=-40,
        )

    fig.update_layout(
        title=title,
        xaxis_title="日期",
        yaxis_title="回撤 (%)",
        template="plotly_white",
        height=height,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig


def create_monthly_returns_heatmap(
    nav_history: List[Tuple[datetime, float]], title: str = "月度收益热力图", height: int = 400
) -> go.Figure:
    """
    创建月度收益热力图

    Args:
        nav_history: 净值历史
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    df = pd.DataFrame(nav_history, columns=["date", "nav"])
    df["month"] = df["date"].dt.to_period("M")

    monthly = df.groupby("month").agg({"nav": ["first", "last"]}).reset_index()
    monthly.columns = ["month", "start_nav", "end_nav"]
    monthly["return"] = (monthly["end_nav"] / monthly["start_nav"] - 1) * 100

    monthly["year"] = monthly["month"].dt.year
    monthly["mon"] = monthly["month"].dt.month

    pivot = monthly.pivot(index="year", columns="mon", values="return")
    pivot = pivot.fillna(0)

    # 计算年度统计
    pivot["年度"] = pivot.mean(axis=1)

    # 自定义颜色映射
    colorscale = [
        [0.0, "#e74c3c"],  # 深红（大亏）
        [0.25, "#f39c12"],  # 橙红
        [0.5, "#f1c40f"],  # 黄色（持平）
        [0.75, "#2ecc71"],  # 浅绿
        [1.0, "#27ae60"],  # 深绿（大赚）
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[
                "1月",
                "2月",
                "3月",
                "4月",
                "5月",
                "6月",
                "7月",
                "8月",
                "9月",
                "10月",
                "11月",
                "12月",
                "年度平均",
            ],
            y=pivot.index,
            colorscale=colorscale,
            zmid=0,
            text=np.round(pivot.values, 1),
            texttemplate="%{text:.1f}%",
            textfont={"size": 10},
            hovertemplate="%{y}年%{x}: %{z:.2f}%<extra></extra>",
            colorbar=dict(title="收益率(%)"),
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="月份",
        yaxis_title="年份",
        template="plotly_white",
        height=height,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig


def create_rolling_metrics_chart(
    nav_history: List[Tuple[datetime, float]],
    window: int = 20,
    title: str = "滚动指标",
    height: int = 400,
) -> go.Figure:
    """
    创建滚动指标图表（滚动波动率、滚动夏普）

    Args:
        nav_history: 净值历史
        window: 滚动窗口大小
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    df = pd.DataFrame(nav_history, columns=["date", "nav"])
    df["daily_return"] = df["nav"].pct_change()
    df["rolling_vol"] = df["daily_return"].rolling(window).std() * np.sqrt(252) * 100
    df["rolling_return"] = df["nav"].pct_change(window) * 100

    # 滚动夏普 (简化计算)
    df["rolling_sharpe"] = (df["daily_return"].rolling(window).mean() * 252 - 0.03) / (
        df["daily_return"].rolling(window).std() * np.sqrt(252)
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("滚动波动率 (%)", "滚动收益 (%)", "滚动夏普"),
        vertical_spacing=0.1,
    )

    # 滚动波动率
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["rolling_vol"],
            mode="lines",
            name="波动率",
            line=dict(color="#3498db"),
        ),
        row=1,
        col=1,
    )

    # 滚动收益
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["rolling_return"],
            mode="lines",
            name="收益",
            line=dict(color="#2ecc71"),
        ),
        row=2,
        col=1,
    )

    # 滚动夏普
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["rolling_sharpe"],
            mode="lines",
            name="夏普",
            line=dict(color="#e74c3c"),
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=height,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig


def create_return_distribution_chart(
    nav_history: List[Tuple[datetime, float]], title: str = "收益率分布", height: int = 400
) -> go.Figure:
    """
    创建收益率分布直方图

    Args:
        nav_history: 净值历史
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    df = pd.DataFrame(nav_history, columns=["date", "nav"])
    df["daily_return"] = df["nav"].pct_change() * 100
    df = df.dropna()

    fig = go.Figure()

    # 日收益率直方图
    fig.add_trace(
        go.Histogram(
            x=df["daily_return"],
            nbinsx=50,
            name="日收益率",
            marker_color="#3498db",
            opacity=0.7,
            histnorm="probability density",
        )
    )

    # 添加正态分布参考线
    mean = df["daily_return"].mean()
    std = df["daily_return"].std()
    x_range = np.linspace(df["daily_return"].min(), df["daily_return"].max(), 100)
    y_normal = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mean) / std) ** 2)

    fig.add_trace(
        go.Scatter(
            x=x_range,
            y=y_normal,
            mode="lines",
            name="正态分布",
            line=dict(color="red", dash="dash"),
        )
    )

    # 添加均值线
    fig.add_vline(x=mean, line_dash="dot", line_color="green", annotation_text=f"均值: {mean:.2f}%")

    fig.update_layout(
        title=title,
        xaxis_title="日收益率 (%)",
        yaxis_title="概率密度",
        template="plotly_white",
        height=height,
        bargap=0.1,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig


def create_trade_analysis_chart(
    trades_df: pd.DataFrame, title: str = "交易分析", height: int = 500
) -> go.Figure:
    """
    创建交易分析图表（盈亏分布、时序）

    Args:
        trades_df: 交易记录DataFrame
        title: 图表标题
        height: 图表高度

    Returns:
        Plotly图表对象
    """
    if trades_df.empty:
        fig = go.Figure()
        fig.update_layout(title="暂无交易数据")
        return fig

    # 计算每笔交易的盈亏
    trades_analysis = []
    for ts_code in trades_df["ts_code"].unique():
        stock_trades = trades_df[trades_df["ts_code"] == ts_code]
        buy_trades = stock_trades[stock_trades["side"].str.lower() == "buy"]
        sell_trades = stock_trades[stock_trades["side"].str.lower() == "sell"]

        if not buy_trades.empty and not sell_trades.empty:
            total_buy = (buy_trades["amount"] + buy_trades["total_cost"]).sum()
            total_sell = (sell_trades["amount"] - sell_trades["total_cost"]).sum()
            pnl = total_sell - total_buy
            trades_analysis.append(
                {
                    "ts_code": ts_code,
                    "pnl": pnl,
                    "buy_count": len(buy_trades),
                    "sell_count": len(sell_trades),
                }
            )

    if not trades_analysis:
        fig = go.Figure()
        fig.update_layout(title="暂无完整交易数据")
        return fig

    analysis_df = pd.DataFrame(trades_analysis)

    fig = make_subplots(
        rows=2, cols=1, subplot_titles=("个股盈亏", "盈亏分布"), vertical_spacing=0.15
    )

    # 个股盈亏柱状图
    colors = ["#2ecc71" if x > 0 else "#e74c3c" for x in analysis_df["pnl"]]
    fig.add_trace(
        go.Bar(x=analysis_df["ts_code"], y=analysis_df["pnl"], marker_color=colors, name="盈亏"),
        row=1,
        col=1,
    )

    # 盈亏分布直方图
    fig.add_trace(
        go.Histogram(x=analysis_df["pnl"], nbinsx=20, marker_color="#3498db", name="分布"),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=height,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    return fig
