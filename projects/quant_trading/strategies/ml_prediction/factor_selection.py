"""
因子选择与降维模块

基于《A股因子挖掘库构建指南》最佳实践实现：
- PCA：主成分分析降维
- LASSO：L1正则化自动特征选择
- Elastic Net：L1+L2结合
- 相关性聚类：将高相关因子归为一类

用于解决多因子共线性问题和过拟合风险。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LassoCV, ElasticNetCV, Lasso, ElasticNet
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from scipy import stats

from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.precomputed_factors import (
    get_factor_precomputer
)

logger = get_logger(__name__)


@dataclass
class PCAResult:
    """PCA分析结果"""
    n_components: int
    explained_variance_ratio: np.ndarray
    cumulative_variance_ratio: np.ndarray
    components: pd.DataFrame
    transformed_data: pd.DataFrame
    feature_importance: pd.DataFrame  # 各因子对主成分的贡献

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_components': self.n_components,
            'explained_variance_ratio': self.explained_variance_ratio.tolist(),
            'cumulative_variance_ratio': self.cumulative_variance_ratio.tolist(),
            'total_variance_explained': float(self.cumulative_variance_ratio[-1]),
        }


@dataclass
class LASSOResult:
    """LASSO回归结果"""
    selected_factors: List[str]
    coefficients: pd.Series
    alpha: float
    cv_score: float
    r_squared: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_selected': len(self.selected_factors),
            'selected_factors': self.selected_factors,
            'alpha': self.alpha,
            'cv_score': self.cv_score,
            'r_squared': self.r_squared,
        }


@dataclass
class ElasticNetResult:
    """Elastic Net回归结果"""
    selected_factors: List[str]
    coefficients: pd.Series
    alpha: float
    l1_ratio: float
    cv_score: float
    r_squared: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_selected': len(self.selected_factors),
            'selected_factors': self.selected_factors,
            'alpha': self.alpha,
            'l1_ratio': self.l1_ratio,
            'cv_score': self.cv_score,
            'r_squared': self.r_squared,
        }


@dataclass
class CorrelationClusterResult:
    """相关性聚类结果"""
    n_clusters: int
    clusters: Dict[int, List[str]]  # 聚类ID -> 因子列表
    cluster_representatives: Dict[int, str]  # 聚类ID -> 代表性因子
    correlation_matrix: pd.DataFrame
    linkage_matrix: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_clusters': self.n_clusters,
            'clusters': self.clusters,
            'cluster_representatives': self.cluster_representatives,
        }


class FactorSelector:
    """
    因子选择器

    提供多种因子选择和降维方法，解决：
    1. 多重共线性（PCA、相关性聚类）
    2. 过拟合（LASSO、Elastic Net）
    3. 维度灾难（PCA、相关性聚类）
    """

    def __init__(
        self,
        factor_data: Optional[pd.DataFrame] = None,
        return_series: Optional[pd.Series] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None
    ):
        """
        初始化因子选择器

        Args:
            factor_data: 因子数据 (index=[date, stock], columns=[factors])
            return_series: 收益率序列 (index=[date, stock])
            date_range: 日期范围（如果factor_data为None时自动获取）
        """
        self.factor_data = factor_data
        self.return_series = return_series
        self.date_range = date_range
        self.precomputer = get_factor_precomputer()
        self._scaler = StandardScaler()

    def _load_data(
        self,
        factor_names: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        forward_period: int = 20
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        从预计算表加载数据

        Args:
            factor_names: 因子列表
            start_date: 开始日期
            end_date: 结束日期
            forward_period: 前瞻期（用于计算forward returns）

        Returns:
            (X, y): 因子数据矩阵和目标收益率
        """
        from projects.quant_trading.backtest.data_manager import DataManager

        if start_date is None:
            start_date = self.date_range[0] if self.date_range else datetime(2019, 1, 1)
        if end_date is None:
            end_date = self.date_range[1] if self.date_range else datetime(2024, 12, 31)

        dm = DataManager()
        trade_dates = dm.get_trade_dates(start_date, end_date)

        logger.info(f"Loading data for {len(factor_names)} factors, {len(trade_dates)} dates...")

        factor_list = []
        return_list = []

        for i, date in enumerate(trade_dates):
            # 跳过最后forward_period天
            if i + forward_period >= len(trade_dates):
                continue

            # 获取因子数据
            factors = self.precomputer.get_precomputed_factors(trade_date=date)

            if factors.empty:
                continue

            # 只保留需要的因子
            available_factors = [f for f in factor_names if f in factors.columns]
            if len(available_factors) < len(factor_names) * 0.5:  # 至少50%因子存在
                continue

            factors = factors[available_factors]

            # 删除缺失值过多的行
            factors = factors.dropna(thresh=len(available_factors) * 0.5)

            if len(factors) < 100:
                continue

            # 获取forward return
            target_date = trade_dates[i + forward_period]

            try:
                current_prices = dm.get_batch_stock_data(
                    ts_codes=list(factors.index),
                    fields=['close'],
                    trade_date=date
                )
                target_prices = dm.get_batch_stock_data(
                    ts_codes=list(factors.index),
                    fields=['close'],
                    trade_date=target_date
                )

                merged = current_prices[['close']].join(
                    target_prices[['close']],
                    rsuffix='_target',
                    how='inner'
                )
                merged['forward_return'] = merged['close_target'] / merged['close'] - 1

                # 对齐数据
                returns = merged['forward_return'].reindex(factors.index)

                # 添加日期索引
                factors['trade_date'] = date.strftime('%Y%m%d')
                factors.reset_index(inplace=True)
                factors.set_index(['trade_date', 'ts_code'], inplace=True)

                returns.index = factors.index

                factor_list.append(factors)
                return_list.append(returns)

            except Exception as e:
                logger.warning(f"Failed to get forward returns for {date}: {e}")
                continue

        if not factor_list:
            raise ValueError("No data loaded")

        X = pd.concat(factor_list)
        y = pd.concat(return_list)

        # 删除有缺失值的行
        valid_idx = X.dropna().index.intersection(y.dropna().index)
        X = X.loc[valid_idx]
        y = y.loc[valid_idx]

        # 删除trade_date列（如果存在）
        if 'trade_date' in X.columns:
            X = X.drop(columns=['trade_date'])

        logger.info(f"Loaded {len(X)} samples with {len(X.columns)} factors")

        return X, y

    def pca_transform(
        self,
        X: Optional[pd.DataFrame] = None,
        n_components: Optional[int] = None,
        variance_threshold: float = 0.95,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PCAResult:
        """
        PCA主成分分析降维

        将高维因子空间映射到低维主成分空间，
        保留大部分方差信息的同时消除共线性。

        Args:
            X: 因子数据矩阵（为None时自动加载）
            n_components: 主成分数量（为None时根据variance_threshold确定）
            variance_threshold: 方差解释比例阈值（默认95%）
            factor_names: 要包含的因子列表
            start_date: 开始日期（自动加载时使用）
            end_date: 结束日期（自动加载时使用）

        Returns:
            PCAResult: PCA分析结果
        """
        # 自动加载数据
        if X is None:
            if factor_names is None:
                raise ValueError("Must provide either X or factor_names")
            X, _ = self._load_data(factor_names, start_date, end_date)

        # 标准化
        X_scaled = self._scaler.fit_transform(X)

        # 确定主成分数量
        if n_components is None:
            # 先拟合全部，再根据阈值确定
            pca_full = PCA()
            pca_full.fit(X_scaled)
            cumsum = np.cumsum(pca_full.explained_variance_ratio_)
            n_components = np.argmax(cumsum >= variance_threshold) + 1

        # 拟合PCA
        pca = PCA(n_components=n_components)
        X_transformed = pca.fit_transform(X_scaled)

        # 构建结果
        components_df = pd.DataFrame(
            pca.components_,
            columns=X.columns,
            index=[f'PC{i+1}' for i in range(n_components)]
        )

        transformed_df = pd.DataFrame(
            X_transformed,
            columns=[f'PC{i+1}' for i in range(n_components)],
            index=X.index
        )

        # 计算各因子对主成分的贡献（按方差加权）
        feature_importance = pd.DataFrame(index=X.columns)
        for i in range(n_components):
            feature_importance[f'PC{i+1}'] = np.abs(pca.components_[i])

        feature_importance['weighted_importance'] = (
            feature_importance.multiply(pca.explained_variance_ratio_, axis=1).sum(axis=1)
        )
        feature_importance = feature_importance.sort_values(
            'weighted_importance', ascending=False
        )

        return PCAResult(
            n_components=n_components,
            explained_variance_ratio=pca.explained_variance_ratio_,
            cumulative_variance_ratio=np.cumsum(pca.explained_variance_ratio_),
            components=components_df,
            transformed_data=transformed_df,
            feature_importance=feature_importance
        )

    def lasso_select(
        self,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        alphas: Optional[np.ndarray] = None,
        cv: int = 5,
        max_iter: int = 2000
    ) -> LASSOResult:
        """
        LASSO回归特征选择

        使用L1正则化自动选择重要因子，
        不重要的因子系数会被压缩至0。

        Args:
            X: 因子数据矩阵
            y: 目标收益率
            factor_names: 要包含的因子列表
            start_date: 开始日期
            end_date: 结束日期
            alphas: 正则化参数搜索范围
            cv: 交叉验证折数
            max_iter: 最大迭代次数

        Returns:
            LASSOResult: LASSO回归结果
        """
        # 自动加载数据
        if X is None or y is None:
            if factor_names is None:
                raise ValueError("Must provide either (X, y) or factor_names")
            X, y = self._load_data(factor_names, start_date, end_date)

        # 标准化
        X_scaled = self._scaler.fit_transform(X)
        X_scaled_df = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)

        # 删除缺失值
        valid_idx = y.dropna().index
        X_scaled_df = X_scaled_df.loc[valid_idx]
        y = y.loc[valid_idx]

        # LASSO交叉验证
        if alphas is None:
            alphas = np.logspace(-4, 1, 50)

        lasso_cv = LassoCV(alphas=alphas, cv=cv, max_iter=max_iter, random_state=42)
        lasso_cv.fit(X_scaled_df, y)

        # 获取结果
        coefs = pd.Series(lasso_cv.coef_, index=X.columns)
        selected = coefs[coefs != 0].index.tolist()

        # 计算R²
        r2 = lasso_cv.score(X_scaled_df, y)

        return LASSOResult(
            selected_factors=selected,
            coefficients=coefs,
            alpha=lasso_cv.alpha_,
            cv_score=lasso_cv.score(X_scaled_df, y),
            r_squared=r2
        )

    def elastic_net_select(
        self,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        alphas: Optional[np.ndarray] = None,
        l1_ratios: Optional[np.ndarray] = None,
        cv: int = 5,
        max_iter: int = 2000
    ) -> ElasticNetResult:
        """
        Elastic Net回归特征选择

        L1+L2正则化结合，相比LASSO：
        - 处理高度相关因子的能力更强
        - 选择的因子更稳定

        Args:
            X: 因子数据矩阵
            y: 目标收益率
            factor_names: 要包含的因子列表
            start_date: 开始日期
            end_date: 结束日期
            alphas: 正则化参数搜索范围
            l1_ratios: L1/L2比例搜索范围
            cv: 交叉验证折数
            max_iter: 最大迭代次数

        Returns:
            ElasticNetResult: Elastic Net回归结果
        """
        # 自动加载数据
        if X is None or y is None:
            if factor_names is None:
                raise ValueError("Must provide either (X, y) or factor_names")
            X, y = self._load_data(factor_names, start_date, end_date)

        # 标准化
        X_scaled = self._scaler.fit_transform(X)
        X_scaled_df = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)

        # 删除缺失值
        valid_idx = y.dropna().index
        X_scaled_df = X_scaled_df.loc[valid_idx]
        y = y.loc[valid_idx]

        # Elastic Net交叉验证
        if alphas is None:
            alphas = np.logspace(-4, 1, 30)
        if l1_ratios is None:
            l1_ratios = [0.1, 0.3, 0.5, 0.7, 0.9, 0.95, 0.99]

        enet_cv = ElasticNetCV(
            alphas=alphas,
            l1_ratio=l1_ratios,
            cv=cv,
            max_iter=max_iter,
            random_state=42
        )
        enet_cv.fit(X_scaled_df, y)

        # 获取结果
        coefs = pd.Series(enet_cv.coef_, index=X.columns)
        selected = coefs[coefs != 0].index.tolist()

        # 计算R²
        r2 = enet_cv.score(X_scaled_df, y)

        return ElasticNetResult(
            selected_factors=selected,
            coefficients=coefs,
            alpha=enet_cv.alpha_,
            l1_ratio=enet_cv.l1_ratio_,
            cv_score=enet_cv.score(X_scaled_df, y),
            r_squared=r2
        )

    def correlation_clustering(
        self,
        X: Optional[pd.DataFrame] = None,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        threshold: float = 0.7,
        n_clusters: Optional[int] = None,
        linkage_method: str = 'average'
    ) -> CorrelationClusterResult:
        """
        相关性聚类

        将高相关的因子归为一类，每类选一个代表性因子。
        解决多重共线性问题，同时保留信息。

        Args:
            X: 因子数据矩阵
            factor_names: 要包含的因子列表
            start_date: 开始日期
            end_date: 结束日期
            threshold: 相关性阈值（用于确定聚类数量）
            n_clusters: 聚类数量（为None时根据threshold自动确定）
            linkage_method: 层次聚类方法

        Returns:
            CorrelationClusterResult: 聚类结果
        """
        # 自动加载数据
        if X is None:
            if factor_names is None:
                raise ValueError("Must provide either X or factor_names")
            X, _ = self._load_data(factor_names, start_date, end_date)

        # 计算相关性矩阵
        corr_matrix = X.corr().abs()

        # 处理缺失值
        corr_matrix = corr_matrix.fillna(0)

        # 距离矩阵 = 1 - 相关性
        distance_matrix = 1 - corr_matrix

        # 层次聚类
        linkage_matrix = linkage(
            squareform(distance_matrix.values),
            method=linkage_method
        )

        # 确定聚类数量
        if n_clusters is None:
            # 根据阈值确定
            # 当聚类内最大距离 <= (1 - threshold)时停止
            max_distance = 1 - threshold
            n_clusters = len(fcluster(linkage_matrix, max_distance, criterion='distance'))

        # 执行聚类
        cluster_labels = fcluster(linkage_matrix, n_clusters, criterion='maxclust')

        # 构建聚类结果
        clusters = defaultdict(list)
        for factor, label in zip(X.columns, cluster_labels):
            clusters[label].append(factor)

        # 选择每类的代表性因子（与同类其他因子相关性最高的）
        representatives = {}
        for label, factors in clusters.items():
            if len(factors) == 1:
                representatives[label] = factors[0]
            else:
                # 计算每个因子与同类的平均相关性
                avg_corrs = {}
                for f in factors:
                    others = [x for x in factors if x != f]
                    avg_corr = corr_matrix.loc[f, others].mean()
                    avg_corrs[f] = avg_corr

                # 选择平均相关性最高的作为代表
                representatives[label] = max(avg_corrs, key=avg_corrs.get)

        return CorrelationClusterResult(
            n_clusters=n_clusters,
            clusters=dict(clusters),
            cluster_representatives=representatives,
            correlation_matrix=corr_matrix,
            linkage_matrix=linkage_matrix
        )

    def comprehensive_selection(
        self,
        factor_names: List[str],
        y: Optional[pd.Series] = None,
        pca_variance: float = 0.95,
        corr_threshold: float = 0.7,
        lasso_alpha: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        综合因子选择

        结合多种方法，提供全面的因子选择建议：
        1. PCA：建议主成分数量和贡献度
        2. 相关性聚类：建议代表性因子
        3. LASSO：基于预测能力的筛选

        Args:
            factor_names: 初始因子列表
            y: 目标收益率（LASSO需要）
            pca_variance: PCA方差阈值
            corr_threshold: 相关性聚类阈值
            lasso_alpha: LASSO正则化参数

        Returns:
            综合选择建议
        """
        results = {}

        logger.info("Running comprehensive factor selection...")

        # 1. PCA分析
        logger.info("1. Running PCA...")
        try:
            pca_result = self.pca_transform(
                factor_names=factor_names,
                variance_threshold=pca_variance
            )
            results['pca'] = {
                'n_components': pca_result.n_components,
                'explained_variance': pca_result.cumulative_variance_ratio[-1],
                'top_contributors': pca_result.feature_importance.head(10).to_dict(),
            }
        except Exception as e:
            logger.error(f"PCA failed: {e}")
            results['pca'] = {'error': str(e)}

        # 2. 相关性聚类
        logger.info("2. Running correlation clustering...")
        try:
            cluster_result = self.correlation_clustering(
                factor_names=factor_names,
                threshold=corr_threshold
            )
            results['clustering'] = {
                'n_clusters': cluster_result.n_clusters,
                'representatives': list(cluster_result.cluster_representatives.values()),
                'clusters': cluster_result.clusters,
            }
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            results['clustering'] = {'error': str(e)}

        # 3. LASSO选择（如果有目标收益率）
        if y is not None:
            logger.info("3. Running LASSO...")
            try:
                lasso_result = self.lasso_select(
                    X=self.factor_data,
                    y=y,
                    alphas=np.array([lasso_alpha]) if lasso_alpha else None
                )
                results['lasso'] = {
                    'n_selected': len(lasso_result.selected_factors),
                    'selected_factors': lasso_result.selected_factors,
                    'alpha': lasso_result.alpha,
                    'r_squared': lasso_result.r_squared,
                }
            except Exception as e:
                logger.error(f"LASSO failed: {e}")
                results['lasso'] = {'error': str(e)}

        # 4. 综合建议
        logger.info("4. Generating recommendations...")
        recommendations = self._generate_recommendations(results, factor_names)
        results['recommendations'] = recommendations

        return results

    def _generate_recommendations(
        self,
        results: Dict[str, Any],
        original_factors: List[str]
    ) -> Dict[str, Any]:
        """生成综合建议"""
        recommendations = {
            'original_count': len(original_factors),
            'methods_applied': [],
            'consensus_factors': [],
            'suggested_factor_count': 0,
        }

        all_selected = []

        if 'clustering' in results and 'representatives' in results['clustering']:
            recommendations['methods_applied'].append('correlation_clustering')
            all_selected.append(set(results['clustering']['representatives']))

        if 'lasso' in results and 'selected_factors' in results['lasso']:
            recommendations['methods_applied'].append('lasso')
            all_selected.append(set(results['lasso']['selected_factors']))

        if 'pca' in results and 'top_contributors' in results['pca']:
            recommendations['methods_applied'].append('pca')
            # PCA前10贡献因子
            pca_top = list(results['pca']['top_contributors'].keys())[:10]
            all_selected.append(set(pca_top))

        # 计算共识因子（被多数方法选中）
        if all_selected:
            from collections import Counter
            factor_votes = Counter()
            for selected in all_selected:
                for f in selected:
                    factor_votes[f] += 1

            # 被至少2种方法选中的因子
            consensus = [f for f, votes in factor_votes.items() if votes >= 2]
            recommendations['consensus_factors'] = consensus
            recommendations['suggested_factor_count'] = len(consensus)

        return recommendations


def quick_factor_reduction(
    factor_names: List[str],
    method: str = 'correlation',
    target_count: int = 20,
    **kwargs
) -> List[str]:
    """
    快速因子降维

    便捷函数，根据指定方法快速降维到目标数量。

    Args:
        factor_names: 初始因子列表
        method: 降维方法 ('correlation', 'pca', 'lasso')
        target_count: 目标因子数量
        **kwargs: 传递给具体方法的参数

    Returns:
        降维后的因子列表
    """
    selector = FactorSelector()

    if method == 'correlation':
        result = selector.correlation_clustering(
            factor_names=factor_names,
            n_clusters=target_count,
            **kwargs
        )
        return list(result.cluster_representatives.values())

    elif method == 'pca':
        result = selector.pca_transform(
            factor_names=factor_names,
            n_components=target_count,
            **kwargs
        )
        # 返回贡献度最高的因子
        return result.feature_importance.head(target_count).index.tolist()

    elif method == 'lasso':
        # LASSO没有直接控制数量的参数，需要通过alpha调节
        # 这里使用一个较大的alpha来减少因子数量
        result = selector.lasso_select(
            factor_names=factor_names,
            **kwargs
        )
        return result.selected_factors[:target_count]

    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--pca":
        # PCA示例
        factor_names = [
            'pe_ttm', 'pb', 'ps_ttm', 'dividend_yield', 'total_mv',
            'return_20d', 'return_60d', 'volatility_20d', 'volatility_60d',
            'main_net_inflow', 'net_inflow_5d', 'net_inflow_20d',
            'roe', 'roa', 'gross_margin', 'net_margin',
        ]

        print("Running PCA...")
        selector = FactorSelector()
        result = selector.pca_transform(factor_names=factor_names, variance_threshold=0.95)

        print(f"\nPCA Results:")
        print(f"  Components: {result.n_components}")
        print(f"  Explained Variance: {result.cumulative_variance_ratio[-1]:.2%}")
        print(f"\nTop Factor Contributions:")
        print(result.feature_importance.head(10))

    elif len(sys.argv) > 1 and sys.argv[1] == "--cluster":
        # 相关性聚类示例
        factor_names = [
            'pe_ttm', 'pb', 'ps_ttm', 'total_mv',
            'return_20d', 'return_60d', 'return_120d',
            'volatility_20d', 'volatility_60d',
            'roe', 'roa', 'gross_margin',
        ]

        print("Running Correlation Clustering...")
        selector = FactorSelector()
        result = selector.correlation_clustering(
            factor_names=factor_names,
            threshold=0.7
        )

        print(f"\nClustering Results:")
        print(f"  Clusters: {result.n_clusters}")
        print(f"\nRepresentative Factors:")
        for label, rep in result.cluster_representatives.items():
            cluster_factors = result.clusters[label]
            print(f"  Cluster {label}: {rep} (from {cluster_factors})")

    else:
        print("Usage:")
        print("  python factor_selection.py --pca")
        print("  python factor_selection.py --cluster")
