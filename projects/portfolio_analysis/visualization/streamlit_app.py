"""
Streamlit 持仓分析仪表盘

运行方式:
    streamlit run projects/portfolio_analysis/visualization/streamlit_app.py

功能:
- 实时持仓概览
- 净值曲线分析
- 行业分布可视化
- 风险预警展示
- 持仓明细列表
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st

from projects.portfolio_analysis import PortfolioAnalyzer
from projects.portfolio_analysis.core.structure_analyzer import StructureAnalyzer
from projects.portfolio_analysis.core.risk_diagnostic import RiskDiagnostic
from projects.portfolio_analysis.visualization.charts import (
    create_nav_chart,
    create_sector_pie,
    create_pnl_waterfall,
    create_drawdown_gauge,
    create_returns_bar,
    create_position_treemap,
)
from projects.portfolio_analysis.database.repository import PositionRepository

# 页面配置
st.set_page_config(
    page_title="持仓分析系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 样式设置
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin: 5px;
    }
    .risk-critical {
        color: #e74c3c;
        font-weight: bold;
    }
    .risk-warning {
        color: #f39c12;
        font-weight: bold;
    }
    .risk-info {
        color: #3498db;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化session state"""
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = PortfolioAnalyzer()
    if 'structure_analyzer' not in st.session_state:
        st.session_state.structure_analyzer = StructureAnalyzer()
    if 'risk_diagnostic' not in st.session_state:
        st.session_state.risk_diagnostic = RiskDiagnostic()


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("⚙️ 设置")

        # 日期范围
        st.subheader("分析区间")
        end_date = st.date_input("结束日期", date.today())
        start_date = st.date_input(
            "开始日期",
            end_date - timedelta(days=90)
        )

        # 基准选择
        benchmark = st.selectbox(
            "基准指数",
            ["沪深300", "中证500", "创业板指", "上证指数"],
            index=0
        )

        # 风险阈值
        st.subheader("风险阈值")
        drawdown_threshold = st.slider(
            "回撤预警阈值 (%)",
            min_value=5,
            max_value=30,
            value=10
        ) / 100

        # 刷新按钮
        st.divider()
        if st.button("🔄 刷新数据", type="primary"):
            st.cache_data.clear()
            st.rerun()

    return start_date, end_date, benchmark, drawdown_threshold


@st.cache_data(ttl=300)
def load_analysis(start_date: date, end_date: date):
    """加载分析数据（带缓存）"""
    analyzer = PortfolioAnalyzer()
    return analyzer.analyze(start_date, end_date)


@st.cache_data(ttl=300)
def load_structure_analysis():
    """加载结构分析数据"""
    analyzer = StructureAnalyzer()
    return {
        'sector': analyzer.analyze_sector_distribution(),
        'market_cap': analyzer.analyze_market_cap_style(),
        'concentration': analyzer.calculate_concentration(),
        'turnover': analyzer.calculate_turnover(30),
    }


@st.cache_data(ttl=300)
def load_risk_report():
    """加载风险报告"""
    diagnostic = RiskDiagnostic()
    return diagnostic.check_all()


def render_kpi_cards(analysis_result):
    """渲染KPI卡片"""
    metrics = analysis_result.metrics

    # 获取最新快照
    repo = PositionRepository()
    latest = repo.get_latest_snapshot()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total_asset = float(latest.total_asset) if latest else 0
        st.metric(
            label="💰 总资产",
            value=f"¥{total_asset:,.0f}",
            delta=f"{metrics.total_return*100:.2f}%" if metrics.total_return else None
        )

    with col2:
        daily_return = metrics.total_return * 100 if metrics.total_return else 0
        st.metric(
            label="📈 累计收益",
            value=f"{daily_return:+.2f}%",
        )

    with col3:
        st.metric(
            label="📊 夏普比率",
            value=f"{metrics.sharpe_ratio:.2f}",
        )

    with col4:
        drawdown = metrics.max_drawdown * 100 if metrics.max_drawdown else 0
        st.metric(
            label="📉 最大回撤",
            value=f"{drawdown:.2f}%",
            delta_color="inverse"
        )

    with col5:
        pos_count = len(analysis_result.positions)
        st.metric(
            label="📋 持仓数量",
            value=f"{pos_count} 只",
        )


def render_nav_chart(analysis_result):
    """渲染净值曲线"""
    st.subheader("净值走势")

    if not analysis_result.snapshots:
        st.info("暂无净值数据")
        return

    # 构建净值DataFrame
    nav_data = [
        {
            'date': s.date,
            'nav': float(s.net_value) if s.net_value else 1.0
        }
        for s in analysis_result.snapshots
    ]
    nav_df = pd.DataFrame(nav_data)

    # 这里可以添加基准数据
    fig = create_nav_chart(nav_df, title="净值曲线")
    st.plotly_chart(fig, use_container_width=True)


def render_position_analysis(analysis_result):
    """渲染持仓分析"""
    st.subheader("持仓分析")

    col1, col2 = st.columns(2)

    with col1:
        # 行业分布
        structure = load_structure_analysis()
        sector_df = structure['sector']

        if not sector_df.empty:
            fig = create_sector_pie(sector_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无行业分布数据")

    with col2:
        # 市值风格
        market_cap = structure['market_cap']

        st.markdown("#### 市值风格分布")
        for style, weight in market_cap.items():
            style_name = {'large': '🔵 大盘', 'mid': '🟢 中盘', 'small': '🟡 小盘'}.get(style, style)
            st.progress(weight, text=f"{style_name}: {weight*100:.1f}%")

        # 集中度
        st.markdown("#### 持仓集中度")
        concentration = structure['concentration']
        st.progress(concentration['top5_weight'], text=f"Top5: {concentration['top5_weight']*100:.1f}%")
        st.progress(concentration['top10_weight'], text=f"Top10: {concentration['top10_weight']*100:.1f}%")


def render_risk_alerts(analysis_result):
    """渲染风险预警"""
    st.subheader("⚠️ 风险预警")

    risk_report = load_risk_report()

    if not risk_report.alerts:
        st.success("✅ 未发现明显风险")
        return

    # 风险分数
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("风险分数", f"{risk_report.risk_score}/100")
    with col2:
        critical_count = len([a for a in risk_report.alerts if a.level == "critical"])
        st.metric("严重风险", critical_count)
    with col3:
        warning_count = len([a for a in risk_report.alerts if a.level == "warning"])
        st.metric("一般预警", warning_count)

    # 预警列表
    for alert in risk_report.alerts:
        if alert.level == "critical":
            st.error(f"🔴 **{alert.category}**: {alert.message}")
        elif alert.level == "warning":
            st.warning(f"🟡 **{alert.category}**: {alert.message}")
        else:
            st.info(f"🔵 **{alert.category}**: {alert.message}")


def render_position_table(analysis_result):
    """渲染持仓明细表"""
    st.subheader("持仓明细")

    if not analysis_result.positions:
        st.info("暂无持仓数据")
        return

    # 转换为DataFrame
    df = pd.DataFrame([
        {
            '代码': p.code,
            '名称': p.name,
            '数量': p.volume,
            '成本价': f"{p.cost_price:.2f}",
            '现价': f"{p.current_price:.2f}",
            '市值': f"{p.market_value:,.0f}",
            '盈亏': f"{p.pnl:+,.0f}",
            '盈亏率': f"{p.pnl_pct*100:+.2f}%",
            '权重': f"{p.weight*100:.2f}%",
            '行业': p.sector,
        }
        for p in analysis_result.positions
    ])

    # 样式化
    def color_pnl(val):
        if '+' in str(val):
            return 'color: #2ecc71'
        elif '-' in str(val):
            return 'color: #e74c3c'
        return ''

    styled_df = df.style.map(color_pnl, subset=['盈亏', '盈亏率'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_metrics_table(analysis_result):
    """渲染绩效指标表"""
    st.subheader("绩效指标")

    metrics = analysis_result.metrics

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 收益指标")
        st.write(f"**总收益率**: {metrics.total_return*100:.2f}%")
        st.write(f"**年化收益率**: {metrics.annual_return*100:.2f}%")
        st.write(f"**累计收益额**: ¥{metrics.cumulative_return:,.0f}")

    with col2:
        st.markdown("#### 风险指标")
        st.write(f"**最大回撤**: {metrics.max_drawdown*100:.2f}%")
        st.write(f"**波动率**: {metrics.volatility*100:.2f}%")
        st.write(f"**下行波动率**: {metrics.downside_volatility*100:.2f}%")
        st.write(f"**VaR(95%)**: {metrics.var_95*100:.2f}%")

    with col3:
        st.markdown("#### 风险调整收益")
        st.write(f"**夏普比率**: {metrics.sharpe_ratio:.2f}")
        st.write(f"**索提诺比率**: {metrics.sortino_ratio:.2f}")
        st.write(f"**卡玛比率**: {metrics.calmar_ratio:.2f}")
        st.write(f"**Omega比率**: {metrics.omega_ratio:.2f}")

    # 相对基准指标
    if metrics.beta != 0:
        st.markdown("#### 相对基准")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.write(f"**Alpha**: {metrics.alpha:.4f}")
        with col2:
            st.write(f"**Beta**: {metrics.beta:.4f}")
        with col3:
            st.write(f"**信息比率**: {metrics.information_ratio:.2f}")
        with col4:
            st.write(f"**超额收益**: {metrics.excess_return*100:.2f}%")


def main():
    """主函数"""
    st.title("📊 持仓健康诊断")
    st.markdown("基于真实持仓数据的专业分析系统")

    # 初始化
    init_session_state()

    # 侧边栏
    start_date, end_date, benchmark, drawdown_threshold = render_sidebar()

    # 加载数据
    with st.spinner("正在加载数据..."):
        try:
            analysis_result = load_analysis(start_date, end_date)
        except Exception as e:
            st.error(f"数据加载失败: {e}")
            analysis_result = None

    if analysis_result is None:
        st.error("无法加载分析数据，请检查数据库连接")
        return

    # KPI卡片
    render_kpi_cards(analysis_result)

    st.divider()

    # 主要内容区域
    tab1, tab2, tab3, tab4 = st.tabs(["📈 净值分析", "📊 持仓结构", "⚠️ 风险诊断", "📋 持仓明细"])

    with tab1:
        render_nav_chart(analysis_result)
        render_metrics_table(analysis_result)

    with tab2:
        render_position_analysis(analysis_result)

    with tab3:
        render_risk_alerts(analysis_result)

    with tab4:
        render_position_table(analysis_result)

    # 页脚
    st.divider()
    st.caption(f"数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
