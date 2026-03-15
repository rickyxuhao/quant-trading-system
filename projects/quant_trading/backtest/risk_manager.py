"""
回测框架 - 风险管理模块

实现回撤控制、仓位限制、单日亏损限制等风控功能。
支持固定止损、移动止损、回撤控制等多种风控策略。

Example:
    >>> config = RiskConfig(max_drawdown_limit=0.15, stop_loss_pct=0.08)
    >>> risk_mgr = RiskManager(config)
    >>> risk_mgr.update_portfolio_value(datetime.now(), 100000)
    >>> should_stop = risk_mgr.check_stop_loss(datetime.now(), '000001.SZ', 9.0, 10.0)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Callable, Any, Set
from enum import Enum
import pandas as pd
import numpy as np
import logging

# Setup logging
logger = logging.getLogger(__name__)


class RiskSeverity(Enum):
    """风险严重程度枚举"""
    WARNING = "warning"
    CRITICAL = "critical"
    INFO = "info"


class RiskAlertType(Enum):
    """风险告警类型枚举"""
    MAX_DRAWDOWN = "max_drawdown"
    DRAWDOWN_WARNING = "drawdown_warning"
    POSITION_LIMIT = "position_limit"
    SECTOR_LIMIT = "sector_limit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DAILY_TRADE_LIMIT = "daily_trade_limit"
    TURNOVER_LIMIT = "turnover_limit"
    CASH_RATIO_LIMIT = "cash_ratio_limit"


@dataclass
class RiskConfig:
    """
    风控配置类

    定义各类风控阈值和限制参数。

    Attributes:
        max_drawdown_limit: 最大回撤限制（如0.15表示15%）
        drawdown_warning: 回撤预警线（如0.10表示10%）
        max_position_weight: 单只股票最大权重
        max_sector_weight: 单个行业最大权重
        min_cash_ratio: 最小现金比例
        max_daily_loss: 单日最大亏损比例
        max_daily_trades: 单日最大交易次数
        max_turnover: 单日最大换手率
        enable_stop_loss: 是否启用止损
        stop_loss_pct: 个股止损线（相对于成本的跌幅）
        trailing_stop: 是否启用移动止损
        trailing_stop_pct: 移动止损幅度（相对于最高点）
    """
    # 回撤控制
    max_drawdown_limit: float = 0.15           # 最大回撤限制（15%）
    drawdown_warning: float = 0.10             # 回撤预警线（10%）

    # 仓位限制
    max_position_weight: float = 0.30          # 单只股票最大权重（30%）
    max_sector_weight: float = 0.50            # 单个行业最大权重（50%）
    min_cash_ratio: float = 0.05               # 最小现金比例（5%）

    # 交易限制
    max_daily_loss: float = 0.03               # 单日最大亏损（3%）
    max_daily_trades: int = 20                 # 单日最大交易次数
    max_turnover: float = 0.50                 # 单日最大换手率（50%）

    # 止损设置
    enable_stop_loss: bool = True
    stop_loss_pct: float = 0.08                # 个股止损线（8%）
    trailing_stop: bool = False                # 是否启用移动止损
    trailing_stop_pct: float = 0.05            # 移动止损幅度（5%）

    def __post_init__(self) -> None:
        """验证配置参数有效性"""
        if not 0 < self.max_drawdown_limit < 1:
            logger.warning(f"max_drawdown_limit should be between 0 and 1, got {self.max_drawdown_limit}")
        if not 0 < self.stop_loss_pct < 1:
            logger.warning(f"stop_loss_pct should be between 0 and 1, got {self.stop_loss_pct}")
        if self.max_position_weight > 1:
            logger.warning(f"max_position_weight should be <= 1, got {self.max_position_weight}")


@dataclass
class RiskAlert:
    """
    风险告警数据类

    记录单个风险事件的详细信息。

    Attributes:
        timestamp: 告警时间戳
        alert_type: 告警类型（RiskAlertType枚举）
        severity: 严重程度（warning/critical/info）
        message: 告警描述信息
        value: 实际值
        threshold: 触发阈值
    """
    timestamp: datetime
    alert_type: RiskAlertType
    severity: RiskSeverity
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'type': self.alert_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold
        }


class RiskManager:
    """
    风险管理器

    负责回撤监控与控制、仓位限制检查、交易频率控制、止损触发判断等功能。

    Attributes:
        config: RiskConfig 风控配置
        alerts: List[RiskAlert] 风险告警列表

    Example:
        >>> config = RiskConfig(max_drawdown_limit=0.15, stop_loss_pct=0.08)
        >>> risk_mgr = RiskManager(config)
        >>> risk_mgr.update_portfolio_value(datetime.now(), 100000)
        >>> violations = risk_mgr.check_position_limits(
        ...     datetime.now(),
        ...     {'000001.SZ': {'quantity': 1000, 'market_value': 10000}},
        ...     100000
        ... )
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        初始化风险管理器

        Args:
            config: 风控配置，若为None则使用默认配置
        """
        self.config = config or RiskConfig()
        self.alerts: List[RiskAlert] = []

        # 内部状态
        self._peak_value: float = 0.0            # 历史最高净值
        self._current_drawdown: float = 0.0      # 当前回撤
        self._daily_pnl: Dict[date, float] = {}  # 每日盈亏
        self._daily_trades: Dict[date, int] = {}  # 每日交易次数
        self._stop_loss_prices: Dict[str, float] = {}  # 止损价格
        self._peak_prices: Dict[str, float] = {}       # 个股最高价（移动止损用）

        logger.debug(f"RiskManager initialized with config: {self.config}")

    def update_portfolio_value(self, timestamp: datetime, total_value: float) -> None:
        """
        更新组合净值，计算回撤

        Args:
            timestamp: 时间戳
            total_value: 当前总资产
        """
        if total_value <= 0:
            logger.warning(f"Invalid portfolio value: {total_value}")
            return

        # 更新峰值
        if total_value > self._peak_value:
            old_peak = self._peak_value
            self._peak_value = total_value
            logger.debug(f"New portfolio peak: {self._peak_value:,.2f}")

            # 重置移动止损基准
            if self.config.trailing_stop:
                for ts_code in self._peak_prices:
                    self._peak_prices[ts_code] = total_value

        # 计算回撤
        if self._peak_value > 0:
            self._current_drawdown = (self._peak_value - total_value) / self._peak_value

        # 检查回撤限制
        if self._current_drawdown >= self.config.max_drawdown_limit:
            self._add_alert(
                timestamp,
                RiskAlertType.MAX_DRAWDOWN,
                RiskSeverity.CRITICAL,
                f'触发最大回撤限制 {self.config.max_drawdown_limit * 100:.1f}%',
                self._current_drawdown,
                self.config.max_drawdown_limit
            )
        elif self._current_drawdown >= self.config.drawdown_warning:
            self._add_alert(
                timestamp,
                RiskAlertType.DRAWDOWN_WARNING,
                RiskSeverity.WARNING,
                f'回撤达到预警线 {self.config.drawdown_warning * 100:.1f}%',
                self._current_drawdown,
                self.config.drawdown_warning
            )

    def check_position_limits(
        self,
        timestamp: datetime,
        positions: Dict[str, Dict[str, Any]],
        total_value: float
    ) -> List[str]:
        """
        检查仓位限制

        Args:
            timestamp: 时间戳
            positions: 持仓字典，格式为 {ts_code: {'quantity': x, 'market_value': y}}
            total_value: 总资产

        Returns:
            超限的股票代码列表
        """
        violations: List[str] = []

        if total_value <= 0:
            logger.warning(f"Invalid total value for position check: {total_value}")
            return violations

        for ts_code, pos in positions.items():
            market_value = pos.get('market_value', 0)
            weight = market_value / total_value if total_value > 0 else 0

            if weight > self.config.max_position_weight:
                violations.append(ts_code)
                self._add_alert(
                    timestamp,
                    RiskAlertType.POSITION_LIMIT,
                    RiskSeverity.WARNING,
                    f'{ts_code} 仓位 {weight * 100:.1f}% 超过限制 {self.config.max_position_weight * 100:.1f}%',
                    weight,
                    self.config.max_position_weight
                )

        return violations

    def check_cash_ratio(
        self,
        timestamp: datetime,
        cash: float,
        total_value: float
    ) -> bool:
        """
        检查现金比例是否满足最小要求

        Args:
            timestamp: 时间戳
            cash: 现金金额
            total_value: 总资产

        Returns:
            是否满足最小现金比例
        """
        if total_value <= 0:
            return True

        cash_ratio = cash / total_value
        if cash_ratio < self.config.min_cash_ratio:
            self._add_alert(
                timestamp,
                RiskAlertType.CASH_RATIO_LIMIT,
                RiskSeverity.WARNING,
                f'现金比例 {cash_ratio * 100:.1f}% 低于最小要求 {self.config.min_cash_ratio * 100:.1f}%',
                cash_ratio,
                self.config.min_cash_ratio
            )
            return False
        return True

    def check_stop_loss(
        self,
        timestamp: datetime,
        ts_code: str,
        current_price: float,
        avg_cost: float
    ) -> bool:
        """
        检查是否触发止损

        支持固定止损和移动止损两种模式。

        Args:
            timestamp: 时间戳
            ts_code: 股票代码
            current_price: 当前价格
            avg_cost: 平均成本

        Returns:
            是否触发止损
        """
        if not self.config.enable_stop_loss or avg_cost <= 0 or current_price <= 0:
            return False

        # 固定止损
        loss_pct = (avg_cost - current_price) / avg_cost
        if loss_pct >= self.config.stop_loss_pct:
            self._add_alert(
                timestamp,
                RiskAlertType.STOP_LOSS,
                RiskSeverity.CRITICAL,
                f'{ts_code} 触发止损线 {self.config.stop_loss_pct * 100:.1f}%，'
                f'当前亏损 {loss_pct * 100:.1f}%',
                loss_pct,
                self.config.stop_loss_pct
            )
            return True

        # 移动止损
        if self.config.trailing_stop:
            if ts_code not in self._peak_prices:
                self._peak_prices[ts_code] = max(avg_cost, current_price)
            else:
                self._peak_prices[ts_code] = max(self._peak_prices[ts_code], current_price)

            peak = self._peak_prices[ts_code]
            trailing_loss = (peak - current_price) / peak

            if trailing_loss >= self.config.trailing_stop_pct:
                self._add_alert(
                    timestamp,
                    RiskAlertType.TRAILING_STOP,
                    RiskSeverity.CRITICAL,
                    f'{ts_code} 触发移动止损，从高点 {peak:.2f} 下跌 {trailing_loss * 100:.1f}%',
                    trailing_loss,
                    self.config.trailing_stop_pct
                )
                return True

        return False

    def check_daily_limits(
        self,
        timestamp: datetime,
        daily_pnl: float,
        trade_count: int,
        turnover: float
    ) -> Dict[str, Any]:
        """
        检查每日限制

        检查单日亏损、交易次数、换手率等限制。

        Args:
            timestamp: 时间戳
            daily_pnl: 当日盈亏金额
            trade_count: 当日交易次数
            turnover: 当日换手率

        Returns:
            {'can_trade': bool, 'reason': str} 是否可以继续交易及原因
        """
        current_date = timestamp.date()

        # 累计当日盈亏
        if current_date not in self._daily_pnl:
            self._daily_pnl[current_date] = 0
        self._daily_pnl[current_date] += daily_pnl

        # 累计当日交易次数
        if current_date not in self._daily_trades:
            self._daily_trades[current_date] = 0
        self._daily_trades[current_date] += trade_count

        results: Dict[str, Any] = {'can_trade': True, 'reason': ''}

        # 检查单日亏损
        total_pnl = self._daily_pnl[current_date]
        if total_pnl < 0 and abs(total_pnl) > self.config.max_daily_loss:
            results['can_trade'] = False
            results['reason'] = (
                f'单日亏损 {abs(total_pnl) * 100:.2f}% 超过限制 '
                f'{self.config.max_daily_loss * 100:.2f}%'
            )
            self._add_alert(
                timestamp,
                RiskAlertType.DAILY_LOSS_LIMIT,
                RiskSeverity.CRITICAL,
                results['reason'],
                abs(total_pnl),
                self.config.max_daily_loss
            )

        # 检查交易次数
        if self._daily_trades[current_date] >= self.config.max_daily_trades:
            results['can_trade'] = False
            results['reason'] = (
                f'单日交易次数 {self._daily_trades[current_date]} '
                f'超过限制 {self.config.max_daily_trades}'
            )
            self._add_alert(
                timestamp,
                RiskAlertType.DAILY_TRADE_LIMIT,
                RiskSeverity.WARNING,
                results['reason'],
                float(self._daily_trades[current_date]),
                float(self.config.max_daily_trades)
            )

        # 检查换手率
        if turnover > self.config.max_turnover:
            results['can_trade'] = False
            results['reason'] = (
                f'单日换手率 {turnover * 100:.1f}% '
                f'超过限制 {self.config.max_turnover * 100:.1f}%'
            )
            self._add_alert(
                timestamp,
                RiskAlertType.TURNOVER_LIMIT,
                RiskSeverity.WARNING,
                results['reason'],
                turnover,
                self.config.max_turnover
            )

        return results

    def should_reduce_position(self) -> bool:
        """
        判断是否应该减仓（回撤预警）

        Returns:
            是否达到减仓条件
        """
        return self._current_drawdown >= self.config.drawdown_warning

    def should_clear_position(self) -> bool:
        """
        判断是否应该清仓（触及回撤限制）

        Returns:
            是否达到清仓条件
        """
        return self._current_drawdown >= self.config.max_drawdown_limit

    def get_current_drawdown(self) -> float:
        """获取当前回撤比例"""
        return self._current_drawdown

    def get_peak_value(self) -> float:
        """获取历史最高净值"""
        return self._peak_value

    def get_risk_summary(self) -> Dict[str, Any]:
        """
        获取风险摘要

        Returns:
            包含当前风险状态的字典
        """
        return {
            'current_drawdown': self._current_drawdown,
            'peak_value': self._peak_value,
            'alert_count': len(self.alerts),
            'critical_alerts': len([a for a in self.alerts if a.severity == RiskSeverity.CRITICAL]),
            'warning_alerts': len([a for a in self.alerts if a.severity == RiskSeverity.WARNING]),
            'config': {
                'max_drawdown_limit': self.config.max_drawdown_limit,
                'stop_loss_pct': self.config.stop_loss_pct,
                'max_position_weight': self.config.max_position_weight
            }
        }

    def get_alerts_df(self) -> pd.DataFrame:
        """
        获取告警记录为DataFrame

        Returns:
            包含所有告警的DataFrame
        """
        if not self.alerts:
            return pd.DataFrame()

        data = [alert.to_dict() for alert in self.alerts]
        return pd.DataFrame(data)

    def get_alerts_by_type(self, alert_type: RiskAlertType) -> List[RiskAlert]:
        """
        按类型获取告警

        Args:
            alert_type: 告警类型

        Returns:
            该类型的告警列表
        """
        return [a for a in self.alerts if a.alert_type == alert_type]

    def _add_alert(
        self,
        timestamp: datetime,
        alert_type: RiskAlertType,
        severity: RiskSeverity,
        message: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None
    ) -> None:
        """
        添加告警

        Args:
            timestamp: 时间戳
            alert_type: 告警类型
            severity: 严重程度
            message: 描述信息
            value: 实际值
            threshold: 阈值
        """
        alert = RiskAlert(
            timestamp=timestamp,
            alert_type=alert_type,
            severity=severity,
            message=message,
            value=value,
            threshold=threshold
        )
        self.alerts.append(alert)

        # 根据严重程度使用不同日志级别
        log_msg = f"[{alert_type.value}] {message}"
        if severity == RiskSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == RiskSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def reset_daily_stats(self, date: date) -> None:
        """
        重置每日统计

        Args:
            date: 要重置的日期
        """
        self._daily_pnl[date] = 0
        self._daily_trades[date] = 0
        logger.debug(f"Reset daily stats for {date}")

    def clear_alerts(self) -> None:
        """清除所有告警记录"""
        count = len(self.alerts)
        self.alerts.clear()
        logger.info(f"Cleared {count} risk alerts")

    def reset(self) -> None:
        """重置所有状态"""
        self._peak_value = 0.0
        self._current_drawdown = 0.0
        self._daily_pnl.clear()
        self._daily_trades.clear()
        self._stop_loss_prices.clear()
        self._peak_prices.clear()
        self.alerts.clear()
        logger.info("RiskManager state reset")


def create_conservative_config() -> RiskConfig:
    """
    创建保守型风控配置

    Returns:
        RiskConfig: 保守型配置（更严格的限制）
    """
    return RiskConfig(
        max_drawdown_limit=0.10,
        drawdown_warning=0.05,
        max_position_weight=0.20,
        max_sector_weight=0.30,
        stop_loss_pct=0.05,
        max_daily_loss=0.02
    )


def create_aggressive_config() -> RiskConfig:
    """
    创建激进型风控配置

    Returns:
        RiskConfig: 激进型配置（更宽松的限制）
    """
    return RiskConfig(
        max_drawdown_limit=0.25,
        drawdown_warning=0.15,
        max_position_weight=0.50,
        max_sector_weight=0.70,
        stop_loss_pct=0.12,
        max_daily_loss=0.05
    )


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    config = RiskConfig(
        max_drawdown_limit=0.15,
        stop_loss_pct=0.08
    )

    risk_mgr = RiskManager(config)

    # 模拟净值变化
    now = datetime.now()
    risk_mgr.update_portfolio_value(now, 100000)
    risk_mgr.update_portfolio_value(now, 105000)
    risk_mgr.update_portfolio_value(now, 90000)  # 回撤14.3%

    # 检查止损
    should_stop = risk_mgr.check_stop_loss(now, '000001.SZ', 9.0, 10.0)
    print(f"止损触发: {should_stop}")

    # 检查仓位限制
    positions = {
        '000001.SZ': {'quantity': 1000, 'market_value': 50000},
        '000002.SZ': {'quantity': 1000, 'market_value': 40000}
    }
    violations = risk_mgr.check_position_limits(now, positions, 100000)
    print(f"仓位超限: {violations}")

    # 打印风险摘要
    print("\n风险摘要:")
    print(risk_mgr.get_risk_summary())

    # 打印告警
    print("\n告警记录:")
    print(risk_mgr.get_alerts_df())
