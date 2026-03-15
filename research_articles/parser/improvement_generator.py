"""
改进建议生成模块 - 针对中国市场特点生成策略改进建议

适配要点：
- T+1制度适配
- 涨跌停限制处理
- 成本精细化（印花税、佣金、滑点）
- 流动性约束（市值过滤、成交量阈值）
- 过拟合防范建议
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.logger import get_logger

from .strategy_extractor import StrategyElements, ModelType, VariableType

logger = get_logger(__name__)


class ComplexityLevel(Enum):
    """复杂度等级"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class ImprovementCategory(Enum):
    """改进建议分类"""
    TRADING_MECHANISM = "交易机制适配"      # T+1、涨跌停
    COST_OPTIMIZATION = "成本优化"          # 印花税、滑点
    LIQUIDITY = "流动性管理"                # 市值过滤、成交量
    RISK_CONTROL = "风险控制增强"           # 过拟合、回撤
    DATA_QUALITY = "数据质量"               # 停牌、复权
    MODEL_ROBUSTNESS = "模型稳健性"         # 正则化、集成


@dataclass
class ImprovementSuggestion:
    """改进建议数据结构"""
    category: ImprovementCategory
    title: str
    problem_description: str
    solution: str
    expected_effect: str
    complexity: ComplexityLevel
    implementation_priority: int  # 1-5, 1最高
    code_example: str = ""


class ImprovementGenerator:
    """改进建议生成器"""

    # 中国市场交易规则
    CHINA_MARKET_RULES = {
        "t_plus_one": True,
        "price_limit": 0.10,  # 主板10%
        "price_limit_st": 0.05,  # ST股5%
        "price_limit_growth": 0.20,  # 创业板/科创板20%
        "stamp_duty": 0.001,  # 印花税卖出方0.1%
        "commission_min": 5,  # 最低佣金5元
        "commission_rate": 0.00025,  # 佣金率0.025%
        "transfer_fee": 0.00002,  # 过户费
    }

    def __init__(self, elements: StrategyElements):
        self.elements = elements
        self.suggestions: list[ImprovementSuggestion] = []

    def generate(self) -> list[ImprovementSuggestion]:
        """
        生成针对中国市场的改进建议

        Returns:
            改进建议列表（按优先级排序）
        """
        logger.info("开始生成改进建议")

        # 分析策略特征
        has_high_frequency = self._is_high_frequency()
        uses_ml = self.elements.model and self.elements.model.model_type in [
            ModelType.NEURAL, ModelType.TREE, ModelType.ENSEMBLE
        ]
        has_short_signal = any(
            s.signal_type.value in ["entry_short", "exit_short"]
            for s in self.elements.signals
        )

        # 生成各类建议
        self._generate_trading_mechanism_suggestions(has_short_signal)
        self._generate_cost_suggestions(has_high_frequency)
        self._generate_liquidity_suggestions()
        self._generate_risk_control_suggestions(uses_ml)
        self._generate_data_quality_suggestions()

        # 按优先级排序
        self.suggestions.sort(key=lambda x: x.implementation_priority)

        logger.info(f"生成了 {len(self.suggestions)} 条改进建议")
        return self.suggestions

    def _is_high_frequency(self) -> bool:
        """判断是否为高频策略"""
        if self.elements.backtest:
            freq = self.elements.backtest.rebalance_frequency.lower()
            return freq in ["daily", "hourly", "minute"]

        # 检查特征是否包含高频指标
        for feature in self.elements.features:
            if feature.frequency in ["minute", "hourly", "tick"]:
                return True
        return False

    def _generate_trading_mechanism_suggestions(self, has_short: bool) -> None:
        """生成交易机制适配建议"""

        # T+1制度
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.TRADING_MECHANISM,
            title="T+1交易制度适配",
            problem_description="""
            中国A股实行T+1制度，当日买入的股票不能当日卖出。
            原策略如果假设可以日内交易，需要调整。
            """.strip(),
            solution="""
            1. 信号生成改为收盘前生成，次日开盘执行
            2. 避免当日买入当日卖出的逻辑
            3. 持仓过夜，次日根据新信号调仓
            4. 在回测中增加T+1约束检查
            """.strip(),
            expected_effect="策略更符合实际交易规则，避免不可执行的交易",
            complexity=ComplexityLevel.LOW,
            implementation_priority=1,
            code_example="""
# T+1约束检查
def can_sell(position_date, trade_date):
    return (trade_date - position_date).days >= 1
            """.strip()
        ))

        # 涨跌停限制
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.TRADING_MECHANISM,
            title="涨跌停限制处理",
            problem_description="""
            A股存在10%（主板）/20%（科创/创业）涨跌停限制，
            可能导致信号无法执行或滑点巨大。
            """.strip(),
            solution="""
            1. 过滤接近涨跌停的股票（如涨幅>9%或<-9%不买入）
            2. 考虑涨停无法买入、跌停无法卖出的情况
            3. 增加开盘集合竞价处理逻辑
            4. 对ST股票使用5%限制
            """.strip(),
            expected_effect="避免无效交易信号，提高策略可执行性",
            complexity=ComplexityLevel.LOW,
            implementation_priority=1,
            code_example="""
# 涨跌停过滤
def is_tradeable(stock, price_change):
    if stock.is_st:
        return -0.05 < price_change < 0.05
    return -0.095 < price_change < 0.095
            """.strip()
        ))

        # 做空限制
        if has_short:
            self.suggestions.append(ImprovementSuggestion(
                category=ImprovementCategory.TRADING_MECHANISM,
                title="融券做空限制适配",
                problem_description="""
                融券成本高、券源有限，做空受限。
                纯做空策略难以实施，配对交易中空头端需要特殊处理。
                """.strip(),
                solution="""
                1. 使用ETF替代个股做空（如沪深300ETF融券）
                2. 统计套利改为只做多相对低估端
                3. 融券成本纳入模型（年化8-10%）
                4. 限制做空仓位比例
                """.strip(),
                expected_effect="做空策略更符合实际可行性",
                complexity=ComplexityLevel.MEDIUM,
                implementation_priority=2
            ))

    def _generate_cost_suggestions(self, is_high_freq: bool) -> None:
        """生成成本优化建议"""

        # 交易成本精细化
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.COST_OPTIMIZATION,
            title="交易成本精细化建模",
            problem_description="""
            中国A股成本结构：卖出印花税0.1%、双边佣金约0.025%、
            过户费0.002%，合计约0.15%（卖出）。
            低估成本会导致收益虚高。
            """.strip(),
            solution="""
            1. 卖出成本 = 印花税0.1% + 佣金0.025% + 过户费0.002%
            2. 买入成本 = 佣金0.025% + 过户费0.002%
            3. 滑点按市值分层：大盘股0.01%，小盘股0.05%
            4. 高频策略需考虑冲击成本
            """.strip(),
            expected_effect="回测收益更接近实盘，年化差异可达2-5%",
            complexity=ComplexityLevel.LOW,
            implementation_priority=1,
            code_example="""
# 精细化成本计算
class ChinaCostModel:
    def __init__(self):
        self.stamp_duty = 0.001  # 仅卖出
        self.commission = 0.00025
        self.transfer_fee = 0.00002

    def calculate_cost(self, amount, is_buy=True, market_cap=None):
        commission = max(5, amount * self.commission)
        transfer = amount * self.transfer_fee
        stamp = 0 if is_buy else amount * self.stamp_duty
        return commission + transfer + stamp
            """.strip()
        ))

        # 滑点优化
        if is_high_freq:
            self.suggestions.append(ImprovementSuggestion(
                category=ImprovementCategory.COST_OPTIMIZATION,
                title="高频滑点与冲击成本",
                problem_description="""
                高频交易滑点显著，大单冲击成本不可忽视。
                简单固定滑点会低估实际成本。
                """.strip(),
                solution="""
                1. 基于成交量预估滑点：滑点 = k / sqrt(成交量)
                2. TWAP/VWAP拆分大单执行
                3. 考虑开盘收盘流动性差异
                4. 设置最小佣金5元过滤
                """.strip(),
                expected_effect="高频策略回测更准确",
                complexity=ComplexityLevel.MEDIUM,
                implementation_priority=2
            ))

    def _generate_liquidity_suggestions(self) -> None:
        """生成流动性管理建议"""

        # 市值过滤
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.LIQUIDITY,
            title="流动性约束与市值过滤",
            problem_description="""
            小盘股流动性差，大单进出困难，容易产生巨大滑点。
            部分策略在小盘股上表现好但不可执行。
            """.strip(),
            solution="""
            1. 设置最低市值门槛（如>50亿）
            2. 设置最低日均成交量（如>5000万）
            3. 仓位按流通市值比例限制
            4. 考虑停牌股票处理
            """.strip(),
            expected_effect="策略更具可执行性，减少流动性风险",
            complexity=ComplexityLevel.LOW,
            implementation_priority=2,
            code_example="""
# 流动性过滤
class LiquidityFilter:
    def __init__(self, min_market_cap=5e9, min_volume=5e7):
        self.min_cap = min_market_cap
        self.min_volume = min_volume

    def filter(self, stock_data):
        return stock_data[
            (stock_data['market_cap'] >= self.min_cap) &
            (stock_data['avg_volume_20d'] >= self.min_volume)
        ]
            """.strip()
        ))

        # 停牌处理
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.LIQUIDITY,
            title="停牌与退市风险处理",
            problem_description="""
            股票可能长时间停牌或退市，
            策略需要处理持仓股票停牌的情况。
            """.strip(),
            solution="""
            1. 持仓股票停牌时冻结该仓位
            2. 复牌首日波动率放大处理
            3. 排除ST/*ST股票
            4. 考虑退市整理期处理
            """.strip(),
            expected_effect="避免停牌导致的资金冻结问题",
            complexity=ComplexityLevel.MEDIUM,
            implementation_priority=3
        ))

    def _generate_risk_control_suggestions(self, uses_ml: bool) -> None:
        """生成风险控制增强建议"""

        # 过拟合防范
        if uses_ml:
            self.suggestions.append(ImprovementSuggestion(
                category=ImprovementCategory.RISK_CONTROL,
                title="机器学习模型过拟合防范",
                problem_description="""
                金融数据信噪比低，ML模型容易过拟合历史数据，
                实盘表现往往差于回测。
                """.strip(),
                solution="""
                1. 增加正则化（L1/L2/Dropout）
                2. 使用Purged K-FCV时序交叉验证
                3. 设置早停机制（Early Stopping）
                4. 特征数量/样本数 < 1/100
                5. 进行样本外测试（OOS）
                """.strip(),
                expected_effect="提高模型泛化能力，减少过拟合风险",
                complexity=ComplexityLevel.MEDIUM,
                implementation_priority=1,
                code_example="""
# Purged K-Fold交叉验证
from sklearn.model_selection import KFold

class PurgedKFold:
    def __init__(self, n_splits=5, embargo_pct=0.01):
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(self, X, y, groups=None):
        # 实现带清除期的时序交叉验证
        pass
            """.strip()
            ))

        # 组合风险控制
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.RISK_CONTROL,
            title="组合层面风险控制",
            problem_description="""
            单策略风险控制不足以应对系统性风险，
            需要组合层面的风控机制。
            """.strip(),
            solution="""
            1. 设置最大回撤阈值（如15%减仓50%）
            2. 波动率目标管理（如目标波动率10%）
            3. 行业/因子暴露限制
            4. 尾部风险对冲（购买虚值看跌期权）
            """.strip(),
            expected_effect="降低组合最大回撤，提高夏普比率",
            complexity=ComplexityLevel.HIGH,
            implementation_priority=3
        ))

    def _generate_data_quality_suggestions(self) -> None:
        """生成数据质量建议"""

        # 复权处理
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.DATA_QUALITY,
            title="复权与分红送股处理",
            problem_description="""
            除权除息会导致价格跳空，
            使用前复权数据会引入未来信息（lookahead bias）。
            """.strip(),
            solution="""
            1. 回测使用不复权价格+复权因子
            2. 分红送股日单独处理
            3. 避免使用前复权计算收益率
            4. 配股、增发等事件处理
            """.strip(),
            expected_effect="消除未来信息泄露，回测更真实",
            complexity=ComplexityLevel.LOW,
            implementation_priority=2,
            code_example="""
# 正确处理复权
class PriceAdjuster:
    def get_adjusted_price(self, raw_price, adj_factor, is_backtest=True):
        if is_backtest:
            # 回测使用不复权价格
            return raw_price
        else:
            # 分析使用后复权
            return raw_price * adj_factor
            """.strip()
        ))

        # 幸存者偏差
        self.suggestions.append(ImprovementSuggestion(
            category=ImprovementCategory.DATA_QUALITY,
            title="幸存者偏差消除",
            problem_description="""
            回测时只使用现存股票会忽略退市股票，
            高估策略表现（幸存者偏差）。
            """.strip(),
            solution="""
            1. 获取历史全量股票列表（含退市）
            2. 回测时考虑退市股票收益
            3. 定期更新股票池
            4. IPO首日避免使用（价格不稳定）
            """.strip(),
            expected_effect="消除幸存者偏差，策略收益估计更准确",
            complexity=ComplexityLevel.MEDIUM,
            implementation_priority=2
        ))

    def to_markdown(self) -> str:
        """生成Markdown格式的建议报告"""
        lines = ["## 针对中国市场的改进建议\n"]

        for i, suggestion in enumerate(self.suggestions, 1):
            lines.append(f"### {i}. {suggestion.title}")
            lines.append(f"\n**类别**: {suggestion.category.value}")
            lines.append(f"**复杂度**: {suggestion.complexity.value}")
            lines.append(f"**优先级**: P{suggestion.implementation_priority}\n")

            lines.append("**问题描述**:")
            lines.append(f"> {suggestion.problem_description}\n")

            lines.append("**改进方案**:")
            for line in suggestion.solution.strip().split('\n'):
                lines.append(f"{line}")
            lines.append("")

            lines.append(f"**预期效果**: {suggestion.expected_effect}\n")

            if suggestion.code_example:
                lines.append("**代码示例**:")
                lines.append("```python")
                lines.append(suggestion.code_example)
                lines.append("```\n")

        return '\n'.join(lines)

    def to_dict(self) -> list[dict]:
        """转换为字典列表"""
        return [
            {
                "category": s.category.value,
                "title": s.title,
                "problem": s.problem_description,
                "solution": s.solution,
                "expected_effect": s.expected_effect,
                "complexity": s.complexity.value,
                "priority": s.implementation_priority,
            }
            for s in self.suggestions
        ]
