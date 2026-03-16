"""关键指标卡片组件"""
import streamlit as st
from typing import Optional, Dict, Any
from projects.quant_trading.backtest.metrics import PerformanceMetrics


def render_metric_cards(
    metrics: PerformanceMetrics,
    benchmark_metrics: Optional[PerformanceMetrics] = None,
    use_columns: bool = True
):
    """
    渲染关键指标卡片

    Args:
        metrics: 策略绩效指标
        benchmark_metrics: 基准绩效指标（可选）
        use_columns: 是否使用列布局
    """
    if use_columns:
        cols = st.columns(4)
    else:
        # 不使用列布局时，创建一个容器
        cols = [st.container()] * 4

    # 年化收益率
    with cols[0]:
        delta = None
        delta_color = "normal"
        if benchmark_metrics:
            delta = f"{(metrics.annual_return - benchmark_metrics.annual_return) * 100:.2f}%"
            delta_color = "green" if metrics.annual_return > benchmark_metrics.annual_return else "red"

        st.metric(
            label="📈 年化收益率",
            value=f"{metrics.annual_return * 100:.2f}%",
            delta=delta,
            delta_color=delta_color if delta else "normal"
        )

    # 夏普比率
    with cols[1]:
        delta = None
        if benchmark_metrics:
            delta = f"{metrics.sharpe_ratio - benchmark_metrics.sharpe_ratio:.2f}"

        st.metric(
            label="⚖️ 夏普比率",
            value=f"{metrics.sharpe_ratio:.2f}",
            delta=delta
        )

    # 最大回撤
    with cols[2]:
        st.metric(
            label="📉 最大回撤",
            value=f"{metrics.max_drawdown * 100:.2f}%",
            delta_color="inverse"
        )

    # Calmar比率
    with cols[3]:
        st.metric(
            label="🎯 Calmar比率",
            value=f"{metrics.calmar_ratio:.2f}"
        )


def render_detailed_metrics_table(metrics: PerformanceMetrics):
    """
    渲染详细绩效指标表格

    Args:
        metrics: 策略绩效指标
    """
    # 收益指标
    with st.expander("📊 收益指标", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**总收益率**")
            st.write(f"{metrics.total_return * 100:+.2f}%")
            st.markdown("**年化收益率**")
            st.write(f"{metrics.annual_return * 100:+.2f}%")
        with col2:
            st.markdown("**累计收益金额**")
            st.write(f"¥{metrics.cumulative_return:,.2f}")
        with col3:
            st.markdown("**Alpha**")
            st.write(f"{metrics.alpha:.4f}")
            st.markdown("**超额收益**")
            st.write(f"{metrics.excess_return * 100:+.2f}%")

    # 风险指标
    with st.expander("⚠️ 风险指标", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**最大回撤**")
            st.write(f"{metrics.max_drawdown * 100:.2f}%")
            st.markdown("**回撤持续天数**")
            st.write(f"{metrics.max_drawdown_duration} 天")
        with col2:
            st.markdown("**年化波动率**")
            st.write(f"{metrics.volatility * 100:.2f}%")
            st.markdown("**下行波动率**")
            st.write(f"{metrics.downside_volatility * 100:.2f}%")
        with col3:
            st.markdown("**VaR (95%)**")
            st.write(f"{metrics.var_95 * 100:.2f}%")
            st.markdown("**CVaR (95%)**")
            st.write(f"{metrics.cvar_95 * 100:.2f}%")

    # 风险调整收益指标
    with st.expander("🎯 风险调整收益", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**夏普比率**")
            st.write(f"{metrics.sharpe_ratio:.2f}")
        with col2:
            st.markdown("**索提诺比率**")
            st.write(f"{metrics.sortino_ratio:.2f}")
        with col3:
            st.markdown("**Calmar比率**")
            st.write(f"{metrics.calmar_ratio:.2f}")
        with col4:
            st.markdown("**Omega比率**")
            st.write(f"{metrics.omega_ratio:.2f}")

    # 交易指标
    with st.expander("💼 交易统计", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**总交易次数**")
            st.write(f"{metrics.total_trades}")
            st.markdown("**胜率**")
            st.write(f"{metrics.win_rate * 100:.1f}%")
        with col2:
            st.markdown("**盈亏比**")
            st.write(f"{metrics.profit_loss_ratio:.2f}")
            st.markdown("**平均交易收益**")
            st.write(f"{metrics.avg_trade_return * 100:+.2f}%")
        with col3:
            st.markdown("**最大连续盈利**")
            st.write(f"{metrics.max_consecutive_wins} 次")
            st.markdown("**最大连续亏损**")
            st.write(f"{metrics.max_consecutive_losses} 次")

    # 相对基准指标
    with st.expander("📏 相对基准指标", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Beta**")
            st.write(f"{metrics.beta:.4f}")
            st.markdown("**信息比率**")
            st.write(f"{metrics.information_ratio:.2f}")
        with col2:
            st.markdown("**跟踪误差**")
            st.write(f"{metrics.tracking_error * 100:.2f}%")
        with col3:
            st.markdown("**上涨捕获率**")
            st.write(f"{metrics.up_capture * 100:.2f}%")
            st.markdown("**下跌捕获率**")
            st.write(f"{metrics.down_capture * 100:.2f}%")
