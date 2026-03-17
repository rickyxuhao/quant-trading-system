"""
Streamlit量化交易策略分析Dashboard

运行方式:
    streamlit run projects/quant_trading/visualization/app.py

或指定端口:
    streamlit run projects/quant_trading/visualization/app.py --server.port 8502
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import datetime, date, timedelta

from projects.quant_trading.visualization.config import viz_config
from projects.quant_trading.visualization.state_manager import StateManager
from projects.quant_trading.visualization.utils.data_loader import DataLoader

# 页面配置
st.set_page_config(
    page_title=viz_config.page_title,
    page_icon=viz_config.page_icon,
    layout=viz_config.layout,
    initial_sidebar_state="expanded",
)

# 初始化状态
StateManager.init()

# 自定义CSS样式
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f2f6;
        border-bottom: 2px solid #1f77b4;
    }
</style>
""",
    unsafe_allow_html=True,
)


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("⚙️ 回测配置")

        # 策略选择
        st.subheader("策略选择")
        strategies = DataLoader.get_available_strategies()
        strategy_names = [s["name"] for s in strategies]

        selected_strategy_name = st.selectbox(
            "选择策略", strategy_names, index=0, key="sidebar_strategy"
        )

        selected_strategy = next(
            (s for s in strategies if s["name"] == selected_strategy_name), None
        )
        StateManager.set("selected_strategy", selected_strategy)

        # 显示策略类型标签
        if selected_strategy:
            strategy_type = selected_strategy.get("type", "unknown")
            type_labels = {"technical": "技术指标", "ml": "机器学习", "arbitrage": "套利策略"}
            st.caption(f"类型: {type_labels.get(strategy_type, strategy_type)}")

        # 日期范围
        st.subheader("时间范围")
        end_date = st.date_input("结束日期", date.today(), key="sidebar_end_date")
        start_date = st.date_input(
            "开始日期", end_date - timedelta(days=365 * 2), key="sidebar_start_date"
        )

        if start_date >= end_date:
            st.error("开始日期必须早于结束日期")

        StateManager.set("start_date", start_date)
        StateManager.set("end_date", end_date)

        # 初始资金
        st.subheader("资金配置")
        initial_capital = (
            st.number_input(
                "初始资金（万元）",
                min_value=10,
                max_value=10000,
                value=100,
                step=10,
                key="sidebar_capital",
            )
            * 10000
        )

        StateManager.set("initial_capital", initial_capital)

        # 基准选择
        st.subheader("基准对比")
        benchmark = st.selectbox(
            "选择基准",
            ["000300.SH (沪深300)", "000905.SH (中证500)", "000001.SH (上证指数)"],
            index=0,
            key="sidebar_benchmark",
        )

        # 运行回测按钮
        st.divider()
        if st.button("🚀 运行回测", type="primary", use_container_width=True):
            run_backtest()

        # 加载示例数据按钮
        if st.button("📊 加载示例数据", use_container_width=True):
            with st.spinner("加载示例数据..."):
                mock_results = DataLoader.generate_mock_backtest_results(
                    start_date=datetime.combine(start_date, datetime.min.time()),
                    end_date=datetime.combine(end_date, datetime.min.time()),
                )
                StateManager.set("backtest_results", mock_results)
                st.success("示例数据已加载！")
                st.rerun()

        # 页面导航
        st.divider()
        st.header("📑 页面导航")
        page = st.radio(
            "选择页面", ["策略绩效", "交易明细", "模型诊断", "参数调优"], key="sidebar_page"
        )

    return page


def run_backtest():
    """执行回测"""
    start_date = StateManager.get("start_date")
    end_date = StateManager.get("end_date")
    strategy = StateManager.get("selected_strategy")

    if not start_date or not end_date:
        st.error("请先设置回测日期范围")
        return

    if start_date >= end_date:
        st.error("开始日期必须早于结束日期")
        return

    with st.spinner("正在运行回测..."):
        try:
            # TODO: 集成实际的回测引擎
            # 目前使用模拟数据演示
            mock_results = DataLoader.generate_mock_backtest_results(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
            )

            # 添加策略信息到结果
            mock_results["config"]["strategy"] = (
                strategy.get("name", "Unknown") if strategy else "Unknown"
            )

            StateManager.set("backtest_results", mock_results)
            StateManager.set(
                "last_run_params",
                {
                    "strategy": strategy,
                    "start_date": start_date,
                    "end_date": end_date,
                    "timestamp": datetime.now(),
                },
            )

            st.success("回测完成！")
            st.rerun()

        except Exception as e:
            st.error(f"回测失败: {str(e)}")


def render_header():
    """渲染页面头部"""
    st.markdown('<p class="main-header">📈 量化交易策略分析</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">交互式策略回测与绩效分析平台</p>', unsafe_allow_html=True)

    # 显示当前回测信息
    last_run = StateManager.get("last_run_params")
    if last_run:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.caption("当前策略")
            strategy = last_run.get("strategy", {})
            st.write(strategy.get("name", "Unknown") if strategy else "Unknown")
        with col2:
            st.caption("回测区间")
            start = last_run.get("start_date")
            end = last_run.get("end_date")
            if start and end:
                st.write(f"{start} ~ {end}")
        with col3:
            st.caption("运行时间")
            ts = last_run.get("timestamp")
            if ts:
                st.write(ts.strftime("%Y-%m-%d %H:%M"))
        with col4:
            results = StateManager.get("backtest_results")
            if results:
                metrics = results.get("metrics")
                if metrics:
                    st.caption("当前年化收益")
                    st.write(f"{metrics.annual_return*100:+.2f}%")

        st.divider()


def main():
    """主函数"""
    render_header()

    # 侧边栏
    page = render_sidebar()

    # 根据选择加载不同页面
    if page == "策略绩效":
        from projects.quant_trading.visualization.pages.performance import render_performance_page

        render_performance_page()
    elif page == "交易明细":
        from projects.quant_trading.visualization.pages.trades import render_trades_page

        render_trades_page()
    elif page == "模型诊断":
        from projects.quant_trading.visualization.pages.model_diagnosis import (
            render_model_diagnosis_page,
        )

        render_model_diagnosis_page()
    elif page == "参数调优":
        from projects.quant_trading.visualization.pages.optimization import render_optimization_page

        render_optimization_page()

    # 页脚
    st.divider()
    footer_col1, footer_col2, footer_col3 = st.columns([1, 2, 1])
    with footer_col2:
        st.caption(
            f"© 2024 量化交易系统 | 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )


if __name__ == "__main__":
    main()
