"""
仓位管理模块

实现多种仓位计算方法：
- Kelly公式仓位
- 风险平价仓位分配
- 波动率目标仓位
- 最大回撤动态控制

参考：
- Kelly Criterion: https://en.wikipedia.org/wiki/Kelly_criterion
- Risk Parity: https://en.wikipedia.org/wiki/Risk_parity
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum

import pandas as pd
import numpy as np
from scipy.optimize import minimize

from core.logger import get_logger

logger = get_logger(__name__)


class PositionSizingMethod(Enum):
    """仓位计算方法枚举"""
    FIXED = "fixed"                    # 固定比例
    KELLY = "kelly"                    # Kelly公式
    RISK_PARITY = "risk_parity"        # 风险平价
    VOL_TARGET = "vol_target"          # 波动率目标
    EQUAL_WEIGHT = "equal_weight"      # 等权重


@dataclass
class SizingResult:
    """
    仓位计算结果

    Attributes:
        method: 计算方法
        weights: 权重字典 {asset: weight}
        total_exposure: 总敞口
        expected_risk: 预期风险
        metadata: 额外信息
    """
    method: str
    weights: Dict[str, float]
    total_exposure: float
    expected_risk: float
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def get_weight(self, asset: str) -> float:
        """获取指定资产的权重"""
        return self.weights.get(asset, 0.0)

    def normalize_weights(self, target_sum: float = 1.0) -> "SizingResult":
        """
        归一化权重

        Args:
            target_sum: 目标和

        Returns:
            新的SizingResult
        """
        current_sum = sum(self.weights.values())
        if current_sum == 0:
            return self

        scale = target_sum / current_sum
        new_weights = {k: v * scale for k, v in self.weights.items()}

        return SizingResult(
            method=self.method,
            weights=new_weights,
            total_exposure=self.total_exposure,
            expected_risk=self.expected_risk,
            metadata=self.metadata
        )


class BasePositionSizer(ABC):
    """仓位计算基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate(self, **kwargs) -> SizingResult:
        """
        计算仓位

        Returns:
            SizingResult
        """
        pass

    def validate_weights(self, weights: Dict[str, float], max_weight: float = 1.0) -> Dict[str, float]:
        """
        验证并限制权重

        Args:
            weights: 原始权重
            max_weight: 单个资产最大权重

        Returns:
            调整后的权重
        """
        # 限制单个权重
        adjusted = {k: min(v, max_weight) for k, v in weights.items()}

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted


class FixedPositionSizer(BasePositionSizer):
    """固定比例仓位"""

    def __init__(self, position_pct: float = 0.1):
        super().__init__("fixed")
        self.position_pct = position_pct

    def calculate(self, assets: List[str], **kwargs) -> SizingResult:
        """
        计算固定比例仓位

        Args:
            assets: 资产列表

        Returns:
            SizingResult
        """
        n = len(assets)
        if n == 0:
            return SizingResult(
                method=self.name,
                weights={},
                total_exposure=0.0,
                expected_risk=0.0
            )

        weight = min(self.position_pct, 1.0 / n)
        weights = {asset: weight for asset in assets}

        return SizingResult(
            method=self.name,
            weights=weights,
            total_exposure=sum(weights.values()),
            expected_risk=0.0,
            metadata={'position_pct': self.position_pct}
        )


class KellyPositionSizer(BasePositionSizer):
    """
    Kelly公式仓位计算

    Kelly公式：f* = (bp - q) / b
    其中:
        f* = 最优仓位比例
        b = 盈亏比 (平均盈利/平均亏损)
        p = 胜率
        q = 败率 = 1-p

    实际使用中通常采用"半Kelly"或"四分之一Kelly"来降低风险。
    """

    def __init__(self, fraction: float = 0.5, max_position: float = 1.0):
        """
        初始化Kelly仓位计算器

        Args:
            fraction: Kelly分数（通常用0.5半Kelly或0.25四分之一Kelly）
            max_position: 最大仓位限制
        """
        super().__init__("kelly")
        self.fraction = fraction
        self.max_position = max_position

    def calculate(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        **kwargs
    ) -> SizingResult:
        """
        计算Kelly仓位

        Args:
            win_rate: 胜率 (0-1)
            avg_win: 平均盈利（正数）
            avg_loss: 平均亏损（正数）

        Returns:
            SizingResult
        """
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            logger.warning(f"[Kelly] 无效参数: win_rate={win_rate}, avg_loss={avg_loss}")
            return SizingResult(
                method=self.name,
                weights={'default': 0.0},
                total_exposure=0.0,
                expected_risk=0.0,
                metadata={'kelly_pct': 0.0, 'fraction': self.fraction}
            )

        # 计算盈亏比
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        # Kelly公式
        kelly_raw = (b * p - q) / b

        # 应用Kelly分数
        kelly_adjusted = kelly_raw * self.fraction

        # 限制在[0, max_position]范围内
        kelly_final = max(0.0, min(kelly_adjusted, self.max_position))

        logger.debug(f"[Kelly] 原始={kelly_raw:.4f}, 调整后={kelly_adjusted:.4f}, "
                    f"最终={kelly_final:.4f}")

        return SizingResult(
            method=self.name,
            weights={'default': kelly_final},
            total_exposure=kelly_final,
            expected_risk=kelly_final * avg_loss,  # 预期风险 = 仓位 × 平均亏损
            metadata={
                'kelly_raw': kelly_raw,
                'kelly_fraction': self.fraction,
                'win_rate': win_rate,
                'profit_loss_ratio': b,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            }
        )

    def calculate_from_trades(self, trades: List[Dict[str, Any]], **kwargs) -> SizingResult:
        """
        从交易记录计算Kelly仓位

        Args:
            trades: 交易记录列表，每个元素包含 'pnl' (盈亏金额)

        Returns:
            SizingResult
        """
        if not trades:
            return SizingResult(
                method=self.name,
                weights={'default': 0.0},
                total_exposure=0.0,
                expected_risk=0.0
            )

        pnls = [t.get('pnl', 0) for t in trades]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0

        return self.calculate(win_rate, avg_win, avg_loss, **kwargs)


class RiskParityPositionSizer(BasePositionSizer):
    """
    风险平价仓位分配

    使各资产对组合的风险贡献相等：
        RC_i = w_i × (Σw)_i / σ_p = 1/n × σ_p

    其中:
        w_i = 资产i的权重
        Σ = 协方差矩阵
        σ_p = 组合波动率
    """

    def __init__(
        self,
        target_risk: float = 0.10,
        risk_budget: Optional[Dict[str, float]] = None,
        max_weight: float = 0.5,
        min_weight: float = 0.0
    ):
        """
        初始化风险平价仓位计算器

        Args:
            target_risk: 目标波动率（年化）
            risk_budget: 风险预算字典 {asset: budget}，None表示等风险预算
            max_weight: 单个资产最大权重
            min_weight: 单个资产最小权重
        """
        super().__init__("risk_parity")
        self.target_risk = target_risk
        self.risk_budget = risk_budget
        self.max_weight = max_weight
        self.min_weight = min_weight

    def calculate(
        self,
        cov_matrix: pd.DataFrame,
        returns: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> SizingResult:
        """
        计算风险平价权重

        Args:
            cov_matrix: 收益率协方差矩阵
            returns: 历史收益率DataFrame（可选，用于计算预期收益）

        Returns:
            SizingResult
        """
        assets = list(cov_matrix.index)
        n = len(assets)

        if n == 0:
            return SizingResult(
                method=self.name,
                weights={},
                total_exposure=0.0,
                expected_risk=0.0
            )

        # 风险预算（默认等风险预算）
        if self.risk_budget is None:
            risk_budget = {asset: 1.0 / n for asset in assets}
        else:
            # 归一化风险预算
            total_budget = sum(self.risk_budget.get(a, 0) for a in assets)
            risk_budget = {asset: self.risk_budget.get(asset, 0) / total_budget
                          for asset in assets}

        # 初始权重（等权重）
        x0 = np.array([1.0 / n] * n)

        # 优化目标：最小化风险贡献偏离
        def risk_budget_objective(w):
            w = np.array(w)
            portfolio_vol = np.sqrt(w.T @ cov_matrix.values @ w)
            if portfolio_vol < 1e-10:
                return 0.0

            # 边际风险贡献
            mrc = cov_matrix.values @ w
            # 风险贡献
            rc = w * mrc
            # 目标风险贡献
            target_rc = np.array([risk_budget[a] for a in assets]) * portfolio_vol

            # 最小化风险贡献与目标差异
            return np.sum((rc - target_rc) ** 2)

        # 约束条件
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}  # 权重和为1
        ]

        # 边界
        bounds = [(self.min_weight, self.max_weight) for _ in range(n)]

        # 优化
        try:
            result = minimize(
                risk_budget_objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )

            if result.success:
                weights_array = result.x
                weights = {asset: weights_array[i] for i, asset in enumerate(assets)}
            else:
                logger.warning(f"[RiskParity] 优化失败: {result.message}，使用等权重")
                weights = {asset: 1.0 / n for asset in assets}

        except Exception as e:
            logger.error(f"[RiskParity] 优化异常: {e}，使用等权重")
            weights = {asset: 1.0 / n for asset in assets}

        # 计算预期风险
        weights_array = np.array([weights[a] for a in assets])
        portfolio_var = weights_array.T @ cov_matrix.values @ weights_array
        portfolio_vol = np.sqrt(portfolio_var)

        # 根据目标波动率调整杠杆
        if portfolio_vol > 0:
            leverage = self.target_risk / (portfolio_vol * np.sqrt(252))  # 假设日波动率
            adjusted_weights = {k: v * leverage for k, v in weights.items()}
        else:
            adjusted_weights = weights

        return SizingResult(
            method=self.name,
            weights=adjusted_weights,
            total_exposure=sum(abs(v) for v in adjusted_weights.values()),
            expected_risk=portfolio_vol * np.sqrt(252),  # 年化波动率
            metadata={
                'target_risk': self.target_risk,
                'portfolio_volatility': portfolio_vol * np.sqrt(252),
                'risk_budget': risk_budget,
                'leverage': leverage if portfolio_vol > 0 else 1.0
            }
        )

    def calculate_from_returns(
        self,
        returns: pd.DataFrame,
        lookback: int = 252,
        **kwargs
    ) -> SizingResult:
        """
        从收益率数据计算风险平价权重

        Args:
            returns: 历史收益率DataFrame
            lookback: 回看周期

        Returns:
            SizingResult
        """
        # 计算协方差矩阵
        recent_returns = returns.tail(lookback)
        cov_matrix = recent_returns.cov()

        return self.calculate(cov_matrix, recent_returns, **kwargs)


class VolatilityTargetSizer(BasePositionSizer):
    """
    波动率目标仓位调整

    根据当前波动率调整仓位，使组合波动率接近目标波动率：
        仓位 ∝ 目标波动率 / 预测波动率
    """

    def __init__(
        self,
        target_vol: float = 0.10,
        max_leverage: float = 2.0,
        min_position: float = 0.0,
        lookback: int = 20
    ):
        """
        初始化波动率目标仓位计算器

        Args:
            target_vol: 目标年化波动率
            max_leverage: 最大杠杆倍数
            min_position: 最小仓位比例
            lookback: 波动率计算回看周期
        """
        super().__init__("vol_target")
        self.target_vol = target_vol
        self.max_leverage = max_leverage
        self.min_position = min_position
        self.lookback = lookback

    def calculate(
        self,
        current_vol: float,
        **kwargs
    ) -> SizingResult:
        """
        计算波动率目标仓位

        Args:
            current_vol: 当前年化波动率

        Returns:
            SizingResult
        """
        if current_vol <= 0:
            position_scale = 1.0
        else:
            # 仓位比例 = 目标波动率 / 当前波动率
            position_scale = self.target_vol / current_vol

        # 限制范围
        position_scale = max(
            self.min_position,
            min(position_scale, self.max_leverage)
        )

        return SizingResult(
            method=self.name,
            weights={'default': position_scale},
            total_exposure=position_scale,
            expected_risk=current_vol * position_scale,
            metadata={
                'target_volatility': self.target_vol,
                'current_volatility': current_vol,
                'position_scale': position_scale,
                'max_leverage': self.max_leverage
            }
        )

    def calculate_from_returns(
        self,
        returns: pd.Series,
        **kwargs
    ) -> SizingResult:
        """
        从收益率序列计算波动率目标仓位

        Args:
            returns: 历史收益率序列

        Returns:
            SizingResult
        """
        # 计算年化波动率
        recent_returns = returns.tail(self.lookback)
        daily_vol = recent_returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        return self.calculate(annual_vol, **kwargs)

    def calculate_for_portfolio(
        self,
        returns: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> SizingResult:
        """
        计算组合层面的波动率目标仓位

        Args:
            returns: 各资产收益率DataFrame
            weights: 当前权重字典，None使用等权重

        Returns:
            SizingResult
        """
        assets = list(returns.columns)

        if weights is None:
            weights = {asset: 1.0 / len(assets) for asset in assets}

        # 计算组合波动率
        weights_array = np.array([weights.get(a, 0) for a in assets])
        recent_returns = returns.tail(self.lookback)
        cov_matrix = recent_returns.cov()
        portfolio_var = weights_array.T @ cov_matrix.values @ weights_array
        portfolio_vol = np.sqrt(portfolio_var) * np.sqrt(252)

        return self.calculate(portfolio_vol, **kwargs)


class DrawdownController(BasePositionSizer):
    """
    最大回撤动态控制

    根据当前回撤状态动态调整仓位比例。
    """

    def __init__(
        self,
        max_drawdown: float = 0.15,
        warning_drawdown: float = 0.10,
        normal_scale: float = 1.0,
        warning_scale: float = 0.5,
        limit_scale: float = 0.0,
        recovery_threshold: float = 0.05
    ):
        """
        初始化回撤控制器

        Args:
            max_drawdown: 最大回撤限制
            warning_drawdown: 回撤预警线
            normal_scale: 正常状态仓位比例
            warning_scale: 预警状态仓位比例
            limit_scale: 限制状态仓位比例（清仓或极低仓位）
            recovery_threshold: 恢复阈值（回撤小于此值恢复正常）
        """
        super().__init__("drawdown_control")
        self.max_drawdown = max_drawdown
        self.warning_drawdown = warning_drawdown
        self.normal_scale = normal_scale
        self.warning_scale = warning_scale
        self.limit_scale = limit_scale
        self.recovery_threshold = recovery_threshold

        # 状态跟踪
        self._current_scale = normal_scale
        self._in_drawdown = False

    def calculate(
        self,
        current_drawdown: float,
        **kwargs
    ) -> SizingResult:
        """
        计算回撤控制仓位

        Args:
            current_drawdown: 当前回撤比例

        Returns:
            SizingResult
        """
        # 确定状态
        if current_drawdown >= self.max_drawdown:
            # 限制状态
            new_scale = self.limit_scale
            status = "limit"
            if not self._in_drawdown:
                logger.warning(f"[DrawdownController] 触发限制状态: 回撤{current_drawdown*100:.1f}%")
                self._in_drawdown = True

        elif current_drawdown >= self.warning_drawdown:
            # 预警状态
            new_scale = self.warning_scale
            status = "warning"
            if not self._in_drawdown:
                logger.warning(f"[DrawdownController] 触发预警状态: 回撤{current_drawdown*100:.1f}%")
                self._in_drawdown = True

        else:
            # 检查是否恢复
            if self._in_drawdown:
                if current_drawdown <= self.recovery_threshold:
                    new_scale = self.normal_scale
                    status = "normal"
                    logger.info(f"[DrawdownController] 恢复正常状态: 回撤{current_drawdown*100:.1f}%")
                    self._in_drawdown = False
                else:
                    # 保持当前缩放比例
                    new_scale = self._current_scale
                    status = "recovering"
            else:
                new_scale = self.normal_scale
                status = "normal"

        self._current_scale = new_scale

        return SizingResult(
            method=self.name,
            weights={'default': new_scale},
            total_exposure=new_scale,
            expected_risk=current_drawdown,  # 这里用回撤作为风险指标
            metadata={
                'current_drawdown': current_drawdown,
                'status': status,
                'position_scale': new_scale,
                'max_drawdown': self.max_drawdown,
                'warning_drawdown': self.warning_drawdown
            }
        )

    def reset(self):
        """重置状态"""
        self._current_scale = self.normal_scale
        self._in_drawdown = False


class CompositePositionSizer(BasePositionSizer):
    """
    复合仓位计算器

    组合多种仓位计算方法，例如：
    - Kelly计算基础仓位
    - 波动率目标调整
    - 回撤控制再调整
    """

    def __init__(
        self,
        sizers: List[Tuple[BasePositionSizer, float]],
        composition_method: str = "multiply"  # multiply, min, max
    ):
        """
        初始化复合仓位计算器

        Args:
            sizers: (仓位计算器, 权重) 列表
            composition_method: 组合方法，multiply(相乘), min(取最小), max(取最大)
        """
        super().__init__("composite")
        self.sizers = sizers
        self.composition_method = composition_method

    def calculate(self, **kwargs) -> SizingResult:
        """
        计算复合仓位

        组合多个仓位计算器的结果。

        Returns:
            SizingResult
        """
        results = []
        for sizer, _ in self.sizers:
            try:
                result = sizer.calculate(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"[Composite] {sizer.name} 计算失败: {e}")

        if not results:
            return SizingResult(
                method=self.name,
                weights={'default': 0.0},
                total_exposure=0.0,
                expected_risk=0.0
            )

        # 组合权重
        final_weight = 1.0
        for result in results:
            w = result.get_weight('default')
            if self.composition_method == "multiply":
                final_weight *= w
            elif self.composition_method == "min":
                final_weight = min(final_weight, w)
            elif self.composition_method == "max":
                final_weight = max(final_weight, w)

        return SizingResult(
            method=self.name,
            weights={'default': final_weight},
            total_exposure=final_weight,
            expected_risk=results[0].expected_risk if results else 0.0,
            metadata={
                'composition_method': self.composition_method,
                'component_results': [r.metadata for r in results]
            }
        )


def create_kelly_vol_composite(
    kelly_fraction: float = 0.5,
    target_vol: float = 0.15,
    max_leverage: float = 2.0
) -> CompositePositionSizer:
    """
    创建Kelly+波动率目标复合仓位计算器

    Args:
        kelly_fraction: Kelly分数
        target_vol: 目标波动率
        max_leverage: 最大杠杆

    Returns:
        CompositePositionSizer
    """
    kelly = KellyPositionSizer(fraction=kelly_fraction)
    vol_target = VolatilityTargetSizer(target_vol=target_vol, max_leverage=max_leverage)

    return CompositePositionSizer(
        sizers=[(kelly, 1.0), (vol_target, 1.0)],
        composition_method="multiply"
    )


def create_full_risk_controlled_sizer(
    kelly_fraction: float = 0.5,
    target_vol: float = 0.15,
    max_drawdown: float = 0.15,
    warning_drawdown: float = 0.10
) -> CompositePositionSizer:
    """
    创建完整的的风控仓位计算器（Kelly + 波动率目标 + 回撤控制）

    Args:
        kelly_fraction: Kelly分数
        target_vol: 目标波动率
        max_drawdown: 最大回撤
        warning_drawdown: 预警回撤

    Returns:
        CompositePositionSizer
    """
    kelly = KellyPositionSizer(fraction=kelly_fraction)
    vol_target = VolatilityTargetSizer(target_vol=target_vol)
    drawdown = DrawdownController(
        max_drawdown=max_drawdown,
        warning_drawdown=warning_drawdown
    )

    return CompositePositionSizer(
        sizers=[(kelly, 1.0), (vol_target, 1.0), (drawdown, 1.0)],
        composition_method="multiply"
    )


if __name__ == "__main__":
    # 测试代码
    print("=== 仓位管理模块测试 ===\n")

    # 1. Kelly公式测试
    print("1. Kelly公式测试")
    kelly = KellyPositionSizer(fraction=0.5)
    result = kelly.calculate(win_rate=0.55, avg_win=100, avg_loss=50)
    print(f"   胜率55%, 盈亏比2:1, 半Kelly仓位: {result.get_weight('default')*100:.1f}%")
    print(f"   元数据: {result.metadata}\n")

    # 2. 风险平价测试
    print("2. 风险平价测试")
    np.random.seed(42)
    returns = pd.DataFrame({
        'A': np.random.normal(0.001, 0.02, 252),
        'B': np.random.normal(0.0005, 0.015, 252),
        'C': np.random.normal(0.0008, 0.025, 252),
    })
    cov_matrix = returns.cov() * 252  # 年化协方差

    rp = RiskParityPositionSizer(target_risk=0.10)
    result = rp.calculate(cov_matrix)
    print(f"   风险平价权重: {result.weights}")
    print(f"   预期波动率: {result.expected_risk*100:.1f}%")
    print(f"   元数据: {result.metadata}\n")

    # 3. 波动率目标测试
    print("3. 波动率目标测试")
    vol_target = VolatilityTargetSizer(target_vol=0.15, max_leverage=2.0)
    result = vol_target.calculate(current_vol=0.20)
    print(f"   当前波动20%, 目标15%, 仓位比例: {result.get_weight('default')*100:.1f}%")
    result = vol_target.calculate(current_vol=0.10)
    print(f"   当前波动10%, 目标15%, 仓位比例: {result.get_weight('default')*100:.1f}%\n")

    # 4. 回撤控制测试
    print("4. 回撤控制测试")
    dd = DrawdownController(max_drawdown=0.15, warning_drawdown=0.10)
    for drawdown in [0.05, 0.12, 0.18, 0.08, 0.03]:
        result = dd.calculate(drawdown)
        print(f"   回撤{drawdown*100:.0f}%: 仓位比例={result.get_weight('default')*100:.0f}%, "
              f"状态={result.metadata['status']}")

    print("\n测试完成!")
