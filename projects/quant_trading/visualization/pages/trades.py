"""交易明细页面"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from projects.quant_trading.visualization.components.tables import render_trades_table
from projects.quant_trading.visualization.state_manager import StateManager
from projects.quant_trading.visualization.utils.data_loader import DataLoader


def render_trades_page():
    """渲染交易明细页面"""
    st.header("交易明细分析")

    # 获取回测结果
    results = StateManager.get("backtest_results")
    if results is None:
        with st.spinner("加载示例数据..."):
            results = DataLoader.generate_mock_backtest_results()

    trades_df = results.get("trades", pd.DataFrame())

    if trades_df.empty:
        st.info("暂无交易数据")
        return

    # 计算交易统计
    trade_stats = calculate_trade_stats(trades_df)

    # 统计概览卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总交易次数", trade_stats["total_trades"])
    with col2:
        st.metric("胜率", f"{trade_stats['win_rate']*100:.1f}%")
    with col3:
        st.metric("平均盈亏", f"¥{trade_stats['avg_pnl']:,.0f}")
    with col4:
        color = "normal" if trade_stats["total_pnl"] >= 0 else "inverse"
        st.metric("总盈亏", f"¥{trade_stats['total_pnl']:,.0f}", delta_color=color)

    st.divider()

    # 图表区域
    tab1, tab2, tab3 = st.tabs(["盈亏分析", "持仓周期", "交易明细"])

    with tab1:
        render_pnl_analysis(trades_df, trade_stats)

    with tab2:
        render_holding_analysis(trades_df)

    with tab3:
        render_trades_table(trades_df, height=600)


def calculate_trade_stats(trades_df: pd.DataFrame) -> dict:
    """计算交易统计信息"""
    if trades_df.empty:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "avg_pnl": 0,
            "total_pnl": 0,
        }

    # 按股票代码分组计算每笔完整交易的盈亏
    trades_by_stock = []
    for ts_code in trades_df["ts_code"].unique():
        stock_trades = trades_df[trades_df["ts_code"] == ts_code].copy()

        buy_trades = stock_trades[stock_trades["side"].str.lower() == "buy"]
        sell_trades = stock_trades[stock_trades["side"].str.lower() == "sell"]

        if not buy_trades.empty and not sell_trades.empty:
            total_buy = (buy_trades["amount"] + buy_trades["total_cost"]).sum()
            total_sell = (sell_trades["amount"] - sell_trades["total_cost"]).sum()
            pnl = total_sell - total_buy
            trades_by_stock.append({"ts_code": ts_code, "pnl": pnl, "is_win": pnl > 0})

    if not trades_by_stock:
        return {
            "total_trades": len(trades_df),
            "win_rate": 0,
            "avg_pnl": 0,
            "total_pnl": 0,
        }

    df = pd.DataFrame(trades_by_stock)

    return {
        "total_trades": len(trades_by_stock),
        "win_rate": df["is_win"].mean(),
        "avg_pnl": df["pnl"].mean(),
        "total_pnl": df["pnl"].sum(),
        "trades_df": df,
    }


def render_pnl_analysis(trades_df: pd.DataFrame, trade_stats: dict):
    """渲染盈亏分析图表"""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("个股盈亏分布")

        # 按股票代码计算盈亏
        stock_pnl = []
        for ts_code in trades_df["ts_code"].unique():
            stock_trades = trades_df[trades_df["ts_code"] == ts_code]
            buy_trades = stock_trades[stock_trades["side"].str.lower() == "buy"]
            sell_trades = stock_trades[stock_trades["side"].str.lower() == "sell"]

            if not buy_trades.empty and not sell_trades.empty:
                total_buy = (buy_trades["amount"] + buy_trades["total_cost"]).sum()
                total_sell = (sell_trades["amount"] - sell_trades["total_cost"]).sum()
                pnl = total_sell - total_buy
                stock_pnl.append({"ts_code": ts_code, "pnl": pnl})

        if stock_pnl:
            pnl_df = pd.DataFrame(stock_pnl)
            colors = ["#2ecc71" if x > 0 else "#e74c3c" for x in pnl_df["pnl"]]

            fig = go.Figure(
                data=[go.Bar(x=pnl_df["ts_code"], y=pnl_df["pnl"], marker_color=colors)]
            )
            fig.update_layout(
                xaxis_title="股票代码", yaxis_title="盈亏 (¥)", template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True, key="pnl_by_stock")

    with col2:
        st.subheader("盈亏分布直方图")

        trades_detail = trade_stats.get("trades_df")
        if trades_detail is not None and not trades_detail.empty:
            profit_trades = trades_detail[trades_detail["pnl"] > 0]
            loss_trades = trades_detail[trades_detail["pnl"] <= 0]

            fig = go.Figure()

            fig.add_trace(
                go.Histogram(
                    x=profit_trades["pnl"], name="盈利", marker_color="#2ecc71", opacity=0.7
                )
            )

            fig.add_trace(
                go.Histogram(x=loss_trades["pnl"], name="亏损", marker_color="#e74c3c", opacity=0.7)
            )

            fig.update_layout(
                xaxis_title="盈亏 (¥)",
                yaxis_title="次数",
                barmode="overlay",
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True, key="pnl_histogram")

    # 连续盈亏分析
    st.subheader("连续盈亏分析")
    render_consecutive_analysis(trades_df)


def render_consecutive_analysis(trades_df: pd.DataFrame):
    """渲染连续盈亏分析"""
    # 按时间排序的交易盈亏序列
    trades_by_stock = []
    for ts_code in trades_df["ts_code"].unique():
        stock_trades = trades_df[trades_df["ts_code"] == ts_code]
        buy_trades = stock_trades[stock_trades["side"].str.lower() == "buy"]
        sell_trades = stock_trades[stock_trades["side"].str.lower() == "sell"]

        if not buy_trades.empty and not sell_trades.empty:
            last_sell = sell_trades.iloc[-1]
            total_buy = (buy_trades["amount"] + buy_trades["total_cost"]).sum()
            total_sell = (sell_trades["amount"] - sell_trades["total_cost"]).sum()
            pnl = total_sell - total_buy

            trades_by_stock.append(
                {
                    "ts_code": ts_code,
                    "date": last_sell["date"] if "date" in last_sell else None,
                    "pnl": pnl,
                    "is_win": pnl > 0,
                }
            )

    if not trades_by_stock:
        st.info("暂无足够数据进行分析")
        return

    # 按日期排序
    trades_df_sorted = pd.DataFrame(trades_by_stock)
    if "date" in trades_df_sorted.columns and trades_df_sorted["date"].notna().any():
        trades_df_sorted = trades_df_sorted.sort_values("date")

    # 计算连续序列
    trades_df_sorted["streak_group"] = (
        trades_df_sorted["is_win"] != trades_df_sorted["is_win"].shift()
    ).cumsum()
    streaks = (
        trades_df_sorted.groupby("streak_group")
        .agg({"is_win": "first", "pnl": "count"})
        .rename(columns={"pnl": "length"})
    )

    win_streaks = streaks[streaks["is_win"]]["length"]
    loss_streaks = streaks[~streaks["is_win"]]["length"]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**连续盈利统计**")
        if len(win_streaks) > 0:
            st.write(f"最长连续盈利: {win_streaks.max()} 次")
            st.write(f"平均连续盈利: {win_streaks.mean():.1f} 次")
            st.write(f"连续盈利次数: {len(win_streaks)} 次")
        else:
            st.write("暂无盈利记录")

    with col2:
        st.markdown("**连续亏损统计**")
        if len(loss_streaks) > 0:
            st.write(f"最长连续亏损: {loss_streaks.max()} 次")
            st.write(f"平均连续亏损: {loss_streaks.mean():.1f} 次")
            st.write(f"连续亏损次数: {len(loss_streaks)} 次")
        else:
            st.write("暂无亏损记录")


def render_holding_analysis(trades_df: pd.DataFrame):
    """渲染持仓周期分析"""
    # 计算持仓周期
    holding_periods = []

    for ts_code in trades_df["ts_code"].unique():
        stock_trades = trades_df[trades_df["ts_code"] == ts_code].copy()

        if "date" in stock_trades.columns:
            stock_trades["date"] = pd.to_datetime(stock_trades["date"])
            stock_trades = stock_trades.sort_values("date")

            # 匹配买卖对
            buy_trades = stock_trades[stock_trades["side"].str.lower() == "buy"]
            sell_trades = stock_trades[stock_trades["side"].str.lower() == "sell"]

            for _, sell in sell_trades.iterrows():
                # 找到对应的买入记录
                matching_buys = buy_trades[buy_trades["date"] < sell["date"]]
                if not matching_buys.empty:
                    buy_date = matching_buys.iloc[-1]["date"]
                    hold_days = (sell["date"] - buy_date).days

                    # 计算盈亏
                    total_buy = (
                        matching_buys.iloc[-1]["amount"] + matching_buys.iloc[-1]["total_cost"]
                    )
                    total_sell = sell["amount"] - sell["total_cost"]
                    pnl = total_sell - total_buy

                    holding_periods.append(
                        {
                            "ts_code": ts_code,
                            "hold_days": max(0, hold_days),
                            "pnl": pnl,
                            "is_win": pnl > 0,
                        }
                    )

    if not holding_periods:
        st.info("暂无持仓周期数据")
        return

    holding_df = pd.DataFrame(holding_periods)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("持仓周期分布")
        fig = px.histogram(
            holding_df,
            x="hold_days",
            nbins=20,
            labels={"hold_days": "持仓天数", "count": "次数"},
            color_discrete_sequence=["#1f77b4"],
        )
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, key="holding_dist")

    with col2:
        st.subheader("持仓周期 vs 盈亏")
        colors = ["#2ecc71" if x else "#e74c3c" for x in holding_df["is_win"]]

        fig = go.Figure(
            data=go.Scatter(
                x=holding_df["hold_days"],
                y=holding_df["pnl"],
                mode="markers",
                marker=dict(color=colors, size=10, opacity=0.6),
                text=holding_df["ts_code"],
            )
        )
        fig.update_layout(xaxis_title="持仓天数", yaxis_title="盈亏 (¥)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, key="holding_pnl")

    # 持仓统计
    st.subheader("持仓统计")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"平均持仓天数: {holding_df['hold_days'].mean():.1f} 天")
    with col2:
        st.write(f"最短持仓: {holding_df['hold_days'].min()} 天")
    with col3:
        st.write(f"最长持仓: {holding_df['hold_days'].max()} 天")
