"""Streamlit session state管理"""

import streamlit as st
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from datetime import date
from projects.quant_trading.backtest.metrics import PerformanceMetrics


@dataclass
class AppState:
    """应用状态"""

    selected_strategy: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    backtest_results: Optional[Dict] = None
    current_params: Optional[Dict] = None
    comparison_results: List[Dict] = field(default_factory=list)
    selected_metrics: Optional[PerformanceMetrics] = None
    benchmark_metrics: Optional[PerformanceMetrics] = None


class StateManager:
    """状态管理器 - 管理Streamlit session state"""

    @staticmethod
    def init():
        """初始化session state"""
        defaults = {
            "selected_strategy": None,
            "start_date": None,
            "end_date": None,
            "backtest_results": None,
            "current_params": {},
            "comparison_results": [],
            "selected_metrics": None,
            "benchmark_metrics": None,
            "last_run_params": None,
            "data_loaded": False,
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @staticmethod
    def get(key: str) -> Any:
        """获取状态值"""
        return st.session_state.get(key)

    @staticmethod
    def set(key: str, value: Any):
        """设置状态值"""
        st.session_state[key] = value

    @staticmethod
    def has(key: str) -> bool:
        """检查状态键是否存在"""
        return key in st.session_state

    @staticmethod
    def clear_backtest_results():
        """清除回测结果"""
        keys_to_clear = [
            "backtest_results",
            "selected_metrics",
            "benchmark_metrics",
            "last_run_params",
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = None

    @staticmethod
    def add_comparison_result(result: Dict):
        """添加参数对比结果"""
        if "comparison_results" not in st.session_state:
            st.session_state["comparison_results"] = []
        st.session_state["comparison_results"].append(result)

    @staticmethod
    def clear_comparison_results():
        """清除所有对比结果"""
        st.session_state["comparison_results"] = []

    @staticmethod
    def get_comparison_results() -> List[Dict]:
        """获取所有对比结果"""
        return st.session_state.get("comparison_results", [])
