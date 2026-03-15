"""
股票持仓分析系统

基于现有回测框架扩展，提供真实持仓分析能力：
1. SQLAlchemy管理真实持仓数据
2. 接入现有MetricsCalculator计算绩效指标
3. Streamlit可视化仪表盘
4. PDF报告生成
5. ML策略回测接口预留

Example:
    >>> from projects.portfolio_analysis import PortfolioAnalyzer
    >>> analyzer = PortfolioAnalyzer()
    >>> result = analyzer.analyze(start_date, end_date)
    >>> print(result.metrics.sharpe_ratio)
"""

from projects.portfolio_analysis.core.analyzer import PortfolioAnalyzer
from projects.portfolio_analysis.core.structure_analyzer import StructureAnalyzer
from projects.portfolio_analysis.core.risk_diagnostic import RiskDiagnostic
from projects.portfolio_analysis.database.models import (
    Position, Transaction, PortfolioSnapshot, PositionHistory
)
from projects.portfolio_analysis.database.repository import PositionRepository

__version__ = "1.0.0"

__all__ = [
    # Core analyzers
    "PortfolioAnalyzer",
    "StructureAnalyzer",
    "RiskDiagnostic",
    # Database models
    "Position",
    "Transaction",
    "PortfolioSnapshot",
    "PositionHistory",
    # Repository
    "PositionRepository",
]
