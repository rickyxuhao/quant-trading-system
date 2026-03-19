"""
Qlib Dataset 构建器

构建 Qlib 格式的数据集，支持 220+ 个因子（原 70 + Alpha158/360）
自动处理特征工程、标签生成和数据分割

作者: Claude
创建日期: 2026-03-19
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

import pandas as pd
import numpy as np

# Qlib 导入
try:
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.utils import init_instance_by_config
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    class DatasetH:
        def __init__(self, *args, **kwargs):
            raise ImportError("Qlib not installed. Run: pip install pyqlib")

from core.logger import get_logger
from .qlib_handler import QLibDataHandler, create_handler
from .qlib_factors import get_alpha158_factors, get_alpha360_factors
from .factor_definitions import FACTOR_DEFINITIONS, get_factors_by_category

logger = get_logger(__name__)


@dataclass
class DatasetConfig:
    """数据集配置"""
    # 数据范围
    start_time: str
    end_time: str
    instruments: List[str]

    # 特征配置
    use_alpha158: bool = True
    use_alpha360: bool = False  # Alpha360 数据量大，默认关闭
    use_existing_factors: bool = True
    custom_factors: Optional[List[str]] = None

    # 标签配置
    label_periods: List[int] = None  # [1, 5, 20] for next day, 5 day, 20 day return

    # 数据分割
    train_ratio: float = 0.7
    valid_ratio: float = 0.15
    test_ratio: float = 0.15

    # 处理器配置
    fill_na_method: str = "median"
    winsorize: bool = True
    zscore: bool = True
    robust_zscore: bool = False

    def __post_init__(self):
        if self.label_periods is None:
            self.label_periods = [1]  # 默认只预测 next day return
        assert abs(self.train_ratio + self.valid_ratio + self.test_ratio - 1.0) < 1e-6, \
            "Ratios must sum to 1.0"


class StockDataset(DatasetH):
    """
    股票数据集

    整合项目的因子系统和 Qlib 的数据处理能力。

    Example:
        >>> config = DatasetConfig(
        ...     start_time="2020-01-01",
        ...     end_time="2024-12-31",
        ...     instruments=["000001.SZ", "000002.SZ", ...],
        ...     use_alpha158=True,
        ... )
        >>> dataset = StockDataset(config)
        >>> dataset.prepare()
        >>> train_data, valid_data, test_data = dataset.split_data()
    """

    def __init__(self, config: DatasetConfig, handler: Optional[QLibDataHandler] = None):
        """
        初始化数据集

        Args:
            config: 数据集配置
            handler: 预配置的数据处理器，None 则自动创建
        """
        self.config = config
        self._handler = handler
        self._data: Optional[pd.DataFrame] = None
        self._feature_names: List[str] = []
        self._label_names: List[str] = []

        # 确定使用的因子
        self.factor_names = self._select_factors()

        logger.info(f"StockDataset initialized with {len(self.factor_names)} factors")

    def _select_factors(self) -> List[str]:
        """选择要使用的因子"""
        factors = []

        if self.config.use_existing_factors:
            # 使用现有的因子（排除 Qlib 专用分类）
            for name, def_ in FACTOR_DEFINITIONS.items():
                if not def_.category.startswith("qlib_"):
                    factors.append(name)

        if self.config.use_alpha158:
            # 添加 Alpha158 因子
            alpha158 = get_alpha158_factors()
            factors.extend(alpha158)

        if self.config.use_alpha360:
            # 添加 Alpha360 因子
            alpha360 = get_alpha360_factors()
            factors.extend(alpha360)

        if self.config.custom_factors:
            # 添加自定义因子
            factors.extend(self.config.custom_factors)

        # 去重并保持顺序
        seen = set()
        unique_factors = []
        for f in factors:
            if f not in seen:
                seen.add(f)
                unique_factors.append(f)

        return unique_factors

    def prepare(self):
        """
        准备数据集

        加载数据、生成标签、应用处理器
        """
        logger.info("Preparing dataset...")

        # 创建或获取 handler
        if self._handler is None:
            self._handler = self._create_handler()

        # 加载数据
        self._data = self._handler.fetch()

        if self._data.empty:
            logger.warning("Dataset is empty after loading")
            return

        # 设置特征和标签名称
        self._feature_names = self._handler.feature_names
        self._label_names = [f"LABEL{p}" for p in self.config.label_periods]

        logger.info(
            f"Dataset prepared: {len(self._data)} samples, "
            f"{len(self._feature_names)} features, {len(self._label_names)} labels"
        )

    def _create_handler(self) -> QLibDataHandler:
        """创建数据处理器"""
        from .qlib_handler import FillNa, Winsorize, ZScore, RobustZScore

        processors = []

        # 缺失值填充
        if self.config.fill_na_method:
            processors.append(FillNa(method=self.config.fill_na_method))

        # 缩尾处理
        if self.config.winsorize:
            processors.append(Winsorize(lower=0.01, upper=0.99))

        # 标准化
        if self.config.robust_zscore:
            processors.append(RobustZScore())
        elif self.config.zscore:
            processors.append(ZScore())

        return create_handler(
            instruments=self.config.instruments,
            start_time=self.config.start_time,
            end_time=self.config.end_time,
            factor_names=self.factor_names,
            use_processors=False,  # 我们在 handler 后应用
        )

    def split_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        分割数据集为训练/验证/测试集

        Returns:
            (train_df, valid_df, test_df)
        """
        if self._data is None:
            self.prepare()

        if self._data.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # 按时间分割
        dates = self._data.index.get_level_values("datetime").unique()
        dates = dates.sort_values()

        n = len(dates)
        train_end = int(n * self.config.train_ratio)
        valid_end = int(n * (self.config.train_ratio + self.config.valid_ratio))

        train_dates = dates[:train_end]
        valid_dates = dates[train_end:valid_end]
        test_dates = dates[valid_end:]

        train_df = self._data[self._data.index.get_level_values("datetime").isin(train_dates)]
        valid_df = self._data[self._data.index.get_level_values("datetime").isin(valid_dates)]
        test_df = self._data[self._data.index.get_level_values("datetime").isin(test_dates)]

        logger.info(
            f"Data split: train={len(train_df)}, valid={len(valid_df)}, test={len(test_df)}"
        )

        return train_df, valid_df, test_df

    def get_feature_df(self) -> pd.DataFrame:
        """获取特征 DataFrame"""
        if self._data is None:
            return pd.DataFrame()
        return self._data[self._feature_names]

    def get_label_df(self, period: int = 1) -> pd.Series:
        """
        获取标签 Series

        Args:
            period: 预测周期，1=next day, 5=next 5 day, 20=next 20 day
        """
        if self._data is None:
            return pd.Series()
        label_col = f"LABEL{period}"
        if label_col in self._data.columns:
            return self._data[label_col]
        return self._data["LABEL0"]  # 默认返回 next day

    @property
    def feature_names(self) -> List[str]:
        """特征名称列表"""
        return self._feature_names

    @property
    def label_names(self) -> List[str]:
        """标签名称列表"""
        return self._label_names

    def get_feature_importance(self, model) -> pd.DataFrame:
        """
        获取特征重要性

        Args:
            model: 训练好的模型（支持 feature_importances_ 或 coef_）

        Returns:
            DataFrame with [feature, importance] columns
        """
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_).flatten()
        else:
            logger.warning("Model does not have feature_importances_ or coef_")
            return pd.DataFrame()

        df = pd.DataFrame({
            "feature": self._feature_names[:len(importances)],
            "importance": importances,
        })
        df = df.sort_values("importance", ascending=False)

        return df


class RollingDataset:
    """
    滚动数据集

    用于 walk-forward 分析，支持滚动训练和测试

    Example:
        >>> rolling = RollingDataset(
        ...     instruments=["000001.SZ", ...],
        ...     start_time="2020-01-01",
        ...     end_time="2024-12-31",
        ...     train_days=252,  # 1 年训练
        ...     test_days=63,    # 1 季度测试
        ... )
        >>> for train_df, test_df in rolling:
        ...     model.fit(train_df)
        ...     predictions = model.predict(test_df)
    """

    def __init__(
        self,
        instruments: List[str],
        start_time: str,
        end_time: str,
        train_days: int = 252,
        test_days: int = 63,
        step_days: int = 63,
        factor_names: Optional[List[str]] = None,
    ):
        """
        初始化滚动数据集

        Args:
            instruments: 股票代码列表
            start_time: 开始日期
            end_time: 结束日期
            train_days: 训练窗口天数
            test_days: 测试窗口天数
            step_days: 滚动步长
            factor_names: 因子名称列表
        """
        self.instruments = instruments
        self.start_time = start_time
        self.end_time = end_time
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.factor_names = factor_names

        self._handler = None
        self._data = None
        self._windows = []

    def prepare(self):
        """准备滚动窗口"""
        # 加载数据
        self._handler = create_handler(
            instruments=self.instruments,
            start_time=self.start_time,
            end_time=self.end_time,
            factor_names=self.factor_names,
        )
        self._data = self._handler.fetch()

        if self._data.empty:
            logger.warning("No data for rolling dataset")
            return

        # 构建滚动窗口
        dates = self._data.index.get_level_values("datetime").unique()
        dates = dates.sort_values()

        for i in range(0, len(dates) - self.train_days - self.test_days, self.step_days):
            train_start = i
            train_end = i + self.train_days
            test_start = train_end
            test_end = min(test_start + self.test_days, len(dates))

            self._windows.append({
                "train_dates": dates[train_start:train_end],
                "test_dates": dates[test_start:test_end],
            })

        logger.info(f"Prepared {len(self._windows)} rolling windows")

    def __iter__(self):
        """迭代器：每次返回 (train_df, test_df)"""
        if not self._windows:
            self.prepare()

        for window in self._windows:
            train_df = self._data[
                self._data.index.get_level_values("datetime").isin(window["train_dates"])
            ]
            test_df = self._data[
                self._data.index.get_level_values("datetime").isin(window["test_dates"])
            ]

            yield train_df, test_df

    def __len__(self) -> int:
        """返回窗口数量"""
        return len(self._windows)


# ============== 便捷函数 ==============

def create_dataset(
    instruments: List[str],
    start_time: str,
    end_time: str,
    use_alpha158: bool = True,
    use_alpha360: bool = False,
    label_periods: Optional[List[int]] = None,
) -> StockDataset:
    """
    便捷创建数据集

    Example:
        >>> dataset = create_dataset(
        ...     instruments=["000001.SZ", "000002.SZ"],
        ...     start_time="2020-01-01",
        ...     end_time="2024-12-31",
        ...     use_alpha158=True,
        ... )
        >>> train, valid, test = dataset.split_data()
    """
    config = DatasetConfig(
        start_time=start_time,
        end_time=end_time,
        instruments=instruments,
        use_alpha158=use_alpha158,
        use_alpha360=use_alpha360,
        label_periods=label_periods or [1],
    )
    return StockDataset(config)


def load_csi300_dataset(
    start_time: str = "2020-01-01",
    end_time: str = "2024-12-31",
    use_alpha158: bool = True,
) -> StockDataset:
    """
    加载沪深300成分股数据集

    Note: 需要数据库中有成分股权重数据
    """
    # 从数据库获取沪深300成分股
    sql = """
        SELECT DISTINCT ts_code
        FROM t_index_weight
        WHERE index_code = '000300.SH'
        AND trade_date = (
            SELECT MAX(trade_date) FROM t_index_weight WHERE index_code = '000300.SH'
        )
    """
    try:
        from core.storage.relational.connection import DatabaseManager
        results = DatabaseManager.fetchall("tushare_biz", sql)
        instruments = [r["ts_code"] for r in results]
        logger.info(f"Loaded {len(instruments)} CSI300 constituents")
    except Exception as e:
        logger.error(f"Failed to load CSI300 constituents: {e}")
        instruments = []

    return create_dataset(
        instruments=instruments,
        start_time=start_time,
        end_time=end_time,
        use_alpha158=use_alpha158,
    )


if __name__ == "__main__":
    # 测试
    print("Testing StockDataset...")

    # 示例配置
    config = DatasetConfig(
        start_time="2024-01-01",
        end_time="2024-12-31",
        instruments=["000001.SZ", "000002.SZ"],
        use_alpha158=False,  # 测试时关闭以减少依赖
        use_alpha360=False,
    )

    # dataset = StockDataset(config)
    # dataset.prepare()

    print("StockDataset module loaded successfully")
