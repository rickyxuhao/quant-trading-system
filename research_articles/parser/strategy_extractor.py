"""
策略要素提取模块 - 从论文中提取量化策略的关键要素

提取要素：
- 信号生成逻辑（入场/出场条件）
- 特征变量列表（名称、计算方法、参数）
- 模型架构（层结构、超参数、优化器）
- 回测设置（时间范围、成本、再平衡频率）
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.logger import get_logger

from .pdf_extractor import PDFContent
from .section_identifier import SectionIdentifier, SectionType

logger = get_logger(__name__)


class SignalType(Enum):
    """信号类型"""
    ENTRY_LONG = "entry_long"      # 做多入场
    ENTRY_SHORT = "entry_short"    # 做空入场
    EXIT_LONG = "exit_long"        # 做多出场
    EXIT_SHORT = "exit_short"      # 做空出场
    STOP_LOSS = "stop_loss"        # 止损
    TAKE_PROFIT = "take_profit"    # 止盈


class VariableType(Enum):
    """变量类型"""
    PRICE = "price"                # 价格类
    VOLUME = "volume"              # 成交量
    TECHNICAL = "technical"        # 技术指标
    FUNDAMENTAL = "fundamental"    # 基本面指标
    MACRO = "macro"                # 宏观指标
    DERIVED = "derived"            # 衍生指标
    OTHER = "other"


class ModelType(Enum):
    """模型类型"""
    LINEAR = "linear"              # 线性模型
    TREE = "tree"                  # 树模型
    NEURAL = "neural"              # 神经网络
    ENSEMBLE = "ensemble"          # 集成模型
    STATISTICAL = "statistical"    # 统计模型
    RL = "reinforcement_learning"  # 强化学习
    OTHER = "other"


@dataclass
class SignalCondition:
    """信号条件"""
    signal_type: SignalType
    description: str
    condition_formula: str = ""
    threshold_value: Optional[float] = None
    related_features: list[str] = field(default_factory=list)


@dataclass
class FeatureVariable:
    """特征变量"""
    name: str
    description: str
    var_type: VariableType
    calculation_formula: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    data_source: str = ""
    frequency: str = "daily"       # daily, hourly, minute, etc.


@dataclass
class ModelArchitecture:
    """模型架构"""
    model_type: ModelType
    description: str
    layers: list[dict[str, Any]] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    optimizer: str = ""
    loss_function: str = ""
    training_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestConfig:
    """回测配置"""
    time_range_start: str = ""
    time_range_end: str = ""
    frequency: str = "daily"
    transaction_cost: float = 0.0
    slippage: float = 0.0
    rebalance_frequency: str = ""
    initial_capital: float = 0.0
    position_sizing: str = ""
    risk_free_rate: float = 0.0


@dataclass
class StrategyElements:
    """策略要素完整结构"""
    # 基本信息
    strategy_name: str = ""
    strategy_description: str = ""

    # 核心要素
    signals: list[SignalCondition] = field(default_factory=list)
    features: list[FeatureVariable] = field(default_factory=list)
    model: Optional[ModelArchitecture] = None
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    # 风险控制
    risk_management: dict[str, Any] = field(default_factory=dict)

    # 其他发现
    key_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class StrategyExtractor:
    """策略要素提取器"""

    # 常见技术指标模式
    TECHNICAL_PATTERNS = {
        "sma": [r"SMA", r"simple moving average", r"简单移动平均"],
        "ema": [r"EMA", r"exponential moving average", r"指数移动平均"],
        "rsi": [r"RSI", r"relative strength index", r"相对强弱指标"],
        "macd": [r"MACD", r"moving average convergence divergence"],
        "bollinger": [r"Bollinger", r"布林带", r"bollinger bands"],
        "atr": [r"ATR", r"average true range", r"真实波动幅度"],
        "volume": [r"volume", r"成交量", r"交易量", r"turnover"],
        "momentum": [r"momentum", r"动量", r"MOM"],
    }

    # 信号关键词
    SIGNAL_KEYWORDS = {
        SignalType.ENTRY_LONG: [
            "买入", "做多", "long", "buy", "entry", "开仓",
            "signal > 0", "positive signal", "bullish"
        ],
        SignalType.ENTRY_SHORT: [
            "卖出", "做空", "short", "sell short", "short entry",
            "signal < 0", "negative signal", "bearish"
        ],
        SignalType.EXIT_LONG: [
            "平多", "exit long", "close long", "sell", "cover long"
        ],
        SignalType.EXIT_SHORT: [
            "平空", "exit short", "close short", "cover short", "buy to cover"
        ],
        SignalType.STOP_LOSS: [
            "止损", "stop loss", "stop-loss", "cut loss", "maximum loss"
        ],
        SignalType.TAKE_PROFIT: [
            "止盈", "take profit", "profit target", "profit taking"
        ],
    }

    # 回测参数模式
    BACKTEST_PATTERNS = {
        "time_range": [
            r"(\d{4})[\-/]?\d{0,2}[\-/]?\d{0,2}\s*(?:to|[-~])\s*(\d{4})",
            r"sample\s+period[:：]?\s*(\d{4}).{0,5}(\d{4})",
            r"(\d{4})\s*年\s*至?\s*(\d{4})\s*年",
        ],
        "transaction_cost": [
            r"transaction\s+cost[:：]?\s*(\d+\.?\d*)\s*%?",
            r"trading\s+cost[:：]?\s*(\d+\.?\d*)\s*%?",
            r"交易成本[:：]?\s*(\d+\.?\d*)\s*%?",
            r"手续费[:：]?\s*(\d+\.?\d*)\s*%?",
        ],
        "rebalance": [
            r"rebalanc\w+[:：]?\s*(daily|weekly|monthly|quarterly|annually)",
            r"再平衡[:：]?\s*(日|周|月|季|年)",
            r"调仓[:：]?\s*(日|周|月|季|年|频率)",
        ],
        "initial_capital": [
            r"initial\s+(?:capital|investment)[:：]?\s*\$?(\d+)",
            r"初始资金[:：]?\s*(\d+)",
        ],
    }

    def __init__(self, content: PDFContent):
        self.content = content
        self.elements = StrategyElements()

    def extract(self) -> StrategyElements:
        """
        执行完整的策略要素提取

        Returns:
            StrategyElements对象
        """
        logger.info("开始提取策略要素")

        # 提取方法论文本
        identifier = SectionIdentifier(self.content)
        sections = identifier.identify()

        # 获取关键章节内容
        methodology_text = identifier.get_methodology_content()
        experiments_text = identifier.get_experiments_content()
        results_text = identifier.get_results_content()
        full_text = self.content.get_full_text()

        # 提取各类要素
        self._extract_strategy_name(full_text)
        self._extract_signals(methodology_text + experiments_text)
        self._extract_features(methodology_text)
        self._extract_model(methodology_text)
        self._extract_backtest_config(experiments_text + results_text)
        self._extract_risk_management(full_text)
        self._extract_findings_and_limitations(full_text)

        logger.info(
            f"策略要素提取完成: "
            f"{len(self.elements.signals)}个信号, "
            f"{len(self.elements.features)}个特征"
        )

        return self.elements

    def _extract_strategy_name(self, text: str) -> None:
        """提取策略名称"""
        # 尝试从标题提取
        if self.content.title:
            self.elements.strategy_name = self.content.title
            return

        # 从正文中寻找策略描述
        patterns = [
            r"we\s+propose\s+(?:a|an)\s+([^.]+(?:strategy|model|approach|method)[^.]*)",
            r"本文提出(?:了)?\s*([：:]?[^，。]*(?:策略|模型|方法)[^，。]*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                self.elements.strategy_description = match.group(1).strip()
                break

    def _extract_signals(self, text: str) -> None:
        """提取信号生成逻辑"""
        signals = []

        for signal_type, keywords in self.SIGNAL_KEYWORDS.items():
            for keyword in keywords:
                # 查找信号描述
                patterns = [
                    rf"{keyword}[^.。]*[.。]",
                    rf"{keyword}[^;；]*[;；]",
                ]

                for pattern in patterns:
                    matches = re.finditer(pattern, text, re.I)
                    for match in matches:
                        description = match.group(0).strip()
                        if len(description) > 10:  # 过滤太短的匹配
                            signal = SignalCondition(
                                signal_type=signal_type,
                                description=description
                            )
                            signals.append(signal)
                            break

        # 去重
        seen = set()
        unique_signals = []
        for s in signals:
            if s.description not in seen:
                seen.add(s.description)
                unique_signals.append(s)

        self.elements.signals = unique_signals

    def _extract_features(self, text: str) -> None:
        """提取特征变量"""
        features = []

        # 查找技术指标
        for tech_name, patterns in self.TECHNICAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.I)
                for match in matches:
                    # 获取上下文
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]

                    feature = FeatureVariable(
                        name=tech_name.upper(),
                        description=self._get_feature_description(context),
                        var_type=VariableType.TECHNICAL,
                        calculation_formula=self._extract_formula(context)
                    )
                    features.append(feature)
                    break  # 每种指标只添加一次

        # 查找价格类变量
        price_patterns = [
            r"(?:close|open|high|low)\s+price",
            r"收盘|开盘|最高|最低价",
            r"returns?\s*(?:\([^)]*\))",
        ]
        for pattern in price_patterns:
            if re.search(pattern, text, re.I):
                features.append(FeatureVariable(
                    name="price",
                    description="价格数据",
                    var_type=VariableType.PRICE
                ))
                break

        self.elements.features = features

    def _extract_model(self, text: str) -> None:
        """提取模型架构"""
        model = ModelArchitecture(
            model_type=ModelType.OTHER,
            description=""
        )

        # 识别模型类型
        model_patterns = {
            ModelType.LINEAR: [r"linear regression", r"OLS", r"logistic", r"线性回归"],
            ModelType.TREE: [r"random forest", r"XGBoost", r"decision tree", r"GBDT", r"lightgbm"],
            ModelType.NEURAL: [r"neural network", r"LSTM", r"GRU", r"CNN", r"transformer", r"神经网络"],
            ModelType.ENSEMBLE: [r"ensemble", r"集成", r"bagging", r"boosting"],
            ModelType.RL: [r"reinforcement learning", r"Q-learning", r"policy gradient", r"强化学习"],
        }

        for model_type, patterns in model_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    model.model_type = model_type
                    model.description = f"使用{pattern}模型"
                    break
            if model.model_type != ModelType.OTHER:
                break

        # 提取层结构（神经网络）
        if model.model_type == ModelType.NEURAL:
            layer_patterns = [
                r"(\d+)\s*(?:layer|层)",
                r"hidden\s+units?[:：]?\s*(\d+)",
                r"LSTM\s*\(\s*(\d+)\s*\)",
            ]
            for pattern in layer_patterns:
                matches = re.findall(pattern, text, re.I)
                for match in matches:
                    model.layers.append({"units": int(match)})

        # 提取超参数
        hyper_patterns = {
            "learning_rate": r"learning\s+rate[:：]?\s*(\d+\.?\d*(?:e-\d+)?)",
            "batch_size": r"batch\s+size[:：]?\s*(\d+)",
            "epochs": r"epochs?[:：]?\s*(\d+)",
            "dropout": r"dropout[:：]?\s*(\d+\.?\d*)",
        }
        for param, pattern in hyper_patterns.items():
            match = re.search(pattern, text, re.I)
            if match:
                model.hyperparameters[param] = match.group(1)

        # 提取优化器
        optimizer_match = re.search(
            r"(Adam|SGD|RMSprop|Adagrad|AdamW)(?:\s+optimizer)?",
            text, re.I
        )
        if optimizer_match:
            model.optimizer = optimizer_match.group(1)

        self.elements.model = model

    def _extract_backtest_config(self, text: str) -> None:
        """提取回测配置"""
        config = BacktestConfig()

        # 时间范围
        for pattern in self.BACKTEST_PATTERNS["time_range"]:
            match = re.search(pattern, text, re.I)
            if match:
                config.time_range_start = match.group(1)
                config.time_range_end = match.group(2)
                break

        # 交易成本
        for pattern in self.BACKTEST_PATTERNS["transaction_cost"]:
            match = re.search(pattern, text, re.I)
            if match:
                config.transaction_cost = float(match.group(1))
                break

        # 再平衡频率
        for pattern in self.BACKTEST_PATTERNS["rebalance"]:
            match = re.search(pattern, text, re.I)
            if match:
                config.rebalance_frequency = match.group(1)
                break

        # 初始资金
        for pattern in self.BACKTEST_PATTERNS["initial_capital"]:
            match = re.search(pattern, text, re.I)
            if match:
                config.initial_capital = float(match.group(1))
                break

        self.elements.backtest = config

    def _extract_risk_management(self, text: str) -> None:
        """提取风险管理配置"""
        risk = {}

        # 止损
        stop_loss_match = re.search(
            r"stop\s*loss[:：]?\s*(\d+\.?\d*)\s*%?",
            text, re.I
        )
        if stop_loss_match:
            risk["stop_loss_pct"] = float(stop_loss_match.group(1))

        # 仓位限制
        position_match = re.search(
            r"position\s*(?:size|limit)[:：]?\s*(\d+\.?\d*)\s*%?",
            text, re.I
        )
        if position_match:
            risk["max_position_pct"] = float(position_match.group(1))

        # 最大回撤
        drawdown_match = re.search(
            r"(?:max|maximum)\s*drawdown[:：]?\s*(\d+\.?\d*)\s*%?",
            text, re.I
        )
        if drawdown_match:
            risk["max_drawdown_pct"] = float(drawdown_match.group(1))

        self.elements.risk_management = risk

    def _extract_findings_and_limitations(self, text: str) -> None:
        """提取主要发现和局限性"""
        # 关键发现
        finding_patterns = [
            r"(?:we find|our results? show|结果表明|结果显示)[^.;。；]*[.；。]",
            r"(?:outperformance|excess return|alpha)[^.]*[.]",
        ]
        for pattern in finding_patterns:
            matches = re.findall(pattern, text, re.I)
            self.elements.key_findings.extend(matches[:5])  # 最多取5个

        # 局限性
        limitation_patterns = [
            r"(?:limitation|limit)[^;:：]*[:;：][^.]*[.]",
            r"(?:future work|further research)[^;：]*[:;：][^.]*[.]",
            r"局限性[:：][^。]*。",
        ]
        for pattern in limitation_patterns:
            matches = re.findall(pattern, text, re.I)
            self.elements.limitations.extend(matches[:5])

    def _get_feature_description(self, context: str) -> str:
        """从上下文中获取特征描述"""
        # 简单的启发式：取包含关键词的句子
        sentences = re.split(r"[.。;；]", context)
        for sentence in sentences:
            if len(sentence) > 10 and len(sentence) < 200:
                return sentence.strip()
        return ""

    def _extract_formula(self, context: str) -> str:
        """提取计算公式"""
        # 匹配数学公式（简化版）
        formula_patterns = [
            r"=\s*[^,.;]{3,50}",
            r"\\\([^\\]+\\\)",  # LaTeX行间公式
            r"\$[^$]+\$",  # LaTeX行内公式
        ]
        for pattern in formula_patterns:
            match = re.search(pattern, context)
            if match:
                return match.group(0).strip()
        return ""

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "strategy_name": self.elements.strategy_name,
            "strategy_description": self.elements.strategy_description,
            "signals": [
                {
                    "type": s.signal_type.value,
                    "description": s.description,
                    "formula": s.condition_formula,
                }
                for s in self.elements.signals
            ],
            "features": [
                {
                    "name": f.name,
                    "type": f.var_type.value,
                    "description": f.description,
                    "formula": f.calculation_formula,
                }
                for f in self.elements.features
            ],
            "model": {
                "type": self.elements.model.model_type.value if self.elements.model else None,
                "description": self.elements.model.description if self.elements.model else "",
                "hyperparameters": self.elements.model.hyperparameters if self.elements.model else {},
                "optimizer": self.elements.model.optimizer if self.elements.model else "",
            },
            "backtest": {
                "time_range": f"{self.elements.backtest.time_range_start}-{self.elements.backtest.time_range_end}",
                "transaction_cost": self.elements.backtest.transaction_cost,
                "rebalance_frequency": self.elements.backtest.rebalance_frequency,
                "initial_capital": self.elements.backtest.initial_capital,
            },
            "risk_management": self.elements.risk_management,
            "key_findings": self.elements.key_findings[:3],
            "limitations": self.elements.limitations[:3],
        }
