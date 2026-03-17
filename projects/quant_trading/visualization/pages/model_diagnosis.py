"""模型诊断页面（适用于机器学习策略）"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from projects.quant_trading.visualization.state_manager import StateManager
from projects.quant_trading.visualization.utils.data_loader import DataLoader


def render_model_diagnosis_page():
    """渲染模型诊断页面"""
    st.header("模型诊断分析")

    # 获取回测结果
    results = StateManager.get("backtest_results")
    if results is None:
        with st.spinner("加载示例数据..."):
            results = DataLoader.generate_mock_backtest_results()

    # 检查是否是ML策略
    strategy_type = results.get("config", {}).get("strategy", "")
    is_ml_strategy = "ml" in strategy_type.lower() or "prediction" in strategy_type.lower()

    if not is_ml_strategy:
        st.info("当前策略不是机器学习策略，显示模拟数据用于演示。")

    st.info("此页面用于分析机器学习模型的预测性能，包括特征重要性、预测准确率等。")

    # 页面标签
    tab1, tab2, tab3, tab4 = st.tabs(["预测性能", "特征分析", "IC/IR分析", "分位数分析"])

    with tab1:
        render_prediction_performance()

    with tab2:
        render_feature_analysis()

    with tab3:
        render_ic_ir_analysis()

    with tab4:
        render_quantile_analysis()


def render_prediction_performance():
    """渲染预测性能分析"""
    st.subheader("预测准确率趋势")

    # 模拟预测准确率时序
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="W")
    np.random.seed(42)

    # 生成准确率数据（带趋势）
    base_accuracy = 0.55
    trend = np.sin(np.linspace(0, 4 * np.pi, len(dates))) * 0.05
    noise = np.random.normal(0, 0.03, len(dates))
    accuracy = (base_accuracy + trend + noise).clip(0.4, 0.75)

    accuracy_data = pd.DataFrame(
        {
            "date": dates,
            "accuracy": accuracy,
            "rolling_mean": pd.Series(accuracy).rolling(window=12).mean(),
        }
    )

    fig = go.Figure()

    # 准确率曲线
    fig.add_trace(
        go.Scatter(
            x=accuracy_data["date"],
            y=accuracy_data["accuracy"] * 100,
            mode="lines",
            name="预测准确率",
            line=dict(color="#1f77b4", width=1),
            opacity=0.6,
        )
    )

    # 滚动平均
    fig.add_trace(
        go.Scatter(
            x=accuracy_data["date"],
            y=accuracy_data["rolling_mean"] * 100,
            mode="lines",
            name="12周移动平均",
            line=dict(color="#e74c3c", width=2),
        )
    )

    # 随机基准线
    fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="随机基准(50%)")

    # 优秀线
    fig.add_hline(y=60, line_dash="dot", line_color="green", annotation_text="优秀线(60%)")

    fig.update_layout(
        xaxis_title="日期",
        yaxis_title="准确率 (%)",
        yaxis_range=[35, 80],
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True, key="accuracy_trend")

    # 性能统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("平均准确率", f"{accuracy.mean()*100:.1f}%")
    with col2:
        st.metric("最高准确率", f"{accuracy.max()*100:.1f}%")
    with col3:
        st.metric("最低准确率", f"{accuracy.min()*100:.1f}%")
    with col4:
        above_baseline = (accuracy > 0.5).mean()
        st.metric("超越基准比例", f"{above_baseline*100:.1f}%")


def render_feature_analysis():
    """渲染特征重要性分析"""
    st.subheader("特征重要性")

    # 模拟特征重要性数据
    features = pd.DataFrame(
        {
            "feature": [
                "MA5",
                "MA20",
                "RSI",
                "MACD",
                "Volatility",
                "Volume_MA",
                "Price_Momentum",
                "ATR",
                "Bollinger",
                "CCI",
                "ADX",
                "Stochastic",
            ],
            "importance": [
                0.145,
                0.128,
                0.115,
                0.098,
                0.087,
                0.076,
                0.072,
                0.065,
                0.058,
                0.032,
                0.024,
                0.018,
            ],
            "category": [
                "Trend",
                "Trend",
                "Momentum",
                "Momentum",
                "Volatility",
                "Volume",
                "Momentum",
                "Volatility",
                "Volatility",
                "Momentum",
                "Trend",
                "Momentum",
            ],
        }
    ).sort_values("importance", ascending=True)

    # 特征重要性柱状图
    color_map = {
        "Trend": "#3498db",
        "Momentum": "#e74c3c",
        "Volatility": "#f39c12",
        "Volume": "#2ecc71",
    }

    colors = [color_map.get(c, "#95a5a6") for c in features["category"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=features["importance"],
                y=features["feature"],
                orientation="h",
                marker_color=colors,
                text=[f"{x:.1%}" for x in features["importance"]],
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        xaxis_title="重要性",
        yaxis_title="特征",
        template="plotly_white",
        height=500,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, key="feature_importance")

    # 类别汇总
    st.subheader("特征类别汇总")
    category_summary = features.groupby("category")["importance"].sum().sort_values(ascending=False)

    col1, col2, col3, col4 = st.columns(4)
    for i, (category, importance) in enumerate(category_summary.items()):
        with [col1, col2, col3, col4][i % 4]:
            st.metric(f"{category}类", f"{importance:.1%}")

    # 特征重要性时序
    st.subheader("特征重要性稳定性")

    # 模拟时序特征重要性
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="M")
    top_features = features.tail(5)["feature"].tolist()

    importance_ts = []
    for feat in top_features:
        base_importance = features[features["feature"] == feat]["importance"].values[0]
        noise = np.random.normal(0, 0.02, len(dates))
        imp_values = (base_importance + np.cumsum(noise) * 0.1).clip(0.01, 0.3)

        for i, date in enumerate(dates):
            importance_ts.append({"date": date, "feature": feat, "importance": imp_values[i]})

    importance_df = pd.DataFrame(importance_ts)

    fig = px.line(
        importance_df,
        x="date",
        y="importance",
        color="feature",
        labels={"importance": "重要性", "date": "日期", "feature": "特征"},
    )
    fig.update_layout(template="plotly_white", height=400)

    st.plotly_chart(fig, use_container_width=True, key="feature_stability")


def render_ic_ir_analysis():
    """渲染IC/IR分析"""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("IC (信息系数) 滚动")

        dates = pd.date_range("2023-01-01", "2024-12-31", freq="W")
        np.random.seed(42)

        # 生成IC数据
        ic_values = np.random.normal(0.05, 0.12, len(dates))
        ic_data = pd.DataFrame(
            {
                "date": dates,
                "ic": ic_values,
                "ic_ma": pd.Series(ic_values).rolling(window=12).mean(),
            }
        )

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=ic_data["date"],
                y=ic_data["ic"],
                name="IC",
                marker_color=["#2ecc71" if x > 0 else "#e74c3c" for x in ic_data["ic"]],
                opacity=0.6,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=ic_data["date"],
                y=ic_data["ic_ma"],
                mode="lines",
                name="12周移动平均",
                line=dict(color="#3498db", width=2),
            )
        )

        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_hline(y=0.05, line_dash="dot", line_color="green", opacity=0.5)
        fig.add_hline(y=-0.05, line_dash="dot", line_color="red", opacity=0.5)

        fig.update_layout(
            xaxis_title="日期",
            yaxis_title="IC",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400,
            showlegend=True,
        )

        st.plotly_chart(fig, use_container_width=True, key="ic_chart")

        # IC统计
        st.markdown("**IC统计**")
        st.write(f"IC均值: {ic_values.mean():.4f}")
        st.write(f"IC标准差: {ic_values.std():.4f}")
        st.write(f"IC > 0 比例: {(ic_values > 0).mean():.1%}")

    with col2:
        st.subheader("IR (信息比率) 滚动")

        # 生成IR数据（累积IC/累积IC标准差）
        cum_ic = np.cumsum(ic_values)
        ir_values = (
            cum_ic
            / (np.arange(1, len(ic_values) + 1))
            / (pd.Series(ic_values).expanding().std() + 1e-6)
        )

        ir_data = pd.DataFrame({"date": dates, "ir": ir_values})

        fig = px.line(ir_data, x="date", y="ir", labels={"ir": "IR", "date": "日期"})
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_hline(y=0.5, line_dash="dot", line_color="green", opacity=0.5)

        fig.update_layout(template="plotly_white", height=400)

        st.plotly_chart(fig, use_container_width=True, key="ir_chart")

        # IR统计
        st.markdown("**IR统计**")
        st.write(f"IR均值: {ir_values.mean():.4f}")
        st.write(f"IR > 0.5 比例: {(ir_values > 0.5).mean():.1%}")


def render_quantile_analysis():
    """渲染分位数分析"""
    st.subheader("分位数收益单调性")

    # 模拟分位数收益数据
    np.random.seed(42)
    quantiles = range(1, 11)

    # 生成单调性较好的分位数收益
    base_returns = np.linspace(-0.02, 0.04, 10)
    noise = np.random.normal(0, 0.003, 10)
    actual_returns = base_returns + noise

    quantile_df = pd.DataFrame(
        {"quantile": quantiles, "actual_return": actual_returns, "predicted_return": base_returns}
    )

    fig = go.Figure()

    # 实际收益柱状图
    colors = ["#e74c3c" if x < 0 else "#2ecc71" for x in quantile_df["actual_return"]]
    fig.add_trace(
        go.Bar(
            x=quantile_df["quantile"],
            y=quantile_df["actual_return"] * 100,
            name="实际收益",
            marker_color=colors,
            text=[f"{x*100:.2f}%" for x in quantile_df["actual_return"]],
            textposition="outside",
        )
    )

    # 预测收益线
    fig.add_trace(
        go.Scatter(
            x=quantile_df["quantile"],
            y=quantile_df["predicted_return"] * 100,
            mode="lines+markers",
            name="预测收益",
            line=dict(color="#3498db", width=2),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        xaxis_title="预测分位 (1=最低, 10=最高)",
        yaxis_title="平均实际收益 (%)",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    st.plotly_chart(fig, use_container_width=True, key="quantile_returns")

    # 单调性检验
    st.subheader("单调性检验")

    # 计算秩相关系数
    from scipy.stats import spearmanr

    corr, pvalue = spearmanr(quantile_df["quantile"], quantile_df["actual_return"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Spearman相关系数", f"{corr:.4f}")
    with col2:
        st.metric("P值", f"{pvalue:.4f}")
    with col3:
        is_monotonic = corr > 0.3 and pvalue < 0.05
        st.metric("单调性检验", "通过 ✅" if is_monotonic else "未通过 ❌")

    # 多空收益
    st.subheader("多空组合表现")

    long_return = quantile_df[quantile_df["quantile"] == 10]["actual_return"].values[0]
    short_return = quantile_df[quantile_df["quantile"] == 1]["actual_return"].values[0]
    long_short_return = long_return - short_return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("多头收益 (Q10)", f"{long_return*100:.2f}%")
    with col2:
        st.metric("空头收益 (Q1)", f"{short_return*100:.2f}%")
    with col3:
        st.metric(
            "多空收益",
            f"{long_short_return*100:.2f}%",
            delta=f"{long_return*100:.2f}% - {short_return*100:.2f}%",
        )

    # 预测-实际散点图
    st.subheader("预测 vs 实际收益")

    n_points = 500
    np.random.seed(42)
    predicted = np.random.normal(0, 0.02, n_points)
    actual = predicted * 0.3 + np.random.normal(0, 0.015, n_points)

    scatter_df = pd.DataFrame({"predicted": predicted, "actual": actual})

    fig = px.scatter(
        scatter_df,
        x="predicted",
        y="actual",
        opacity=0.5,
        labels={"predicted": "预测收益", "actual": "实际收益"},
    )

    # 添加趋势线
    z = np.polyfit(predicted, actual, 1)
    p = np.poly1d(z)
    x_line = np.linspace(predicted.min(), predicted.max(), 100)

    fig.add_trace(
        go.Scatter(
            x=x_line, y=p(x_line), mode="lines", line=dict(color="red", width=2), name="趋势线"
        )
    )

    # 添加理想线
    fig.add_trace(
        go.Scatter(
            x=[-0.1, 0.1],
            y=[-0.1, 0.1],
            mode="lines",
            line=dict(color="gray", dash="dash"),
            name="理想线(y=x)",
        )
    )

    # 计算R²
    ss_res = np.sum((actual - p(predicted)) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    fig.update_layout(
        template="plotly_white",
        height=400,
        annotations=[
            dict(
                x=0.05,
                y=0.95,
                xref="paper",
                yref="paper",
                text=f"R² = {r_squared:.4f}",
                showarrow=False,
                bgcolor="white",
                bordercolor="black",
                borderwidth=1,
            )
        ],
    )

    st.plotly_chart(fig, use_container_width=True, key="pred_vs_actual")
