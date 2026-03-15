"""
回测框架 - 账户管理模块
负责现金、持仓、交易成本管理
滑点调整为万2（0.0002）
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Iterator
from enum import Enum
from pathlib import Path
import logging
import sys

import pandas as pd
import numpy as np

# Setup logging
logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Order:
    """订单"""
    ts_code: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    order_date: Optional[datetime] = None
    order_id: Optional[str] = None

    def __post_init__(self) -> None:
        """验证订单数据"""
        if self.quantity <= 0:
            raise ValueError(f"Order quantity must be positive, got {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit order must have a limit price")


@dataclass(frozen=True)
class Trade:
    """成交记录"""
    ts_code: str
    side: OrderSide
    quantity: int
    price: float
    amount: float
    commission: float
    slip_cost: float
    total_cost: float
    trade_date: datetime
    trade_id: Optional[str] = None

    @property
    def net_amount(self) -> float:
        """净成交金额（考虑成本）"""
        if self.side == OrderSide.BUY:
            return -(self.amount + self.total_cost)
        else:
            return self.amount - self.total_cost


@dataclass
class Position:
    """持仓"""
    ts_code: str
    quantity: int = 0
    avg_cost: float = 0.0
    market_value: float = 0.0
    current_price: float = 0.0
    _realized_pnl: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        """初始化后验证"""
        if self.quantity < 0:
            raise ValueError(f"Position quantity cannot be negative, got {self.quantity}")

    def update_price(self, current_price: float) -> None:
        """更新当前价格"""
        if current_price < 0:
            raise ValueError(f"Price cannot be negative, got {current_price}")
        self.current_price = current_price
        self.market_value = self.quantity * current_price

    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏"""
        if self.quantity == 0:
            return 0.0
        return self.market_value - (self.quantity * self.avg_cost)

    @property
    def unrealized_pnl_pct(self) -> float:
        """未实现盈亏百分比"""
        if self.quantity == 0 or self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost

    @property
    def realized_pnl(self) -> float:
        """已实现盈亏"""
        return self._realized_pnl

    def add_realized_pnl(self, pnl: float) -> None:
        """增加已实现盈亏"""
        self._realized_pnl += pnl

    def copy(self) -> 'Position':
        """创建持仓副本"""
        pos = Position(
            ts_code=self.ts_code,
            quantity=self.quantity,
            avg_cost=self.avg_cost,
            market_value=self.market_value,
            current_price=self.current_price
        )
        pos._realized_pnl = self._realized_pnl
        return pos


@dataclass
class PortfolioState:
    """账户状态"""
    date: datetime
    cash: float
    positions_value: float
    total_value: float
    positions: Dict[str, Position]

    @property
    def position_count(self) -> int:
        """持仓数量"""
        return len(self.positions)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'date': self.date,
            'cash': self.cash,
            'positions_value': self.positions_value,
            'total_value': self.total_value,
            'position_count': self.position_count
        }


class TransactionCostError(Exception):
    """交易成本计算异常"""
    pass


class PortfolioError(Exception):
    """投资组合操作异常"""
    pass


class TransactionCost:
    """
    交易成本计算器
    滑点调整为万2（0.0002）
    """

    def __init__(
        self,
        commission_rate: float = 0.00015,    # 万1.5佣金
        min_commission: float = 5.0,          # 最低佣金5元
        slip_rate: float = 0.0002,            # 万2滑点
        stamp_tax_rate: float = 0.001,        # 千1印花税（卖出）
        transfer_fee_rate: float = 0.00002    # 万0.2过户费
    ) -> None:
        """
        初始化交易成本计算器

        Args:
            commission_rate: 佣金率
            min_commission: 最低佣金
            slip_rate: 滑点率
            stamp_tax_rate: 印花税率
            transfer_fee_rate: 过户费率
        """
        # Validate rates
        if not (0 <= commission_rate <= 0.1):
            raise TransactionCostError(f"Commission rate should be between 0 and 0.1, got {commission_rate}")
        if not (0 <= slip_rate <= 0.1):
            raise TransactionCostError(f"Slippage rate should be between 0 and 0.1, got {slip_rate}")

        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slip_rate = slip_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate

        logger.debug(f"TransactionCost initialized: commission={commission_rate}, slip={slip_rate}")

    def calculate(
        self,
        side: OrderSide,
        quantity: int,
        price: float
    ) -> Tuple[float, float, float, float]:
        """
        计算交易成本

        Args:
            side: 订单方向
            quantity: 数量
            price: 价格

        Returns:
            (佣金, 滑点成本, 印花税, 过户费)

        Raises:
            TransactionCostError: 当输入参数无效时
        """
        if quantity <= 0:
            raise TransactionCostError(f"Quantity must be positive, got {quantity}")
        if price < 0:
            raise TransactionCostError(f"Price cannot be negative, got {price}")

        amount = quantity * price

        # 佣金（买卖双向）
        commission = max(amount * self.commission_rate, self.min_commission)

        # 滑点成本
        slip_cost = amount * self.slip_rate

        # 印花税（仅卖出）
        stamp_tax = amount * self.stamp_tax_rate if side == OrderSide.SELL else 0.0

        # 过户费（买卖双向，沪市）
        transfer_fee = amount * self.transfer_fee_rate

        logger.debug(f"Cost calculation: side={side.value}, qty={quantity}, price={price:.4f}, "
                    f"commission={commission:.2f}, slip={slip_cost:.2f}, tax={stamp_tax:.2f}, transfer={transfer_fee:.2f}")

        return commission, slip_cost, stamp_tax, transfer_fee

    def get_exec_price(self, side: OrderSide, price: float) -> float:
        """
        获取实际成交价格（考虑滑点）

        Args:
            side: 订单方向
            price: 理论价格

        Returns:
            实际成交价格
        """
        if price < 0:
            raise TransactionCostError(f"Price cannot be negative, got {price}")

        if side == OrderSide.BUY:
            return price * (1 + self.slip_rate)
        else:
            return price * (1 - self.slip_rate)

    def get_total_cost(
        self,
        side: OrderSide,
        quantity: int,
        price: float
    ) -> float:
        """
        获取总交易成本

        Args:
            side: 订单方向
            quantity: 数量
            price: 价格

        Returns:
            总交易成本
        """
        commission, slip_cost, stamp_tax, transfer_fee = self.calculate(
            side, quantity, price
        )
        return commission + slip_cost + stamp_tax + transfer_fee


class Portfolio:
    """
    投资组合管理器
    管理现金、持仓、执行交易
    """

    def __init__(
        self,
        initial_cash: float = 200000.0,
        commission_rate: float = 0.00015,
        slip_rate: float = 0.0002,      # 万2滑点
        risk_manager: Optional[Any] = None,
        name: str = "default"
    ) -> None:
        """
        初始化投资组合

        Args:
            initial_cash: 初始资金
            commission_rate: 佣金率
            slip_rate: 滑点率
            risk_manager: 风控管理器（可选）
            name: 组合名称
        """
        if initial_cash <= 0:
            raise PortfolioError(f"Initial cash must be positive, got {initial_cash}")

        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.daily_values: List[PortfolioState] = []
        self.risk_manager = risk_manager
        self.transaction_cost = TransactionCost(
            commission_rate=commission_rate,
            slip_rate=slip_rate
        )
        self._frozen_cash: float = 0.0  # 冻结资金（用于风控）

        # Performance tracking
        self._peak_value: float = initial_cash
        self._current_drawdown: float = 0.0

        logger.info(f"Portfolio '{name}' initialized with cash={initial_cash:,.2f}")

    # ========== Properties ==========

    @property
    def total_value(self) -> float:
        """获取总资产"""
        return self.cash + self.get_position_value()

    @property
    def position_value(self) -> float:
        """获取持仓市值"""
        return sum(p.market_value for p in self.positions.values())

    @property
    def nav(self) -> float:
        """当前净值"""
        return self.total_value / self.initial_cash if self.initial_cash > 0 else 1.0

    @property
    def total_return(self) -> float:
        """总收益率"""
        return (self.total_value - self.initial_cash) / self.initial_cash if self.initial_cash > 0 else 0.0

    @property
    def drawdown(self) -> float:
        """当前回撤"""
        return self._current_drawdown

    # ========== Position Methods ==========

    def get_position(self, ts_code: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(ts_code)

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓（副本）"""
        return {k: v.copy() for k, v in self.positions.items()}

    def get_position_value(self) -> float:
        """获取持仓市值"""
        return sum(p.market_value for p in self.positions.values())

    def get_available_cash(self) -> float:
        """获取可用资金"""
        return self.cash - self._frozen_cash

    def get_weights(self) -> Dict[str, float]:
        """获取持仓权重"""
        total = self.total_value
        if total == 0:
            return {}
        return {
            ts_code: pos.market_value / total
            for ts_code, pos in self.positions.items()
        }

    def get_position_pnl(self) -> Dict[str, Dict[str, float]]:
        """获取各持仓盈亏情况"""
        return {
            ts_code: {
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct,
                'realized_pnl': pos.realized_pnl,
                'market_value': pos.market_value
            }
            for ts_code, pos in self.positions.items()
        }

    def has_position(self, ts_code: str) -> bool:
        """检查是否有持仓"""
        return ts_code in self.positions and self.positions[ts_code].quantity > 0

    # ========== Risk Check Methods ==========

    def check_risk_limits(self, order: Order, price: float) -> Tuple[bool, str]:
        """检查风控限制"""
        if self.risk_manager is None:
            return True, ""

        try:
            # 构建临时持仓用于检查
            temp_portfolio = {
                'cash': self.cash,
                'positions': {
                    ts_code: {
                        'quantity': pos.quantity,
                        'market_value': pos.market_value,
                        'avg_cost': pos.avg_cost
                    }
                    for ts_code, pos in self.positions.items()
                },
                'total_value': self.total_value,
                'frozen_cash': self._frozen_cash
            }

            amount = order.quantity * price

            # Check if risk_manager has check_order method
            if hasattr(self.risk_manager, 'check_order'):
                return self.risk_manager.check_order(temp_portfolio, order, amount)
            else:
                return True, ""
        except Exception as e:
            logger.warning(f"Risk check failed: {e}")
            return True, ""  # Fail open

    # ========== Order Execution Methods ==========

    def execute_order(
        self,
        order: Order,
        price: float,
        date: datetime
    ) -> Optional[Trade]:
        """
        执行订单

        Args:
            order: 订单对象
            price: 执行价格
            date: 交易日期

        Returns:
            成交记录，如果执行失败则返回None
        """
        try:
            # 风控检查
            can_trade, reason = self.check_risk_limits(order, price)
            if not can_trade:
                logger.warning(f"Order rejected by risk manager: {reason}")
                return None

            # 计算实际成交价格（含滑点）
            exec_price = self.transaction_cost.get_exec_price(order.side, price)

            # 计算成本
            commission, slip_cost, stamp_tax, transfer_fee = self.transaction_cost.calculate(
                order.side, order.quantity, price
            )
            total_cost = commission + slip_cost + stamp_tax + transfer_fee

            # 成交金额
            amount = order.quantity * exec_price

            if order.side == OrderSide.BUY:
                trade = self._execute_buy(order, exec_price, amount, total_cost,
                                          commission, slip_cost, stamp_tax, transfer_fee, date)
            else:
                trade = self._execute_sell(order, exec_price, amount, total_cost,
                                           commission, slip_cost, stamp_tax, transfer_fee, date)

            if trade:
                logger.debug(f"Order executed: {order.ts_code} {order.side.value} {order.quantity} @ {exec_price:.4f}")
                self._update_peak_and_drawdown()

            return trade

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            return None

    def _execute_buy(
        self,
        order: Order,
        exec_price: float,
        amount: float,
        total_cost: float,
        commission: float,
        slip_cost: float,
        stamp_tax: float,
        transfer_fee: float,
        date: datetime
    ) -> Optional[Trade]:
        """执行买入"""
        total_needed = amount + total_cost

        if total_needed > self.cash:
            # 资金不足，调整数量
            max_amount = self.cash - total_cost
            if max_amount <= 0:
                logger.warning(f"Insufficient cash for order: {order.ts_code}, cash={self.cash:.2f}, needed={total_needed:.2f}")
                return None
            adjusted_quantity = int(max_amount / exec_price / 100) * 100
            if adjusted_quantity == 0:
                logger.warning(f"Cannot buy any shares of {order.ts_code} with available cash")
                return None

            order = Order(
                ts_code=order.ts_code,
                side=order.side,
                quantity=adjusted_quantity,
                order_type=order.order_type,
                limit_price=order.limit_price,
                order_date=order.order_date
            )
            amount = order.quantity * exec_price
            commission, slip_cost, stamp_tax, transfer_fee = self.transaction_cost.calculate(
                order.side, order.quantity, exec_price / (1 + self.transaction_cost.slip_rate)
            )
            total_cost = commission + slip_cost + stamp_tax + transfer_fee

        # 更新现金
        self.cash -= (amount + total_cost)

        # 更新持仓
        if order.ts_code in self.positions:
            pos = self.positions[order.ts_code]
            total_cost_basis = pos.quantity * pos.avg_cost + amount + total_cost
            pos.quantity += order.quantity
            pos.avg_cost = total_cost_basis / pos.quantity
        else:
            self.positions[order.ts_code] = Position(
                ts_code=order.ts_code,
                quantity=order.quantity,
                avg_cost=exec_price + total_cost / order.quantity,
                market_value=amount,
                current_price=exec_price
            )

        # 记录交易
        trade = Trade(
            ts_code=order.ts_code,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            amount=amount,
            commission=commission + stamp_tax + transfer_fee,
            slip_cost=slip_cost,
            total_cost=total_cost,
            trade_date=date
        )
        self.trades.append(trade)

        return trade

    def _execute_sell(
        self,
        order: Order,
        exec_price: float,
        amount: float,
        total_cost: float,
        commission: float,
        slip_cost: float,
        stamp_tax: float,
        transfer_fee: float,
        date: datetime
    ) -> Optional[Trade]:
        """执行卖出"""
        if order.ts_code not in self.positions:
            logger.warning(f"Cannot sell {order.ts_code}: no position")
            return None

        pos = self.positions[order.ts_code]
        if pos.quantity < order.quantity:
            logger.warning(f"Cannot sell {order.ts_code}: insufficient quantity ({pos.quantity} < {order.quantity})")
            return None

        # 计算已实现盈亏
        realized_pnl = (exec_price - pos.avg_cost) * order.quantity - total_cost
        pos.add_realized_pnl(realized_pnl)

        # 更新现金
        self.cash += (amount - total_cost)

        # 更新持仓
        pos.quantity -= order.quantity
        if pos.quantity == 0:
            del self.positions[order.ts_code]
            logger.debug(f"Position closed: {order.ts_code}")
        else:
            pos.market_value = pos.quantity * exec_price

        # 记录交易
        trade = Trade(
            ts_code=order.ts_code,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            amount=amount,
            commission=commission + stamp_tax + transfer_fee,
            slip_cost=slip_cost,
            total_cost=total_cost,
            trade_date=date
        )
        self.trades.append(trade)

        return trade

    def execute_orders_batch(
        self,
        orders: List[Order],
        prices: Dict[str, float],
        date: datetime
    ) -> List[Trade]:
        """
        批量执行订单

        Args:
            orders: 订单列表
            prices: 价格字典 {ts_code: price}
            date: 交易日期

        Returns:
            成交记录列表
        """
        if not orders:
            return []

        trades: List[Trade] = []
        failed_orders: List[str] = []

        for order in orders:
            if order.ts_code not in prices:
                failed_orders.append(f"{order.ts_code}(no price)")
                continue

            try:
                trade = self.execute_order(order, prices[order.ts_code], date)
                if trade:
                    trades.append(trade)
                else:
                    failed_orders.append(order.ts_code)
            except Exception as e:
                logger.error(f"Failed to execute order for {order.ts_code}: {e}")
                failed_orders.append(f"{order.ts_code}(error)")

        if failed_orders:
            logger.warning(f"Failed orders: {failed_orders}")

        logger.info(f"Batch execution completed: {len(trades)}/{len(orders)} orders filled")
        return trades

    # ========== Rebalance Methods ==========

    def rebalance(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        date: datetime,
        min_weight_diff: float = 0.01,
        max_single_order_value: Optional[float] = None
    ) -> List[Trade]:
        """
        调仓至目标权重

        Args:
            target_weights: 目标权重 {ts_code: weight}
            current_prices: 当前价格 {ts_code: price}
            date: 交易日期
            min_weight_diff: 最小权重差异（低于此值不调仓）
            max_single_order_value: 单笔订单最大金额限制

        Returns:
            成交记录列表
        """
        trades: List[Trade] = []
        total_value = self.total_value

        if total_value <= 0:
            logger.warning("Cannot rebalance: portfolio value is zero")
            return trades

        current_weights = self.get_weights()
        all_stocks = set(target_weights.keys()) | set(current_weights.keys())

        logger.info(f"Rebalancing {len(all_stocks)} stocks on {date.strftime('%Y-%m-%d')}")

        # Sort: sell first, then buy
        sells: List[Tuple[str, float, float]] = []  # (ts_code, current_w, target_w)
        buys: List[Tuple[str, float, float]] = []   # (ts_code, current_w, target_w)

        for ts_code in all_stocks:
            target_w = target_weights.get(ts_code, 0.0)
            current_w = current_weights.get(ts_code, 0.0)

            if abs(target_w - current_w) < min_weight_diff:
                continue

            if ts_code not in current_prices:
                logger.warning(f"No price for {ts_code}, skipping")
                continue

            if target_w < current_w:
                sells.append((ts_code, current_w, target_w))
            else:
                buys.append((ts_code, current_w, target_w))

        # Execute sells first to free up cash
        for ts_code, current_w, target_w in sells:
            trade = self._rebalance_sell(ts_code, current_w, target_w, total_value,
                                         current_prices, date, max_single_order_value)
            if trade:
                trades.append(trade)

        # Execute buys
        for ts_code, current_w, target_w in buys:
            trade = self._rebalance_buy(ts_code, current_w, target_w, total_value,
                                        current_prices, date, max_single_order_value)
            if trade:
                trades.append(trade)

        logger.info(f"Rebalancing completed: {len(trades)} trades executed")
        return trades

    def _rebalance_sell(
        self,
        ts_code: str,
        current_w: float,
        target_w: float,
        total_value: float,
        current_prices: Dict[str, float],
        date: datetime,
        max_single_order_value: Optional[float]
    ) -> Optional[Trade]:
        """执行调仓卖出"""
        target_value = total_value * target_w
        current_value = total_value * current_w
        sell_value = current_value - target_value

        pos = self.positions.get(ts_code)
        if not pos or pos.quantity == 0:
            return None

        price = current_prices[ts_code]
        sell_quantity = int(sell_value / price / 100) * 100
        sell_quantity = min(sell_quantity, pos.quantity)

        # Apply max order limit
        if max_single_order_value:
            max_qty = int(max_single_order_value / price / 100) * 100
            sell_quantity = min(sell_quantity, max_qty)

        if sell_quantity <= 0:
            return None

        order = Order(
            ts_code=ts_code,
            side=OrderSide.SELL,
            quantity=sell_quantity,
            order_date=date
        )
        return self.execute_order(order, price, date)

    def _rebalance_buy(
        self,
        ts_code: str,
        current_w: float,
        target_w: float,
        total_value: float,
        current_prices: Dict[str, float],
        date: datetime,
        max_single_order_value: Optional[float]
    ) -> Optional[Trade]:
        """执行调仓买入"""
        target_value = total_value * target_w
        current_value = total_value * current_w
        buy_value = target_value - current_value

        # Reserve some cash buffer
        buy_value = min(buy_value, self.get_available_cash() * 0.98)

        if buy_value <= 0:
            return None

        price = current_prices[ts_code]

        # Apply max order limit
        if max_single_order_value:
            buy_value = min(buy_value, max_single_order_value)

        quantity = int(buy_value / price / 100) * 100

        if quantity <= 0:
            return None

        order = Order(
            ts_code=ts_code,
            side=OrderSide.BUY,
            quantity=quantity,
            order_date=date
        )
        return self.execute_order(order, price, date)

    def close_position(self, ts_code: str, price: float, date: datetime) -> Optional[Trade]:
        """
        清仓指定持仓

        Args:
            ts_code: 股票代码
            price: 当前价格
            date: 交易日期

        Returns:
            成交记录，如果没有持仓则返回None
        """
        if ts_code not in self.positions:
            return None

        pos = self.positions[ts_code]
        if pos.quantity == 0:
            return None

        order = Order(
            ts_code=ts_code,
            side=OrderSide.SELL,
            quantity=pos.quantity,
            order_date=date
        )

        trade = self.execute_order(order, price, date)
        if trade:
            logger.info(f"Position closed: {ts_code}, realized_pnl={pos.realized_pnl:.2f}")

        return trade

    def close_all_positions(self, prices: Dict[str, float], date: datetime) -> List[Trade]:
        """
        清仓所有持仓

        Args:
            prices: 价格字典
            date: 交易日期

        Returns:
            成交记录列表
        """
        trades: List[Trade] = []

        for ts_code in list(self.positions.keys()):
            if ts_code in prices:
                trade = self.close_position(ts_code, prices[ts_code], date)
                if trade:
                    trades.append(trade)

        logger.info(f"Closed all positions: {len(trades)} trades executed")
        return trades

    # ========== Update Methods ==========

    def update_market_value(self, current_prices: Dict[str, float]) -> None:
        """
        更新持仓市值

        Args:
            current_prices: 当前价格字典 {ts_code: price}
        """
        for ts_code, pos in self.positions.items():
            if ts_code in current_prices:
                try:
                    pos.update_price(current_prices[ts_code])
                except Exception as e:
                    logger.warning(f"Failed to update price for {ts_code}: {e}")

        self._update_peak_and_drawdown()

    def _update_peak_and_drawdown(self) -> None:
        """更新峰值和回撤"""
        current_value = self.total_value
        if current_value > self._peak_value:
            self._peak_value = current_value

        if self._peak_value > 0:
            self._current_drawdown = (self._peak_value - current_value) / self._peak_value

    def record_state(self, date: datetime) -> PortfolioState:
        """
        记录账户状态

        Args:
            date: 记录日期

        Returns:
            账户状态对象
        """
        state = PortfolioState(
            date=date,
            cash=self.cash,
            positions_value=self.get_position_value(),
            total_value=self.total_value,
            positions={k: v.copy() for k, v in self.positions.items()}
        )
        self.daily_values.append(state)
        return state

    def get_state_df(self) -> pd.DataFrame:
        """
        获取账户历史状态DataFrame

        Returns:
            历史状态DataFrame
        """
        if not self.daily_values:
            return pd.DataFrame()

        records = [state.to_dict() for state in self.daily_values]
        df = pd.DataFrame(records)
        if 'date' in df.columns:
            df = df.set_index('date')
        return df

    def get_trades_df(self) -> pd.DataFrame:
        """
        获取交易记录DataFrame

        Returns:
            交易记录DataFrame
        """
        if not self.trades:
            return pd.DataFrame()

        records = []
        for t in self.trades:
            records.append({
                'date': t.trade_date,
                'ts_code': t.ts_code,
                'side': t.side.value,
                'quantity': t.quantity,
                'price': t.price,
                'amount': t.amount,
                'commission': t.commission,
                'slip_cost': t.slip_cost,
                'total_cost': t.total_cost
            })

        return pd.DataFrame(records)

    def get_nav_history(self) -> List[Tuple[datetime, float]]:
        """获取净值历史"""
        return [(state.date, state.total_value / self.initial_cash)
                for state in self.daily_values]

    def summary(self) -> Dict[str, Any]:
        """
        获取组合摘要

        Returns:
            组合摘要字典
        """
        return {
            'name': self.name,
            'initial_cash': self.initial_cash,
            'current_cash': self.cash,
            'total_value': self.total_value,
            'total_return': self.total_return,
            'nav': self.nav,
            'drawdown': self._current_drawdown,
            'position_count': len(self.positions),
            'position_value': self.get_position_value(),
            'available_cash': self.get_available_cash(),
            'trade_count': len(self.trades),
            'peak_value': self._peak_value
        }

    def reset(self) -> None:
        """重置账户"""
        logger.info(f"Resetting portfolio '{self.name}'")
        self.cash = self.initial_cash
        self.positions.clear()
        self.trades.clear()
        self.daily_values.clear()
        self._frozen_cash = 0.0
        self._peak_value = self.initial_cash
        self._current_drawdown = 0.0


# Import handling for RiskManager type hint
if sys.version_info >= (3, 7):
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from projects.quant_trading.backtest.risk_manager import RiskManager
