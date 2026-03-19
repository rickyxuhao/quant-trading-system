"""
Qlib MySQL 适配器

将项目的 MySQL 数据封装为 Qlib 的 DataHandler 接口。
支持从 precomputed_factors 表直接查询，无需导出数据。

功能：
1. QLibDataHandler: 直接查询 MySQL，封装为 Qlib DataFrame 格式
2. 支持 Qlib 的 Processor 链（FillNa, ZScore, Neutralize）
3. 自动构建 features 和 labels

作者: Claude
创建日期: 2026-03-19
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging

import pandas as pd
import numpy as np

# Qlib 导入
try:
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset.loader import DataLoader
    from qlib.data import D
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    # 创建基类占位符
    class DataHandlerLP:
        def __init__(self, *args, **kwargs):
            raise ImportError("Qlib not installed. Run: pip install pyqlib")

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager
from .factor_definitions import FACTOR_DEFINITIONS, get_factors_by_category
from .qlib_factors import QlibFactorRegistry

logger = get_logger(__name__)


class MySQLDataLoader:
    """
    MySQL 数据加载器

    直接从 precomputed_factors 或其他表查询数据
    """

    def __init__(
        self,
        factor_names: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        instruments: Optional[List[str]] = None,
    ):
        """
        初始化数据加载器

        Args:
            factor_names: 要加载的因子名称列表，None 表示全部
            start_time: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_time: 结束日期
            instruments: 股票代码列表，None 表示全部
        """
        self.factor_names = factor_names
        self.start_time = self._normalize_date(start_time)
        self.end_time = self._normalize_date(end_time)
        self.instruments = instruments

    def _normalize_date(self, date: Optional[str]) -> Optional[str]:
        """标准化日期格式为 YYYYMMDD"""
        if date is None:
            return None
        # 移除分隔符
        return date.replace("-", "").replace("/", "")

    def load(
        self,
        instruments: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        加载数据

        Args:
            instruments: 股票代码列表
            start_time: 开始日期
            end_time: 结束日期

        Returns:
            DataFrame with columns: [datetime, instrument, factor1, factor2, ...]
        """
        inst = instruments or self.instruments
        start = start_time or self.start_time
        end = end_time or self.end_time

        # 从 precomputed_factors 表查询
        df = self._load_from_precomputed(inst, start, end)

        if df.empty:
            logger.warning("No data loaded from database")
            return df

        # 转换为 Qlib 格式
        df = self._to_qlib_format(df)

        return df

    def _load_from_precomputed(
        self,
        instruments: Optional[List[str]],
        start: Optional[str],
        end: Optional[str],
    ) -> pd.DataFrame:
        """从 precomputed_factors 表加载"""
        # 构建查询
        columns = ["ts_code", "trade_date"]

        if self.factor_names:
            # 只选择指定的因子
            valid_factors = [f for f in self.factor_names if f in FACTOR_DEFINITIONS]
            if len(valid_factors) != len(self.factor_names):
                missing = set(self.factor_names) - set(valid_factors)
                logger.warning(f"Unknown factors: {missing}")
            columns.extend(valid_factors)
        else:
            # 选择所有因子（除了基础字段）
            columns.extend(list(FACTOR_DEFINITIONS.keys()))

        # 检查表是否存在
        check_sql = """
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_schema = 'interface'
            AND table_name = 't_precomputed_factors'
        """
        result = DatabaseManager.fetchone("interface", check_sql)
        if not result or result.get("cnt", 0) == 0:
            logger.warning("t_precomputed_factors table does not exist")
            # 回退到从原始表计算
            return self._load_from_source_tables(instruments, start, end)

        # 构建 WHERE 子句
        where_conditions = []
        params = []

        if start:
            where_conditions.append("trade_date >= %s")
            params.append(start)
        if end:
            where_conditions.append("trade_date <= %s")
            params.append(end)
        if instruments:
            placeholders = ",".join(["%s"] * len(instruments))
            where_conditions.append(f"ts_code IN ({placeholders})")
            params.extend(instruments)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        sql = f"""
            SELECT {', '.join(columns)}
            FROM t_precomputed_factors
            WHERE {where_clause}
            ORDER BY trade_date, ts_code
        """

        try:
            results = DatabaseManager.fetchall("interface", sql, tuple(params))
            df = pd.DataFrame(results)
            logger.info(f"Loaded {len(df)} rows from t_precomputed_factors")
            return df
        except Exception as e:
            logger.error(f"Failed to load from precomputed_factors: {e}")
            return pd.DataFrame()

    def _load_from_source_tables(
        self,
        instruments: Optional[List[str]],
        start: Optional[str],
        end: Optional[str],
    ) -> pd.DataFrame:
        """从原始表加载（当 precomputed_factors 不存在时）"""
        logger.info("Loading from source tables...")

        # 构建基础价格数据查询
        where_conditions = []
        params = []

        if start and end:
            # 为计算窗口预留历史数据
            start_dt = datetime.strptime(start, "%Y%m%d")
            start_dt = start_dt - timedelta(days=120)  # 预留 120 天
            where_conditions.append("trade_date >= %s")
            params.append(start_dt.strftime("%Y%m%d"))

            where_conditions.append("trade_date <= %s")
            params.append(end)

        if instruments:
            placeholders = ",".join(["%s"] * len(instruments))
            where_conditions.append(f"ts_code IN ({placeholders})")
            params.extend(instruments)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        sql = f"""
            SELECT
                ts_code,
                trade_date,
                open,
                high,
                low,
                close,
                vol as volume,
                amount,
                pct_chg
            FROM t_stock_dailymarketdata
            WHERE {where_clause}
            ORDER BY ts_code, trade_date
        """

        try:
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))
            df = pd.DataFrame(results)
            logger.info(f"Loaded {len(df)} rows from source tables")
            return df
        except Exception as e:
            logger.error(f"Failed to load from source tables: {e}")
            return pd.DataFrame()

    def _to_qlib_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换为 Qlib 格式"""
        if df.empty:
            return df

        # 重命名列以匹配 Qlib 格式
        column_mapping = {
            "ts_code": "instrument",
            "trade_date": "datetime",
        }
        df = df.rename(columns=column_mapping)

        # 转换日期格式
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d")

        # 设置索引
        df = df.set_index(["datetime", "instrument"])

        # 排序
        df = df.sort_index()

        return df


class QLibDataHandler(DataHandlerLP):
    """
    Qlib 数据处理器 - MySQL 适配器

    直接查询 MySQL 数据库，封装为 Qlib 可用的数据格式。
    支持 Processor 链进行数据预处理。

    Example:
        >>> handler = QLibDataHandler(
        ...     instruments=["000001.SZ", "000002.SZ"],
        ...     start_time="2020-01-01",
        ...     end_time="2024-12-31",
        ...     factor_names=["KMID", "ROC20", "MA20"],
        ... )
        >>> df = handler.fetch()
    """

    def __init__(
        self,
        instruments: List[str],
        start_time: str,
        end_time: str,
        factor_names: Optional[List[str]] = None,
        label_names: Optional[List[str]] = None,
        learn_processors: Optional[List] = None,
        infer_processors: Optional[List] = None,
        **kwargs,
    ):
        """
        初始化数据处理器

        Args:
            instruments: 股票代码列表，如 ["000001.SZ", "000002.SZ"]
            start_time: 开始日期 (YYYY-MM-DD)
            end_time: 结束日期
            factor_names: 特征因子名称列表，None 表示使用全部可用因子
            label_names: 标签名称列表，如 ["LABEL0"]（未来收益率）
            learn_processors: 训练时使用的处理器链
            infer_processors: 推理时使用的处理器链
        """
        self._instruments = instruments
        self._start_time = start_time
        self._end_time = end_time
        self._factor_names = factor_names
        self._label_names = label_names or ["LABEL0"]

        # 数据加载器
        self._loader = MySQLDataLoader(
            factor_names=factor_names,
            start_time=start_time,
            end_time=end_time,
            instruments=instruments,
        )

        # 处理器
        self.learn_processors = learn_processors or []
        self.infer_processors = infer_processors or []

        # 数据缓存
        self._data: Optional[pd.DataFrame] = None

        logger.info(
            f"QLibDataHandler initialized: {len(instruments)} instruments, "
            f"period: {start_time} to {end_time}"
        )

    def setup_data(self, **kwargs):
        """加载并处理数据"""
        # 加载数据
        self._data = self._loader.load(
            instruments=self._instruments,
            start_time=self._start_time,
            end_time=self._end_time,
        )

        if self._data.empty:
            logger.warning("No data loaded")
            return

        # 添加标签（未来收益率）
        self._add_labels()

        # 应用处理器
        self._apply_processors()

        logger.info(f"Data setup complete: {len(self._data)} rows, {len(self._data.columns)} columns")

    def _add_labels(self):
        """添加标签（未来收益率）"""
        if self._data is None or self._data.empty:
            return

        # 计算未来收益率
        close_col = "close" if "close" in self._data.columns else None

        if close_col:
            # 计算 next day return
            self._data["LABEL0"] = self._data.groupby(level="instrument")[close_col].shift(-1) / self._data[close_col] - 1

            # 也可以计算多周期收益
            for period in [5, 20]:
                self._data[f"LABEL{period}"] = (
                    self._data.groupby(level="instrument")[close_col].shift(-period) / self._data[close_col] - 1
                )

        # 删除最后一期（没有未来数据）
        self._data = self._data.dropna(subset=["LABEL0"])

    def _apply_processors(self):
        """应用数据处理器"""
        if self._data is None or self._data.empty:
            return

        # 默认处理器
        default_processors = [
            FillNa(),
            ZScore(),
        ]

        processors = self.learn_processors or default_processors

        for processor in processors:
            try:
                self._data = processor(self._data)
                logger.debug(f"Applied processor: {processor.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to apply processor {processor}: {e}")

    def fetch(self, *args, **kwargs) -> pd.DataFrame:
        """获取数据"""
        if self._data is None:
            self.setup_data()
        return self._data

    @property
    def feature_names(self) -> List[str]:
        """获取特征名称列表"""
        if self._data is None:
            return []
        # 排除标签列
        exclude_cols = set(self._label_names) | {"LABEL0", "LABEL5", "LABEL20"}
        return [col for col in self._data.columns if col not in exclude_cols]

    @property
    def label_names(self) -> List[str]:
        """获取标签名称列表"""
        return self._label_names

    def get_feature_df(self) -> pd.DataFrame:
        """获取特征 DataFrame"""
        if self._data is None:
            return pd.DataFrame()
        return self._data[self.feature_names]

    def get_label_df(self) -> pd.DataFrame:
        """获取标签 DataFrame"""
        if self._data is None:
            return pd.DataFrame()
        return self._data[self.label_names]


# ============== 数据处理器 ==============

class Processor:
    """数据处理器基类"""

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


class FillNa(Processor):
    """缺失值填充"""

    def __init__(self, method: str = "median"):
        """
        Args:
            method: "median", "mean", "zero", "ffill"
        """
        self.method = method

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.method == "median":
            return df.fillna(df.median())
        elif self.method == "mean":
            return df.fillna(df.mean())
        elif self.method == "zero":
            return df.fillna(0)
        elif self.method == "ffill":
            return df.fillna(method="ffill").fillna(method="bfill")
        return df


class ZScore(Processor):
    """横截面 Z-Score 标准化"""

    def __init__(self, group_by: str = "datetime"):
        """
        Args:
            group_by: 按什么维度分组标准化，"datetime" 表示每天横截面
        """
        self.group_by = group_by

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.group_by == "datetime":
            # 按日期分组，每天横截面标准化
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col in ["LABEL0", "LABEL5", "LABEL20"]:
                    continue  # 不标准化标签
                df[col] = df.groupby(level="datetime")[col].transform(
                    lambda x: (x - x.mean()) / (x.std() + 1e-8)
                )
        return df


class RobustZScore(Processor):
    """稳健 Z-Score（使用中位数和 MAD）"""

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col in ["LABEL0", "LABEL5", "LABEL20"]:
                continue

            def robust_zscore(x):
                median = x.median()
                mad = np.median(np.abs(x - median)) + 1e-8
                return (x - median) / (1.4826 * mad)

            df[col] = df.groupby(level="datetime")[col].transform(robust_zscore)
        return df


class Neutralize(Processor):
    """行业/市值中性化"""

    def __init__(self, group_col: str = "industry", risk_factors: Optional[List[str]] = None):
        """
        Args:
            group_col: 分组列名（如 industry）
            risk_factors: 风险因子列名（如 ["log_mv"]）
        """
        self.group_col = group_col
        self.risk_factors = risk_factors or []

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # TODO: 实现行业中性化
        # 需要行业分类数据
        logger.warning("Neutralize processor not fully implemented")
        return df


class Winsorize(Processor):
    """缩尾处理（去除极值）"""

    def __init__(self, lower: float = 0.01, upper: float = 0.99):
        """
        Args:
            lower: 下分位数
            upper: 上分位数
        """
        self.lower = lower
        self.upper = upper

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col in ["LABEL0", "LABEL5", "LABEL20"]:
                continue

            def winsorize(x):
                lower_val = x.quantile(self.lower)
                upper_val = x.quantile(self.upper)
                return x.clip(lower_val, upper_val)

            df[col] = df.groupby(level="datetime")[col].transform(winsorize)
        return df


# ============== 便捷函数 ==============

def create_handler(
    instruments: List[str],
    start_time: str,
    end_time: str,
    factor_names: Optional[List[str]] = None,
    use_processors: bool = True,
) -> QLibDataHandler:
    """
    便捷创建数据处理器

    Example:
        >>> handler = create_handler(
        ...     instruments=["000001.SZ", "000002.SZ"],
        ...     start_time="2020-01-01",
        ...     end_time="2024-12-31",
        ...     factor_names=["KMID", "ROC20", "MA20"],
        ... )
        >>> df = handler.fetch()
    """
    processors = None
    if use_processors:
        processors = [
            FillNa(method="median"),
            Winsorize(lower=0.01, upper=0.99),
            ZScore(),
        ]

    return QLibDataHandler(
        instruments=instruments,
        start_time=start_time,
        end_time=end_time,
        factor_names=factor_names,
        learn_processors=processors,
    )


def load_stock_pool(
    date: str,
    min_market_cap: float = 1e8,  # 1亿
    exclude_st: bool = True,
) -> List[str]:
    """
    加载指定日期的股票池

    Args:
        date: 日期 (YYYY-MM-DD)
        min_market_cap: 最小市值
        exclude_st: 是否排除 ST 股票

    Returns:
        股票代码列表
    """
    date_str = date.replace("-", "")

    sql = """
        SELECT DISTINCT db.ts_code
        FROM t_stock_daily_basic db
        JOIN t_stock_basic sb ON db.ts_code = sb.ts_code
        WHERE db.trade_date = %s
        AND db.total_mv >= %s
        AND sb.list_status = 'L'
    """
    params = [date_str, min_market_cap / 1e4]  # tushare 市值单位是万元

    if exclude_st:
        sql += " AND (sb.name NOT LIKE '%ST%' AND sb.name NOT LIKE '%*ST%')"

    try:
        results = DatabaseManager.fetchall("tushare_biz", sql, params)
        stocks = [r["ts_code"] for r in results]
        logger.info(f"Loaded {len(stocks)} stocks for {date}")
        return stocks
    except Exception as e:
        logger.error(f"Failed to load stock pool: {e}")
        return []


if __name__ == "__main__":
    # 测试
    print("Testing QLibDataHandler...")

    # 创建处理器（需要实际数据库连接）
    # handler = create_handler(
    #     instruments=["000001.SZ", "000002.SZ"],
    #     start_time="2024-01-01",
    #     end_time="2024-12-31",
    #     factor_names=["close", "open", "high", "low", "volume"],
    # )
    # df = handler.fetch()
    # print(df.head())

    print("QLibDataHandler module loaded successfully")
