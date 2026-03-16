"""可视化模块配置"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class VizConfig:
    """可视化配置"""

    # 页面设置
    page_title: str = "量化交易策略分析"
    page_icon: str = "📈"
    layout: str = "wide"

    # 默认参数
    default_initial_capital: float = 1_000_000.0
    default_start_date: str = "2020-01-01"
    default_benchmark: str = "000300.SH"  # 沪深300

    # 缓存设置
    cache_ttl: int = 300  # 5分钟

    # 图表样式
    color_primary: str = "#1f77b4"
    color_positive: str = "#2ecc71"
    color_negative: str = "#e74c3c"
    color_benchmark: str = "#ffa502"
    color_neutral: str = "#95a5a6"

    # 图表尺寸
    chart_height: int = 500
    chart_width: int = 800

    # 表格设置
    table_page_size: int = 20

    # 可用的策略列表
    available_strategies: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.available_strategies is None:
            self.available_strategies = [
                {"id": "ma_trend", "name": "MA趋势策略", "type": "technical"},
                {"id": "mean_reversion", "name": "均值回归策略", "type": "technical"},
                {"id": "ml_prediction", "name": "ML预测策略", "type": "ml"},
                {"id": "statistical_arbitrage", "name": "统计套利策略", "type": "arbitrage"},
                {"id": "leading_stock", "name": "龙头股策略", "type": "technical"},
            ]


# 全局配置实例
viz_config = VizConfig()
