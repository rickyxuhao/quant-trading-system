"""回测配置模块

提供回测配置的统一管理，包括策略参数、回测参数等。
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum


class StrategyType(Enum):
    """策略类型枚举"""

    MA_TREND = "ma_trend"
    MEAN_REVERSION = "mean_reversion"
    ML_PREDICTION = "ml_prediction"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    LEADING_STOCK = "leading_stock"


class RebalanceFrequency(Enum):
    """调仓频率枚举"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class StrategyParams:
    """策略参数基类"""

    strategy_type: StrategyType
    name: str = ""
    description: str = ""


@dataclass
class MATrendParams(StrategyParams):
    """MA趋势策略参数"""

    ma_short: int = 10
    ma_long: int = 60
    entry_threshold: float = 0.02
    exit_threshold: float = 0.01

    def __post_init__(self):
        self.strategy_type = StrategyType.MA_TREND
        self.name = "MA趋势策略"


@dataclass
class MeanReversionParams(StrategyParams):
    """均值回归策略参数"""

    lookback_period: int = 20
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    position_size: float = 0.1

    def __post_init__(self):
        self.strategy_type = StrategyType.MEAN_REVERSION
        self.name = "均值回归策略"


@dataclass
class MLPredictionParams(StrategyParams):
    """ML预测策略参数"""

    model_type: str = "xgboost"  # xgboost, lstm, random_forest
    lookback_days: int = 20
    prediction_horizon: int = 5
    feature_subset: List[str] = field(default_factory=list)
    retrain_frequency: int = 63  # 约每季度重新训练

    def __post_init__(self):
        self.strategy_type = StrategyType.ML_PREDICTION
        self.name = "ML预测策略"
        if not self.feature_subset:
            self.feature_subset = ["close", "volume", "ma5", "ma20", "rsi", "macd"]


@dataclass
class BacktestRunConfig:
    """回测运行配置"""

    # 时间范围
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # 资金配置
    initial_capital: float = 1_000_000.0

    # 调仓配置
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.WEEKLY
    max_positions: int = 10
    min_positions: int = 3

    # 交易成本
    commission_rate: float = 0.00015  # 万1.5
    slippage_rate: float = 0.0002  # 万2

    # 风控配置
    stop_loss: float = 0.05  # 5%止损
    take_profit: float = 0.10  # 10%止盈
    max_drawdown_limit: float = 0.20  # 20%最大回撤限制

    # 基准
    benchmark: str = "000300.SH"  # 沪深300

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "rebalance_frequency": self.rebalance_frequency.value,
            "max_positions": self.max_positions,
            "min_positions": self.min_positions,
            "commission_rate": self.commission_rate,
            "slippage_rate": self.slippage_rate,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_drawdown_limit": self.max_drawdown_limit,
            "benchmark": self.benchmark,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestRunConfig":
        """从字典创建"""
        config = cls()

        if "start_date" in data and data["start_date"]:
            config.start_date = datetime.fromisoformat(data["start_date"]).date()
        if "end_date" in data and data["end_date"]:
            config.end_date = datetime.fromisoformat(data["end_date"]).date()

        config.initial_capital = data.get("initial_capital", 1_000_000.0)
        config.max_positions = data.get("max_positions", 10)
        config.min_positions = data.get("min_positions", 3)
        config.commission_rate = data.get("commission_rate", 0.00015)
        config.slippage_rate = data.get("slippage_rate", 0.0002)
        config.stop_loss = data.get("stop_loss", 0.05)
        config.take_profit = data.get("take_profit", 0.10)
        config.max_drawdown_limit = data.get("max_drawdown_limit", 0.20)
        config.benchmark = data.get("benchmark", "000300.SH")

        freq = data.get("rebalance_frequency", "weekly")
        config.rebalance_frequency = RebalanceFrequency(freq)

        return config


@dataclass
class BacktestConfigManager:
    """回测配置管理器"""

    strategy_params: StrategyParams = field(default_factory=lambda: MATrendParams())
    run_config: BacktestRunConfig = field(default_factory=BacktestRunConfig)

    def set_strategy(self, strategy_type: StrategyType, **kwargs):
        """设置策略类型和参数"""
        if strategy_type == StrategyType.MA_TREND:
            self.strategy_params = MATrendParams(**kwargs)
        elif strategy_type == StrategyType.MEAN_REVERSION:
            self.strategy_params = MeanReversionParams(**kwargs)
        elif strategy_type == StrategyType.ML_PREDICTION:
            self.strategy_params = MLPredictionParams(**kwargs)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    def update_run_config(self, **kwargs):
        """更新运行配置"""
        for key, value in kwargs.items():
            if hasattr(self.run_config, key):
                setattr(self.run_config, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "strategy_params": {
                "type": self.strategy_params.strategy_type.value,
                "params": self._strategy_params_to_dict(),
            },
            "run_config": self.run_config.to_dict(),
        }

    def _strategy_params_to_dict(self) -> Dict[str, Any]:
        """将策略参数转换为字典"""
        params = {}
        if isinstance(self.strategy_params, MATrendParams):
            params = {
                "ma_short": self.strategy_params.ma_short,
                "ma_long": self.strategy_params.ma_long,
                "entry_threshold": self.strategy_params.entry_threshold,
                "exit_threshold": self.strategy_params.exit_threshold,
            }
        elif isinstance(self.strategy_params, MeanReversionParams):
            params = {
                "lookback_period": self.strategy_params.lookback_period,
                "entry_zscore": self.strategy_params.entry_zscore,
                "exit_zscore": self.strategy_params.exit_zscore,
                "position_size": self.strategy_params.position_size,
            }
        elif isinstance(self.strategy_params, MLPredictionParams):
            params = {
                "model_type": self.strategy_params.model_type,
                "lookback_days": self.strategy_params.lookback_days,
                "prediction_horizon": self.strategy_params.prediction_horizon,
                "feature_subset": self.strategy_params.feature_subset,
                "retrain_frequency": self.strategy_params.retrain_frequency,
            }
        return params


# 预设配置
PRESET_CONFIGS = {
    "conservative": BacktestConfigManager(
        strategy_params=MATrendParams(ma_short=20, ma_long=120),
        run_config=BacktestRunConfig(
            max_positions=5, stop_loss=0.03, take_profit=0.05, max_drawdown_limit=0.10
        ),
    ),
    "aggressive": BacktestConfigManager(
        strategy_params=MATrendParams(ma_short=5, ma_long=20),
        run_config=BacktestRunConfig(
            max_positions=20, stop_loss=0.10, take_profit=0.20, max_drawdown_limit=0.30
        ),
    ),
    "balanced": BacktestConfigManager(
        strategy_params=MATrendParams(ma_short=10, ma_long=60),
        run_config=BacktestRunConfig(
            max_positions=10, stop_loss=0.05, take_profit=0.10, max_drawdown_limit=0.20
        ),
    ),
}


def get_preset_config(name: str) -> Optional[BacktestConfigManager]:
    """获取预设配置"""
    return PRESET_CONFIGS.get(name)


def list_preset_configs() -> List[str]:
    """列出所有预设配置名称"""
    return list(PRESET_CONFIGS.keys())
