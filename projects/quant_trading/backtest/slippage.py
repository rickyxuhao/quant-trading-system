"""
滑点模型模块

实现多种滑点估计方法：
- 固定滑点
- 百分比滑点
- 波动率相关滑点（基于ATR）
- 成交量冲击滑点

滑点是指下单价格与实际成交价格之间的差异，
是回测中重要的成本因素。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

import pandas as pd
import numpy as np

from core.logger import get_logger

logger = get_logger(__name__)


class SlippageModel(ABC):
    """滑点模型基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        获取执行价格（已包含滑点）

        Args:
            direction: 交易方向，'BUY'或'SELL'
            intended_price: 意向价格
            volume: 交易数量
            market_data: 市场数据字典

        Returns:
            实际成交价格
        """
        pass

    def calculate_slippage(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        计算滑点金额

        Returns:
            滑点金额（正数）
        """
        execution_price = self.get_execution_price(
            direction, intended_price, volume, market_data
        )
        return abs(execution_price - intended_price)

    def calculate_slippage_pct(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        计算滑点比例

        Returns:
            滑点比例
        """
        if intended_price == 0:
            return 0.0

        slippage = self.calculate_slippage(direction, intended_price, volume, market_data)
        return slippage / intended_price


class FixedSlippage(SlippageModel):
    """
    固定金额滑点

    最简单模型，固定金额滑点。
    """

    def __init__(self, fixed_amount: float = 0.01):
        """
        初始化固定滑点模型

        Args:
            fixed_amount: 固定滑点金额（如0.01元）
        """
        super().__init__("fixed")
        self.fixed_amount = fixed_amount

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        if direction.upper() == 'BUY':
            return intended_price + self.fixed_amount
        else:
            return intended_price - self.fixed_amount


class PercentageSlippage(SlippageModel):
    """
    百分比滑点

    按价格百分比计算滑点。
    """

    def __init__(self, slippage_pct: float = 0.0005):  # 默认0.05%
        """
        初始化百分比滑点模型

        Args:
            slippage_pct: 滑点百分比（如0.0005表示0.05%）
        """
        super().__init__("percentage")
        self.slippage_pct = slippage_pct

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        slippage = intended_price * self.slippage_pct

        if direction.upper() == 'BUY':
            return intended_price + slippage
        else:
            return intended_price - slippage


class VolatilitySlippage(SlippageModel):
    """
    基于ATR的波动率滑点

    根据市场波动率动态调整滑点估计。
    高波动时期滑点更大，低波动时期滑点更小。
    """

    def __init__(
        self,
        atr_ratio: float = 0.1,
        atr_period: int = 14,
        min_slippage_pct: float = 0.0001,
        max_slippage_pct: float = 0.01
    ):
        """
        初始化波动率滑点模型

        Args:
            atr_ratio: ATR乘数（如0.1表示10%的ATR）
            atr_period: ATR计算周期
            min_slippage_pct: 最小滑点比例
            max_slippage_pct: 最大滑点比例
        """
        super().__init__("volatility")
        self.atr_ratio = atr_ratio
        self.atr_period = atr_period
        self.min_slippage_pct = min_slippage_pct
        self.max_slippage_pct = max_slippage_pct

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        market_data = market_data or {}

        # 获取ATR，如果没有则使用默认值
        atr = market_data.get('atr')
        if atr is None or atr <= 0:
            # 尝试从历史数据计算
            hist_data = market_data.get('historical_data')
            if hist_data is not None:
                atr = self._calculate_atr(hist_data)

        if atr is None or atr <= 0:
            # 使用默认波动率（1%）
            atr = intended_price * 0.01

        # 计算滑点
        slippage = atr * self.atr_ratio

        # 转换为百分比并限制范围
        slippage_pct = slippage / intended_price
        slippage_pct = max(self.min_slippage_pct, min(slippage_pct, self.max_slippage_pct))

        slippage = intended_price * slippage_pct

        if direction.upper() == 'BUY':
            return intended_price + slippage
        else:
            return intended_price - slippage

    def _calculate_atr(self, data: pd.DataFrame, period: Optional[int] = None) -> float:
        """
        计算ATR

        Args:
            data: 包含high, low, close的DataFrame
            period: ATR周期，None使用默认值

        Returns:
            ATR值
        """
        period = period or self.atr_period

        if len(data) < period:
            return 0.0

        try:
            high = data['high']
            low = data['low']
            close = data['close']

            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]

            return atr if not pd.isna(atr) else 0.0
        except Exception as e:
            logger.warning(f"ATR计算失败: {e}")
            return 0.0


class VolumeImpactSlippage(SlippageModel):
    """
    基于成交量冲击的滑点模型

    根据订单量相对于市场成交量的比例估计滑点。
    成交量越大，对价格的冲击越大，滑点越大。

    参考：Almgren-Chriss市场冲击模型简化版
    """

    def __init__(
        self,
        volume_threshold: float = 0.01,      # 日成交量的1%
        base_slippage_pct: float = 0.0005,   # 基础滑点0.05%
        impact_exponent: float = 0.5,        # 冲击弹性系数
        min_slippage_pct: float = 0.0001,
        max_slippage_pct: float = 0.02
    ):
        """
        初始化成交量冲击滑点模型

        Args:
            volume_threshold: 成交量阈值（占总成交量的比例）
            base_slippage_pct: 基础滑点比例
            impact_exponent: 冲击弹性系数（0.5为平方根模型）
            min_slippage_pct: 最小滑点比例
            max_slippage_pct: 最大滑点比例
        """
        super().__init__("volume_impact")
        self.volume_threshold = volume_threshold
        self.base_slippage_pct = base_slippage_pct
        self.impact_exponent = impact_exponent
        self.min_slippage_pct = min_slippage_pct
        self.max_slippage_pct = max_slippage_pct

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        market_data = market_data or {}

        # 获取市场成交量
        daily_volume = market_data.get('daily_volume', 0)
        if daily_volume <= 0:
            # 如果没有市场成交量数据，使用基础滑点
            slippage_pct = self.base_slippage_pct
        else:
            # 计算成交量占比
            volume_ratio = volume / daily_volume if daily_volume > 0 else 0

            if volume_ratio <= self.volume_threshold:
                # 小单，使用基础滑点
                slippage_pct = self.base_slippage_pct
            else:
                # 大单，计算冲击成本
                impact_multiplier = (
                    volume_ratio / self.volume_threshold
                ) ** self.impact_exponent
                slippage_pct = self.base_slippage_pct * impact_multiplier

        # 限制滑点范围
        slippage_pct = max(
            self.min_slippage_pct,
            min(slippage_pct, self.max_slippage_pct)
        )

        slippage = intended_price * slippage_pct

        if direction.upper() == 'BUY':
            return intended_price + slippage
        else:
            return intended_price - slippage

    def estimate_market_impact(
        self,
        volume: float,
        daily_volume: float,
        volatility: float = 0.02
    ) -> float:
        """
        估计市场冲击成本

        Args:
            volume: 订单量
            daily_volume: 日成交量
            volatility: 日波动率

        Returns:
            估计的冲击成本比例
        """
        if daily_volume <= 0:
            return self.base_slippage_pct

        volume_ratio = volume / daily_volume

        # 简化的Almgren-Chriss模型
        # 冲击 = 波动率 * (订单量/日成交量)^弹性
        impact = volatility * (volume_ratio ** self.impact_exponent)

        # 加上基础滑点
        total_slippage = self.base_slippage_pct + impact

        return max(
            self.min_slippage_pct,
            min(total_slippage, self.max_slippage_pct)
        )


class SpreadBasedSlippage(SlippageModel):
    """
    基于买卖价差的滑点模型

    根据实时买卖价差计算滑点。
    """

    def __init__(
        self,
        spread_pct: float = 0.001,           # 默认0.1%价差
        slippage_ratio: float = 0.5,          # 滑点占价差的比例（0.5表示吃一半价差）
        min_slippage_pct: float = 0.0001
    ):
        """
        初始化价差滑点模型

        Args:
            spread_pct: 买卖价差比例
            slippage_ratio: 滑点占价差的比例
            min_slippage_pct: 最小滑点比例
        """
        super().__init__("spread_based")
        self.spread_pct = spread_pct
        self.slippage_ratio = slippage_ratio
        self.min_slippage_pct = min_slippage_pct

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        market_data = market_data or {}

        # 尝试获取实时价差
        spread_pct = market_data.get('spread_pct', self.spread_pct)
        bid = market_data.get('bid')
        ask = market_data.get('ask')

        if bid is not None and ask is not None:
            # 使用实时买卖价
            if direction.upper() == 'BUY':
                return ask
            else:
                return bid

        # 使用估计的价差
        slippage_pct = max(spread_pct * self.slippage_ratio, self.min_slippage_pct)
        slippage = intended_price * slippage_pct

        if direction.upper() == 'BUY':
            return intended_price + slippage
        else:
            return intended_price - slippage


class TimeBasedSlippage(SlippageModel):
    """
    基于时间维度的滑点模型

    考虑交易时间对滑点的影响：
    - 开盘/收盘时段滑点较大
    - 午间休市前后滑点较大
    - 连续交易时段滑点较小
    """

    # 时段乘数配置
    SESSION_MULTIPLIERS = {
        'open': 2.0,        # 开盘（9:30-10:00）
        'morning': 1.0,     # 上午正常（10:00-11:30）
        'noon': 1.5,        # 午间（11:30-13:00）
        'afternoon': 1.0,   # 下午正常（13:00-14:30）
        'close': 2.0,       # 收盘前（14:30-15:00）
    }

    def __init__(
        self,
        base_slippage_pct: float = 0.0005,
        session_multipliers: Optional[Dict[str, float]] = None
    ):
        """
        初始化时间滑点模型

        Args:
            base_slippage_pct: 基础滑点比例
            session_multipliers: 时段乘数字典
        """
        super().__init__("time_based")
        self.base_slippage_pct = base_slippage_pct
        self.session_multipliers = session_multipliers or self.SESSION_MULTIPLIERS

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        market_data = market_data or {}

        # 获取当前时段
        session = market_data.get('session', 'morning')
        multiplier = self.session_multipliers.get(session, 1.0)

        slippage_pct = self.base_slippage_pct * multiplier
        slippage = intended_price * slippage_pct

        if direction.upper() == 'BUY':
            return intended_price + slippage
        else:
            return intended_price - slippage


class CompositeSlippage(SlippageModel):
    """
    复合滑点模型

    组合多种滑点模型，例如：
    - 基础滑点（固定或百分比）
    - 波动率调整
    - 成交量冲击
    """

    def __init__(
        self,
        models: list,
        weights: Optional[list] = None,
        combination_method: str = "sum"  # sum, max, weighted_avg
    ):
        """
        初始化复合滑点模型

        Args:
            models: 滑点模型列表
            weights: 模型权重列表（用于weighted_avg）
            combination_method: 组合方法
        """
        super().__init__("composite")
        self.models = models
        self.weights = weights or [1.0] * len(models)
        self.combination_method = combination_method

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        slippages = []

        for model in self.models:
            try:
                slippage = model.calculate_slippage(
                    direction, intended_price, volume, market_data
                )
                slippages.append(slippage)
            except Exception as e:
                logger.warning(f"{model.name}滑点计算失败: {e}")

        if not slippages:
            return intended_price

        # 组合滑点
        if self.combination_method == "sum":
            total_slippage = sum(slippages)
        elif self.combination_method == "max":
            total_slippage = max(slippages)
        elif self.combination_method == "weighted_avg":
            total_slippage = sum(
                s * w for s, w in zip(slippages, self.weights[:len(slippages)])
            ) / sum(self.weights[:len(slippages)])
        else:
            total_slippage = sum(slippages)

        if direction.upper() == 'BUY':
            return intended_price + total_slippage
        else:
            return intended_price - total_slippage


class AdaptiveSlippage(SlippageModel):
    """
    自适应滑点模型

    根据市场状态动态选择滑点模型：
    - 高波动市场：使用波动率滑点
    - 大单交易：使用成交量冲击滑点
    - 正常情况：使用百分比滑点
    """

    def __init__(
        self,
        base_model: SlippageModel = None,
        volatility_model: SlippageModel = None,
        volume_model: SlippageModel = None,
        vol_threshold: float = 0.02,          # 波动率阈值（日波动2%）
        volume_threshold: float = 0.01         # 成交量阈值（1%日成交量）
    ):
        """
        初始化自适应滑点模型

        Args:
            base_model: 基础滑点模型
            volatility_model: 波动率滑点模型
            volume_model: 成交量冲击模型
            vol_threshold: 波动率阈值
            volume_threshold: 成交量阈值
        """
        super().__init__("adaptive")
        self.base_model = base_model or PercentageSlippage(0.0005)
        self.volatility_model = volatility_model or VolatilitySlippage(0.1)
        self.volume_model = volume_model or VolumeImpactSlippage(0.01)
        self.vol_threshold = vol_threshold
        self.volume_threshold = volume_threshold

    def get_execution_price(
        self,
        direction: str,
        intended_price: float,
        volume: float = 0.0,
        market_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """获取执行价格"""
        market_data = market_data or {}

        # 检查成交量
        daily_volume = market_data.get('daily_volume', float('inf'))
        volume_ratio = volume / daily_volume if daily_volume > 0 else 0

        if volume_ratio > self.volume_threshold:
            # 大单，使用成交量冲击模型
            logger.debug(f"[AdaptiveSlippage] 使用成交量冲击模型 (ratio={volume_ratio:.4f})")
            return self.volume_model.get_execution_price(
                direction, intended_price, volume, market_data
            )

        # 检查波动率
        atr = market_data.get('atr', 0)
        volatility = atr / intended_price if intended_price > 0 else 0

        if volatility > self.vol_threshold:
            # 高波动，使用波动率模型
            logger.debug(f"[AdaptiveSlippage] 使用波动率模型 (vol={volatility:.4f})")
            return self.volatility_model.get_execution_price(
                direction, intended_price, volume, market_data
            )

        # 正常情况，使用基础模型
        return self.base_model.get_execution_price(
            direction, intended_price, volume, market_data
        )


# 便捷函数
def create_default_slippage_model() -> SlippageModel:
    """创建默认滑点模型（百分比0.05%）"""
    return PercentageSlippage(slippage_pct=0.0005)


def create_conservative_slippage_model() -> SlippageModel:
    """创建保守滑点模型（高滑点估计，0.1%）"""
    return PercentageSlippage(slippage_pct=0.001)


def create_aggressive_slippage_model() -> SlippageModel:
    """创建激进滑点模型（低滑点估计，0.02%）"""
    return PercentageSlippage(slippage_pct=0.0002)


def create_adaptive_slippage_model() -> AdaptiveSlippage:
    """创建自适应滑点模型"""
    return AdaptiveSlippage()


if __name__ == "__main__":
    # 测试代码
    print("=== 滑点模型测试 ===\n")

    price = 100.0
    volume = 10000

    # 1. 固定滑点测试
    print("1. 固定滑点模型")
    fixed = FixedSlippage(fixed_amount=0.01)
    buy_price = fixed.get_execution_price('BUY', price)
    sell_price = fixed.get_execution_price('SELL', price)
    print(f"   意向价格: {price}")
    print(f"   买入执行价: {buy_price} (滑点+{buy_price-price})")
    print(f"   卖出执行价: {sell_price} (滑点{sell_price-price})\n")

    # 2. 百分比滑点测试
    print("2. 百分比滑点模型 (0.05%)")
    pct = PercentageSlippage(slippage_pct=0.0005)
    buy_price = pct.get_execution_price('BUY', price)
    sell_price = pct.get_execution_price('SELL', price)
    print(f"   买入执行价: {buy_price:.4f} (滑点{(buy_price-price)/price*100:.3f}%)")
    print(f"   卖出执行价: {sell_price:.4f} (滑点{(price-sell_price)/price*100:.3f}%)\n")

    # 3. 波动率滑点测试
    print("3. 波动率滑点模型")
    vol = VolatilitySlippage(atr_ratio=0.1)

    # 高波动情况
    market_data_high = {'atr': 5.0}  # ATR=5元
    buy_price_high = vol.get_execution_price('BUY', price, market_data=market_data_high)

    # 低波动情况
    market_data_low = {'atr': 1.0}  # ATR=1元
    buy_price_low = vol.get_execution_price('BUY', price, market_data=market_data_low)

    print(f"   高波动(ATR=5): 买入执行价 {buy_price_high:.4f}")
    print(f"   低波动(ATR=1): 买入执行价 {buy_price_low:.4f}\n")

    # 4. 成交量冲击滑点测试
    print("4. 成交量冲击滑点模型")
    vol_impact = VolumeImpactSlippage(volume_threshold=0.01, base_slippage_pct=0.0005)

    # 小单（0.5%成交量）
    market_data_small = {'daily_volume': 2000000}
    buy_price_small = vol_impact.get_execution_price('BUY', price, volume=10000, market_data=market_data_small)

    # 大单（5%成交量）
    market_data_large = {'daily_volume': 200000}
    buy_price_large = vol_impact.get_execution_price('BUY', price, volume=10000, market_data=market_data_large)

    print(f"   小单(占0.5%成交量): 买入执行价 {buy_price_small:.4f}")
    print(f"   大单(占5%成交量): 买入执行价 {buy_price_large:.4f}\n")

    # 5. 复合滑点测试
    print("5. 复合滑点模型")
    composite = CompositeSlippage(
        models=[
            PercentageSlippage(0.0003),
            VolatilitySlippage(atr_ratio=0.05, min_slippage_pct=0, max_slippage_pct=0.01)
        ],
        combination_method="sum"
    )
    market_data = {'atr': 3.0}
    buy_price = composite.get_execution_price('BUY', price, market_data=market_data)
    print(f"   基础0.03% + 波动率调整: 买入执行价 {buy_price:.4f}\n")

    print("测试完成!")
