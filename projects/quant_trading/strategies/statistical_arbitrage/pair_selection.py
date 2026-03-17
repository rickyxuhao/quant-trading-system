"""
配对筛选模块 - 基于相关系数和距离法的配对选择

功能：
- 同行业配对筛选
- 相关系数计算（60日滚动）
- 距离法（价格序列欧氏距离）
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from scipy.spatial.distance import euclidean
from scipy.stats import pearsonr

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SelectionCriteria:
    """配对筛选条件"""

    # 相关系数阈值
    min_correlation: float = 0.8

    # 距离法阈值（标准化后的欧氏距离）
    max_distance: float = 2.0

    # 最小共同交易日
    min_common_days: int = 60

    # 价格水平比率限制（避免价格差异过大）
    max_price_ratio: float = 5.0

    # 市值限制
    min_market_cap: float = 1e9  # 10亿


@dataclass
class PairCandidate:
    """配对候选"""

    stock_a: str
    stock_b: str
    correlation: float
    distance: float
    price_ratio: float
    half_life: Optional[float] = None
    cointegration_pvalue: Optional[float] = None
    score: float = 0.0

    def __repr__(self) -> str:
        return (
            f"Pair({self.stock_a}-{self.stock_b}, "
            f"corr={self.correlation:.3f}, "
            f"dist={self.distance:.3f})"
        )


class PairSelector:
    """配对选择器"""

    def __init__(self, criteria: Optional[SelectionCriteria] = None):
        self.criteria = criteria or SelectionCriteria()
        self.candidates: list[PairCandidate] = []

    def select_by_correlation(
        self, price_data: pd.DataFrame, window: int = 60
    ) -> list[PairCandidate]:
        """
        基于相关系数筛选配对

        Args:
            price_data: 价格数据DataFrame，列为股票代码
            window: 滚动窗口天数

        Returns:
            配对候选列表
        """
        stocks = price_data.columns.tolist()
        n = len(stocks)

        candidates = []

        for i in range(n):
            for j in range(i + 1, n):
                stock_a, stock_b = stocks[i], stocks[j]

                # 获取共同交易日的数据
                pair_data = price_data[[stock_a, stock_b]].dropna()

                if len(pair_data) < self.criteria.min_common_days:
                    continue

                # 计算相关系数
                corr, _ = pearsonr(pair_data[stock_a], pair_data[stock_b])

                if corr >= self.criteria.min_correlation:
                    # 计算价格比率
                    price_ratio = pair_data[stock_a].mean() / pair_data[stock_b].mean()

                    if (
                        price_ratio > self.criteria.max_price_ratio
                        or price_ratio < 1 / self.criteria.max_price_ratio
                    ):
                        continue

                    candidate = PairCandidate(
                        stock_a=stock_a,
                        stock_b=stock_b,
                        correlation=corr,
                        distance=0.0,  # 稍后计算
                        price_ratio=price_ratio,
                    )
                    candidates.append(candidate)

        self.candidates = candidates
        logger.info(f"相关系数筛选: 找到 {len(candidates)} 对候选")

        return sorted(candidates, key=lambda x: x.correlation, reverse=True)

    def select_by_distance(
        self, price_data: pd.DataFrame, normalize: bool = True
    ) -> list[PairCandidate]:
        """
        基于距离法（欧氏距离）筛选配对

        Args:
            price_data: 价格数据DataFrame
            normalize: 是否标准化价格序列

        Returns:
            配对候选列表
        """
        stocks = price_data.columns.tolist()
        n = len(stocks)

        candidates = []

        for i in range(n):
            for j in range(i + 1, n):
                stock_a, stock_b = stocks[i], stocks[j]

                pair_data = price_data[[stock_a, stock_b]].dropna()

                if len(pair_data) < self.criteria.min_common_days:
                    continue

                # 标准化价格序列
                series_a = pair_data[stock_a].values
                series_b = pair_data[stock_b].values

                if normalize:
                    series_a = (series_a - series_a.mean()) / series_a.std()
                    series_b = (series_b - series_b.mean()) / series_b.std()

                # 计算欧氏距离
                distance = euclidean(series_a, series_b)

                if distance <= self.criteria.max_distance:
                    # 同时计算相关系数
                    corr, _ = pearsonr(pair_data[stock_a], pair_data[stock_b])

                    candidate = PairCandidate(
                        stock_a=stock_a,
                        stock_b=stock_b,
                        correlation=corr,
                        distance=distance,
                        price_ratio=pair_data[stock_a].mean() / pair_data[stock_b].mean(),
                    )
                    candidates.append(candidate)

        self.candidates = candidates
        logger.info(f"距离法筛选: 找到 {len(candidates)} 对候选")

        # 按距离升序排序（距离越小越好）
        return sorted(candidates, key=lambda x: x.distance)

    def combine_methods(
        self, price_data: pd.DataFrame, corr_weight: float = 0.6, dist_weight: float = 0.4
    ) -> list[PairCandidate]:
        """
        综合相关系数法和距离法筛选

        Args:
            price_data: 价格数据DataFrame
            corr_weight: 相关系数权重
            dist_weight: 距离法权重

        Returns:
            综合评分后的配对候选列表
        """
        # 分别计算两种方法
        corr_candidates = {
            f"{c.stock_a}-{c.stock_b}": c for c in self.select_by_correlation(price_data)
        }
        dist_candidates = {
            f"{c.stock_a}-{c.stock_b}": c for c in self.select_by_distance(price_data)
        }

        # 合并候选
        all_pairs = set(corr_candidates.keys()) | set(dist_candidates.keys())

        combined = []
        for pair_key in all_pairs:
            corr_cand = corr_candidates.get(pair_key)
            dist_cand = dist_candidates.get(pair_key)

            if corr_cand and dist_cand:
                # 同时满足两种方法，计算综合得分
                # 相关系数越高越好，距离越小越好
                corr_score = (corr_cand.correlation - self.criteria.min_correlation) / (
                    1 - self.criteria.min_correlation
                )
                dist_score = 1 - (dist_cand.distance / self.criteria.max_distance)

                total_score = corr_weight * corr_score + dist_weight * dist_score

                candidate = PairCandidate(
                    stock_a=corr_cand.stock_a,
                    stock_b=corr_cand.stock_b,
                    correlation=corr_cand.correlation,
                    distance=dist_cand.distance,
                    price_ratio=corr_cand.price_ratio,
                    score=total_score,
                )
                combined.append(candidate)

        self.candidates = combined
        logger.info(f"综合筛选: 找到 {len(combined)} 对候选")

        return sorted(combined, key=lambda x: x.score, reverse=True)

    def filter_by_sector(
        self, candidates: list[PairCandidate], sector_mapping: dict[str, str]
    ) -> list[PairCandidate]:
        """
        按行业过滤，只保留同行业配对

        Args:
            candidates: 配对候选列表
            sector_mapping: {股票代码: 行业名称}

        Returns:
            过滤后的候选列表
        """
        filtered = []
        for cand in candidates:
            sector_a = sector_mapping.get(cand.stock_a)
            sector_b = sector_mapping.get(cand.stock_b)

            if sector_a and sector_b and sector_a == sector_b:
                filtered.append(cand)

        logger.info(f"行业过滤: {len(candidates)} -> {len(filtered)}")
        return filtered

    def get_top_pairs(self, n: int = 10) -> list[PairCandidate]:
        """获取前N对配对"""
        return self.candidates[:n]

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        return pd.DataFrame(
            [
                {
                    "stock_a": c.stock_a,
                    "stock_b": c.stock_b,
                    "correlation": c.correlation,
                    "distance": c.distance,
                    "price_ratio": c.price_ratio,
                    "half_life": c.half_life,
                    "cointegration_pvalue": c.cointegration_pvalue,
                    "score": c.score,
                }
                for c in self.candidates
            ]
        )
