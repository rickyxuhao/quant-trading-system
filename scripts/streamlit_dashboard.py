"""
Phase 6: Streamlit Dashboard
============================
多因子策略研究结果可视化仪表板

Usage:
    streamlit run scripts/streamlit_dashboard.py

依赖输出文件:
    - output/factor_icir_results.json   (Phase 2)
    - output/layered_returns.csv        (Phase 3)
    - output/layered_stats.json         (Phase 3)
    - output/backtest_nav.csv           (Phase 4)
    - output/backtest_metrics.json      (Phase 4)
    - output/risk_report.json           (Phase 5)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ============================================================
# Config
# ============================================================
st.set_page_config(
    page_title="量化多因子策略仪表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')


# ============================================================
# Data loading helpers
# ============================================================
@st.cache_data
def load_icir_results():
    path = os.path.join(OUTPUT_DIR, 'factor_icir_results.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_layered_returns():
    path = os.path.join(OUTPUT_DIR, 'layered_returns.csv')
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, parse_dates=['date'])


@st.cache_data
def load_layered_stats():
    path = os.path.join(OUTPUT_DIR, 'layered_stats.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_nav():
    path = os.path.join(OUTPUT_DIR, 'backtest_nav.csv')
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, parse_dates=['date'])


@st.cache_data
def load_metrics():
    path = os.path.join(OUTPUT_DIR, 'backtest_metrics.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_risk_report():
    path = os.path.join(OUTPUT_DIR, 'risk_report.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ============================================================
# Sidebar
# ============================================================
st.sidebar.title("📊 量化多因子策略")
st.sidebar.markdown("**数据范围**: 2024-01-02 ~ 2026-03-20")
st.sidebar.markdown("**Universe**: ~5,400 只 A 股")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "导航",
    ["🏠 概览", "📊 因子 ICIR 分析", "📈 分层回测", "🎯 策略回测", "⚠️ 风险报告"]
)

# ============================================================
# Page: 概览
# ============================================================
if page == "🏠 概览":
    st.title("📈 量化多因子策略研究仪表板")
    st.markdown("基于 A 股 2024-2026 年数据，涵盖 70 个因子的全流程研究成果。")

    icir_data = load_icir_results()
    nav_df    = load_nav()
    metrics   = load_metrics()
    risk      = load_risk_report()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if icir_data:
            n_valid = len(icir_data.get('valid_factors', []))
            st.metric("有效因子", f"{n_valid}", delta=f"/ {len(icir_data.get('all_results', []))} 总计")
    with col2:
        if icir_data:
            n_sel = len(icir_data.get('selected_factors', []))
            st.metric("入模因子", f"{n_sel}")
    with col3:
        if metrics:
            sharpe = metrics.get('strategy_sharpe', 0)
            st.metric("策略 Sharpe", f"{sharpe:.2f}", delta=f"目标 > 1.0")
    with col4:
        if metrics:
            max_dd = abs(metrics.get('max_drawdown', 0))
            st.metric("最大回撤", f"{max_dd*100:.1f}%", delta=f"目标 < 20%", delta_color="inverse")

    if metrics:
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("年化收益率", f"{metrics.get('strategy_annual_return',0)*100:.1f}%")
        c2.metric("CSI300 基准", f"{metrics.get('benchmark_annual_return',0)*100:.1f}%")
        c3.metric("超额年化", f"{metrics.get('excess_annual_return',0)*100:.1f}%")
        c4.metric("信息比率 IR", f"{metrics.get('information_ratio',0):.2f}")

    if nav_df is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=nav_df['date'], y=nav_df['strategy'],
                                 name='策略净值', line=dict(color='#1f77b4', width=2)))
        fig.add_trace(go.Scatter(x=nav_df['date'], y=nav_df['benchmark'],
                                 name='CSI300', line=dict(color='#d62728', width=1.5, dash='dot')))
        fig.update_layout(title='策略净值 vs CSI300', height=400,
                          xaxis_title='日期', yaxis_title='净值',
                          legend=dict(x=0.01, y=0.99))
        st.plotly_chart(fig, use_container_width=True)

    if risk:
        approval = risk.get('approval', {})
        verdict = approval.get('verdict', '未知')
        if '✅' in verdict:
            st.success(f"风控审查: {verdict}")
        else:
            st.error(f"风控审查: {verdict}")
        if 'checks' in approval:
            for c in approval['checks']:
                icon = "✅" if c['pass'] else "❌"
                st.write(f"{icon} **{c['rule']}**: {c['detail']}")


# ============================================================
# Page: 因子 ICIR 分析
# ============================================================
elif page == "📊 因子 ICIR 分析":
    st.title("📊 因子 ICIR 分析")
    icir_data = load_icir_results()

    if icir_data is None:
        st.warning("Phase 2 结果尚未生成，请先运行 factor_icir_analysis.py")
        st.stop()

    all_results = pd.DataFrame(icir_data['all_results'])
    selected = icir_data['selected_factors']

    st.markdown(f"**分析因子数**: {len(all_results)}  |  "
                f"**有效因子 (|ICIR|>0.3)**: {len(icir_data['valid_factors'])}  |  "
                f"**入模因子 (去冗余)**: {len(selected)}")

    # ICIR bar chart
    df_sorted = all_results.sort_values('icir', ascending=True)
    colors = ['#2ca02c' if v > 0 else '#d62728' for v in df_sorted['icir']]
    selected_marker = ['★ ' + f if f in selected else f for f in df_sorted['factor']]

    fig = go.Figure(go.Bar(
        y=selected_marker,
        x=df_sorted['icir'],
        orientation='h',
        marker_color=colors,
        text=[f'{v:.3f}' for v in df_sorted['icir']],
        textposition='outside',
    ))
    fig.update_layout(
        title='因子 ICIR（★ = 入模因子）',
        height=max(400, len(all_results) * 18),
        xaxis_title='ICIR（年化）',
        yaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=200),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table
    st.subheader("📋 完整因子列表")
    st.dataframe(
        all_results.sort_values('icir', key=abs, ascending=False)
                   .style.background_gradient(subset=['icir'], cmap='RdYlGn', vmin=-3, vmax=3),
        use_container_width=True,
    )

    # Heatmap by group
    st.subheader("🗺️ 因子分组 ICIR 热力图")
    heatmap_data = all_results.pivot_table(
        values='icir', index='group', columns='factor', aggfunc='first'
    ).fillna(0)
    fig2 = px.imshow(heatmap_data, color_continuous_scale='RdYlGn',
                     color_continuous_midpoint=0, aspect='auto',
                     title='因子 ICIR 热力图（按分组）')
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("✅ 入模因子")
    st.write(selected)


# ============================================================
# Page: 分层回测
# ============================================================
elif page == "📈 分层回测":
    st.title("📈 5分位分层回测")
    layered_df = load_layered_returns()
    stats_data = load_layered_stats()

    if layered_df is None or stats_data is None:
        st.warning("Phase 3 结果尚未生成，请先运行 run_layered_backtest.py")
        st.stop()

    stats_list = stats_data.get('results', [])
    factors = layered_df['factor'].unique().tolist() if 'factor' in layered_df.columns else []

    if not factors:
        st.warning("没有分层回测数据")
        st.stop()

    selected_factor = st.selectbox("选择因子", factors)

    factor_nav = layered_df[layered_df['factor'] == selected_factor] if 'factor' in layered_df.columns else layered_df
    factor_stats = next((s for s in stats_list if s['factor'] == selected_factor), {})

    if factor_stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("单调性", f"{factor_stats.get('monotonicity', 0):.3f}")
        c2.metric("L-S 年化", f"{factor_stats.get('ls_annual', 0)*100:.1f}%")
        c3.metric("L-S Sharpe", f"{factor_stats.get('ls_sharpe', 0):.2f}")
        c4.metric("Q1-Q5 价差", f"{factor_stats.get('spread_q1_q5', 0)*100:.1f}%")

    # Quintile NAV chart
    colors = ['#d73027', '#fc8d59', '#fee090', '#91bfdb', '#4575b4']
    fig = go.Figure()
    for q, color in enumerate(colors, 1):
        col = f'Q{q}'
        if col in factor_nav.columns:
            ann = factor_stats.get('q_annual_returns', [0]*5)[q-1] if factor_stats else 0
            fig.add_trace(go.Scatter(
                x=factor_nav['date'], y=factor_nav[col],
                name=f'Q{q} ({ann*100:.1f}%/yr)',
                line=dict(color=color, width=1.5)
            ))
    if 'LS' in factor_nav.columns:
        ls_ann = factor_stats.get('ls_annual', 0) if factor_stats else 0
        fig.add_trace(go.Scatter(
            x=factor_nav['date'], y=factor_nav['LS'],
            name=f'L-S ({ls_ann*100:.1f}%/yr)',
            line=dict(color='black', width=2, dash='dot')
        ))
    fig.update_layout(title=f'{selected_factor} — 5分位净值', height=450,
                      xaxis_title='日期', yaxis_title='净值',
                      legend=dict(x=0.01, y=0.99))
    st.plotly_chart(fig, use_container_width=True)

    # Bar chart of annual returns per quintile
    if factor_stats and 'q_annual_returns' in factor_stats:
        q_rets = [r * 100 for r in factor_stats['q_annual_returns']]
        bar_colors = ['green' if v > 0 else 'red' for v in q_rets]
        fig2 = go.Figure(go.Bar(
            x=[f'Q{i}' for i in range(1, 6)],
            y=q_rets,
            marker_color=bar_colors,
            text=[f'{v:.1f}%' for v in q_rets],
            textposition='auto',
        ))
        fig2.update_layout(title='各分组年化收益率',
                           yaxis_title='年化收益率 (%)', height=300)
        st.plotly_chart(fig2, use_container_width=True)

    # Summary table
    st.subheader("📋 所有因子单调性汇总")
    stats_df = pd.DataFrame(stats_list).sort_values('monotonicity', ascending=False)
    st.dataframe(stats_df[['factor', 'monotonicity', 'spread_q1_q5',
                            'ls_annual', 'ls_sharpe']].style.background_gradient(
                     subset=['monotonicity'], cmap='RdYlGn', vmin=0, vmax=1),
                 use_container_width=True)


# ============================================================
# Page: 策略回测
# ============================================================
elif page == "🎯 策略回测":
    st.title("🎯 多因子 XGBoost 策略回测")
    nav_df  = load_nav()
    metrics = load_metrics()

    if nav_df is None or metrics is None:
        st.warning("Phase 4 结果尚未生成，请先运行 run_multifactor_strategy.py")
        st.stop()

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("年化收益", f"{metrics.get('strategy_annual_return',0)*100:.1f}%")
    c2.metric("超额年化", f"{metrics.get('excess_annual_return',0)*100:.1f}%")
    c3.metric("Sharpe", f"{metrics.get('strategy_sharpe',0):.2f}")
    c4.metric("最大回撤", f"{abs(metrics.get('max_drawdown',0))*100:.1f}%")
    c5.metric("信息比率", f"{metrics.get('information_ratio',0):.2f}")

    # NAV chart
    fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3],
                        shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=['净值曲线', '策略回撤'])

    fig.add_trace(go.Scatter(x=nav_df['date'], y=nav_df['strategy'],
                             name='策略', line=dict(color='#1f77b4', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=nav_df['date'], y=nav_df['benchmark'],
                             name='CSI300', line=dict(color='#d62728', width=1.5, dash='dot')),
                  row=1, col=1)

    dd = (nav_df['strategy'] / nav_df['strategy'].cummax() - 1) * 100
    fig.add_trace(go.Scatter(x=nav_df['date'], y=dd, fill='tozeroy',
                             fillcolor='rgba(255,0,0,0.2)', line=dict(color='red', width=0.5),
                             name='回撤 (%)'), row=2, col=1)

    fig.update_layout(height=600, legend=dict(x=0.01, y=0.99),
                      xaxis2_title='日期', yaxis_title='净值', yaxis2_title='回撤 (%)')
    st.plotly_chart(fig, use_container_width=True)

    # Excess return
    if len(nav_df) > 1 and 'benchmark' in nav_df.columns:
        excess = (nav_df['strategy'] / nav_df['strategy'].iloc[0] -
                  nav_df['benchmark'] / nav_df['benchmark'].iloc[0])
        fig2 = go.Figure(go.Scatter(
            x=nav_df['date'], y=excess,
            fill='tozeroy',
            fillcolor='rgba(31,119,180,0.2)',
            line=dict(color='#1f77b4'),
            name='超额净值'
        ))
        fig2.update_layout(title='超额收益净值', height=300,
                           yaxis_title='超额净值', xaxis_title='日期')
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 全部指标")
    for k, v in metrics.items():
        pct_keys = {'strategy_annual_return', 'benchmark_annual_return',
                    'excess_annual_return', 'max_drawdown', 'total_return',
                    'benchmark_total_return'}
        display = f"{v*100:.2f}%" if k in pct_keys else str(v)
        st.write(f"- **{k}**: {display}")


# ============================================================
# Page: 风险报告
# ============================================================
elif page == "⚠️ 风险报告":
    st.title("⚠️ 风险审查报告")
    risk = load_risk_report()

    if risk is None:
        st.warning("Phase 5 结果尚未生成，请先运行 run_risk_report.py")
        st.stop()

    # Approval gate
    approval = risk.get('approval', {})
    verdict = approval.get('verdict', '未知')
    if '✅' in verdict:
        st.success(f"### 风控最终结论: {verdict}")
    else:
        st.error(f"### 风控最终结论: {verdict}")

    st.subheader("检查清单")
    for c in approval.get('checks', []):
        icon = "✅" if c['pass'] else "❌"
        st.write(f"{icon} **{c['rule']}**: {c['detail']}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 风险指标")
        rm = risk.get('risk_metrics', {})
        metrics_display = {
            'Sortino 比率': rm.get('sortino_ratio', 0),
            'Calmar 比率': rm.get('calmar_ratio', 0),
            'VaR (95%, 日)': f"{rm.get('var_95', 0)*100:.3f}%",
            'VaR (99%, 日)': f"{rm.get('var_99', 0)*100:.3f}%",
            'CVaR (95%, 日)': f"{rm.get('cvar_95', 0)*100:.3f}%",
            'CVaR (99%, 日)': f"{rm.get('cvar_99', 0)*100:.3f}%",
            '年化波动率': f"{rm.get('annual_volatility', 0)*100:.2f}%",
            '偏度 (Skewness)': rm.get('skewness', 0),
            '超额峰度 (Kurt)': rm.get('kurtosis', 0),
        }
        for k, v in metrics_display.items():
            st.write(f"- **{k}**: {v}")

    with col2:
        st.subheader("📉 最大回撤分析")
        dd_analysis = risk.get('drawdown_analysis', {})
        st.write(f"- **最大回撤**: {dd_analysis.get('max_drawdown', 0)*100:.1f}%")
        st.write(f"- **发生日期**: {dd_analysis.get('max_drawdown_date', 'N/A')}")
        st.write(f"- **平均回撤**: {dd_analysis.get('avg_drawdown', 0)*100:.1f}%")

        st.write("\n**Top 5 回撤事件:**")
        for d in dd_analysis.get('top_5_drawdowns', []):
            st.write(f"  - {d['start']} ~ {d['end']}: 深度={d['depth']*100:.1f}%, "
                     f"持续{d['length_days']}天")

    st.subheader("📅 年度绩效")
    yearly = risk.get('yearly_performance', {})
    if yearly:
        yearly_df = pd.DataFrame(yearly).T.reset_index()
        yearly_df.columns = ['年份', '年化收益率', 'Sharpe', '最大回撤']
        for col in ['年化收益率', '最大回撤']:
            yearly_df[col] = yearly_df[col].apply(lambda x: f"{float(x)*100:.1f}%")
        st.dataframe(yearly_df, use_container_width=True)

        fig = go.Figure(go.Bar(
            x=list(yearly.keys()),
            y=[float(v['total_return']) * 100 for v in yearly.values()],
            marker_color=['green' if float(v['total_return']) > 0 else 'red'
                          for v in yearly.values()],
            text=[f"{float(v['total_return'])*100:.1f}%" for v in yearly.values()],
            textposition='auto',
        ))
        fig.update_layout(title='年度收益率', yaxis_title='收益率 (%)', height=300)
        st.plotly_chart(fig, use_container_width=True)

    # Lookahead check
    st.subheader("🔍 前瞻偏差检查")
    la = risk.get('lookahead_check', {})
    la_status = "⚠️ 可疑" if la.get('lookahead_suspicious') else "✅ 通过"
    st.write(f"**结果**: {la_status}")
    st.write(f"**说明**: {la.get('note', '')}")
    st.write(f"- 策略 Sharpe: {la.get('sharpe', 0):.2f}")
    st.write(f"- 月度盈利占比: {la.get('positive_months_pct', 0)*100:.1f}%")
