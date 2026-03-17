"""数据表格组件"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List


def format_currency(value: float, precision: int = 2) -> str:
    """格式化为货币"""
    return f"¥{value:,.{precision}f}"


def format_percentage(value: float, precision: int = 2) -> str:
    """格式化为百分比"""
    return f"{value * 100:.{precision}f}%"


def format_number(value: float, precision: int = 2) -> str:
    """格式化数字"""
    return f"{value:,.{precision}f}"


def render_trades_table(
    trades_df: pd.DataFrame, height: int = 400, use_container_width: bool = True
):
    """
    渲染交易明细表格

    Args:
        trades_df: 交易记录DataFrame
        height: 表格高度
        use_container_width: 是否使用容器宽度
    """
    if trades_df.empty:
        st.info("暂无交易数据")
        return

    # 复制数据避免修改原始数据
    display_df = trades_df.copy()

    # 格式化日期列
    if "date" in display_df.columns:
        display_df["date"] = pd.to_datetime(display_df["date"]).dt.strftime("%Y-%m-%d")

    if "trade_date" in display_df.columns:
        display_df["trade_date"] = pd.to_datetime(display_df["trade_date"]).dt.strftime("%Y-%m-%d")

    # 格式化金额列
    currency_columns = ["price", "amount", "commission", "slip_cost", "total_cost", "pnl"]
    for col in currency_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: format_currency(x))

    # 列名映射
    column_config = {
        "date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
        "trade_date": st.column_config.DateColumn("交易日期", format="YYYY-MM-DD"),
        "ts_code": st.column_config.TextColumn("股票代码"),
        "side": st.column_config.TextColumn("方向"),
        "quantity": st.column_config.NumberColumn("数量", format="%d"),
        "price": st.column_config.TextColumn("价格"),
        "amount": st.column_config.TextColumn("金额"),
        "commission": st.column_config.TextColumn("佣金"),
        "slip_cost": st.column_config.TextColumn("滑点成本"),
        "total_cost": st.column_config.TextColumn("总成本"),
    }

    st.dataframe(
        display_df,
        use_container_width=use_container_width,
        height=height,
        column_config=column_config,
        hide_index=True,
    )


def render_positions_table(
    positions_df: pd.DataFrame, height: int = 400, use_container_width: bool = True
):
    """
    渲染持仓表格

    Args:
        positions_df: 持仓数据DataFrame
        height: 表格高度
        use_container_width: 是否使用容器宽度
    """
    if positions_df.empty:
        st.info("暂无持仓数据")
        return

    display_df = positions_df.copy()

    # 格式化日期
    if "date" in display_df.columns:
        display_df["date"] = pd.to_datetime(display_df["date"]).dt.strftime("%Y-%m-%d")

    # 格式化数值列
    currency_columns = ["cash", "positions_value", "total_value"]
    for col in currency_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: format_currency(x))

    column_config = {
        "date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
        "cash": st.column_config.TextColumn("现金"),
        "positions_value": st.column_config.TextColumn("持仓市值"),
        "total_value": st.column_config.TextColumn("总资产"),
        "position_count": st.column_config.NumberColumn("持仓数量", format="%d"),
    }

    st.dataframe(
        display_df,
        use_container_width=use_container_width,
        height=height,
        column_config=column_config,
        hide_index=True,
    )


def render_comparison_table(results: List[Dict[str, Any]], use_container_width: bool = True):
    """
    渲染参数对比表格

    Args:
        results: 对比结果列表，每项包含params和metrics
        use_container_width: 是否使用容器宽度
    """
    if not results:
        st.info("暂无对比数据")
        return

    rows = []
    for i, result in enumerate(results):
        row = {
            "组合": f"组合{i+1}",
        }

        # 添加参数
        params = result.get("params", {})
        row.update(params)

        # 添加指标
        metrics = result.get("metrics", {})
        if isinstance(metrics, dict):
            row["年化收益率"] = f"{metrics.get('annual_return', 0) * 100:.2f}%"
            row["夏普比率"] = f"{metrics.get('sharpe_ratio', 0):.2f}"
            row["最大回撤"] = f"{metrics.get('max_drawdown', 0) * 100:.2f}%"
            row["胜率"] = f"{metrics.get('win_rate', 0) * 100:.1f}%"
            row["总交易次数"] = metrics.get("total_trades", 0)

        rows.append(row)

    comparison_df = pd.DataFrame(rows)

    st.dataframe(comparison_df, use_container_width=use_container_width, hide_index=True)
