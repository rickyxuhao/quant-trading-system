"""
Walk-forward 分析模块

防止过拟合的稳健回测方法：
1. 滚动训练/验证/测试分割
2. 参数稳定性分析
3. 样本外性能评估

与现有回测引擎集成，提供比简单分割更可靠的策略评估。

作者: Claude
创建日期: 2026-03-19
"""

from typing import List, Optional, Dict, Any, Tuple, Iterator, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from core.logger import get_logger

logger = get_logger(__name__)


class SplitType(Enum):
    """分割类型"""
    EXPANDING = "expanding"  # 扩展窗口
    ROLLING = "rolling"      # 滚动窗口
    FIXED = "fixed"          # 固定窗口


@dataclass
class WalkForwardConfig:
    """Walk-forward 配置"""
    # 窗口配置
    train_days: int = 252        # 训练窗口天数（约1年）
    valid_days: int = 63         # 验证窗口天数（约1季度）
    test_days: int = 63          # 测试窗口天数（约1季度）
    step_days: int = 63          # 滚动步长

    # 分割类型
    split_type: SplitType = SplitType.ROLLING

    # 最小数据要求
    min_train_samples: int = 100
    min_test_samples: int = 20

    # 是否包含验证集
    use_validation: bool = False

    def __post_init__(self):
        assert self.train_days > 0, "train_days must be positive"
        assert self.test_days > 0, "test_days must be positive"
        assert self.step_days > 0, "step_days must be positive"


@dataclass
class WindowResult:
    """单个窗口的结果"""
    # 时间范围
    window_id: int
    train_start: datetime
    train_end: datetime
    valid_start: Optional[datetime]
    valid_end: Optional[datetime]
    test_start: datetime
    test_end: datetime

    # 数据
    train_data: pd.DataFrame
    valid_data: Optional[pd.DataFrame]
    test_data: pd.DataFrame

    # 性能指标
    train_metrics: Dict[str, float]
    valid_metrics: Optional[Dict[str, float]]
    test_metrics: Dict[str, float]

    # 最优参数（如果在训练集上优化了参数）
    best_params: Optional[Dict[str, Any]] = None


class RollingWindowSplitter:
    """
    滚动窗口分割器

    生成训练/验证/测试窗口的迭代器

    Example:
        >>> splitter = RollingWindowSplitter(
        ...     config=WalkForwardConfig(
        ...         train_days=252,
        ...         test_days=63,
        ...         step_days=63,
        ...     )
        ... )
        >>> for window in splitter.split(data):
        ...     model.fit(window.train_data)
        ...     predictions = model.predict(window.test_data)
    """

    def __init__(self, config: Optional[WalkForwardConfig] = None):
        """
        初始化分割器

        Args:
            config: Walk-forward 配置
        """
        self.config = config or WalkForwardConfig()

    def split(
        self,
        data: pd.DataFrame,
        date_col: str = "datetime",
    ) -> Iterator[Dict[str, Any]]:
        """
        分割数据为滚动窗口

        Args:
            data: 时间序列数据，需要有时间索引
            date_col: 日期列名

        Yields:
            包含 train/valid/test 数据的字典
        """
        # 获取唯一日期
        if isinstance(data.index, pd.MultiIndex):
            dates = data.index.get_level_values(date_col).unique()
        else:
            dates = pd.to_datetime(data[date_col]).unique()

        dates = pd.DatetimeIndex(dates).sort_values()

        config = self.config

        # 生成窗口
        for i in range(0, len(dates) - config.train_days - config.test_days, config.step_days):
            # 计算窗口边界
            train_start_idx = i
            train_end_idx = i + config.train_days
            test_start_idx = train_end_idx
            test_end_idx = min(test_start_idx + config.test_days, len(dates))

            # 处理验证集
            if config.use_validation and config.valid_days > 0:
                valid_start_idx = train_end_idx
                valid_end_idx = min(valid_start_idx + config.valid_days, test_start_idx)
                test_start_idx = valid_end_idx
            else:
                valid_start_idx = None
                valid_end_idx = None

            # 获取日期
            train_dates = dates[train_start_idx:train_end_idx]
            test_dates = dates[test_start_idx:test_end_idx]
            valid_dates = dates[valid_start_idx:valid_end_idx] if valid_start_idx else None

            # 检查最小样本数
            if len(train_dates) < config.min_train_samples:
                continue
            if len(test_dates) < config.min_test_samples:
                continue

            # 分割数据
            if isinstance(data.index, pd.MultiIndex):
                train_data = data[data.index.get_level_values(date_col).isin(train_dates)]
                test_data = data[data.index.get_level_values(date_col).isin(test_dates)]
                valid_data = data[data.index.get_level_values(date_col).isin(valid_dates)] if valid_dates is not None else None
            else:
                train_data = data[data[date_col].isin(train_dates)]
                test_data = data[data[date_col].isin(test_dates)]
                valid_data = data[data[date_col].isin(valid_dates)] if valid_dates is not None else None

            yield {
                "window_id": i // config.step_days + 1,
                "train_dates": (train_dates[0], train_dates[-1]),
                "valid_dates": (valid_dates[0], valid_dates[-1]) if valid_dates is not None else None,
                "test_dates": (test_dates[0], test_dates[-1]),
                "train_data": train_data,
                "valid_data": valid_data,
                "test_data": test_data,
            }

    def get_n_splits(self, data: pd.DataFrame, date_col: str = "datetime") -> int:
        """获取窗口数量"""
        if isinstance(data.index, pd.MultiIndex):
            dates = data.index.get_level_values(date_col).unique()
        else:
            dates = pd.to_datetime(data[date_col]).unique()

        dates = pd.DatetimeIndex(dates).sort_values()
        config = self.config

        n = 0
        for i in range(0, len(dates) - config.train_days - config.test_days, config.step_days):
            n += 1

        return n


class WalkForwardAnalyzer:
    """
    Walk-forward 分析器

    执行完整的 walk-forward 分析，包括：
    1. 滚动回测
    2. 参数稳定性分析
    3. 样本外性能评估
    4. 可视化

    Example:
        >>> analyzer = WalkForwardAnalyzer(
        ...     config=WalkForwardConfig(train_days=252, test_days=63),
        ... )
        >>> results = analyzer.analyze(
        ...     data=dataset,
        ...     train_fn=lambda data, **params: train_model(data, params),
        ...     predict_fn=lambda model, data: model.predict(data),
        ...     param_space={"lookback": [5, 10, 20]},
        ... )
        >>> analyzer.plot_results(results)
    """

    def __init__(self, config: Optional[WalkForwardConfig] = None):
        """
        初始化分析器

        Args:
            config: Walk-forward 配置
        """
        self.config = config or WalkForwardConfig()
        self.splitter = RollingWindowSplitter(config)
        self.results: List[WindowResult] = []

    def analyze(
        self,
        data: pd.DataFrame,
        train_fn: Callable,
        predict_fn: Callable,
        evaluate_fn: Callable,
        param_space: Optional[Dict[str, List]] = None,
        optimize_fn: Optional[Callable] = None,
    ) -> List[WindowResult]:
        """
        执行 Walk-forward 分析

        Args:
            data: 完整数据集
            train_fn: 训练函数，接收训练数据和参数，返回模型
            predict_fn: 预测函数，接收模型和测试数据，返回预测结果
            evaluate_fn: 评估函数，接收预测结果和真实值，返回指标字典
            param_space: 参数空间（如果需要在每个窗口优化参数）
            optimize_fn: 优化函数（如果需要在每个窗口优化参数）

        Returns:
            各窗口的结果列表
        """
        logger.info("Starting Walk-forward analysis...")

        self.results = []

        for window_data in self.splitter.split(data):
            window_id = window_data["window_id"]
            logger.info(f"Processing window {window_id}...")

            train_data = window_data["train_data"]
            test_data = window_data["test_data"]
            valid_data = window_data["valid_data"]

            # 如果在窗口内优化参数
            best_params = None
            if param_space and optimize_fn:
                logger.debug(f"Optimizing parameters for window {window_id}...")
                best_params = optimize_fn(train_data, valid_data, param_space)
                logger.debug(f"Best params: {best_params}")

            # 训练模型
            model = train_fn(train_data, **(best_params or {}))

            # 在训练集上评估
            train_pred = predict_fn(model, train_data)
            train_metrics = evaluate_fn(train_pred, train_data)

            # 在验证集上评估
            valid_metrics = None
            if valid_data is not None:
                valid_pred = predict_fn(model, valid_data)
                valid_metrics = evaluate_fn(valid_pred, valid_data)

            # 在测试集上评估（样本外）
            test_pred = predict_fn(model, test_data)
            test_metrics = evaluate_fn(test_pred, test_data)

            # 保存结果
            result = WindowResult(
                window_id=window_id,
                train_start=window_data["train_dates"][0],
                train_end=window_data["train_dates"][1],
                valid_start=window_data["valid_dates"][0] if window_data["valid_dates"] else None,
                valid_end=window_data["valid_dates"][1] if window_data["valid_dates"] else None,
                test_start=window_data["test_dates"][0],
                test_end=window_data["test_dates"][1],
                train_data=train_data,
                valid_data=valid_data,
                test_data=test_data,
                train_metrics=train_metrics,
                valid_metrics=valid_metrics,
                test_metrics=test_metrics,
                best_params=best_params,
            )

            self.results.append(result)
            logger.info(
                f"Window {window_id}: train_sharpe={train_metrics.get('sharpe_ratio', 0):.3f}, "
                f"test_sharpe={test_metrics.get('sharpe_ratio', 0):.3f}"
            )

        logger.info(f"Walk-forward analysis complete: {len(self.results)} windows")

        return self.results

    def analyze_stability(self) -> Dict[str, Any]:
        """
        分析结果稳定性

        Returns:
            稳定性分析结果
        """
        if not self.results:
            return {}

        # 收集指标
        train_sharpes = [r.train_metrics.get("sharpe_ratio", 0) for r in self.results]
        test_sharpes = [r.test_metrics.get("sharpe_ratio", 0) for r in self.results]

        # 参数稳定性（如果在窗口内优化了参数）
        param_stability = {}
        results_with_params = [r for r in self.results if r.best_params]
        if results_with_params:
            param_names = list(results_with_params[0].best_params.keys())
            for param_name in param_names:
                param_values = [r.best_params[param_name] for r in results_with_params]
                # 计算参数的变异系数
                if all(isinstance(v, (int, float)) for v in param_values):
                    param_stability[param_name] = {
                        "mean": np.mean(param_values),
                        "std": np.std(param_values),
                        "cv": np.std(param_values) / (abs(np.mean(param_values)) + 1e-8),
                        "values": param_values,
                    }
                else:
                    # 分类参数：计算最频繁值的比例
                    from collections import Counter
                    counter = Counter(param_values)
                    most_common = counter.most_common(1)[0]
                    param_stability[param_name] = {
                        "most_common": most_common[0],
                        "frequency": most_common[1] / len(param_values),
                        "distribution": dict(counter),
                    }

        return {
            "train_sharpe": {
                "mean": np.mean(train_sharpes),
                "std": np.std(train_sharpes),
                "min": np.min(train_sharpes),
                "max": np.max(train_sharpes),
            },
            "test_sharpe": {
                "mean": np.mean(test_sharpes),
                "std": np.std(test_sharpes),
                "min": np.min(test_sharpes),
                "max": np.max(test_sharpes),
            },
            "overfitting_ratio": np.mean(train_sharpes) / (np.mean(test_sharpes) + 1e-8),
            "consistency": sum(1 for t, v in zip(train_sharpes, test_sharpes) if v > 0) / len(test_sharpes),
            "param_stability": param_stability,
        }

    def plot_results(self, save_path: Optional[str] = None):
        """
        可视化 Walk-forward 结果

        Args:
            save_path: 保存路径，None 则显示
        """
        if not self.results:
            logger.warning("No results to plot")
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. 各窗口性能对比
        ax1 = axes[0, 0]
        window_ids = [r.window_id for r in self.results]
        train_sharpes = [r.train_metrics.get("sharpe_ratio", 0) for r in self.results]
        test_sharpes = [r.test_metrics.get("sharpe_ratio", 0) for r in self.results]

        x = np.arange(len(window_ids))
        width = 0.35

        ax1.bar(x - width/2, train_sharpes, width, label="Train", alpha=0.8)
        ax1.bar(x + width/2, test_sharpes, width, label="Test", alpha=0.8)
        ax1.set_xlabel("Window")
        ax1.set_ylabel("Sharpe Ratio")
        ax1.set_title("Train vs Test Performance by Window")
        ax1.set_xticks(x)
        ax1.set_xticklabels([f"W{i}" for i in window_ids])
        ax1.legend()
        ax1.axhline(y=0, color="k", linestyle="--", alpha=0.3)

        # 2. 累计收益曲线
        ax2 = axes[0, 1]
        # 简化：绘制测试期的平均收益
        test_returns = [r.test_metrics.get("total_return", 0) for r in self.results]
        ax2.plot(window_ids, np.cumsum(test_returns), marker="o")
        ax2.set_xlabel("Window")
        ax2.set_ylabel("Cumulative Return")
        ax2.set_title("Cumulative Test Returns")
        ax2.grid(True, alpha=0.3)

        # 3. 训练 vs 测试散点图
        ax3 = axes[1, 0]
        ax3.scatter(train_sharpes, test_sharpes, alpha=0.6)
        ax3.plot([-1, 3], [-1, 3], "r--", alpha=0.5, label="y=x")
        ax3.set_xlabel("Train Sharpe")
        ax3.set_ylabel("Test Sharpe")
        ax3.set_title("Train vs Test Sharpe Ratio")
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. 参数稳定性（如果有）
        ax4 = axes[1, 1]
        stability = self.analyze_stability()
        if stability.get("param_stability"):
            param_names = list(stability["param_stability"].keys())
            if param_names:
                param_name = param_names[0]  # 只显示第一个参数
                param_data = stability["param_stability"][param_name]
                if "values" in param_data:
                    ax4.plot(window_ids, param_data["values"], marker="o")
                    ax4.set_ylabel(param_name)
                    ax4.set_title(f"Parameter Stability: {param_name}")
                    ax4.grid(True, alpha=0.3)
                else:
                    ax4.text(0.5, 0.5, f"{param_name}: {param_data}",
                            ha="center", va="center", transform=ax4.transAxes)
                    ax4.set_title(f"Parameter Distribution: {param_name}")
        else:
            ax4.text(0.5, 0.5, "No parameter optimization performed",
                    ha="center", va="center", transform=ax4.transAxes)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

    def generate_report(self) -> str:
        """
        生成分析报告

        Returns:
            Markdown 格式的报告
        """
        if not self.results:
            return "No results to report."

        stability = self.analyze_stability()

        report = f"""# Walk-Forward Analysis Report

## Summary
- **Number of Windows**: {len(self.results)}
- **Train Period**: {self.config.train_days} days
- **Test Period**: {self.config.test_days} days
- **Step Size**: {self.config.step_days} days

## Performance Metrics

### Train Set
- Mean Sharpe: {stability['train_sharpe']['mean']:.3f}
- Std Sharpe: {stability['train_sharpe']['std']:.3f}
- Min/Max Sharpe: {stability['train_sharpe']['min']:.3f} / {stability['train_sharpe']['max']:.3f}

### Test Set (Out-of-Sample)
- Mean Sharpe: {stability['test_sharpe']['mean']:.3f}
- Std Sharpe: {stability['test_sharpe']['std']:.3f}
- Min/Max Sharpe: {stability['test_sharpe']['min']:.3f} / {stability['test_sharpe']['max']:.3f}
- Win Rate: {stability['consistency']:.1%}

## Overfitting Analysis
- Overfitting Ratio (Train/Test): {stability['overfitting_ratio']:.2f}
- Interpretation: {"Low overfitting" if stability['overfitting_ratio'] < 1.5 else "Moderate overfitting" if stability['overfitting_ratio'] < 2.0 else "High overfitting"}

"""

        # 参数稳定性
        if stability.get("param_stability"):
            report += "## Parameter Stability\n\n"
            for param_name, param_data in stability["param_stability"].items():
                if "cv" in param_data:
                    report += f"- **{param_name}**: CV={param_data['cv']:.3f}, "
                    report += f"Mean={param_data['mean']:.3f}, Std={param_data['std']:.3f}\n"
                else:
                    report += f"- **{param_name}**: Most common={param_data['most_common']}, "
                    report += f"Frequency={param_data['frequency']:.1%}\n"
            report += "\n"

        # 各窗口详情
        report += "## Window Details\n\n"
        report += "| Window | Train Period | Test Period | Train Sharpe | Test Sharpe |\n"
        report += "|--------|--------------|-------------|--------------|-------------|\n"
        for r in self.results:
            train_period = f"{r.train_start.strftime('%Y-%m-%d')} to {r.train_end.strftime('%Y-%m-%d')}"
            test_period = f"{r.test_start.strftime('%Y-%m-%d')} to {r.test_end.strftime('%Y-%m-%d')}"
            train_sharpe = r.train_metrics.get("sharpe_ratio", 0)
            test_sharpe = r.test_metrics.get("sharpe_ratio", 0)
            report += f"| {r.window_id} | {train_period} | {test_period} | {train_sharpe:.3f} | {test_sharpe:.3f} |\n"

        return report


# ============== 便捷函数 ==============

def run_walk_forward(
    data: pd.DataFrame,
    train_fn: Callable,
    predict_fn: Callable,
    evaluate_fn: Callable,
    config: Optional[WalkForwardConfig] = None,
    **kwargs,
) -> List[WindowResult]:
    """
    便捷执行 Walk-forward 分析

    Example:
        >>> results = run_walk_forward(
        ...     data=dataset,
        ...     train_fn=lambda data: model.fit(data),
        ...     predict_fn=lambda model, data: model.predict(data),
        ...     evaluate_fn=lambda pred, data: {"sharpe_ratio": calc_sharpe(pred)},
        ...     train_days=252,
        ...     test_days=63,
        ... )
    """
    if config is None:
        config = WalkForwardConfig(**kwargs)

    analyzer = WalkForwardAnalyzer(config)
    return analyzer.analyze(data, train_fn, predict_fn, evaluate_fn)


if __name__ == "__main__":
    # 测试
    print("Testing WalkForwardAnalyzer...")

    # 创建模拟数据
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    np.random.seed(42)

    data = pd.DataFrame({
        "datetime": dates,
        "close": 100 + np.cumsum(np.random.randn(len(dates)) * 0.01),
        "return": np.random.randn(len(dates)) * 0.02,
    })

    # 测试分割器
    config = WalkForwardConfig(
        train_days=252,
        test_days=63,
        step_days=63,
    )

    splitter = RollingWindowSplitter(config)
    splits = list(splitter.split(data))
    print(f"Number of splits: {len(splits)}")

    if splits:
        first_split = splits[0]
        print(f"First split train size: {len(first_split['train_data'])}")
        print(f"First split test size: {len(first_split['test_data'])}")

    print("\nWalkForward module loaded successfully")
