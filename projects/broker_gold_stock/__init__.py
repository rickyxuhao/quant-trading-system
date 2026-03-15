"""
券商金股监控分析系统

主要功能：
1. 券商金股数据同步 - 从Tushare获取券商推荐
2. 多维度分析 - 技术面、财务面、量化因子
3. 异动检测 - 价格、成交量异动监控
4. AI分析 - 新闻情感分析、投资建议
5. 晨间报告 - 每日投资报告生成
"""

__version__ = "1.0.0"
__author__ = "Stock Trading System"

from projects.broker_gold_stock.data.models import (
    GoldStock,
    GoldStockPerformance,
    FinancialAnalysis,
    QuantFactorScore,
    StockAnomaly,
    NewsSentiment,
    MorningReport,
)

from projects.broker_gold_stock.data.repository import (
    GoldStockRepository,
    PerformanceRepository,
    FinancialRepository,
    QuantFactorRepository,
    AnomalyRepository,
    NewsRepository,
    MorningReportRepository,
)

__all__ = [
    # 数据模型
    'GoldStock',
    'GoldStockPerformance',
    'FinancialAnalysis',
    'QuantFactorScore',
    'StockAnomaly',
    'NewsSentiment',
    'MorningReport',
    # 数据访问
    'GoldStockRepository',
    'PerformanceRepository',
    'FinancialRepository',
    'QuantFactorRepository',
    'AnomalyRepository',
    'NewsRepository',
    'MorningReportRepository',
]
