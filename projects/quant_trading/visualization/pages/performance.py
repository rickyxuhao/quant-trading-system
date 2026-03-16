"""策略绩效页面"""
import streamlit as st
import pandas as pd
from datetime import datetime

from projects.quant_trading.visualization.components.metric_cards import (
    render_metric_cards, render_detailed_metrics_table
)
from projects.quant_trading.visualization.components.charts import (
    create_cumulative_return_chart,
    create_drawdown_chart,
    create_monthly_returns_heatmap,
    create_rolling_metrics_chart,
    create_return_distribution_chart
)
from projects.quant_trading.visualization.state_manager import StateManager
from projects.quant_trading.visualization.utils.data_loader import DataLoader


def render_performance_page():
    """渲染策略绩效页面"""
    st.header("策略绩效概览")

    # 检查是否有回测结果，如果没有则使用模拟数据
    results = StateManager.get('backtest_results')

    if results is None:
        with st.spinner("加载示例数据..."):
            results = DataLoader.generate_mock_backtest_results()
            StateManager.set('backtest_results', results)

    metrics = results.get('metrics')
    nav_history = results.get('nav_history', [])
    benchmark_nav = results.get('benchmark_nav')

    if metrics is None or not nav_history:
        st.warning("暂无回测数据，请先在侧边栏运行回测")
        return

    # 控制栏
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        log_scale = st.toggle("对数刻度", value=False, key="perf_log_scale")
    with col2:
        show_benchmark = st.toggle("显示基准", value=True, key="perf_show_benchmark")
    with col3:
        view_mode = st.segmented_control(
            "视图模式",
            options=["概览", "详细", "分析"],
            default="概览",
            key="perf_view_mode"
        )

    # 指标卡片
    render_metric_cards(metrics)

    st.divider()

    if view_mode == "概览":
        # 概览视图 - 主要图表
        col1, col2 = st.columns(2)

        with col1:
            # 累计收益曲线
            fig_return = create_cumulative_return_chart(
                nav_history,
                benchmark_nav if show_benchmark else None,
                log_scale=log_scale,
                title="累计收益曲线"
            )
            st.plotly_chart(fig_return, use_container_width=True, key="overview_return_chart")

        with col2:
            # 回撤曲线
            fig_dd = create_drawdown_chart(nav_history, title="回撤曲线")
            st.plotly_chart(fig_dd, use_container_width=True, key="overview_dd_chart")

        # 月度收益热力图
        st.subheader("月度收益分析")
        fig_heatmap = create_monthly_returns_heatmap(nav_history)
        st.plotly_chart(fig_heatmap, use_container_width=True, key="overview_heatmap")

    elif view_mode == "详细":
        # 详细视图 - 详细指标表格
        render_detailed_metrics_table(metrics)

    else:  # 分析视图
        # 分析视图 - 滚动指标和分布
        col1, col2 = st.columns(2)

        with col1:
            # 滚动指标
            fig_rolling = create_rolling_metrics_chart(nav_history, window=20)
            st.plotly_chart(fig_rolling, use_container_width=True, key="analysis_rolling")

        with col2:
            # 收益率分布
            fig_dist = create_return_distribution_chart(nav_history)
            st.plotly_chart(fig_dist, use_container_width=True, key="analysis_dist")

        # 回测统计信息
        st.subheader("回测统计")
        stats = results.get('stats', {})
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("回测天数", stats.get('total_days', 0))
            with col2:
                st.metric("调仓次数", stats.get('rebalance_count', 0))
            with col3:
                st.metric("交易次数", stats.get('trade_count', 0))
            with col4:
                st.metric("耗时(秒)", f"{stats.get('duration_seconds', 0):.2f}")


def get_mock_backtest_results():
    """
    获取模拟回测结果（兼容旧代码）
    已废弃，请使用 DataLoader.generate_mock_backtest_results
    """
    return DataLoader.generate_mock_backtest_results()
