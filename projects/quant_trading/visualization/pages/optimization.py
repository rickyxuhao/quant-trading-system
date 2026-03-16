"""参数调优页面"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from projects.quant_trading.visualization.state_manager import StateManager
from projects.quant_trading.visualization.components.metric_cards import render_metric_cards
from projects.quant_trading.visualization.utils.data_loader import DataLoader
from projects.quant_trading.backtest.metrics import PerformanceMetrics


def render_optimization_page():
    """渲染参数调优页面"""
    st.header("参数调优")

    st.info("在此页面调整策略参数，运行回测并对比不同参数组合的效果。")

    # 参数设置侧边栏部分
    with st.sidebar:
        render_parameter_controls()

    # 主内容区
    comparison = StateManager.get_comparison_results()

    if not comparison:
        st.info("请点击左侧'运行回测'按钮开始参数调优。")
        return

    # 对比结果展示
    st.subheader("参数组合对比")

    # 对比表格
    render_comparison_table(comparison)

    # 雷达图对比
    st.subheader("多维度对比")
    render_radar_chart(comparison)

    # 参数敏感性分析
    st.subheader("参数敏感性分析")
    render_sensitivity_analysis(comparison)

    # 清除对比按钮
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🗑️ 清除所有对比", use_container_width=True):
            StateManager.clear_comparison_results()
            st.rerun()
    with col2:
        if st.button("📥 导出对比结果", use_container_width=True):
            export_comparison_results(comparison)


def render_parameter_controls():
    """渲染参数控制面板"""
    st.header("🔧 参数设置")

    # 策略选择
    st.subheader("策略选择")
    strategy = st.selectbox(
        "选择策略",
        ["MA趋势策略", "均值回归策略", "ML预测策略"],
        key="opt_strategy"
    )

    # MA参数
    st.subheader("均线参数")
    ma_short = st.slider("短期均线", 5, 30, 10, 5, key="opt_ma_short")
    ma_long = st.slider("长期均线", 20, 120, 60, 10, key="opt_ma_long")

    # 信号阈值
    st.subheader("信号阈值")
    entry_threshold = st.slider("入场阈值", 0.0, 0.1, 0.02, 0.01, key="opt_entry")
    exit_threshold = st.slider("出场阈值", 0.0, 0.1, 0.01, 0.01, key="opt_exit")

    # 风控参数
    st.subheader("风险控制")
    stop_loss = st.slider("止损比例 (%)", 1, 10, 5, 1, key="opt_stop_loss") / 100
    take_profit = st.slider("止盈比例 (%)", 5, 20, 10, 1, key="opt_take_profit") / 100

    # 运行回测按钮
    st.divider()
    if st.button("🚀 运行回测", type="primary", use_container_width=True):
        with st.spinner("正在运行回测..."):
            # 模拟回测执行
            import time
            time.sleep(1.5)

            # 根据参数生成不同的模拟结果
            params = {
                'ma_short': ma_short,
                'ma_long': ma_long,
                'entry_threshold': entry_threshold,
                'exit_threshold': exit_threshold,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }

            # 基于参数计算一个确定性但变化的收益
            seed = ma_short * 1000 + ma_long + int(entry_threshold * 1000)
            np.random.seed(seed)

            # 参数合理程度影响结果
            if ma_short >= ma_long:
                # 不合理的参数组合
                annual_return = np.random.uniform(-0.05, 0.02)
                sharpe = np.random.uniform(-0.5, 0.3)
            else:
                # 合理的参数组合
                base_return = 0.08 + (30 - ma_short) * 0.002 - (ma_long - 20) * 0.0005
                annual_return = np.random.uniform(base_return - 0.03, base_return + 0.05)
                sharpe = np.random.uniform(0.5, 1.5)

            max_dd = np.random.uniform(-0.25, -0.08)
            win_rate = np.random.uniform(0.45, 0.65)

            metrics = PerformanceMetrics(
                total_return=annual_return * 4,  # 假设4年
                annual_return=annual_return,
                max_drawdown=max_dd,
                max_drawdown_duration=np.random.randint(20, 60),
                volatility=np.random.uniform(0.15, 0.25),
                sharpe_ratio=sharpe,
                calmar_ratio=abs(annual_return / max_dd) if max_dd != 0 else 0,
                win_rate=win_rate,
                total_trades=np.random.randint(50, 150)
            )

            result = {
                'params': params,
                'metrics': metrics,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            StateManager.add_comparison_result(result)
            st.success("回测完成！")
            st.rerun()


def render_comparison_table(comparison: list):
    """渲染对比表格"""
    rows = []
    for i, result in enumerate(comparison):
        params = result.get('params', {})
        metrics = result.get('metrics', {})

        row = {
            '组合': f"组合{i+1}",
            '短期均线': params.get('ma_short', '-'),
            '长期均线': params.get('ma_long', '-'),
            '入场阈值': f"{params.get('entry_threshold', 0):.2%}",
            '出场阈值': f"{params.get('exit_threshold', 0):.2%}",
            '止损': f"{params.get('stop_loss', 0):.0%}",
            '止盈': f"{params.get('take_profit', 0):.0%}",
            '年化收益': f"{metrics.annual_return*100:.2f}%",
            '夏普比率': f"{metrics.sharpe_ratio:.2f}",
            '最大回撤': f"{metrics.max_drawdown*100:.2f}%",
            '胜率': f"{metrics.win_rate*100:.1f}%",
            '交易次数': metrics.total_trades,
        }
        rows.append(row)

    comparison_df = pd.DataFrame(rows)

    # 高亮最佳值
    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            '组合': st.column_config.TextColumn('组合', width='small'),
            '年化收益': st.column_config.TextColumn('年化收益', help='越高越好'),
            '夏普比率': st.column_config.TextColumn('夏普', help='越高越好'),
            '最大回撤': st.column_config.TextColumn('最大回撤', help='绝对值越小越好'),
            '胜率': st.column_config.TextColumn('胜率', help='越高越好'),
        }
    )


def render_radar_chart(comparison: list):
    """渲染雷达图对比"""
    fig = go.Figure()

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i, result in enumerate(comparison):
        metrics = result.get('metrics', {})

        # 归一化指标（0-1范围）
        annual_return_norm = min(max(metrics.annual_return * 3, 0), 1)  # 30%收益=1
        sharpe_norm = min(max(metrics.sharpe_ratio / 2, 0), 1)  # 夏普2=1
        drawdown_norm = min(max(1 + metrics.max_drawdown / 0.3, 0), 1)  # 回撤30%=0
        win_rate_norm = metrics.win_rate
        calmar_norm = min(max(metrics.calmar_ratio / 2, 0), 1)  # Calmar 2=1

        fig.add_trace(go.Scatterpolar(
            r=[annual_return_norm, sharpe_norm, drawdown_norm, win_rate_norm, calmar_norm],
            theta=['年化收益', '夏普比率', '回撤控制', '胜率', 'Calmar'],
            fill='toself',
            name=f"组合{i+1}",
            line_color=colors[i % len(colors)],
            fillcolor=colors[i % len(colors)],
            opacity=0.3
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
            angularaxis=dict(direction='clockwise')
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        height=500,
        template='plotly_white'
    )

    st.plotly_chart(fig, use_container_width=True, key="radar_comparison")


def render_sensitivity_analysis(comparison: list):
    """渲染参数敏感性分析"""
    if len(comparison) < 3:
        st.info("运行3次以上回测以查看参数敏感性分析")
        return

    # 提取数据
    df_data = []
    for result in comparison:
        params = result.get('params', {})
        metrics = result.get('metrics', {})
        row = {**params, **{
            'annual_return': metrics.annual_return,
            'sharpe_ratio': metrics.sharpe_ratio,
            'max_drawdown': metrics.max_drawdown
        }}
        df_data.append(row)

    df = pd.DataFrame(df_data)

    # 参数敏感性图表
    param_cols = ['ma_short', 'ma_long', 'entry_threshold', 'stop_loss']

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[f'{col} vs 年化收益' for col in param_cols],
        vertical_spacing=0.15
    )

    for i, col in enumerate(param_cols):
        row = i // 2 + 1
        col_idx = i % 2 + 1

        fig.add_trace(
            go.Scatter(
                x=df[col],
                y=df['annual_return'] * 100,
                mode='markers+lines',
                name=col,
                marker=dict(size=10)
            ),
            row=row, col=col_idx
        )

        fig.update_xaxes(title_text=col, row=row, col=col_idx)
        fig.update_yaxes(title_text='年化收益 (%)', row=row, col=col_idx)

    fig.update_layout(
        height=600,
        showlegend=False,
        template='plotly_white'
    )

    st.plotly_chart(fig, use_container_width=True, key="sensitivity_analysis")

    # 参数相关性热图
    st.subheader("参数-指标相关性")

    corr_cols = ['ma_short', 'ma_long', 'entry_threshold', 'stop_loss',
                 'annual_return', 'sharpe_ratio', 'max_drawdown']
    corr_matrix = df[corr_cols].corr()

    fig = px.imshow(
        corr_matrix,
        text_auto='.2f',
        aspect='auto',
        color_continuous_scale='RdBu_r',
        zmin=-1, zmax=1
    )
    fig.update_layout(height=400, template='plotly_white')

    st.plotly_chart(fig, use_container_width=True, key="correlation_heatmap")


def export_comparison_results(comparison: list):
    """导出对比结果为CSV"""
    rows = []
    for i, result in enumerate(comparison):
        params = result.get('params', {})
        metrics = result.get('metrics', {})

        row = {
            '组合': f"组合{i+1}",
            **params,
            'annual_return': metrics.annual_return,
            'sharpe_ratio': metrics.sharpe_ratio,
            'max_drawdown': metrics.max_drawdown,
            'win_rate': metrics.win_rate,
            'total_trades': metrics.total_trades,
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # 转换为CSV下载
    csv = df.to_csv(index=False)
    st.download_button(
        label="下载CSV",
        data=csv,
        file_name=f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime='text/csv'
    )
