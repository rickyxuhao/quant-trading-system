"""
投资组合优化器 - 支持多种优化目标和约束

功能：
- 均值-方差优化（Markowitz）
- 风险平价优化
- 最大化夏普比率
- 行业约束（单行业上限20%）
- 个股持仓约束（最小2万/最大10万）
- 回撤控制
- 波动率目标
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from enum import Enum
import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize, NonlinearConstraint

from core.logger import get_logger
from projects.quant_trading.backtest.risk_model import FactorRiskModel, RiskDecomposition

logger = get_logger(__name__)


class OptimizationObjective(Enum):
    """优化目标"""
    MAX_SHARPE = "max_sharpe"  # 最大化夏普比率
    MIN_VARIANCE = "min_variance"  # 最小化方差
    MAX_RETURN = "max_return"  # 最大化收益
    RISK_PARITY = "risk_parity"  # 风险平价
    MAX_UTILITY = "max_utility"  # 最大化效用（收益-风险厌恶*方差）


@dataclass
class OptimizationConstraints:
    """优化约束配置"""

    # 权重约束
    min_weight: float = 0.0  # 最小权重
    max_weight: float = 0.10  # 最大权重（单股10%）
    long_only: bool = True  # 只允许做多

    # 持仓金额约束（针对A股账户）
    min_position_value: float = 20_000  # 最小持仓2万
    max_position_value: float = 100_000  # 最大持仓10万
    total_capital: float = 1_000_000  # 总资金100万

    # 行业约束
    max_sector_weight: float = 0.20  # 单行业最大20%
    industry_factors: Optional[Dict[str, List[str]]] = None  # 行业分类

    # 风险约束
    target_volatility: Optional[float] = None  # 目标波动率（年化）
    max_tracking_error: Optional[float] = None  # 最大跟踪误差
    risk_model: Optional[FactorRiskModel] = None  # 风险模型

    # 目标收益
    target_return: Optional[float] = None


@dataclass
class OptimizationResult:
    """优化结果"""

    success: bool
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    objective_value: float
    sector_exposures: Dict[str, float]
    risk_decomposition: Optional[RiskDecomposition] = None
    message: str = ""

    def get_position_values(self, total_capital: float) -> Dict[str, float]:
        """获取各仓位金额"""
        return {stock: w * total_capital for stock, w in self.weights.items()}


class PortfolioOptimizer:
    """
    投资组合优化器

    支持多种优化目标和约束条件
    """

    def __init__(
        self,
        objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
        constraints: Optional[OptimizationConstraints] = None,
        risk_free_rate: float = 0.03,
    ):
        self.objective = objective
        self.constraints = constraints or OptimizationConstraints()
        self.risk_free_rate = risk_free_rate

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        current_weights: Optional[pd.Series] = None,
        sector_mapping: Optional[Dict[str, str]] = None,
    ) -> OptimizationResult:
        """
        执行组合优化

        Args:
            expected_returns: 预期收益
            cov_matrix: 收益协方差矩阵
            current_weights: 当前权重（用于换手率约束）
            sector_mapping: 股票到行业的映射

        Returns:
            优化结果
        """
        n_assets = len(expected_returns)
        assets = expected_returns.index.tolist()

        if n_assets == 0:
            return OptimizationResult(
                success=False,
                weights={},
                expected_return=0,
                expected_risk=0,
                sharpe_ratio=0,
                objective_value=0,
                sector_exposures={},
                message="Empty asset list",
            )

        # 对齐数据
        cov_matrix = cov_matrix.reindex(index=assets, columns=assets).fillna(0)

        # 初始权重（等权）
        x0 = np.ones(n_assets) / n_assets

        # 权重边界
        bounds = self._get_weight_bounds(assets)

        # 约束条件
        constraints_list = self._get_constraints(
            assets, expected_returns, cov_matrix, sector_mapping
        )

        # 目标函数
        obj_func = self._get_objective_function(
            expected_returns, cov_matrix, self.objective
        )

        # 执行优化
        try:
            result = minimize(
                obj_func,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints_list,
                options={"maxiter": 1000, "ftol": 1e-9},
            )

            if result.success:
                weights = pd.Series(result.x, index=assets)
                weights = weights[weights > 1e-6]  # 过滤极小权重

                # 归一化
                weights = weights / weights.sum()

                # 计算结果指标
                opt_result = self._calculate_result(
                    weights, expected_returns, cov_matrix, sector_mapping
                )
                opt_result.success = True
                opt_result.message = result.message

                return opt_result
            else:
                logger.warning(f"Optimization failed: {result.message}")
                # 返回等权组合作为备选
                return self._create_equal_weight_result(
                    assets, expected_returns, cov_matrix, sector_mapping, result.message
                )

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return self._create_equal_weight_result(
                assets, expected_returns, cov_matrix, sector_mapping, str(e)
            )

    def optimize_with_risk_model(
        self,
        expected_returns: pd.Series,
        risk_model: FactorRiskModel,
        sector_mapping: Optional[Dict[str, str]] = None,
    ) -> OptimizationResult:
        """
        使用风险模型进行优化

        Args:
            expected_returns: 预期收益
            risk_model: 因子风险模型
            sector_mapping: 行业映射

        Returns:
            优化结果
        """
        # 使用风险模型的协方差估计
        # 这里简化为使用历史协方差，实际可以使用因子模型估计的协方差
        cov_matrix = self._estimate_covariance_from_risk_model(
            expected_returns.index, risk_model
        )

        return self.optimize(expected_returns, cov_matrix, None, sector_mapping)

    def _get_weight_bounds(self, assets: List[str]) -> List[Tuple[float, float]]:
        """获取权重边界"""
        bounds = []

        for asset in assets:
            min_w = self.constraints.min_weight
            max_w = self.constraints.max_weight

            # 根据资金约束调整
            if self.constraints.total_capital > 0:
                # 最大持仓金额约束
                max_weight_by_value = self.constraints.max_position_value / self.constraints.total_capital
                max_w = min(max_w, max_weight_by_value)

                # 最小持仓金额约束
                min_weight_by_value = self.constraints.min_position_value / self.constraints.total_capital
                min_w = max(min_w, min_weight_by_value)

            if self.constraints.long_only:
                min_w = max(0, min_w)

            bounds.append((min_w, max_w))

        return bounds

    def _get_constraints(
        self,
        assets: List[str],
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        sector_mapping: Optional[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """获取约束条件"""
        constraints = []

        # 1. 权重和为1
        constraints.append({"type": "eq", "fun": lambda x: np.sum(x) - 1.0})

        # 2. 行业约束
        if sector_mapping and self.constraints.max_sector_weight < 1.0:
            sector_constraints = self._get_sector_constraints(
                assets, sector_mapping
            )
            constraints.extend(sector_constraints)

        # 3. 目标收益约束（如果指定）
        if self.constraints.target_return is not None:
            constraints.append({
                "type": "eq",
                "fun": lambda x: x @ expected_returns.values - self.constraints.target_return,
            })

        # 4. 目标波动率约束（如果指定）
        if self.constraints.target_volatility is not None:
            target_var = self.constraints.target_volatility ** 2 / 252  # 转换为日方差
            constraints.append({
                "type": "ineq",
                "fun": lambda x: target_var - x @ cov_matrix.values @ x,
            })

        # 5. 使用风险模型的约束
        if self.constraints.risk_model:
            # 跟踪误差约束
            if self.constraints.max_tracking_error:
                risk_model = self.constraints.risk_model

                def tracking_error_constraint(x):
                    weights = pd.Series(x, index=assets)
                    te = risk_model.calculate_tracking_error(weights)
                    return self.constraints.max_tracking_error - te

                constraints.append({
                    "type": "ineq",
                    "fun": tracking_error_constraint,
                })

        return constraints

    def _get_sector_constraints(
        self, assets: List[str], sector_mapping: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """获取行业约束"""
        constraints = []

        # 按行业分组
        industry_groups: Dict[str, List[int]] = {}
        for i, asset in enumerate(assets):
            industry = sector_mapping.get(asset, "其他")
            if industry not in industry_groups:
                industry_groups[industry] = []
            industry_groups[industry].append(i)

        # 每个行业的权重上限
        for industry, indices in industry_groups.items():
            def create_sector_constraint(idx_list):
                return lambda x: self.constraints.max_sector_weight - np.sum(x[idx_list])

            constraints.append({
                "type": "ineq",
                "fun": create_sector_constraint(indices),
            })

        return constraints

    def _get_objective_function(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        objective: OptimizationObjective,
    ) -> Callable:
        """获取目标函数"""
        mu = expected_returns.values
        Sigma = cov_matrix.values

        if objective == OptimizationObjective.MIN_VARIANCE:
            return lambda x: x @ Sigma @ x

        elif objective == OptimizationObjective.MAX_RETURN:
            return lambda x: -x @ mu  # 最小化负收益

        elif objective == OptimizationObjective.MAX_SHARPE:
            def negative_sharpe(x):
                port_return = x @ mu
                port_var = x @ Sigma @ x
                port_vol = np.sqrt(port_var) if port_var > 0 else 1e-10
                return -(port_return - self.risk_free_rate / 252) / port_vol
            return negative_sharpe

        elif objective == OptimizationObjective.RISK_PARITY:
            def risk_parity_objective(x):
                port_var = x @ Sigma @ x
                if port_var < 1e-10:
                    return 0

                # 边际风险贡献
                mrc = Sigma @ x
                rc = x * mrc

                # 目标：各资产风险贡献相等
                target_rc = port_var / len(x)
                return np.sum((rc - target_rc) ** 2)
            return risk_parity_objective

        elif objective == OptimizationObjective.MAX_UTILITY:
            risk_aversion = 2.0  # 风险厌恶系数
            def utility(x):
                return -(x @ mu - 0.5 * risk_aversion * x @ Sigma @ x)
            return utility

        else:
            return lambda x: x @ Sigma @ x

    def _calculate_result(
        self,
        weights: pd.Series,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        sector_mapping: Optional[Dict[str, str]],
    ) -> OptimizationResult:
        """计算优化结果指标"""
        assets = weights.index.tolist()
        expected_returns = expected_returns.reindex(assets)
        cov_matrix = cov_matrix.reindex(index=assets, columns=assets)

        # 预期收益
        port_return = weights @ expected_returns

        # 预期风险
        port_var = weights @ cov_matrix @ weights
        port_risk = np.sqrt(port_var)

        # 夏普比率
        sharpe = (port_return - self.risk_free_rate / 252) / port_risk if port_risk > 0 else 0

        # 行业暴露
        sector_exposures = {}
        if sector_mapping:
            for stock, weight in weights.items():
                sector = sector_mapping.get(stock, "其他")
                sector_exposures[sector] = sector_exposures.get(sector, 0) + weight

        # 风险分解
        risk_decomp = None
        if self.constraints.risk_model:
            try:
                risk_decomp = self.constraints.risk_model.calculate_portfolio_risk(weights)
            except Exception as e:
                logger.debug(f"Risk decomposition failed: {e}")

        return OptimizationResult(
            success=True,
            weights=weights.to_dict(),
            expected_return=port_return,
            expected_risk=port_risk,
            sharpe_ratio=sharpe,
            objective_value=port_return,  # 根据目标类型可能需要调整
            sector_exposures=sector_exposures,
            risk_decomposition=risk_decomp,
        )

    def _create_equal_weight_result(
        self,
        assets: List[str],
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        sector_mapping: Optional[Dict[str, str]],
        message: str,
    ) -> OptimizationResult:
        """创建等权组合结果作为备选"""
        n = len(assets)
        equal_weights = pd.Series([1.0 / n] * n, index=assets)

        result = self._calculate_result(
            equal_weights, expected_returns, cov_matrix, sector_mapping
        )
        result.success = False
        result.message = f"Optimization failed, using equal weight: {message}"

        return result

    def _estimate_covariance_from_risk_model(
        self, assets: List[str], risk_model: FactorRiskModel
    ) -> pd.DataFrame:
        """从风险模型估计协方差矩阵"""
        # 简化实现：使用历史协方差
        # 实际应该使用因子模型估计的协方差
        n = len(assets)
        return pd.DataFrame(
            np.eye(n) * 0.0004,  # 假设20%年化波动率
            index=assets,
            columns=assets,
        )


class DrawdownController:
    """
    回撤控制器

    根据当前回撤动态调整仓位
    """

    def __init__(
        self,
        max_drawdown: float = 0.15,
        warning_drawdown: float = 0.10,
        drawdown_trigger: float = 0.10,
        position_reduction: float = 0.50,
    ):
        self.max_drawdown = max_drawdown
        self.warning_drawdown = warning_drawdown
        self.drawdown_trigger = drawdown_trigger
        self.position_reduction = position_reduction

        self.peak_value = 0
        self.current_drawdown = 0.0
        self.is_in_drawdown = False

    def update(self, current_value: float) -> Dict[str, Any]:
        """
        更新回撤状态

        Returns:
            控制指令
        """
        if current_value > self.peak_value:
            self.peak_value = current_value
            self.current_drawdown = 0.0
            self.is_in_drawdown = False
            return {"action": "normal", "scale": 1.0}

        self.current_drawdown = (self.peak_value - current_value) / self.peak_value

        # 触发减仓
        if self.current_drawdown >= self.drawdown_trigger:
            self.is_in_drawdown = True
            scale = 1.0 - self.position_reduction

            logger.warning(
                f"Drawdown triggered: {self.current_drawdown:.2%}, "
                f"reducing positions by {self.position_reduction:.0%}"
            )

            return {"action": "reduce", "scale": scale}

        # 警告但未触发
        if self.current_drawdown >= self.warning_drawdown:
            return {"action": "warning", "scale": 1.0}

        return {"action": "normal", "scale": 1.0}

    def should_clear_positions(self) -> bool:
        """判断是否应该清仓"""
        return self.current_drawdown >= self.max_drawdown


class VolatilityTargeter:
    """
    波动率目标管理器

    根据目标波动率动态调整杠杆
    """

    def __init__(
        self,
        target_volatility: float = 0.15,  # 15%年化目标
        max_leverage: float = 2.0,
        min_leverage: float = 0.5,
        lookback_window: int = 20,
    ):
        self.target_volatility = target_volatility
        self.max_leverage = max_leverage
        self.min_leverage = min_leverage
        self.lookback_window = lookback_window

        self.return_history: List[float] = []

    def update(self, daily_return: float) -> float:
        """
        更新并计算杠杆倍数

        Returns:
            杠杆倍数
        """
        self.return_history.append(daily_return)

        if len(self.return_history) > self.lookback_window:
            self.return_history.pop(0)

        if len(self.return_history) < 20:
            return 1.0

        # 计算当前年化波动率
        current_vol = np.std(self.return_history) * np.sqrt(252)

        if current_vol < 1e-10:
            return 1.0

        # 计算目标杠杆
        leverage = self.target_volatility / current_vol
        leverage = np.clip(leverage, self.min_leverage, self.max_leverage)

        return leverage


class RebalancingScheduler:
    """
    再平衡调度器

    决定何时进行组合再平衡
    """

    def __init__(
        self,
        frequency: str = "weekly",  # daily, weekly, monthly
        rebalance_day: int = 1,  # 周几或几号
        threshold: float = 0.05,  # 权重偏离阈值
    ):
        self.frequency = frequency
        self.rebalance_day = rebalance_day
        self.threshold = threshold

    def should_rebalance(
        self,
        date: datetime,
        current_weights: pd.Series,
        target_weights: pd.Series,
    ) -> bool:
        """判断是否需要再平衡"""
        # 检查日期条件
        if self.frequency == "daily":
            date_trigger = True
        elif self.frequency == "weekly":
            date_trigger = date.weekday() == self.rebalance_day - 1
        elif self.frequency == "monthly":
            date_trigger = date.day == self.rebalance_day
        else:
            date_trigger = True

        if not date_trigger:
            return False

        # 检查权重偏离
        if current_weights.empty or target_weights.empty:
            return True

        # 对齐权重
        all_assets = current_weights.index.union(target_weights.index)
        current = current_weights.reindex(all_assets, fill_value=0)
        target = target_weights.reindex(all_assets, fill_value=0)

        max_deviation = np.abs(current - target).max()

        return max_deviation > self.threshold


def create_default_optimizer(
    total_capital: float = 1_000_000,
    max_sector_weight: float = 0.20,
) -> PortfolioOptimizer:
    """创建默认优化器"""
    constraints = OptimizationConstraints(
        min_weight=0.0,
        max_weight=0.10,
        max_sector_weight=max_sector_weight,
        min_position_value=20_000,
        max_position_value=100_000,
        total_capital=total_capital,
    )

    return PortfolioOptimizer(
        objective=OptimizationObjective.MAX_SHARPE,
        constraints=constraints,
    )


def create_risk_parity_optimizer(
    total_capital: float = 1_000_000,
) -> PortfolioOptimizer:
    """创建风险平价优化器"""
    constraints = OptimizationConstraints(
        min_weight=0.01,  # 风险平价需要最小权重
        max_weight=0.10,
        min_position_value=20_000,
        max_position_value=100_000,
        total_capital=total_capital,
    )

    return PortfolioOptimizer(
        objective=OptimizationObjective.RISK_PARITY,
        constraints=constraints,
    )
