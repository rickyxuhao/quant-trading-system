"""
模型可解释性模块

基于SHAP (SHapley Additive exPlanations) 实现：
- 全局特征重要性
- 单样本预测解释
- 因子贡献度分解
- 交互效应分析

用于增强对机器学习模型决策的理解和信任。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)

# SHAP可选导入（避免强依赖）
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not installed. Model interpretability features will be limited.")


@dataclass
class SHAPExplanation:
    """单样本SHAP解释结果"""
    base_value: float
    prediction: float
    shap_values: Dict[str, float]
    feature_values: Dict[str, float]

    def top_contributors(self, n: int = 5) -> List[Tuple[str, float]]:
        """获取最重要的贡献因子"""
        sorted_contrib = sorted(
            self.shap_values.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        return sorted_contrib[:n]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'base_value': self.base_value,
            'prediction': self.prediction,
            'shap_values': self.shap_values,
            'top_positive': [(k, v) for k, v in self.shap_values.items() if v > 0][:5],
            'top_negative': [(k, v) for k, v in self.shap_values.items() if v < 0][:5],
        }


@dataclass
class GlobalImportance:
    """全局特征重要性"""
    feature_names: List[str]
    mean_abs_shap: pd.Series
    shap_std: pd.Series
    feature_importance_rank: pd.Series

    def to_dict(self) -> Dict[str, Any]:
        return {
            'top_features': self.mean_abs_shap.head(10).to_dict(),
            'importance_rank': self.feature_importance_rank.to_dict(),
        }


class ModelExplainer:
    """
    模型解释器

    基于SHAP提供模型决策的可解释性：
    1. 全局特征重要性 - 哪些因子对模型最重要
    2. 单样本解释 - 为什么模型做出这个预测
    3. 因子贡献度分解 - 各因子对预测的具体贡献
    4. 交互效应分析 - 因子之间的交互作用
    """

    def __init__(self, model, feature_names: Optional[List[str]] = None):
        """
        初始化模型解释器

        Args:
            model: 训练好的模型（支持sklearn/xgboost/lightgbm）
            feature_names: 特征名称列表
        """
        if not SHAP_AVAILABLE:
            raise ImportError(
                "SHAP is required for model interpretability. "
                "Install with: pip install shap"
            )

        self.model = model
        self.feature_names = feature_names
        self.explainer = None
        self._background_data = None

    def fit_explainer(
        self,
        X_background: Optional[pd.DataFrame] = None,
        sample_size: int = 100
    ) -> 'ModelExplainer':
        """
        拟合SHAP解释器

        Args:
            X_background: 背景数据（用于计算baseline）
            sample_size: 采样大小

        Returns:
            self
        """
        if X_background is not None:
            if len(X_background) > sample_size:
                self._background_data = shap.sample(X_background, sample_size)
            else:
                self._background_data = X_background

        # 根据模型类型选择合适的解释器
        model_type = type(self.model).__name__.lower()

        if 'xgb' in model_type or 'lgb' in model_type or 'catboost' in model_type:
            # 树模型使用TreeExplainer
            self.explainer = shap.TreeExplainer(self.model)
        elif hasattr(self.model, 'predict_proba'):
            # 支持概率预测的模型使用KernelExplainer
            self.explainer = shap.KernelExplainer(
                self.model.predict_proba if hasattr(self.model, 'predict_proba') else self.model.predict,
                self._background_data or shap.sample(X_background, sample_size)
            )
        else:
            # 默认使用KernelExplainer
            self.explainer = shap.KernelExplainer(
                self.model.predict,
                self._background_data or shap.sample(X_background, sample_size)
            )

        logger.info(f"Fitted {type(self.explainer).__name__}")
        return self

    def explain_sample(
        self,
        X: pd.DataFrame,
        index: Optional[int] = None
    ) -> Union[SHAPExplanation, List[SHAPExplanation]]:
        """
        解释单样本或多样本的预测

        Args:
            X: 特征数据（单行或多行）
            index: 指定样本索引（为None时返回全部）

        Returns:
            SHAPExplanation 或 SHAPExplanation列表
        """
        if self.explainer is None:
            raise ValueError("Explainer not fitted. Call fit_explainer() first.")

        # 确保是DataFrame
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.feature_names)

        # 计算SHAP值
        shap_values = self.explainer.shap_values(X)

        # 处理二分类情况（shap_values是list）
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # 取正类的SHAP值

        explanations = []

        for i in range(len(X)):
            row_shap = shap_values[i] if len(shap_values.shape) > 1 else shap_values

            shap_dict = dict(zip(X.columns, row_shap))
            feature_dict = dict(zip(X.columns, X.iloc[i].values))

            explanation = SHAPExplanation(
                base_value=self.explainer.expected_value if hasattr(self.explainer, 'expected_value') else 0,
                prediction=self.model.predict(X.iloc[i:i+1])[0],
                shap_values=shap_dict,
                feature_values=feature_dict
            )
            explanations.append(explanation)

        if index is not None:
            return explanations[index]

        return explanations[0] if len(explanations) == 1 else explanations

    def get_global_importance(
        self,
        X: pd.DataFrame,
        plot: bool = False,
        save_path: Optional[str] = None
    ) -> GlobalImportance:
        """
        获取全局特征重要性

        Args:
            X: 特征数据
            plot: 是否生成可视化
            save_path: 保存路径

        Returns:
            GlobalImportance: 全局重要性结果
        """
        if self.explainer is None:
            raise ValueError("Explainer not fitted. Call fit_explainer() first.")

        # 计算SHAP值
        shap_values = self.explainer.shap_values(X)

        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        # 计算统计指标
        mean_abs_shap = pd.Series(np.abs(shap_values).mean(axis=0), index=X.columns)
        shap_std = pd.Series(shap_values.std(axis=0), index=X.columns)

        # 排序
        mean_abs_shap = mean_abs_shap.sort_values(ascending=False)
        feature_rank = pd.Series(
            range(1, len(mean_abs_shap) + 1),
            index=mean_abs_shap.index
        )

        # 可视化
        if plot:
            self._plot_importance(shap_values, X, save_path)

        return GlobalImportance(
            feature_names=list(X.columns),
            mean_abs_shap=mean_abs_shap,
            shap_std=shap_std,
            feature_importance_rank=feature_rank
        )

    def _plot_importance(
        self,
        shap_values: np.ndarray,
        X: pd.DataFrame,
        save_path: Optional[str] = None
    ):
        """绘制重要性图表"""
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X, show=False)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved importance plot to {save_path}")
        else:
            plt.show()

        plt.close()

    def explain_factor_contribution(
        self,
        X: pd.DataFrame,
        factor_name: str,
        y_true: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        分析单个因子的贡献度

        Args:
            X: 特征数据
            factor_name: 因子名称
            y_true: 真实标签（用于验证）

        Returns:
            因子贡献度分析
        """
        if factor_name not in X.columns:
            raise ValueError(f"Factor {factor_name} not found in data")

        # 计算SHAP值
        shap_values = self.explainer.shap_values(X)

        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        factor_idx = list(X.columns).index(factor_name)
        factor_shap = shap_values[:, factor_idx]
        factor_values = X[factor_name].values

        # 分析因子值与SHAP值的关系
        correlation = np.corrcoef(factor_values, factor_shap)[0, 1]

        # 分位数分析
        quantiles = pd.qcut(factor_values, q=5, duplicates='drop')
        quantile_contrib = pd.Series(factor_shap).groupby(quantiles).mean()

        result = {
            'factor_name': factor_name,
            'mean_contribution': float(np.mean(factor_shap)),
            'contribution_std': float(np.std(factor_shap)),
            'correlation_with_value': float(correlation),
            'contribution_by_quantile': quantile_contrib.to_dict(),
        }

        if y_true is not None:
            # 分析因子与真实标签的关系
            result['correlation_with_target'] = float(
                np.corrcoef(factor_values, y_true.values)[0, 1]
            )

        return result

    def analyze_interactions(
        self,
        X: pd.DataFrame,
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        分析因子交互效应

        Args:
            X: 特征数据
            top_n: 返回前N个重要交互

        Returns:
            DataFrame: 交互效应分析
        """
        if not hasattr(self.explainer, 'shap_interaction_values'):
            logger.warning("Current explainer does not support interaction values")
            return pd.DataFrame()

        # 计算交互SHAP值
        interaction_values = self.explainer.shap_interaction_values(X)

        if isinstance(interaction_values, list):
            interaction_values = interaction_values[1]

        # 计算平均绝对交互值
        mean_interactions = np.abs(interaction_values).mean(axis=0)

        # 提取非对角线元素（真正的交互）
        interactions = []
        n_features = len(X.columns)

        for i in range(n_features):
            for j in range(i + 1, n_features):
                interactions.append({
                    'factor_1': X.columns[i],
                    'factor_2': X.columns[j],
                    'interaction_strength': mean_interactions[i, j],
                })

        df = pd.DataFrame(interactions)
        df = df.sort_values('interaction_strength', ascending=False)

        return df.head(top_n)

    def generate_explanation_report(
        self,
        X: pd.DataFrame,
        sample_indices: Optional[List[int]] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成完整的解释报告

        Args:
            X: 特征数据
            sample_indices: 要详细解释的样本索引
            output_dir: 输出目录

        Returns:
            报告数据
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'n_samples': len(X),
            'n_features': len(X.columns),
        }

        # 全局重要性
        logger.info("Computing global importance...")
        global_imp = self.get_global_importance(X)
        report['global_importance'] = global_imp.to_dict()

        # 样本解释
        if sample_indices:
            logger.info(f"Explaining {len(sample_indices)} samples...")
            sample_explanations = []
            for idx in sample_indices:
                explanation = self.explain_sample(X.iloc[idx:idx+1])
                sample_explanations.append({
                    'index': idx,
                    'explanation': explanation.to_dict()
                })
            report['sample_explanations'] = sample_explanations

        # 交互效应
        logger.info("Analyzing interactions...")
        interactions = self.analyze_interactions(X, top_n=10)
        if not interactions.empty:
            report['top_interactions'] = interactions.to_dict('records')

        # 保存报告
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            report_file = output_path / f"explanation_report_{datetime.now():%Y%m%d_%H%M%S}.json"
            import json
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Saved report to {report_file}")

        return report


class FactorAttribution:
    """
    因子归因分析

    不依赖SHAP的简化版本，用于计算因子对收益的贡献。
    """

    def __init__(self, model, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names

    def attribute_returns(
        self,
        X: pd.DataFrame,
        returns: pd.Series,
        method: str = 'sensitivity'
    ) -> pd.DataFrame:
        """
        归因收益到各个因子

        Args:
            X: 因子暴露
            returns: 实际收益
            method: 归因方法 ('sensitivity', 'contribution')

        Returns:
            DataFrame: 各因子的归因结果
        """
        if method == 'sensitivity':
            return self._sensitivity_analysis(X, returns)
        elif method == 'contribution':
            return self._contribution_analysis(X, returns)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _sensitivity_analysis(
        self,
        X: pd.DataFrame,
        returns: pd.Series
    ) -> pd.DataFrame:
        """敏感性分析"""
        results = []

        for factor in self.feature_names:
            if factor not in X.columns:
                continue

            # 计算因子与收益的相关性
            corr = returns.corr(X[factor])

            # 计算因子的IC
            ic = returns.corr(X[factor], method='spearman')

            results.append({
                'factor': factor,
                'correlation': corr,
                'ic': ic,
                'abs_correlation': abs(corr),
                'abs_ic': abs(ic),
            })

        return pd.DataFrame(results).sort_values('abs_ic', ascending=False)

    def _contribution_analysis(
        self,
        X: pd.DataFrame,
        returns: pd.Series
    ) -> pd.DataFrame:
        """贡献度分析"""
        # 使用回归系数作为贡献度
        from sklearn.linear_model import LinearRegression

        # 标准化因子
        X_std = (X - X.mean()) / X.std()

        # 回归
        reg = LinearRegression()
        reg.fit(X_std, returns)

        results = []
        for i, factor in enumerate(self.feature_names):
            if factor not in X.columns:
                continue

            coefficient = reg.coef_[i]
            contribution = coefficient * X_std[factor].mean()

            results.append({
                'factor': factor,
                'coefficient': coefficient,
                'avg_contribution': contribution,
                'abs_contribution': abs(contribution),
            })

        return pd.DataFrame(results).sort_values('abs_contribution', ascending=False)


def explain_prediction_difference(
    explainer: ModelExplainer,
    X1: pd.DataFrame,
    X2: pd.DataFrame,
    top_n: int = 5
) -> Dict[str, Any]:
    """
    解释两个预测之间的差异

    Args:
        explainer: 模型解释器
        X1: 第一个样本
        X2: 第二个样本
        top_n: 显示前N个差异因子

    Returns:
        差异分析结果
    """
    exp1 = explainer.explain_sample(X1)
    exp2 = explainer.explain_sample(X2)

    # 计算SHAP值差异
    diff = {}
    for factor in exp1.shap_values.keys():
        diff[factor] = exp2.shap_values.get(factor, 0) - exp1.shap_values.get(factor, 0)

    # 排序
    sorted_diff = sorted(diff.items(), key=lambda x: abs(x[1]), reverse=True)

    return {
        'prediction_1': exp1.prediction,
        'prediction_2': exp2.prediction,
        'prediction_diff': exp2.prediction - exp1.prediction,
        'top_diff_factors': sorted_diff[:top_n],
        'all_differences': diff,
    }


if __name__ == "__main__":
    import sys

    print("Model Interpretability Module")
    print(f"SHAP available: {SHAP_AVAILABLE}")

    if not SHAP_AVAILABLE:
        print("\nTo use SHAP features, install with:")
        print("  pip install shap")
        sys.exit(0)

    print("\nUsage example:")
    print("""
    from model_interpretability import ModelExplainer

    # After training your model
    explainer = ModelExplainer(model, feature_names)
    explainer.fit_explainer(X_train)

    # Global importance
    importance = explainer.get_global_importance(X_test, plot=True)

    # Explain single prediction
    explanation = explainer.explain_sample(X_test.iloc[0:1])
    print(explanation.top_contributors(5))
    """)
