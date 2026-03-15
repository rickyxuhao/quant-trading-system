"""
数据模型定义 - 券商金股监控分析系统
使用 dataclass 定义核心数据结构
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AnomalyType(Enum):
    """异动类型"""
    PRICE_SPIKE = "price_spike"          # 价格异动
    VOLUME_SURGE = "volume_surge"        # 成交量异动
    LIMIT_UP = "limit_up"                # 涨停
    LIMIT_DOWN = "limit_down"            # 跌停
    TECHNICAL_BREAKOUT = "technical_breakout"  # 技术突破
    NEWS_DRIVEN = "news_driven"          # 新闻驱动


class AnomalySeverity(Enum):
    """异动严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StockStatus(Enum):
    """股票状态"""
    HOLDING = "holding"      # 持仓中
    CLOSED = "closed"        # 已结束
    WATCHING = "watching"    # 观察中


class Recommendation(Enum):
    """投资建议"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL = "sell"
    AVOID = "avoid"


@dataclass
class GoldStock:
    """券商金股推荐"""
    id: Optional[int] = None
    month: str = ""                          # 月份 YYYYMM
    broker_name: str = ""                    # 券商名称
    ts_code: str = ""                        # TS股票代码
    name: str = ""                           # 股票名称
    industry: str = ""                       # 所属行业
    analyst: str = ""                        # 分析师
    logic: str = ""                          # 推荐逻辑
    target_price: Optional[float] = None     # 目标价
    previous_perf: Optional[float] = None    # 上月涨跌幅%
    created_at: Optional[datetime] = None


@dataclass
class GoldStockPerformance:
    """金股表现追踪"""
    id: Optional[int] = None
    month: str = ""                          # 推荐月份
    ts_code: str = ""                        # TS代码
    name: str = ""                           # 股票名称
    recommend_date: str = ""                 # 推荐日期
    end_date: Optional[str] = None           # 统计截止日期

    # 价格表现
    recommend_price: Optional[float] = None  # 推荐日收盘价
    current_price: Optional[float] = None    # 当前价格
    max_price: Optional[float] = None        # 月内最高价
    min_price: Optional[float] = None        # 月内最低价

    # 收益统计
    total_return: Optional[float] = None     # 累计收益率%
    excess_return: Optional[float] = None    # 超额收益%
    max_drawdown: Optional[float] = None     # 最大回撤%

    # 市场数据
    avg_volume: Optional[float] = None       # 日均成交额(万元)
    volatility: Optional[float] = None       # 波动率

    # 技术信号
    technical_score: Optional[int] = None    # 技术评分
    technical_signals: Optional[Dict] = None # 技术信号详情

    # 扩展字段
    ext_data: Optional[Dict] = None

    status: StockStatus = StockStatus.WATCHING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class FinancialAnalysis:
    """财务指标分析"""
    id: Optional[int] = None
    ts_code: str = ""                        # TS代码
    name: str = ""                           # 股票名称
    report_date: str = ""                    # 报告期

    # 估值指标
    pe_ttm: Optional[float] = None           # PE TTM
    pb: Optional[float] = None               # PB
    ps_ttm: Optional[float] = None           # PS TTM
    peg: Optional[float] = None              # PEG

    # 盈利能力
    roe: Optional[float] = None              # ROE%
    roa: Optional[float] = None              # ROA%
    gross_margin: Optional[float] = None     # 毛利率%
    net_margin: Optional[float] = None       # 净利率%

    # 成长性
    revenue_growth: Optional[float] = None   # 营收增长率%
    profit_growth: Optional[float] = None    # 净利润增长率%

    # 财务健康
    debt_ratio: Optional[float] = None       # 资产负债率%
    current_ratio: Optional[float] = None    # 流动比率

    # 综合评分
    financial_score: Optional[int] = None    # 财务评分
    quality_tag: Optional[str] = None        # 质量标签

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class QuantFactorScore:
    """量化因子评分"""
    id: Optional[int] = None
    ts_code: str = ""                        # TS代码
    name: str = ""                           # 股票名称
    trade_date: str = ""                     # 交易日

    # 各因子得分
    value_factor: Optional[float] = None     # 估值因子
    quality_factor: Optional[float] = None   # 质量因子
    growth_factor: Optional[float] = None    # 成长因子
    momentum_factor: Optional[float] = None  # 动量因子
    volatility_factor: Optional[float] = None  # 波动率因子
    liquidity_factor: Optional[float] = None   # 流动性因子

    # 综合评分
    total_score: Optional[float] = None      # 综合因子得分
    rank_in_industry: Optional[int] = None   # 行业内排名
    rank_in_market: Optional[int] = None     # 全市场排名

    created_at: Optional[datetime] = None


@dataclass
class StockAnomaly:
    """股票异动检测记录"""
    id: Optional[int] = None
    ts_code: str = ""                        # TS代码
    name: str = ""                           # 股票名称
    detect_date: str = ""                    # 检测日期
    anomaly_type: str = ""                   # 异动类型
    severity: AnomalySeverity = AnomalySeverity.MEDIUM

    # 异动数据
    trigger_price: Optional[float] = None    # 触发价格
    price_change: Optional[float] = None     # 涨跌幅%
    volume_ratio: Optional[float] = None     # 量比

    # 分析结果
    news_collected: bool = False             # 是否收集新闻
    news_analyzed: bool = False              # 是否AI分析
    ai_analysis: Optional[str] = None        # AI分析结果
    ai_sentiment: Optional[str] = None       # AI情感判断

    # 投资建议
    recommendation: Optional[str] = None     # 建议动作
    confidence: Optional[float] = None       # 置信度

    created_at: Optional[datetime] = None


@dataclass
class NewsSentiment:
    """新闻舆情数据"""
    id: Optional[int] = None
    ts_code: str = ""                        # TS代码
    name: str = ""                           # 股票名称
    news_date: str = ""                      # 新闻日期
    title: str = ""                          # 标题
    content: Optional[str] = None            # 内容
    source: Optional[str] = None             # 来源
    url: Optional[str] = None                # 链接

    # 情感分析
    sentiment_score: Optional[float] = None  # 情感得分(-1到1)
    sentiment_label: Optional[str] = None    # 情感标签

    # AI分析
    ai_summary: Optional[str] = None         # AI摘要
    key_points: Optional[List[str]] = None   # 关键要点
    impact_assessment: Optional[str] = None  # 影响评估

    # 关联性
    relevance_score: Optional[float] = None  # 相关度得分

    created_at: Optional[datetime] = None


@dataclass
class MorningReport:
    """晨间投资报告"""
    id: Optional[int] = None
    report_date: str = ""                    # 报告日期

    # 报告元数据
    gold_stock_count: int = 0                # 监控金股数量
    anomaly_count: int = 0                   # 异动股票数量
    buy_signals: int = 0                     # 买入信号数量
    sell_signals: int = 0                    # 卖出信号数量

    # 报告内容
    summary: Optional[str] = None            # 执行摘要
    highlight_stocks: Optional[List[Dict]] = None  # 重点股票
    market_outlook: Optional[str] = None     # 市场展望

    # 策略信号(预留)
    strategy_signals: Optional[Dict] = None

    # 文件路径
    markdown_path: Optional[str] = None      # Markdown文件路径
    pdf_path: Optional[str] = None           # PDF文件路径

    # 发送记录
    sent_at: Optional[datetime] = None       # 发送时间
    send_status: Optional[str] = None        # 发送状态

    created_at: Optional[datetime] = None


@dataclass
class TechnicalScore:
    """技术评分结果"""
    total: int = 0                           # 总分(0-100)
    trend_score: int = 0                     # 趋势评分
    level_score: int = 0                     # 支撑压力评分
    momentum_score: int = 0                  # 动量评分
    volume_score: int = 0                    # 成交量评分
    signals: List[Dict[str, Any]] = field(default_factory=list)  # 信号详情


@dataclass
class FinancialScore:
    """财务评分结果"""
    total: int = 0                           # 总分(0-100)
    valuation_score: int = 0                 # 估值评分
    profitability_score: int = 0             # 盈利能力评分
    growth_score: int = 0                    # 成长性评分
    health_score: int = 0                    # 财务健康评分


@dataclass
class FactorScore:
    """因子评分结果"""
    value: Optional[float] = None            # 价值因子
    quality: Optional[float] = None          # 质量因子
    growth: Optional[float] = None           # 成长因子
    momentum: Optional[float] = None         # 动量因子
    volatility: Optional[float] = None       # 波动率因子
    liquidity: Optional[float] = None        # 流动性因子
    total: Optional[float] = None            # 综合得分


@dataclass
class StockAnalysis:
    """股票综合分析结果"""
    ts_code: str = ""
    name: str = ""
    trade_date: str = ""

    # 各维度评分
    technical: Optional[TechnicalScore] = None
    financial: Optional[FinancialScore] = None
    quant: Optional[FactorScore] = None

    # 综合评分
    composite_score: float = 0.0

    # 券商共识度
    broker_count: int = 1  # 被多少家券商推荐
    consensus_score: float = 0.0  # 共识度得分(0-100)

    # 数据溯源
    data_sources: Dict[str, Any] = field(default_factory=dict)

    # 异动信息
    anomalies: List[StockAnomaly] = field(default_factory=list)

    # 新闻舆情
    news: List[NewsSentiment] = field(default_factory=list)

    # 行业信息
    industry: str = ""
    industry_rank: Optional[int] = None  # 行业内排名


@dataclass
class InvestmentAdvice:
    """投资建议"""
    ts_code: str = ""
    name: str = ""
    action: Recommendation = Recommendation.HOLD
    confidence: float = 0.0                  # 置信度(0-1)
    reasoning: str = ""                      # 核心理由
    risk_factors: List[str] = field(default_factory=list)  # 风险提示
    target_price: Optional[float] = None     # 目标价
    stop_loss_price: Optional[float] = None  # 止损价
    position_suggestion: Optional[str] = None  # 仓位建议


@dataclass
class DailyStrategy:
    """每日投资策略"""
    date: str = ""
    market_outlook: str = ""
    overall_position: str = ""               # 整体仓位建议
    style_bias: str = ""                     # 风格偏好
    risk_level: str = ""                     # 风险等级

    # 操作建议
    focus_stocks: List[str] = field(default_factory=list)     # 开盘关注
    dip_buying: List[str] = field(default_factory=list)       # 逢低布局
    profit_taking: List[str] = field(default_factory=list)    # 止盈考虑
    avoid_stocks: List[str] = field(default_factory=list)     # 规避股票

    summary: str = ""                        # 策略总结
