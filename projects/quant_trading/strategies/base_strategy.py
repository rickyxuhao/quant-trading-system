"""
策略基类 - 定义所有策略的通用接口

为Backtrader集成提供统一的策略框架
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import backtrader as bt

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyConfig:
    """策略配置基类"""

    # 基础配置
    name: str = "base_strategy"
    description: str = ""

    # 资金配置
    initial_capital: float = 1_000_000.0
    position_size_pct: float = 0.1  # 单仓位占总资金比例
    max_positions: int = 10  # 最大持仓数

    # 成本配置
    commission_rate: float = 0.00025  # 佣金率 0.025%
    stamp_duty_rate: float = 0.001  # 印花税 0.1%（仅卖出）
    slippage: float = 0.0005  # 滑点 0.05%

    # 风险控制
    stop_loss_pct: float = 0.05  # 止损比例 5%
    take_profit_pct: float = 0.1  # 止盈比例 10%
    max_drawdown_pct: float = 0.15  # 最大回撤 15%
    trailing_stop_pct: Optional[float] = None  # 移动止损比例

    # 时间配置
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rebalance_frequency: str = "daily"  # daily, weekly, monthly

    # 其他参数
    params: dict[str, Any] = field(default_factory=dict)

    def to_backtrader_params(self) -> dict:
        """转换为Backtrader参数格式"""
        return {
            "initial_capital": self.initial_capital,
            "commission": self.commission_rate,
            "slippage": self.slippage,
        }


class BaseStrategy(bt.Strategy):
    """
    策略基类

    继承自Backtrader的Strategy，提供统一的接口和工具方法
    """

    params = (
        ("config", None),
        ("verbose", False),
    )

    def __init__(self):
        """初始化策略"""
        self.config: StrategyConfig = self.p.config or StrategyConfig()
        self.order_list: list[bt.Order] = []
        self.trade_log: list[dict] = []

        # 风险控制状态
        self.current_drawdown: float = 0.0
        self.peak_value: float = self.config.initial_capital
        self.is_drawdown_control_active: bool = False

        # 订单状态跟踪
        self.pending_orders: dict[int, bt.Order] = {}
        self.position_costs: dict[str, float] = {}

        self._init_indicators()

    def _init_indicators(self) -> None:
        """初始化技术指标（子类可重写）"""

    def log(self, txt: str, dt: Optional[datetime] = None) -> None:
        """记录日志"""
        if self.p.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            logger.info(f"{dt.isoformat()} - {txt}")

    def notify_order(self, order: bt.Order) -> None:
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"买入执行: 价格={order.executed.price:.2f}, "
                    f"数量={order.executed.size}, "
                    f"成本={order.executed.value:.2f}, "
                    f"佣金={order.executed.comm:.2f}"
                )
            else:
                self.log(
                    f"卖出执行: 价格={order.executed.price:.2f}, "
                    f"数量={order.executed.size}, "
                    f"成本={order.executed.value:.2f}, "
                    f"佣金={order.executed.comm:.2f}"
                )

            # 记录交易
            self._record_trade(order)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"订单取消/保证金不足/拒绝: {order.status}")

        # 从待处理订单中移除
        if order.ref in self.pending_orders:
            del self.pending_orders[order.ref]

    def notify_trade(self, trade: bt.Trade) -> None:
        """交易完成通知"""
        if not trade.isclosed:
            return

        pnl = trade.pnlcomm
        self.log(f"交易完成: 盈亏={pnl:.2f}, 毛利={trade.pnl:.2f}, 净利={pnl:.2f}")

    def _record_trade(self, order: bt.Order) -> None:
        """记录交易详情"""
        trade_record = {
            "date": self.datas[0].datetime.date(0).isoformat(),
            "type": "buy" if order.isbuy() else "sell",
            "price": order.executed.price,
            "size": order.executed.size,
            "value": order.executed.value,
            "commission": order.executed.comm,
        }
        self.trade_log.append(trade_record)

    def prenext(self) -> None:
        """数据未全部就绪时调用"""

    def nextstart(self) -> None:
        """数据首次全部就绪时调用"""
        self.next()

    @abstractmethod
    def next(self) -> None:
        """
        核心交易逻辑（子类必须实现）

        每个bar调用一次
        """
        raise NotImplementedError("子类必须实现next方法")

    def should_rebalance(self) -> bool:
        """检查是否需要再平衡"""
        if self.config.rebalance_frequency == "daily":
            return True
        elif self.config.rebalance_frequency == "weekly":
            return self.datas[0].datetime.date(0).weekday() == 0
        elif self.config.rebalance_frequency == "monthly":
            return self.datas[0].datetime.date(0).day == 1
        return True

    def calculate_position_size(self, data, target_pct: Optional[float] = None) -> int:
        """
        计算仓位大小

        Args:
            data: 数据源
            target_pct: 目标仓位占比，默认使用配置值

        Returns:
            交易数量
        """
        target_pct = target_pct or self.config.position_size_pct
        available_cash = self.broker.getcash()
        target_value = available_cash * target_pct
        price = data.close[0]

        # 考虑交易成本
        size = int(target_value / price)

        return size

    def check_stop_loss(self, data, position) -> bool:
        """
        检查是否触发止损

        Returns:
            是否触发止损
        """
        if not position:
            return False

        entry_price = position.price
        current_price = data.close[0]

        if position.size > 0:  # 多头
            loss_pct = (entry_price - current_price) / entry_price
        else:  # 空头
            loss_pct = (current_price - entry_price) / entry_price

        return loss_pct >= self.config.stop_loss_pct

    def check_take_profit(self, data, position) -> bool:
        """
        检查是否触发止盈

        Returns:
            是否触发止盈
        """
        if not position:
            return False

        entry_price = position.price
        current_price = data.close[0]

        if position.size > 0:  # 多头
            profit_pct = (current_price - entry_price) / entry_price
        else:  # 空头
            profit_pct = (entry_price - current_price) / entry_price

        return profit_pct >= self.config.take_profit_pct

    def update_drawdown(self) -> None:
        """更新回撤状态"""
        current_value = self.broker.getvalue()

        if current_value > self.peak_value:
            self.peak_value = current_value

        self.current_drawdown = (self.peak_value - current_value) / self.peak_value

        # 回撤控制
        if self.current_drawdown >= self.config.max_drawdown_pct:
            if not self.is_drawdown_control_active:
                self.log(f"触发回撤控制: 当前回撤 {self.current_drawdown:.2%}")
                self.is_drawdown_control_active = True
        else:
            self.is_drawdown_control_active = False

    def is_trading_allowed(self) -> bool:
        """检查是否允许交易"""
        return not self.is_drawdown_control_active

    def get_analytics(self) -> dict:
        """
        获取策略分析指标

        Returns:
            策略分析数据字典
        """
        return {
            "total_trades": len(self.trade_log),
            "pending_orders": len(self.pending_orders),
            "current_drawdown": self.current_drawdown,
            "peak_value": self.peak_value,
            "is_drawdown_control": self.is_drawdown_control_active,
        }


class MultiAssetStrategy(BaseStrategy):
    """多资产策略基类"""

    def __init__(self):
        super().__init__()
        self.asset_weights: dict[str, float] = {}
        self.last_rebalance_date: Optional[datetime] = None

    def get_data_by_name(self, name: str):
        """根据名称获取数据源"""
        for data in self.datas:
            if data._name == name:
                return data
        return None

    def set_weights(self, weights: dict[str, float]) -> None:
        """
        设置资产权重

        Args:
            weights: {资产名称: 权重}，权重之和应接近1
        """
        self.asset_weights = weights

    def rebalance(self) -> None:
        """执行再平衡"""
        if not self.should_rebalance():
            return

        total_value = self.broker.getvalue()

        for name, target_weight in self.asset_weights.items():
            data = self.get_data_by_name(name)
            if not data:
                continue

            target_value = total_value * target_weight
            current_position = self.getposition(data)
            current_value = current_position.size * data.close[0]

            # 计算需要调整的金额
            diff_value = target_value - current_value

            if abs(diff_value) > 1000:  # 最小调整阈值
                size = int(diff_value / data.close[0])
                if size > 0:
                    self.buy(data=data, size=size)
                elif size < 0:
                    self.sell(data=data, size=abs(size))

        self.last_rebalance_date = self.datas[0].datetime.date(0)


class ChinaCommissionScheme(bt.CommInfoBase):
    """中国市场交易成本方案"""

    params = (
        ("commission", 0.00025),  # 佣金率
        ("stamp_duty", 0.001),  # 印花税（仅卖出）
        ("transfer_fee", 0.00002),  # 过户费
        ("min_commission", 5.0),  # 最低佣金
    )

    def _getcommission(self, size, price, pseudoexec):
        """计算佣金"""
        value = abs(size) * price

        # 佣金（双向，有最低）
        commission = max(value * self.p.commission, self.p.min_commission)

        # 过户费（双向）
        transfer_fee = value * self.p.transfer_fee

        # 印花税（仅卖出）
        stamp_duty = 0
        if size < 0:  # 卖出
            stamp_duty = value * self.p.stamp_duty

        return commission + transfer_fee + stamp_duty


def create_cerebro(config: StrategyConfig) -> bt.Cerebro:
    """
    创建并配置Backtrader Cerebro引擎

    Args:
        config: 策略配置

    Returns:
        配置好的Cerebro实例
    """
    cerebro = bt.Cerebro()

    # 设置初始资金
    cerebro.broker.setcash(config.initial_capital)

    # 设置佣金方案
    comminfo = ChinaCommissionScheme(
        commission=config.commission_rate,
        stamp_duty=config.stamp_duty_rate,
    )
    cerebro.broker.addcommissioninfo(comminfo)

    # 设置滑点
    cerebro.broker.set_slippage_perc(config.slippage)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    return cerebro
