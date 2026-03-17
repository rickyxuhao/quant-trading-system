"""
增强版风险管理模块

实现精细化的风险管理系统，支持多种止盈止损机制：
- 固定止盈止损
- 移动止盈（Trailing Stop）
- ATR止损
- 时间止损
- 分级止盈（Partial Exits）

并支持出场条件优先级处理和多子持仓跟踪。
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd

from core.logger import get_logger
from projects.quant_trading.backtest.risk_config import EnhancedRiskConfig

logger = get_logger(__name__)


@dataclass
class ExitSignal:
    """
    出场信号数据类

    Attributes:
        should_exit: 是否应该出场
        exit_type: 出场类型
        exit_size: 平仓比例（1.0表示全部平仓，0.5表示平仓50%）
        exit_reason: 出场原因描述
        priority: 优先级（越小优先级越高）
        metadata: 额外元数据
    """

    should_exit: bool
    exit_type: str = ""
    exit_size: float = 0.0
    exit_reason: str = ""
    priority: int = 999
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def no_exit(cls) -> "ExitSignal":
        """创建无出场信号"""
        return cls(should_exit=False)

    @classmethod
    def full_exit(cls, exit_type: str, reason: str, priority: int = 999) -> "ExitSignal":
        """创建全部平仓信号"""
        return cls(
            should_exit=True,
            exit_type=exit_type,
            exit_size=1.0,
            exit_reason=reason,
            priority=priority,
        )

    @classmethod
    def partial_exit(
        cls, exit_type: str, size: float, reason: str, priority: int = 999
    ) -> "ExitSignal":
        """创建部分平仓信号"""
        return cls(
            should_exit=True,
            exit_type=exit_type,
            exit_size=size,
            exit_reason=reason,
            priority=priority,
        )


@dataclass
class SubPosition:
    """
    子持仓记录

    用于跟踪分笔建仓的情况，支持分级止盈。

    Attributes:
        id: 子持仓唯一标识
        entry_date: 入场日期
        entry_price: 入场价格
        size: 持仓数量
        exit_level: 已执行的止盈级别
        highest_price: 最高价（用于移动止盈）
        lowest_price: 最低价（用于移动止盈，空头）
    """

    id: str
    entry_date: datetime
    entry_price: float
    size: float
    exit_level: int = 0
    highest_price: float = 0.0
    lowest_price: float = 0.0

    def __post_init__(self):
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == 0.0:
            self.lowest_price = self.entry_price

    @property
    def is_long(self) -> bool:
        """是否为多头持仓"""
        return self.size > 0

    def update_extreme_prices(self, current_price: float):
        """更新极端价格"""
        self.highest_price = max(self.highest_price, current_price)
        self.lowest_price = min(self.lowest_price, current_price)

    def calculate_profit_pct(self, current_price: float) -> float:
        """
        计算当前盈亏比例

        Args:
            current_price: 当前价格

        Returns:
            盈亏比例（正数表示盈利，负数表示亏损）
        """
        if self.is_long:
            return (current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - current_price) / self.entry_price


class PositionTracker:
    """
    多笔子持仓跟踪器

    管理一个标的的多笔子持仓，支持分级止盈跟踪。
    """

    def __init__(self, ts_code: str, config: EnhancedRiskConfig):
        """
        初始化持仓跟踪器

        Args:
            ts_code: 股票代码
            config: 风控配置
        """
        self.ts_code = ts_code
        self.config = config
        self.sub_positions: Dict[str, SubPosition] = {}
        self.total_entry_value: float = 0.0
        self.total_size: float = 0.0

    def add_position(self, price: float, size: float, date: datetime) -> str:
        """
        添加子持仓

        Args:
            price: 入场价格
            size: 持仓数量
            date: 入场日期

        Returns:
            子持仓ID
        """
        sub_id = str(uuid.uuid4())[:8]
        sub_pos = SubPosition(id=sub_id, entry_date=date, entry_price=price, size=size)
        self.sub_positions[sub_id] = sub_pos
        self.total_entry_value += price * abs(size)
        self.total_size += size
        logger.debug(
            f"[PositionTracker] {self.ts_code} 添加子持仓 {sub_id}: "
            f"价格={price:.2f}, 数量={size}"
        )
        return sub_id

    def remove_position(self, sub_id: str, exit_size: float) -> Optional[SubPosition]:
        """
        移除或部分减少子持仓

        Args:
            sub_id: 子持仓ID
            exit_size: 平仓数量

        Returns:
            被移除的子持仓（如果全部移除），否则None
        """
        if sub_id not in self.sub_positions:
            return None

        sub_pos = self.sub_positions[sub_id]
        if exit_size >= abs(sub_pos.size):
            # 全部移除
            self.total_size -= sub_pos.size
            self.total_entry_value -= sub_pos.entry_price * abs(sub_pos.size)
            del self.sub_positions[sub_id]
            logger.debug(f"[PositionTracker] {self.ts_code} 移除子持仓 {sub_id}")
            return sub_pos
        else:
            # 部分减少
            reduce_size = exit_size if sub_pos.size > 0 else -exit_size
            sub_pos.size -= reduce_size
            self.total_size -= reduce_size
            self.total_entry_value -= sub_pos.entry_price * exit_size
            logger.debug(
                f"[PositionTracker] {self.ts_code} 减少子持仓 {sub_id}: "
                f"减少{exit_size}, 剩余{abs(sub_pos.size)}"
            )
            return None

    def update_partial_exit(self, sub_id: str, exit_level: int):
        """
        更新子持仓的止盈级别

        Args:
            sub_id: 子持仓ID
            exit_level: 新的止盈级别
        """
        if sub_id in self.sub_positions:
            self.sub_positions[sub_id].exit_level = exit_level

    def get_average_cost(self) -> float:
        """
        计算加权平均成本

        Returns:
            平均成本
        """
        if self.total_size == 0:
            return 0.0
        total_cost = sum(sub.entry_price * abs(sub.size) for sub in self.sub_positions.values())
        total_qty = sum(abs(sub.size) for sub in self.sub_positions.values())
        return total_cost / total_qty if total_qty > 0 else 0.0

    def get_total_size(self) -> float:
        """获取总持仓数量"""
        return self.total_size

    def get_holding_days(self, current_date: datetime) -> int:
        """
        获取持仓天数（按最早入场计算）

        Args:
            current_date: 当前日期

        Returns:
            持仓天数
        """
        if not self.sub_positions:
            return 0
        earliest_date = min(sub.entry_date for sub in self.sub_positions.values())
        return (current_date - earliest_date).days

    def update_extreme_prices(self, current_price: float):
        """更新所有子持仓的极端价格"""
        for sub_pos in self.sub_positions.values():
            sub_pos.update_extreme_prices(current_price)

    def check_partial_exits(self, current_price: float) -> List[Tuple[str, float, str]]:
        """
        检查分级止盈条件

        Args:
            current_price: 当前价格

        Returns:
            [(sub_id, exit_size, reason), ...] 需要执行的平仓列表
        """
        exits = []
        partial_exits = sorted(self.config.partial_exits, key=lambda x: x[0])

        for sub_id, sub_pos in self.sub_positions.items():
            profit_pct = sub_pos.calculate_profit_pct(current_price)

            # 检查每一级止盈
            for level, (profit_threshold, exit_pct) in enumerate(partial_exits):
                if level < sub_pos.exit_level:
                    # 已经执行过这一级
                    continue

                if profit_pct >= profit_threshold:
                    # 触发这一级止盈
                    exit_size = abs(sub_pos.size) * exit_pct
                    exits.append(
                        (
                            sub_id,
                            exit_size,
                            f"分级止盈第{level+1}档: 盈利{profit_pct*100:.1f}% >= {profit_threshold*100:.1f}%",
                        )
                    )
                    # 更新已执行级别
                    sub_pos.exit_level = level + 1
                    logger.debug(
                        f"[PositionTracker] {self.ts_code} 子持仓 {sub_id} "
                        f"触发分级止盈第{level+1}档"
                    )

        return exits

    def get_sub_positions(self) -> List[SubPosition]:
        """获取所有子持仓列表"""
        return list(self.sub_positions.values())


class EnhancedRiskManager:
    """
    增强版风险管理器

    实现多种止盈止损机制：
    - 固定止盈止损
    - 移动止盈（Trailing Stop）
    - ATR止损
    - 时间止损
    - 分级止盈

    并支持出场条件优先级处理和多子持仓跟踪。

    Example:
        >>> config = EnhancedRiskConfig()
        >>> risk_mgr = EnhancedRiskManager(config)
        >>> risk_mgr.add_position('000001.SZ', 10.0, 1000, datetime.now())
        >>> signal = risk_mgr.check_all_exits('000001.SZ', 9.0, 5, market_data={'atr': 0.5})
    """

    def __init__(self, config: Optional[EnhancedRiskConfig] = None):
        """
        初始化增强版风险管理器

        Args:
            config: 风控配置，若为None则使用默认配置
        """
        self.config = config or EnhancedRiskConfig()
        self.position_trackers: Dict[str, PositionTracker] = {}
        self.atr_values: Dict[str, float] = {}  # 缓存ATR值

        # 回撤控制状态
        self._peak_value: float = 0.0
        self._current_drawdown: float = 0.0

        # 每日统计
        self._daily_trades: Dict[datetime, int] = defaultdict(int)
        self._daily_pnl: Dict[datetime, float] = defaultdict(float)

        logger.info(f"[EnhancedRiskManager] 初始化完成，配置: {self.config.to_dict()}")

    def add_position(
        self, ts_code: str, entry_price: float, size: float, entry_date: datetime
    ) -> str:
        """
        添加持仓

        Args:
            ts_code: 股票代码
            entry_price: 入场价格
            size: 持仓数量
            entry_date: 入场日期

        Returns:
            子持仓ID
        """
        if ts_code not in self.position_trackers:
            self.position_trackers[ts_code] = PositionTracker(ts_code, self.config)

        tracker = self.position_trackers[ts_code]
        sub_id = tracker.add_position(entry_price, size, entry_date)

        logger.info(
            f"[RiskManager] 添加持仓 {ts_code}: 价格={entry_price:.2f}, "
            f"数量={size}, 子ID={sub_id}"
        )
        return sub_id

    def remove_position(self, ts_code: str, exit_size: Optional[float] = None) -> bool:
        """
        移除或部分减少持仓

        Args:
            ts_code: 股票代码
            exit_size: 平仓数量，None表示全部平仓

        Returns:
            是否完全移除该标的的持仓
        """
        if ts_code not in self.position_trackers:
            return True

        tracker = self.position_trackers[ts_code]

        if exit_size is None:
            # 全部平仓
            del self.position_trackers[ts_code]
            logger.info(f"[RiskManager] 全部移除持仓 {ts_code}")
            return True
        else:
            # 部分平仓 - 按先进先出原则
            remaining = exit_size
            for sub_id in list(tracker.sub_positions.keys()):
                if remaining <= 0:
                    break
                sub_pos = tracker.sub_positions[sub_id]
                reduce_size = min(remaining, abs(sub_pos.size))
                tracker.remove_position(sub_id, reduce_size)
                remaining -= reduce_size

            # 检查是否完全移除
            if tracker.get_total_size() == 0:
                del self.position_trackers[ts_code]
                logger.info(f"[RiskManager] 全部移除持仓 {ts_code} (部分平仓后)")
                return True

            logger.info(
                f"[RiskManager] 部分移除持仓 {ts_code}: 移除{exit_size}, "
                f"剩余{tracker.get_total_size()}"
            )
            return False

    def check_all_exits(
        self,
        ts_code: str,
        current_price: float,
        holding_days: int,
        market_data: Optional[Dict[str, Any]] = None,
        predicted_signal: Optional[str] = None,
    ) -> ExitSignal:
        """
        检查所有出场条件

        Args:
            ts_code: 股票代码
            current_price: 当前价格
            holding_days: 持仓天数
            market_data: 市场数据，包含ATR等
            predicted_signal: 模型预测信号，用于信号反转出场

        Returns:
            ExitSignal: 出场信号
        """
        if ts_code not in self.position_trackers:
            return ExitSignal.no_exit()

        tracker = self.position_trackers[ts_code]
        market_data = market_data or {}

        # 更新极端价格（用于移动止盈）
        tracker.update_extreme_prices(current_price)

        # 收集所有出场信号
        exit_signals: List[ExitSignal] = []

        # 1. 固定止损
        signal = self._check_fixed_stop_loss(tracker, current_price)
        if signal.should_exit:
            exit_signals.append(signal)

        # 2. 固定止盈
        signal = self._check_fixed_take_profit(tracker, current_price)
        if signal.should_exit:
            exit_signals.append(signal)

        # 3. 移动止盈
        signal = self._check_trailing_stop(tracker, current_price)
        if signal.should_exit:
            exit_signals.append(signal)

        # 4. ATR止损
        signal = self._check_atr_stop(tracker, current_price, market_data)
        if signal.should_exit:
            exit_signals.append(signal)

        # 5. 时间止损
        signal = self._check_time_stop(tracker, holding_days)
        if signal.should_exit:
            exit_signals.append(signal)

        # 6. 分级止盈
        partial_signals = self._check_partial_exits(tracker, current_price)
        exit_signals.extend(partial_signals)

        # 7. 信号反转
        if predicted_signal:
            signal = self._check_signal_reverse(tracker, predicted_signal)
            if signal.should_exit:
                exit_signals.append(signal)

        # 解决冲突，返回最高优先级的信号
        if exit_signals:
            return self._resolve_exit_conflicts(exit_signals)

        return ExitSignal.no_exit()

    def _check_fixed_stop_loss(self, tracker: PositionTracker, current_price: float) -> ExitSignal:
        """检查固定止损"""
        avg_cost = tracker.get_average_cost()
        if avg_cost <= 0:
            return ExitSignal.no_exit()

        # 对于多头，亏损 = (成本 - 现价) / 成本
        # 对于空头，亏损 = (现价 - 成本) / 成本
        total_size = tracker.get_total_size()
        if total_size > 0:  # 多头
            loss_pct = (avg_cost - current_price) / avg_cost
        else:  # 空头
            loss_pct = (current_price - avg_cost) / avg_cost

        if loss_pct >= self.config.fixed_stop_loss_pct:
            priority = self.config.get_exit_priority_rank("stop_loss")
            return ExitSignal.full_exit(
                exit_type="stop_loss",
                reason=f"固定止损触发: 亏损{loss_pct*100:.1f}% >= {self.config.fixed_stop_loss_pct*100:.1f}%",
                priority=priority,
            )
        return ExitSignal.no_exit()

    def _check_fixed_take_profit(
        self, tracker: PositionTracker, current_price: float
    ) -> ExitSignal:
        """检查固定止盈"""
        avg_cost = tracker.get_average_cost()
        if avg_cost <= 0:
            return ExitSignal.no_exit()

        total_size = tracker.get_total_size()
        if total_size > 0:  # 多头
            profit_pct = (current_price - avg_cost) / avg_cost
        else:  # 空头
            profit_pct = (avg_cost - current_price) / avg_cost

        if profit_pct >= self.config.fixed_take_profit_pct:
            priority = self.config.get_exit_priority_rank("take_profit")
            return ExitSignal.full_exit(
                exit_type="take_profit",
                reason=f"固定止盈触发: 盈利{profit_pct*100:.1f}% >= {self.config.fixed_take_profit_pct*100:.1f}%",
                priority=priority,
            )
        return ExitSignal.no_exit()

    def _check_trailing_stop(self, tracker: PositionTracker, current_price: float) -> ExitSignal:
        """检查移动止盈"""
        if not self.config.enable_trailing_stop:
            return ExitSignal.no_exit()

        avg_cost = tracker.get_average_cost()
        if avg_cost <= 0:
            return ExitSignal.no_exit()

        total_size = tracker.get_total_size()

        # 检查每个子持仓的移动止盈
        for sub_pos in tracker.get_sub_positions():
            if total_size > 0:  # 多头
                profit_pct = (sub_pos.highest_price - avg_cost) / avg_cost
                if profit_pct >= self.config.trailing_activation_pct:
                    # 已启动移动止盈
                    pullback_pct = (sub_pos.highest_price - current_price) / sub_pos.highest_price
                    if pullback_pct >= self.config.trailing_stop_pct:
                        priority = self.config.get_exit_priority_rank("trailing_stop")
                        return ExitSignal.full_exit(
                            exit_type="trailing_stop",
                            reason=f"移动止盈触发: 从高点{sub_pos.highest_price:.2f}回撤{pullback_pct*100:.1f}%",
                            priority=priority,
                        )
            else:  # 空头
                profit_pct = (avg_cost - sub_pos.lowest_price) / avg_cost
                if profit_pct >= self.config.trailing_activation_pct:
                    # 已启动移动止盈
                    pullback_pct = (current_price - sub_pos.lowest_price) / sub_pos.lowest_price
                    if pullback_pct >= self.config.trailing_stop_pct:
                        priority = self.config.get_exit_priority_rank("trailing_stop")
                        return ExitSignal.full_exit(
                            exit_type="trailing_stop",
                            reason=f"移动止盈触发(空头): 从低点{sub_pos.lowest_price:.2f}反弹{pullback_pct*100:.1f}%",
                            priority=priority,
                        )

        return ExitSignal.no_exit()

    def _check_atr_stop(
        self, tracker: PositionTracker, current_price: float, market_data: Dict[str, Any]
    ) -> ExitSignal:
        """检查ATR止损"""
        if not self.config.enable_atr_stop:
            return ExitSignal.no_exit()

        atr = market_data.get("atr")
        if atr is None or atr <= 0:
            return ExitSignal.no_exit()

        avg_cost = tracker.get_average_cost()
        if avg_cost <= 0:
            return ExitSignal.no_exit()

        total_size = tracker.get_total_size()
        stop_distance = atr * self.config.atr_multiplier

        if total_size > 0:  # 多头
            stop_price = avg_cost - stop_distance
            if current_price <= stop_price:
                priority = self.config.get_exit_priority_rank("atr_stop")
                return ExitSignal.full_exit(
                    exit_type="atr_stop",
                    reason=f"ATR止损触发: 价格{current_price:.2f} <= 止损价{stop_price:.2f} (ATR={atr:.2f})",
                    priority=priority,
                )
        else:  # 空头
            stop_price = avg_cost + stop_distance
            if current_price >= stop_price:
                priority = self.config.get_exit_priority_rank("atr_stop")
                return ExitSignal.full_exit(
                    exit_type="atr_stop",
                    reason=f"ATR止损触发(空头): 价格{current_price:.2f} >= 止损价{stop_price:.2f} (ATR={atr:.2f})",
                    priority=priority,
                )

        return ExitSignal.no_exit()

    def _check_time_stop(self, tracker: PositionTracker, holding_days: int) -> ExitSignal:
        """检查时间止损"""
        if not self.config.enable_time_stop:
            return ExitSignal.no_exit()

        if holding_days >= self.config.max_holding_days:
            priority = self.config.get_exit_priority_rank("time_stop")
            return ExitSignal.full_exit(
                exit_type="time_stop",
                reason=f"时间止损触发: 持仓{holding_days}天 >= 最大{self.config.max_holding_days}天",
                priority=priority,
            )

        return ExitSignal.no_exit()

    def _check_partial_exits(
        self, tracker: PositionTracker, current_price: float
    ) -> List[ExitSignal]:
        """检查分级止盈"""
        exits = []
        partial_exits = tracker.check_partial_exits(current_price)

        for sub_id, exit_size, reason in partial_exits:
            priority = self.config.get_exit_priority_rank("take_profit")
            signal = ExitSignal.partial_exit(
                exit_type="take_profit", size=exit_size, reason=reason, priority=priority
            )
            signal.metadata["sub_id"] = sub_id
            exits.append(signal)

        return exits

    def _check_signal_reverse(self, tracker: PositionTracker, predicted_signal: str) -> ExitSignal:
        """检查信号反转"""
        total_size = tracker.get_total_size()

        # 多头持仓遇到卖出信号，或空头持仓遇到买入信号
        if (total_size > 0 and predicted_signal == "SELL") or (
            total_size < 0 and predicted_signal == "BUY"
        ):
            priority = self.config.get_exit_priority_rank("signal_reverse")
            return ExitSignal.full_exit(
                exit_type="signal_reverse",
                reason=f"信号反转: 模型预测{predicted_signal}",
                priority=priority,
            )

        return ExitSignal.no_exit()

    def _resolve_exit_conflicts(self, exit_signals: List[ExitSignal]) -> ExitSignal:
        """
        解决出场条件冲突

        按优先级返回最高优先级的信号。
        如果多个信号优先级相同，优先返回全部平仓信号。

        Args:
            exit_signals: 出场信号列表

        Returns:
            最高优先级的出场信号
        """
        if not exit_signals:
            return ExitSignal.no_exit()

        # 按优先级排序
        sorted_signals = sorted(exit_signals, key=lambda s: (s.priority, -s.exit_size))

        # 返回最高优先级的信号
        return sorted_signals[0]

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """
        计算ATR（Average True Range）

        Args:
            data: 包含high, low, close的DataFrame
            period: ATR周期

        Returns:
            ATR值
        """
        if len(data) < period:
            return 0.0

        high = data["high"]
        low = data["low"]
        close = data["close"]

        # 计算True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]

        return atr if not pd.isna(atr) else 0.0

    def update_portfolio_value(self, total_value: float) -> float:
        """
        更新组合净值，计算回撤

        Args:
            total_value: 当前总资产

        Returns:
            当前回撤比例
        """
        if total_value <= 0:
            return 0.0

        # 更新峰值
        if total_value > self._peak_value:
            self._peak_value = total_value

        # 计算回撤
        if self._peak_value > 0:
            self._current_drawdown = (self._peak_value - total_value) / self._peak_value

        return self._current_drawdown

    def should_reduce_position(self) -> bool:
        """判断是否应该减仓（回撤预警）"""
        return self._current_drawdown >= self.config.drawdown_warning_pct

    def should_clear_position(self) -> bool:
        """判断是否应该清仓（触及回撤限制）"""
        return self._current_drawdown >= self.config.max_drawdown_pct

    def record_daily_trade(self, date: datetime, pnl: float = 0.0):
        """记录每日交易"""
        self._daily_trades[date] += 1
        self._daily_pnl[date] += pnl

    def check_daily_limits(self, date: datetime) -> Tuple[bool, str]:
        """
        检查每日限制

        Returns:
            (是否可以交易, 原因)
        """
        # 检查交易次数
        if self._daily_trades[date] >= self.config.max_daily_trades:
            return False, f"单日交易次数达到上限 {self.config.max_daily_trades}"

        # 检查当日亏损
        daily_loss = -self._daily_pnl[date]
        if daily_loss > self.config.max_daily_loss_pct * self._peak_value:
            return False, f"单日亏损超过限制 {self.config.max_daily_loss_pct*100:.1f}%"

        return True, ""

    def get_position_summary(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取持仓摘要"""
        if ts_code not in self.position_trackers:
            return None

        tracker = self.position_trackers[ts_code]
        return {
            "ts_code": ts_code,
            "total_size": tracker.get_total_size(),
            "avg_cost": tracker.get_average_cost(),
            "sub_positions": len(tracker.sub_positions),
        }

    def reset(self):
        """重置所有状态"""
        self.position_trackers.clear()
        self.atr_values.clear()
        self._peak_value = 0.0
        self._current_drawdown = 0.0
        self._daily_trades.clear()
        self._daily_pnl.clear()
        logger.info("[EnhancedRiskManager] 状态已重置")


if __name__ == "__main__":
    # 测试代码
    from datetime import datetime

    # 创建配置
    config = EnhancedRiskConfig(
        fixed_stop_loss_pct=0.05,
        fixed_take_profit_pct=0.10,
        enable_trailing_stop=True,
        trailing_activation_pct=0.05,
        trailing_stop_pct=0.03,
        enable_atr_stop=True,
        atr_multiplier=2.0,
        enable_time_stop=True,
        max_holding_days=20,
    )

    # 创建风险管理器
    risk_mgr = EnhancedRiskManager(config)

    # 添加持仓
    entry_date = datetime.now()
    risk_mgr.add_position("000001.SZ", 100.0, 1000, entry_date)

    # 测试固定止损
    print("\n=== 测试固定止损 ===")
    signal = risk_mgr.check_all_exits("000001.SZ", 94.0, 1)
    print(f"价格94.0 (亏损6%): {signal}")

    signal = risk_mgr.check_all_exits("000001.SZ", 96.0, 1)
    print(f"价格96.0 (亏损4%): {signal}")

    # 测试固定止盈
    print("\n=== 测试固定止盈 ===")
    signal = risk_mgr.check_all_exits("000001.SZ", 111.0, 1)
    print(f"价格111.0 (盈利11%): {signal}")

    # 测试移动止盈
    print("\n=== 测试移动止盈 ===")
    # 先涨5%启动移动止盈
    risk_mgr.position_trackers["000001.SZ"].update_extreme_prices(105.0)
    signal = risk_mgr.check_all_exits("000001.SZ", 101.5, 1)  # 从105回撤约3.3%
    print(f"价格101.5 (高点105, 回撤3.3%): {signal}")

    # 测试时间止损
    print("\n=== 测试时间止损 ===")
    signal = risk_mgr.check_all_exits("000001.SZ", 100.0, 25)
    print(f"持仓25天: {signal}")

    # 测试分级止盈
    print("\n=== 测试分级止盈 ===")
    # 清理之前的持仓，重新建仓
    risk_mgr.reset()
    risk_mgr.add_position("000001.SZ", 100.0, 1000, entry_date)

    signal = risk_mgr.check_all_exits("000001.SZ", 105.0, 1)  # 盈利5%
    print(f"价格105.0 (盈利5%, 触发第一档分级止盈): {signal}")

    # 再次检查，不应该重复触发
    signal = risk_mgr.check_all_exits("000001.SZ", 105.0, 1)
    print(f"再次检查105.0: {signal}")

    print("\n测试完成!")
