"""
Backtrader佣金方案集成

将精细化的成本模型和滑点模型集成到Backtrader的佣金体系中。

主要组件：
- EnhancedChinaCommInfo: 增强版中国市场佣金方案
- CostModelCommInfo: 通用成本模型佣金方案
- SlippageCommissionInfo: 带滑点的佣金方案
"""

from typing import Optional, Dict, Any

import backtrader as bt

from core.logger import get_logger
from projects.quant_trading.backtest.transaction_cost import (
    StockCostModel,
    CostBreakdown,
    TradeDirection,
)
from projects.quant_trading.backtest.slippage import PercentageSlippage

logger = get_logger(__name__)


class EnhancedChinaCommInfo(bt.CommInfoBase):
    """
    增强版中国市场佣金方案

    集成精细化的成本模型（佣金、印花税、过户费等）和滑点模型。

    Example:
        >>> from projects.quant_trading.backtest.transaction_cost import StockCostModel
        >>> from projects.quant_trading.backtest.slippage import PercentageSlippage
        >>>
        >>> cost_model = StockCostModel(commission_rate=0.00025)
        >>> slippage_model = PercentageSlippage(0.0005)
        >>>
        >>> comminfo = EnhancedChinaCommInfo(
        ...     cost_model=cost_model,
        ...     slippage_model=slippage_model
        ... )
        >>> cerebro.broker.addcommissioninfo(comminfo, name='stock')
    """

    params = (
        ("cost_model", None),  # CostModel实例
        ("slippage_model", None),  # SlippageModel实例
        ("commission", 0.00025),  # 默认佣金率（Backtrader兼容）
        ("stamp_duty", 0.001),  # 印花税（仅卖出）
        ("transfer_fee", 0.00001),  # 过户费
        ("min_commission", 5.0),  # 最低佣金
    )

    def __init__(self):
        super().__init__()

        # 如果没有提供成本模型，使用默认的A股成本模型
        if self.p.cost_model is None:
            self.p.cost_model = StockCostModel(
                commission_rate=self.p.commission,
                min_commission=self.p.min_commission,
                stamp_duty_rate=self.p.stamp_duty,
                transfer_fee_rate=self.p.transfer_fee,
            )
            logger.debug("[EnhancedChinaCommInfo] 使用默认A股成本模型")

    def _getcommission(self, size: float, price: float, pseudoexec: bool = False) -> float:
        """
        计算佣金（Backtrader回调）

        Args:
            size: 交易数量（正为买入，负为卖出）
            price: 成交价格
            pseudoexec: 是否为预执行

        Returns:
            佣金金额
        """
        if self.p.cost_model:
            direction = TradeDirection.BUY if size > 0 else TradeDirection.SELL
            breakdown = self.p.cost_model.calculate_cost(
                price=price, size=abs(size), direction=direction
            )
            return breakdown.total

        # 回退到基础计算
        value = abs(size) * price
        commission = max(value * self.p.commission, self.p.min_commission)

        # 印花税（仅卖出）
        if size < 0:
            commission += value * self.p.stamp_duty

        # 过户费
        commission += value * self.p.transfer_fee

        return commission

    def get_slippage_price(
        self,
        direction: str,
        price: float,
        size: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        获取包含滑点的价格

        Args:
            direction: 交易方向，'BUY'或'SELL'
            price: 意向价格
            size: 交易数量
            market_data: 市场数据

        Returns:
            实际成交价格
        """
        if self.p.slippage_model:
            return self.p.slippage_model.get_execution_price(
                direction=direction, intended_price=price, volume=abs(size), market_data=market_data
            )
        return price

    def get_cost_breakdown(self, size: float, price: float) -> CostBreakdown:
        """
        获取成本明细

        Args:
            size: 交易数量
            price: 成交价格

        Returns:
            CostBreakdown
        """
        direction = TradeDirection.BUY if size > 0 else TradeDirection.SELL

        if self.p.cost_model:
            return self.p.cost_model.calculate_cost(
                price=price, size=abs(size), direction=direction
            )

        # 基础成本明细
        value = abs(size) * price
        commission = max(value * self.p.commission, self.p.min_commission)
        tax = value * self.p.stamp_duty if size < 0 else 0.0
        transfer = value * self.p.transfer_fee

        return CostBreakdown(commission=commission, tax=tax, transfer_fee=transfer)


class CostModelCommInfo(bt.CommInfoBase):
    """
    通用成本模型佣金方案

    支持任意CostModel的Backtrader佣金方案。
    """

    params = (("cost_model", None),)

    def _getcommission(self, size: float, price: float, pseudoexec: bool = False) -> float:
        """计算佣金"""
        if self.p.cost_model is None:
            return 0.0

        direction = TradeDirection.BUY if size > 0 else TradeDirection.SELL
        breakdown = self.p.cost_model.calculate_cost(
            price=price, size=abs(size), direction=direction
        )
        return breakdown.total


class SlippageCommissionInfo(bt.CommInfoBase):
    """
    带滑点调整的佣金方案

    在标准佣金基础上增加滑点模型。
    """

    params = (
        ("commission", 0.00025),
        ("slippage_model", None),
        ("slippage_pct", 0.0005),  # 默认百分比滑点
    )

    def __init__(self):
        super().__init__()

        # 如果没有提供滑点模型，使用默认百分比滑点
        if self.p.slippage_model is None:
            self.p.slippage_model = PercentageSlippage(self.p.slippage_pct)

    def _getcommission(self, size: float, price: float, pseudoexec: bool = False) -> float:
        """计算佣金（不含滑点，滑点体现在价格上）"""
        value = abs(size) * price
        return value * self.p.commission

    def getexecutionprice(self, size: float, price: float) -> float:
        """
        获取执行价格（含滑点）

        Backtrader会在订单执行时调用此方法。
        """
        direction = "BUY" if size > 0 else "SELL"
        return self.p.slippage_model.get_execution_price(direction, price, abs(size))


class MultiAssetCommInfo:
    """
    多资产佣金方案管理器

    为不同资产类型配置不同的佣金方案。
    """

    def __init__(self):
        self._comm_infos: Dict[str, bt.CommInfoBase] = {}

    def register(self, name: str, comminfo: bt.CommInfoBase):
        """
        注册佣金方案

        Args:
            name: 资产类型名称
            comminfo: 佣金方案实例
        """
        self._comm_infos[name] = comminfo
        logger.info(f"[MultiAssetCommInfo] 注册佣金方案: {name}")

    def get(self, name: str) -> Optional[bt.CommInfoBase]:
        """获取佣金方案"""
        return self._comm_infos.get(name)

    def apply_to_cerebro(self, cerebro: bt.Cerebro):
        """
        将所有佣金方案应用到Cerebro

        Args:
            cerebro: Backtrader Cerebro实例
        """
        for name, comminfo in self._comm_infos.items():
            cerebro.broker.addcommissioninfo(comminfo, name=name)
            logger.debug(f"[MultiAssetCommInfo] 应用佣金方案到Cerebro: {name}")

    @classmethod
    def create_default_stock_config(cls) -> "MultiAssetCommInfo":
        """
        创建默认A股配置

        Returns:
            MultiAssetCommInfo
        """
        manager = cls()

        # 股票（沪市）
        stock_sh = EnhancedChinaCommInfo(cost_model=StockCostModel(is_shanghai=True))
        manager.register("stock_sh", stock_sh)

        # 股票（深市）
        stock_sz = EnhancedChinaCommInfo(cost_model=StockCostModel(is_shanghai=False))
        manager.register("stock_sz", stock_sz)

        # ETF
        from projects.quant_trading.backtest.transaction_cost import ETFCostModel

        etf = EnhancedChinaCommInfo(cost_model=ETFCostModel())
        manager.register("etf", etf)

        return manager


# 便捷函数
def create_stock_commission(
    commission_rate: float = 0.00025, slippage_pct: float = 0.0005, is_shanghai: bool = True
) -> EnhancedChinaCommInfo:
    """
    创建股票佣金方案

    Args:
        commission_rate: 佣金率
        slippage_pct: 滑点比例
        is_shanghai: 是否为沪市

    Returns:
        EnhancedChinaCommInfo
    """
    cost_model = StockCostModel(commission_rate=commission_rate, is_shanghai=is_shanghai)
    slippage_model = PercentageSlippage(slippage_pct)

    return EnhancedChinaCommInfo(cost_model=cost_model, slippage_model=slippage_model)


def create_etf_commission(
    commission_rate: float = 0.00025, slippage_pct: float = 0.0003
) -> EnhancedChinaCommInfo:
    """
    创建ETF佣金方案

    Args:
        commission_rate: 佣金率
        slippage_pct: 滑点比例（ETF通常滑点更小）

    Returns:
        EnhancedChinaCommInfo
    """
    from projects.quant_trading.backtest.transaction_cost import ETFCostModel

    cost_model = ETFCostModel(commission_rate=commission_rate)
    slippage_model = PercentageSlippage(slippage_pct)

    return EnhancedChinaCommInfo(cost_model=cost_model, slippage_model=slippage_model)


def setup_china_stock_commission(
    cerebro: bt.Cerebro,
    initial_cash: float = 1_000_000.0,
    commission_rate: float = 0.00025,
    slippage_pct: float = 0.0005,
):
    """
    为Cerebro设置A股标准佣金方案

    Args:
        cerebro: Backtrader Cerebro实例
        initial_cash: 初始资金
        commission_rate: 佣金率
        slippage_pct: 滑点比例
    """
    # 设置初始资金
    cerebro.broker.setcash(initial_cash)

    # 创建并添加佣金方案
    comminfo = create_stock_commission(commission_rate, slippage_pct)
    cerebro.broker.addcommissioninfo(comminfo)

    # 设置默认滑点
    cerebro.broker.set_slippage_perc(slippage_pct)

    logger.info(
        f"[setup_china_stock_commission] "
        f"初始资金={initial_cash:,.0f}, "
        f"佣金率={commission_rate*10000:.2f}bp, "
        f"滑点={slippage_pct*10000:.2f}bp"
    )


if __name__ == "__main__":
    # 测试代码
    print("=== Backtrader佣金方案测试 ===\n")

    # 创建佣金方案
    comminfo = create_stock_commission(
        commission_rate=0.00025, slippage_pct=0.0005, is_shanghai=True
    )

    # 测试买入
    size = 1000
    price = 100.0

    commission = comminfo._getcommission(size, price)
    breakdown = comminfo.get_cost_breakdown(size, price)

    print(f"买入 {size}股 @ {price}元")
    print(f"  佣金: {breakdown.commission:.2f}")
    print(f"  过户费: {breakdown.transfer_fee:.2f}")
    print(f"  总成本: {breakdown.total:.2f} ({breakdown.total_pct*100:.3f}%)")
    print()

    # 测试卖出
    commission = comminfo._getcommission(-size, 110.0)
    breakdown = comminfo.get_cost_breakdown(-size, 110.0)

    print(f"卖出 {size}股 @ 110元")
    print(f"  佣金: {breakdown.commission:.2f}")
    print(f"  印花税: {breakdown.tax:.2f}")
    print(f"  过户费: {breakdown.transfer_fee:.2f}")
    print(f"  总成本: {breakdown.total:.2f} ({breakdown.total_pct*100:.3f}%)")
    print()

    # 测试滑点
    exec_price = comminfo.get_slippage_price("BUY", 100.0, 1000)
    print(f"买入滑点后价格: {exec_price:.4f}")

    exec_price = comminfo.get_slippage_price("SELL", 110.0, 1000)
    print(f"卖出滑点后价格: {exec_price:.4f}")

    print("\n测试完成!")
