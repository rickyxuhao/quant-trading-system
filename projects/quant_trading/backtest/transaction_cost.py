"""
交易成本模型模块

实现覆盖多资产类别的精细化成本模型：
- A股股票成本（佣金、印花税、过户费）
- ETF成本（佣金）
- 基金成本（申购费、赎回费分层）
- 期货成本（手续费、保证金）

参考：
- A股交易成本: https://www.chinaclear.cn/
- 期货手续费: 各交易所最新标准
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum

from core.logger import get_logger

logger = get_logger(__name__)


class AssetType(Enum):
    """资产类型枚举"""

    STOCK = "stock"  # A股股票
    ETF = "etf"  # ETF
    LOF = "lof"  # LOF基金
    FUND = "fund"  # 场外基金
    FUTURES = "futures"  # 期货
    OPTIONS = "options"  # 期权
    BOND = "bond"  # 债券
    CRYPTOCURRENCY = "crypto"  # 加密货币


class TradeDirection(Enum):
    """交易方向枚举"""

    BUY = "buy"
    SELL = "sell"
    OPEN_LONG = "open_long"
    CLOSE_LONG = "close_long"
    OPEN_SHORT = "open_short"
    CLOSE_SHORT = "close_short"


@dataclass
class CostBreakdown:
    """
    成本明细

    Attributes:
        commission: 佣金
        tax: 税费（印花税等）
        transfer_fee: 过户费
        exchange_fee: 交易所费用
        other_fees: 其他费用
        total: 总费用
        total_pct: 总费用占交易金额比例
        metadata: 额外元数据
    """

    commission: float = 0.0
    tax: float = 0.0
    transfer_fee: float = 0.0
    exchange_fee: float = 0.0
    other_fees: float = 0.0
    total: float = 0.0
    total_pct: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """计算总费用"""
        self.total = (
            self.commission + self.tax + self.transfer_fee + self.exchange_fee + self.other_fees
        )
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "commission": self.commission,
            "tax": self.tax,
            "transfer_fee": self.transfer_fee,
            "exchange_fee": self.exchange_fee,
            "other_fees": self.other_fees,
            "total": self.total,
            "total_pct": self.total_pct,
            "metadata": self.metadata,
        }


class CostModel(ABC):
    """交易成本模型基类"""

    def __init__(self, asset_type: AssetType, name: str):
        self.asset_type = asset_type
        self.name = name

    @abstractmethod
    def calculate_cost(
        self, price: float, size: float, direction: TradeDirection, **kwargs
    ) -> CostBreakdown:
        """
        计算交易成本

        Args:
            price: 成交价格
            size: 成交数量
            direction: 交易方向
            **kwargs: 额外参数（如持仓天数等）

        Returns:
            CostBreakdown
        """

    def calculate_total_cost(
        self, price: float, size: float, direction: TradeDirection, **kwargs
    ) -> float:
        """
        计算总交易成本

        Returns:
            总费用
        """
        breakdown = self.calculate_cost(price, size, direction, **kwargs)
        return breakdown.total

    def calculate_cost_percentage(
        self, price: float, size: float, direction: TradeDirection, **kwargs
    ) -> float:
        """
        计算成本占交易金额比例

        Returns:
            成本比例
        """
        amount = price * abs(size)
        if amount == 0:
            return 0.0

        total_cost = self.calculate_total_cost(price, size, direction, **kwargs)
        return total_cost / amount


class StockCostModel(CostModel):
    """
    A股股票成本模型

    包含：
    - 佣金：双向，0.025%，最低5元
    - 印花税：卖出时0.1%
    - 过户费：双向，0.001‰（沪市），深市免收
    """

    def __init__(
        self,
        commission_rate: float = 0.00025,  # 佣金率0.025%
        min_commission: float = 5.0,  # 最低佣金5元
        stamp_duty_rate: float = 0.001,  # 印花税0.1%（仅卖出）
        transfer_fee_rate: float = 0.00001,  # 过户费0.001‰（双向，沪市）
        is_shanghai: bool = True,  # 是否为沪市股票
    ):
        super().__init__(AssetType.STOCK, "A股股票")
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_duty_rate = stamp_duty_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.is_shanghai = is_shanghai

    def calculate_cost(
        self, price: float, size: float, direction: TradeDirection, **kwargs
    ) -> CostBreakdown:
        """计算股票交易成本"""
        amount = price * abs(size)

        # 佣金（双向，有最低）
        commission = max(amount * self.commission_rate, self.min_commission)

        # 过户费（双向，仅沪市）
        transfer_fee = 0.0
        if self.is_shanghai:
            transfer_fee = amount * self.transfer_fee_rate

        # 印花税（仅卖出）
        tax = 0.0
        if direction in [TradeDirection.SELL]:
            tax = amount * self.stamp_duty_rate

        breakdown = CostBreakdown(commission=commission, tax=tax, transfer_fee=transfer_fee)

        # 计算总成本占比
        if amount > 0:
            breakdown.total_pct = breakdown.total / amount

        return breakdown


class ETFCostModel(CostModel):
    """
    ETF成本模型

    ETF交易特点：
    - 佣金：双向，通常0.025%
    - 无印花税
    - 无过户费
    """

    def __init__(
        self,
        commission_rate: float = 0.00025,  # 佣金率0.025%
        min_commission: float = 5.0,  # 最低佣金5元
    ):
        super().__init__(AssetType.ETF, "ETF")
        self.commission_rate = commission_rate
        self.min_commission = min_commission

    def calculate_cost(
        self, price: float, size: float, direction: TradeDirection, **kwargs
    ) -> CostBreakdown:
        """计算ETF交易成本"""
        amount = price * abs(size)

        # 仅佣金
        commission = max(amount * self.commission_rate, self.min_commission)

        breakdown = CostBreakdown(commission=commission)

        if amount > 0:
            breakdown.total_pct = breakdown.total / amount

        return breakdown


class FundCostModel(CostModel):
    """
    场外基金成本模型

    包含：
    - 申购费：通常在0.1%-1.5%之间，打一折后0.01%-0.15%
    - 赎回费：按持有天数分层，通常7天内1.5%，超过2年免费
    """

    # 默认赎回费率分层 (持有天数, 费率)
    DEFAULT_REDEMPTION_TIERS: List[Tuple[int, float]] = [
        (7, 0.015),  # <7天: 1.5%
        (30, 0.0075),  # <30天: 0.75%
        (90, 0.005),  # <90天: 0.5%
        (180, 0.0025),  # <180天: 0.25%
        (365, 0.001),  # <1年: 0.1%
        (730, 0.0005),  # <2年: 0.05%
        (float("inf"), 0.0),  # >2年: 0
    ]

    def __init__(
        self,
        subscribe_fee_rate: float = 0.0015,  # 申购费率1.5%（打一折前）
        fee_discount: float = 0.1,  # 费率折扣（打一折=0.1）
        redemption_tiers: Optional[List[Tuple[int, float]]] = None,
    ):
        super().__init__(AssetType.FUND, "场外基金")
        self.subscribe_fee_rate = subscribe_fee_rate
        self.fee_discount = fee_discount
        self.redemption_tiers = redemption_tiers or self.DEFAULT_REDEMPTION_TIERS

    def get_redemption_fee_rate(self, holding_days: int) -> float:
        """
        获取赎回费率

        Args:
            holding_days: 持有天数

        Returns:
            赎回费率
        """
        for days, fee_rate in self.redemption_tiers:
            if holding_days < days:
                return fee_rate
        return 0.0

    def calculate_cost(
        self, price: float, size: float, direction: TradeDirection, holding_days: int = 0, **kwargs
    ) -> CostBreakdown:
        """
        计算基金交易成本

        Args:
            price: 净值
            size: 份额
            direction: 交易方向
            holding_days: 持有天数（用于计算赎回费）
        """
        amount = price * abs(size)

        if direction == TradeDirection.BUY:  # 申购
            # 申购费
            subscribe_fee = amount * self.subscribe_fee_rate * self.fee_discount
            breakdown = CostBreakdown(commission=subscribe_fee)
        else:  # 赎回
            # 赎回费
            redemption_rate = self.get_redemption_fee_rate(holding_days)
            redemption_fee = amount * redemption_rate
            breakdown = CostBreakdown(
                commission=redemption_fee,
                other_fees=0.0,
                metadata={"holding_days": holding_days, "redemption_rate": redemption_rate},
            )

        if amount > 0:
            breakdown.total_pct = breakdown.total / amount

        return breakdown

    def calculate_total_holding_cost(
        self, price_buy: float, price_sell: float, size: float, holding_days: int
    ) -> CostBreakdown:
        """
        计算完整持有周期的总成本

        Args:
            price_buy: 申购净值
            price_sell: 赎回净值
            size: 份额
            holding_days: 持有天数

        Returns:
            CostBreakdown
        """
        # 申购成本
        buy_cost = self.calculate_cost(price_buy, size, TradeDirection.BUY)

        # 赎回成本
        sell_cost = self.calculate_cost(price_sell, size, TradeDirection.SELL, holding_days)

        return CostBreakdown(
            commission=buy_cost.commission + sell_cost.commission,
            other_fees=buy_cost.other_fees + sell_cost.other_fees,
            total=buy_cost.total + sell_cost.total,
        )


class FuturesCostModel(CostModel):
    """
    期货成本模型

    期货成本特点：
    - 手续费：按手数固定金额或按成交额比例
    - 无印花税
    - 需要保证金（不是成本，但影响资金占用）

    股指期货手续费参考（2024年标准）：
    - 沪深300(IF): 成交金额的0.23%%
    - 中证500(IC): 成交金额的0.23%%
    - 上证50(IH): 成交金额的0.23%%

    商品期货手续费通常为固定金额/手。
    """

    # 默认合约配置
    DEFAULT_CONTRACT_CONFIGS: Dict[str, Dict[str, Any]] = {
        "IF": {"type": "ratio", "value": 2.3e-5, "name": "沪深300股指", "multiplier": 300},
        "IC": {"type": "ratio", "value": 2.3e-5, "name": "中证500股指", "multiplier": 200},
        "IH": {"type": "ratio", "value": 2.3e-5, "name": "上证50股指", "multiplier": 300},
        "IM": {"type": "ratio", "value": 2.3e-5, "name": "中证1000股指", "multiplier": 200},
        "RB": {"type": "fixed", "value": 3.0, "name": "螺纹钢", "multiplier": 10},
        "CU": {"type": "fixed", "value": 15.0, "name": "铜", "multiplier": 5},
        "AU": {"type": "fixed", "value": 10.0, "name": "黄金", "multiplier": 1000},
        "AG": {"type": "ratio", "value": 5e-5, "name": "白银", "multiplier": 15},
        "CF": {"type": "fixed", "value": 4.3, "name": "棉花", "multiplier": 5},
    }

    def __init__(
        self,
        contract_code: str,
        contract_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        margin_rate: float = 0.12,
        close_today_factor: float = 2.0,  # 平今仓手续费倍数
    ):
        """
        初始化期货成本模型

        Args:
            contract_code: 合约代码（如'IF', 'RB'）
            contract_configs: 合约配置字典，None使用默认配置
            margin_rate: 保证金比例
            close_today_factor: 平今仓手续费倍数
        """
        super().__init__(AssetType.FUTURES, f"期货-{contract_code}")
        self.contract_code = contract_code
        self.contract_configs = contract_configs or self.DEFAULT_CONTRACT_CONFIGS
        self.margin_rate = margin_rate
        self.close_today_factor = close_today_factor

        self._config = self.contract_configs.get(
            contract_code, {"type": "ratio", "value": 2.3e-5, "name": "未知合约", "multiplier": 1}
        )

    def calculate_cost(
        self,
        price: float,
        size: float,
        direction: TradeDirection,
        is_close_today: bool = False,
        **kwargs,
    ) -> CostBreakdown:
        """
        计算期货交易成本

        Args:
            price: 成交价格
            size: 手数
            direction: 交易方向
            is_close_today: 是否为平今仓
        """
        multiplier = self._config.get("multiplier", 1)
        amount = price * abs(size) * multiplier

        # 计算手续费
        if self._config["type"] == "ratio":
            # 按比例收费
            fee = amount * self._config["value"]
        else:
            # 按固定金额收费
            fee = abs(size) * self._config["value"]

        # 平今仓调整
        if is_close_today and direction in [TradeDirection.CLOSE_LONG, TradeDirection.CLOSE_SHORT]:
            fee *= self.close_today_factor

        # 交易所费用（假设为手续费的10%）
        exchange_fee = fee * 0.1

        breakdown = CostBreakdown(commission=fee, exchange_fee=exchange_fee)

        # 计算保证金占用
        margin = amount * self.margin_rate
        breakdown.metadata = {
            "margin_required": margin,
            "notional_value": amount,
            "contract_multiplier": multiplier,
        }

        if amount > 0:
            breakdown.total_pct = breakdown.total / amount

        return breakdown

    def calculate_margin(self, price: float, size: float) -> float:
        """
        计算保证金

        Args:
            price: 价格
            size: 手数

        Returns:
            保证金金额
        """
        multiplier = self._config.get("multiplier", 1)
        notional_value = price * abs(size) * multiplier
        return notional_value * self.margin_rate


class OptionsCostModel(CostModel):
    """
    期权成本模型

    期权成本特点：
    - 权利金（买方支付，不是费用）
    - 手续费：固定金额/张
    - 行权费用（如有）
    """

    def __init__(
        self,
        commission_per_contract: float = 5.0,  # 每张手续费
        exercise_fee: float = 10.0,  # 行权费用
    ):
        super().__init__(AssetType.OPTIONS, "期权")
        self.commission_per_contract = commission_per_contract
        self.exercise_fee = exercise_fee

    def calculate_cost(
        self,
        price: float,
        size: float,
        direction: TradeDirection,
        is_exercise: bool = False,
        **kwargs,
    ) -> CostBreakdown:
        """计算期权交易成本"""
        contracts = abs(size)

        # 手续费
        commission = contracts * self.commission_per_contract

        # 行权费用
        exercise_fee = 0.0
        if is_exercise:
            exercise_fee = contracts * self.exercise_fee

        breakdown = CostBreakdown(commission=commission, other_fees=exercise_fee)

        # 权利金（不是费用，但记录）
        premium = price * contracts * 10000  # 假设每手10000份
        breakdown.metadata = {"premium": premium}

        return breakdown


class CryptocurrencyCostModel(CostModel):
    """
    加密货币成本模型

    加密货币交易特点：
    - 手续费：挂单/吃单不同费率
    - 无印花税
    - 提币费用（场外）
    """

    def __init__(
        self,
        maker_fee: float = 0.001,  # 挂单费率0.1%
        taker_fee: float = 0.0015,  # 吃单费率0.15%
        withdrawal_fee: float = 0.0,  # 提币费用
    ):
        super().__init__(AssetType.CRYPTOCURRENCY, "加密货币")
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.withdrawal_fee = withdrawal_fee

    def calculate_cost(
        self, price: float, size: float, direction: TradeDirection, is_maker: bool = True, **kwargs
    ) -> CostBreakdown:
        """
        计算加密货币交易成本

        Args:
            price: 成交价格
            size: 数量
            direction: 交易方向
            is_maker: 是否为挂单（maker）
        """
        amount = price * abs(size)

        # 选择费率
        fee_rate = self.maker_fee if is_maker else self.taker_fee

        commission = amount * fee_rate

        breakdown = CostBreakdown(commission=commission)

        if amount > 0:
            breakdown.total_pct = breakdown.total / amount

        breakdown.metadata = {"is_maker": is_maker, "fee_rate": fee_rate}

        return breakdown


class CompositeCostModel(CostModel):
    """
    复合成本模型

    根据不同资产类型自动选择对应的成本模型。
    """

    def __init__(
        self,
        models: Optional[Dict[AssetType, CostModel]] = None,
        default_model: Optional[CostModel] = None,
    ):
        super().__init__(AssetType.STOCK, "复合成本模型")
        self.models = models or {}
        self.default_model = default_model or StockCostModel()

    def register_model(self, asset_type: AssetType, model: CostModel):
        """注册资产类型的成本模型"""
        self.models[asset_type] = model

    def calculate_cost(
        self,
        price: float,
        size: float,
        direction: TradeDirection,
        asset_type: Optional[AssetType] = None,
        **kwargs,
    ) -> CostBreakdown:
        """
        计算交易成本

        Args:
            price: 成交价格
            size: 成交数量
            direction: 交易方向
            asset_type: 资产类型
            **kwargs: 额外参数
        """
        model = self.models.get(asset_type, self.default_model)
        return model.calculate_cost(price, size, direction, **kwargs)


# 便捷函数
def create_stock_cost_model(exchange: str = "sh") -> StockCostModel:
    """
    创建股票成本模型

    Args:
        exchange: 交易所，'sh'沪市，'sz'深市

    Returns:
        StockCostModel
    """
    is_shanghai = exchange.lower() in ["sh", "shanghai", "sse"]
    return StockCostModel(is_shanghai=is_shanghai)


def create_etf_cost_model() -> ETFCostModel:
    """创建ETF成本模型"""
    return ETFCostModel()


def create_fund_cost_model(fund_type: str = "hybrid") -> FundCostModel:
    """
    创建基金成本模型

    Args:
        fund_type: 基金类型，'stock'股票型, 'hybrid'混合型, 'bond'债券型

    Returns:
        FundCostModel
    """
    # 不同类型基金的申购费率
    subscribe_rates = {"stock": 0.015, "hybrid": 0.015, "bond": 0.008, "money": 0.0}
    rate = subscribe_rates.get(fund_type, 0.015)
    return FundCostModel(subscribe_fee_rate=rate)


def create_futures_cost_model(contract_code: str) -> FuturesCostModel:
    """
    创建期货成本模型

    Args:
        contract_code: 合约代码，如'IF', 'RB'

    Returns:
        FuturesCostModel
    """
    return FuturesCostModel(contract_code=contract_code)


if __name__ == "__main__":
    # 测试代码
    print("=== 交易成本模型测试 ===\n")

    # 1. 股票成本测试
    print("1. A股股票成本测试")
    stock_model = StockCostModel(is_shanghai=True)
    buy_cost = stock_model.calculate_cost(100.0, 1000, TradeDirection.BUY)
    sell_cost = stock_model.calculate_cost(110.0, 1000, TradeDirection.SELL)
    print(
        f"   买入10万元: 佣金={buy_cost.commission:.2f}, 过户费={buy_cost.transfer_fee:.2f}, "
        f"总计={buy_cost.total:.2f} ({buy_cost.total_pct*100:.3f}%)"
    )
    print(
        f"   卖出11万元: 佣金={sell_cost.commission:.2f}, 印花税={sell_cost.tax:.2f}, "
        f"总计={sell_cost.total:.2f} ({sell_cost.total_pct*100:.3f}%)"
    )
    print(f"   双向成本: {(buy_cost.total + sell_cost.total):.2f}\n")

    # 2. ETF成本测试
    print("2. ETF成本测试")
    etf_model = ETFCostModel()
    buy_cost = etf_model.calculate_cost(3.0, 10000, TradeDirection.BUY)
    sell_cost = etf_model.calculate_cost(3.2, 10000, TradeDirection.SELL)
    print(f"   买入3万元: 佣金={buy_cost.commission:.2f}")
    print(f"   卖出3.2万元: 佣金={sell_cost.commission:.2f}")
    print(f"   双向成本: {(buy_cost.total + sell_cost.total):.2f}\n")

    # 3. 基金成本测试
    print("3. 场外基金成本测试")
    fund_model = FundCostModel(subscribe_fee_rate=0.015, fee_discount=0.1)  # 打一折
    subscribe_cost = fund_model.calculate_cost(1.0, 10000, TradeDirection.BUY)
    redeem_cost = fund_model.calculate_cost(1.1, 10000, TradeDirection.SELL, holding_days=30)
    print(f"   申购1万元: 申购费={subscribe_cost.commission:.2f}")
    print(f"   赎回(持有30天): 赎回费={redeem_cost.commission:.2f}")

    # 持有7天内赎回（惩罚性费率）
    redeem_early = fund_model.calculate_cost(1.0, 10000, TradeDirection.SELL, holding_days=5)
    print(f"   赎回(持有5天): 赎回费={redeem_early.commission:.2f} (惩罚性费率)\n")

    # 4. 期货成本测试
    print("4. 股指期货成本测试")
    futures_model = FuturesCostModel("IF")
    open_cost = futures_model.calculate_cost(4000.0, 1, TradeDirection.OPEN_LONG)
    close_cost = futures_model.calculate_cost(4050.0, 1, TradeDirection.CLOSE_LONG)
    print(
        f"   开多1手IF(4000点): 手续费={open_cost.commission:.2f}, "
        f"保证金={open_cost.metadata['margin_required']:.0f}"
    )
    print(f"   平多1手IF(4050点): 手续费={close_cost.commission:.2f}")

    # 商品期货
    futures_rb = FuturesCostModel("RB")
    rb_cost = futures_rb.calculate_cost(4000.0, 1, TradeDirection.OPEN_LONG)
    print(
        f"   开多1手螺纹钢(4000元): 手续费={rb_cost.commission:.2f}, "
        f"保证金={rb_cost.metadata['margin_required']:.0f}\n"
    )

    print("测试完成!")
