"""
仓位管理模块 - 配对交易仓位计算

功能：
- 固定比例仓位
- 波动率调整（ATR-based）
- 分级止盈
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PositionConfig:
    """仓位配置"""
    # 基础配置
    max_position_pct: float = 0.1      # 最大仓位占比（相对于总资金）
    single_side_pct: float = 0.05      # 单边仓位占比

    # 波动率调整
    use_volatility_adjustment: bool = True
    atr_window: int = 14
    target_atr_multiple: float = 2.0   # 目标风险 = ATR * multiple

    # 分级止盈
    use_staged_exit: bool = True
    first_stage_profit: float = 0.05   # 5%止盈第一部分
    first_stage_pct: float = 0.3       # 止盈30%仓位
    second_stage_profit: float = 0.10  # 10%止盈剩余

    # 时间止损
    use_time_stop: bool = True
    max_holding_days: int = 25

    # 移动止盈
    use_trailing_stop: bool = True
    trailing_activation: float = 0.10  # 盈利10%启动
    trailing_drawdown: float = 0.05    # 回撤5%触发


class PairPositionSizer:
    """配对交易仓位管理器"""

    def __init__(self, config: Optional[PositionConfig] = None):
        self.config = config or PositionConfig()
        self.position_history: list[dict] = []

    def calculate_position_sizes(
        self,
        capital: float,
        price_a: float,
        price_b: float,
        hedge_ratio: float,
        atr_a: Optional[float] = None,
        atr_b: Optional[float] = None
    ) -> Tuple[int, int]:
        """
        计算配对交易的仓位大小

        Args:
            capital: 总资金
            price_a: 股票A价格
            price_b: 股票B价格
            hedge_ratio: 对冲比例β
            atr_a: 股票A的ATR
            atr_b: 股票B的ATR

        Returns:
            (A股数量, B股数量)，正数表示买入，负数表示卖出
        """
        # 基础仓位金额
        position_value = capital * self.config.max_position_pct

        # 波动率调整
        if self.config.use_volatility_adjustment and atr_a is not None and atr_b is not None:
            avg_atr = (atr_a + hedge_ratio * atr_b) / 2
            if avg_atr > 0:
                risk_per_share = avg_atr
                max_risk = capital * self.config.single_side_pct * 0.02  # 2%风险
                position_value = min(position_value, max_risk / risk_per_share * price_a)

        # 计算股数（取整到100的倍数）
        shares_a = int((position_value / price_a) / 100) * 100
        shares_b = int((position_value * hedge_ratio / price_b) / 100) * 100

        return shares_a, shares_b

    def calculate_spread_position(
        self,
        capital: float,
        spread_price: float,
        spread_volatility: Optional[float] = None
    ) -> int:
        """
        基于价差计算仓位（用于Spread合成交易）

        Args:
            capital: 总资金
            spread_price: 价差
            spread_volatility: 价差波动率

        Returns:
            价差合约数量
        """
        # 基础仓位
        position_value = capital * self.config.max_position_pct

        # 波动率调整
        if self.config.use_volatility_adjustment and spread_volatility is not None:
            if spread_volatility > 0:
                position_value = position_value * (0.1 / spread_volatility)

        # 计算数量
        size = int(position_value / spread_price)

        return max(size, 0)

    def check_staged_exit(
        self,
        entry_price: float,
        current_price: float,
        position_size: int,
        days_held: int
    ) -> Tuple[Optional[int], str]:
        """
        检查分级止盈条件

        Args:
            entry_price: 入场价格
            current_price: 当前价格
            position_size: 当前持仓数量
            days_held: 持仓天数

        Returns:
            (减仓数量, 原因)，无需减仓时返回(None, "")
        """
        if not self.config.use_staged_exit:
            return None, ""

        profit_pct = (current_price - entry_price) / entry_price

        # 分级止盈
        if profit_pct >= self.config.second_stage_profit:
            # 达到第二级止盈，全部平仓
            return position_size, f"二级止盈 ({profit_pct:.1%})"
        elif profit_pct >= self.config.first_stage_profit:
            # 达到第一级止盈，平部分仓位
            exit_size = int(position_size * self.config.first_stage_pct / 100) * 100
            if exit_size > 0:
                return exit_size, f"一级止盈 ({profit_pct:.1%})"

        # 时间止损
        if self.config.use_time_stop and days_held >= self.config.max_holding_days:
            return position_size, f"时间止损 ({days_held}天)"

        return None, ""

    def calculate_trailing_stop(
        self,
        entry_price: float,
        highest_price: float,
        current_price: float,
        position_size: int
    ) -> Tuple[Optional[int], str]:
        """
        计算移动止盈

        Args:
            entry_price: 入场价格
            highest_price: 持仓期间最高价
            current_price: 当前价格
            position_size: 持仓数量

        Returns:
            (平仓数量, 原因)
        """
        if not self.config.use_trailing_stop:
            return None, ""

        profit_pct = (highest_price - entry_price) / entry_price

        # 盈利达到启动条件
        if profit_pct >= self.config.trailing_activation:
            drawdown_from_high = (highest_price - current_price) / highest_price

            if drawdown_from_high >= self.config.trailing_drawdown:
                return position_size, f"移动止盈 (回撤{drawdown_from_high:.1%})"

        return None, ""

    def calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: Optional[int] = None
    ) -> pd.Series:
        """
        计算ATR（平均真实波幅）

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            window: 计算窗口，默认使用配置值

        Returns:
            ATR序列
        """
        window = window or self.config.atr_window

        # 真实波幅
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR
        atr = tr.rolling(window=window).mean()

        return atr

    def calculate_kelly_position(
        self,
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        max_pct: float = 0.25
    ) -> float:
        """
        使用Kelly公式计算最优仓位

        Args:
            capital: 总资金
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损
            max_pct: 最大仓位限制

        Returns:
            建议仓位金额
        """
        if avg_loss == 0:
            return 0

        # Kelly公式: f* = (p*b - q) / b
        # p = 胜率, q = 败率, b = 盈亏比
        b = avg_win / avg_loss
        q = 1 - win_rate

        kelly_fraction = (win_rate * b - q) / b

        # 使用半Kelly
        half_kelly = kelly_fraction / 2

        # 限制最大仓位
        position_pct = min(max(half_kelly, 0), max_pct)

        return capital * position_pct

    def record_position(
        self,
        timestamp,
        action: str,
        size_a: int,
        size_b: int,
        price_a: float,
        price_b: float,
        reason: str = ""
    ) -> None:
        """记录仓位变动"""
        self.position_history.append({
            "timestamp": timestamp,
            "action": action,
            "size_a": size_a,
            "size_b": size_b,
            "price_a": price_a,
            "price_b": price_b,
            "value": abs(size_a) * price_a + abs(size_b) * price_b,
            "reason": reason
        })

    def get_position_summary(self) -> dict:
        """获取仓位汇总信息"""
        if not self.position_history:
            return {}

        df = pd.DataFrame(self.position_history)

        return {
            "total_trades": len(df),
            "avg_position_value": df["value"].mean(),
            "max_position_value": df["value"].max(),
        }


class RiskManager:
    """风险管理器"""

    def __init__(
        self,
        max_drawdown_pct: float = 0.15,
        daily_loss_limit_pct: float = 0.03
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct

        self.peak_value = 0
        self.daily_pnl = 0
        self.last_date = None

    def update(self, current_value: float, current_date) -> dict:
        """
        更新风险状态

        Returns:
            风险状态字典
        """
        # 更新峰值
        if current_value > self.peak_value:
            self.peak_value = current_value

        # 计算回撤
        drawdown = (self.peak_value - current_value) / self.peak_value

        # 检查是否需要风控
        status = {
            "drawdown": drawdown,
            "max_drawdown_triggered": drawdown >= self.max_drawdown_pct,
            "daily_loss_triggered": False,
            "trading_allowed": True
        }

        if status["max_drawdown_triggered"]:
            status["trading_allowed"] = False
            logger.warning(f"触发最大回撤限制: {drawdown:.2%}")

        return status
