"""
风险配置模块 - 定义增强版风控参数配置

提供灵活的风险管理配置，支持多种止盈止损机制和优先级设置。
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class ExitType(Enum):
    """出场类型枚举"""
    FORCED_STOP = "forced_stop"          # 强制止损（最高优先级）
    TRAILING_STOP = "trailing_stop"      # 移动止盈
    TAKE_PROFIT = "take_profit"          # 固定止盈
    STOP_LOSS = "stop_loss"              # 固定止损
    TIME_STOP = "time_stop"              # 时间止损
    ATR_STOP = "atr_stop"                # ATR止损
    SIGNAL_REVERSE = "signal_reverse"    # 信号反转（最低优先级）


@dataclass
class EnhancedRiskConfig:
    """
    增强版风控配置类

    支持复合条件、分级止盈、ATR止损、时间止损等多种风控机制。

    Attributes:
        # 固定止盈止损
        fixed_stop_loss_pct: 固定止损比例
        fixed_take_profit_pct: 固定止盈比例

        # 移动止盈
        enable_trailing_stop: 是否启用移动止盈
        trailing_activation_pct: 移动止盈启动阈值（盈利比例）
        trailing_stop_pct: 移动止盈回撤触发比例

        # ATR止损
        enable_atr_stop: 是否启用ATR止损
        atr_period: ATR计算周期
        atr_multiplier: ATR乘数

        # 时间止损
        enable_time_stop: 是否启用时间止损
        max_holding_days: 最大持仓天数

        # 分级止盈
        partial_exits: 分级止盈配置 [(盈利比例, 平仓比例), ...]

        # 出场优先级
        exit_priority: 出场条件优先级列表
    """

    # 固定止盈止损
    fixed_stop_loss_pct: float = 0.05           # 固定止损5%
    fixed_take_profit_pct: float = 0.10         # 固定止盈10%

    # 移动止盈
    enable_trailing_stop: bool = True
    trailing_activation_pct: float = 0.05       # 盈利5%后启动移动止盈
    trailing_stop_pct: float = 0.03             # 回撤3%触发移动止盈

    # ATR止损
    enable_atr_stop: bool = True
    atr_period: int = 14
    atr_multiplier: float = 2.0                 # 2×ATR

    # 时间止损
    enable_time_stop: bool = True
    max_holding_days: int = 20

    # 分级止盈 [(盈利比例, 平仓比例), ...]
    # 默认：盈利5%平30%，盈利10%平50%（累计80%），盈利15%平剩余
    partial_exits: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.05, 0.3),   # 盈利5%平30%
        (0.10, 0.5),   # 盈利10%平50%（累计80%）
        (0.15, 1.0),   # 盈利15%平剩余
    ])

    # 出场优先级（从高到低）
    exit_priority: List[str] = field(default_factory=lambda: [
        'forced_stop',      # 强制止损（最高）
        'atr_stop',         # ATR止损
        'trailing_stop',    # 移动止盈
        'stop_loss',        # 固定止损
        'take_profit',      # 固定止盈
        'time_stop',        # 时间止损
        'signal_reverse',   # 信号反转（最低）
    ])

    # 回撤控制
    max_drawdown_pct: float = 0.15              # 最大回撤限制
    drawdown_warning_pct: float = 0.10          # 回撤预警线

    # 仓位限制
    max_position_weight: float = 0.30           # 单票最大权重
    max_sector_weight: float = 0.50             # 行业最大权重

    # 每日限制
    max_daily_loss_pct: float = 0.03            # 单日最大亏损
    max_daily_trades: int = 20                  # 单日最大交易次数

    def __post_init__(self):
        """验证配置参数有效性"""
        # 验证百分比参数
        for name, value in [
            ('fixed_stop_loss_pct', self.fixed_stop_loss_pct),
            ('fixed_take_profit_pct', self.fixed_take_profit_pct),
            ('trailing_activation_pct', self.trailing_activation_pct),
            ('trailing_stop_pct', self.trailing_stop_pct),
            ('max_drawdown_pct', self.max_drawdown_pct),
            ('drawdown_warning_pct', self.drawdown_warning_pct),
            ('max_position_weight', self.max_position_weight),
            ('max_daily_loss_pct', self.max_daily_loss_pct),
        ]:
            if not 0 < value < 1:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")

        # 验证整数参数
        if self.atr_period < 1:
            raise ValueError(f"atr_period must be >= 1, got {self.atr_period}")
        if self.max_holding_days < 1:
            raise ValueError(f"max_holding_days must be >= 1, got {self.max_holding_days}")
        if self.max_daily_trades < 0:
            raise ValueError(f"max_daily_trades must be >= 0, got {self.max_daily_trades}")

        # 验证分级止盈配置
        for i, (profit_pct, exit_pct) in enumerate(self.partial_exits):
            if not 0 < profit_pct <= 1:
                raise ValueError(f"partial_exits[{i}]: profit_pct must be in (0, 1]")
            if not 0 < exit_pct <= 1:
                raise ValueError(f"partial_exits[{i}]: exit_pct must be in (0, 1]")

        # 验证优先级配置
        valid_exit_types = {e.value for e in ExitType}
        for exit_type in self.exit_priority:
            if exit_type not in valid_exit_types:
                raise ValueError(f"Invalid exit_type in priority: {exit_type}")

    def get_exit_priority_rank(self, exit_type: str) -> int:
        """
        获取出场类型的优先级排名

        Args:
            exit_type: 出场类型

        Returns:
            优先级排名（越小优先级越高）
        """
        try:
            return self.exit_priority.index(exit_type)
        except ValueError:
            return len(self.exit_priority)  # 未配置的优先级最低

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'fixed_stop_loss_pct': self.fixed_stop_loss_pct,
            'fixed_take_profit_pct': self.fixed_take_profit_pct,
            'enable_trailing_stop': self.enable_trailing_stop,
            'trailing_activation_pct': self.trailing_activation_pct,
            'trailing_stop_pct': self.trailing_stop_pct,
            'enable_atr_stop': self.enable_atr_stop,
            'atr_period': self.atr_period,
            'atr_multiplier': self.atr_multiplier,
            'enable_time_stop': self.enable_time_stop,
            'max_holding_days': self.max_holding_days,
            'partial_exits': self.partial_exits,
            'exit_priority': self.exit_priority,
            'max_drawdown_pct': self.max_drawdown_pct,
            'drawdown_warning_pct': self.drawdown_warning_pct,
            'max_position_weight': self.max_position_weight,
            'max_sector_weight': self.max_sector_weight,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'max_daily_trades': self.max_daily_trades,
        }


# 预定义配置模板
def create_conservative_risk_config() -> EnhancedRiskConfig:
    """
    创建保守型风控配置

    更严格的止损和仓位限制，适合风险厌恶型策略。
    """
    return EnhancedRiskConfig(
        fixed_stop_loss_pct=0.03,
        fixed_take_profit_pct=0.06,
        enable_trailing_stop=True,
        trailing_activation_pct=0.03,
        trailing_stop_pct=0.02,
        enable_atr_stop=True,
        atr_multiplier=1.5,
        enable_time_stop=True,
        max_holding_days=10,
        partial_exits=[
            (0.03, 0.5),   # 盈利3%平50%
            (0.06, 1.0),   # 盈利6%平剩余
        ],
        max_drawdown_pct=0.10,
        drawdown_warning_pct=0.05,
        max_position_weight=0.20,
        max_daily_loss_pct=0.02,
    )


def create_aggressive_risk_config() -> EnhancedRiskConfig:
    """
    创建激进型风控配置

    更宽松的止损和仓位限制，适合高风险高回报策略。
    """
    return EnhancedRiskConfig(
        fixed_stop_loss_pct=0.10,
        fixed_take_profit_pct=0.20,
        enable_trailing_stop=True,
        trailing_activation_pct=0.10,
        trailing_stop_pct=0.05,
        enable_atr_stop=True,
        atr_multiplier=3.0,
        enable_time_stop=True,
        max_holding_days=40,
        partial_exits=[
            (0.10, 0.25),  # 盈利10%平25%
            (0.20, 0.35),  # 盈利20%平35%（累计60%）
            (0.30, 0.40),  # 盈利30%平40%（累计100%）
        ],
        max_drawdown_pct=0.25,
        drawdown_warning_pct=0.15,
        max_position_weight=0.50,
        max_daily_loss_pct=0.05,
    )


def create_trend_following_config() -> EnhancedRiskConfig:
    """
    创建趋势跟踪策略风控配置

    特点：宽止损、移动止盈为主、长持仓周期
    """
    return EnhancedRiskConfig(
        fixed_stop_loss_pct=0.08,
        fixed_take_profit_pct=None,  # 不使用固定止盈
        enable_trailing_stop=True,
        trailing_activation_pct=0.05,
        trailing_stop_pct=0.05,      # 较宽的移动止盈
        enable_atr_stop=True,
        atr_period=14,
        atr_multiplier=2.5,          # 较宽的ATR止损
        enable_time_stop=False,      # 趋势策略不限制时间
        max_holding_days=999,        # 实际不生效
        partial_exits=[
            (0.20, 0.3),   # 盈利20%平30%
            (0.50, 0.5),   # 盈利50%平50%（累计80%）
        ],
        exit_priority=[
            'forced_stop',
            'atr_stop',
            'trailing_stop',    # 移动止盈优先于固定止损
            'stop_loss',
            'signal_reverse',
        ],
        max_drawdown_pct=0.20,
    )


def create_mean_reversion_config() -> EnhancedRiskConfig:
    """
    创建均值回归策略风控配置

    特点：窄止损、固定止盈为主、短持仓周期
    """
    return EnhancedRiskConfig(
        fixed_stop_loss_pct=0.03,
        fixed_take_profit_pct=0.05,
        enable_trailing_stop=False,  # 均值回归不用移动止盈
        enable_atr_stop=True,
        atr_period=10,
        atr_multiplier=1.0,          # 较紧的ATR止损
        enable_time_stop=True,
        max_holding_days=5,          # 短持仓周期
        partial_exits=[
            (0.03, 1.0),   # 盈利3%全部平仓
        ],
        exit_priority=[
            'forced_stop',
            'stop_loss',        # 固定止损优先
            'take_profit',
            'time_stop',        # 时间止损很重要
            'atr_stop',
            'signal_reverse',
        ],
        max_drawdown_pct=0.10,
    )


if __name__ == "__main__":
    # 测试配置
    config = EnhancedRiskConfig()
    print("默认配置:")
    print(config.to_dict())

    print("\n保守型配置:")
    conservative = create_conservative_risk_config()
    print(conservative.to_dict())

    print("\n激进型配置:")
    aggressive = create_aggressive_risk_config()
    print(aggressive.to_dict())

    print("\n趋势跟踪配置:")
    trend = create_trend_following_config()
    print(trend.to_dict())

    print("\n均值回归配置:")
    mean_reversion = create_mean_reversion_config()
    print(mean_reversion.to_dict())
