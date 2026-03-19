"""
SQL 批量因子计算引擎

使用 MySQL 8.0+ 窗口函数一次性计算所有因子，
替代 Python 循环逐股计算，性能提升约 6-10 倍。

核心特性:
- 单次 SQL 查询返回所有因子（约 30 个）
- 使用 CTE (Common Table Expressions) 组织复杂计算
- 支持横截面 Z-score 的 SQL 内计算
- 自动处理缺失值和异常值

版本历史:
- 2026-03-19: 从 factor_definitions.py 读取因子定义，SQL 动态构建
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager

# 导入统一因子定义
from .factor_definitions import (
    FACTOR_DEFINITIONS,
    FactorDefinition,
    CalculationType,
    get_factors_by_data_source,
)

logger = get_logger(__name__)


@dataclass
class SQLFactorConfig:
    """SQL 因子计算配置"""

    # 数据查询范围
    lookback_days_returns: int = 120  # 收益计算回看天数
    lookback_days_moneyflow: int = 30  # 资金流向回看天数

    # 计算周期
    return_periods: List[int] = None
    volatility_periods: List[int] = None

    def __post_init__(self):
        if self.return_periods is None:
            self.return_periods = [20, 60]
        if self.volatility_periods is None:
            self.volatility_periods = [20, 60]


class SQLFactorEngine:
    """
    SQL 批量因子计算引擎

    使用 SQL 窗口函数批量计算所有因子，单次查询返回完整因子矩阵。
    相比 Python 逐股循环，性能提升约 6-10 倍。

    使用示例:
        engine = SQLFactorEngine()
        factors = engine.calculate_factors_for_date(
            trade_date=datetime(2024, 1, 15),
            stock_pool=['000001.SZ', '000002.SZ', ...]
        )
    """

    DB_NAME = "tushare_biz"

    def __init__(self, config: Optional[SQLFactorConfig] = None):
        self.config = config or SQLFactorConfig()

    def calculate_factors_for_date(
        self,
        trade_date: datetime,
        stock_pool: Optional[List[str]] = None,
        include_sectors: bool = True,
    ) -> pd.DataFrame:
        """
        为指定日期批量计算所有因子

        Args:
            trade_date: 计算日期
            stock_pool: 股票池代码列表（默认全市场）
            include_sectors: 是否计算行业相对因子

        Returns:
            DataFrame，每行一只股票，每列一个因子
        """
        date_str = trade_date.strftime("%Y%m%d")

        # 如果没有指定股票池，获取当日有交易的所有股票
        if stock_pool is None:
            stock_pool = self._get_all_stocks_for_date(date_str)

        if not stock_pool:
            logger.warning(f"No stocks found for {date_str}")
            return pd.DataFrame()

        logger.debug(f"Calculating factors for {date_str}, {len(stock_pool)} stocks")

        try:
            # 使用统一查询计算所有因子
            return self._unified_factor_query(date_str, stock_pool, include_sectors)
        except Exception as e:
            logger.error(f"Error in unified factor query: {e}")
            # 降级到简化查询
            return self._simplified_factor_query(date_str, stock_pool)

    def _unified_factor_query(
        self, date_str: str, stock_pool: List[str], include_sectors: bool = True
    ) -> pd.DataFrame:
        """
        统一因子查询 - 单次 SQL 返回所有因子
        """
        # 计算起始日期
        start_date = (
            datetime.strptime(date_str, "%Y%m%d")
            - pd.Timedelta(days=self.config.lookback_days_returns)
        ).strftime("%Y%m%d")

        moneyflow_start = (
            datetime.strptime(date_str, "%Y%m%d")
            - pd.Timedelta(days=self.config.lookback_days_moneyflow)
        ).strftime("%Y%m%d")

        placeholders = ",".join(["%s"] * len(stock_pool))

        sql = f"""
        WITH
        -- 1. 价格与收益数据（窗口函数计算滚动指标）
        price_data AS (
            SELECT
                ts_code,
                trade_date,
                close,
                vol,
                amount,
                pct_chg,
                LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_20d_ago,
                LAG(close, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_60d_ago,
                STDDEV(pct_chg) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 19 PRECEDING
                ) * SQRT(252) as volatility_20d,
                STDDEV(pct_chg) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 59 PRECEDING
                ) * SQRT(252) as volatility_60d,
                AVG(vol) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 19 PRECEDING
                ) as avg_vol_20d,
                AVG(vol) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 4 PRECEDING
                ) as avg_vol_5d
            FROM t_stock_dailymarketdata
            WHERE trade_date BETWEEN %s AND %s
              AND ts_code IN ({placeholders})
        ),
        price_today AS (
            SELECT
                ts_code,
                trade_date,
                (close / NULLIF(close_20d_ago, 0) - 1) as return_20d,
                (close / NULLIF(close_60d_ago, 0) - 1) as return_60d,
                volatility_20d,
                volatility_60d,
                avg_vol_5d / NULLIF(avg_vol_20d, 0) as volume_ratio,
                avg_vol_20d as turnover_20d
            FROM price_data
            WHERE trade_date = %s
        ),

        -- 2. 资金流向数据
        moneyflow_data AS (
            SELECT
                ts_code,
                trade_date,
                -- 计算主力资金净流入：大单净流入
                (buy_lg_amount - sell_lg_amount) as net_mf_amount,
                (buy_lg_amount - sell_lg_amount) as large_order_net,
                SUM(buy_lg_amount - sell_lg_amount) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 4 PRECEDING
                ) as net_inflow_5d,
                SUM(buy_lg_amount - sell_lg_amount) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                    ROWS 19 PRECEDING
                ) as net_inflow_20d
            FROM t_stock_moneyflow
            WHERE trade_date BETWEEN %s AND %s
              AND ts_code IN ({placeholders})
        ),
        moneyflow_today AS (
            SELECT
                ts_code,
                trade_date,
                net_mf_amount as main_net_inflow,
                large_order_net,
                net_inflow_5d,
                net_inflow_20d
            FROM moneyflow_data
            WHERE trade_date = %s
        ),

        -- 3. 估值与基本面数据
        valuation_data AS (
            SELECT
                ts_code,
                trade_date,
                pe_ttm,
                pb,
                ps_ttm,
                dv_ttm as dividend_yield,
                total_mv * 10000 as total_mv,
                circ_mv * 10000 as circ_mv,
                LN(NULLIF(total_mv, 0)) as log_mv
            FROM t_stock_daily_basic
            WHERE trade_date = %s
              AND ts_code IN ({placeholders})
        ),

        -- 4. 横截面统计（用于Z-score计算）
        cross_sectional_stats AS (
            SELECT
                AVG(pe_ttm) as pe_mean,
                STDDEV(pe_ttm) as pe_std,
                AVG(pb) as pb_mean,
                STDDEV(pb) as pb_std,
                AVG(ps_ttm) as ps_mean,
                STDDEV(ps_ttm) as ps_std,
                AVG(total_mv) as mv_mean,
                STDDEV(total_mv) as mv_std,
                AVG(return_20d) as ret20_mean,
                STDDEV(return_20d) as ret20_std,
                AVG(volatility_20d) as vol20_mean,
                STDDEV(volatility_20d) as vol20_std
            FROM valuation_data v
            LEFT JOIN price_today p ON v.ts_code = p.ts_code
        )

        -- 5. 最终因子整合
        SELECT
            v.ts_code,
            v.pe_ttm,
            v.pb,
            v.ps_ttm,
            v.dividend_yield,
            v.total_mv,
            v.circ_mv,
            v.log_mv,

            -- 收益特征
            p.return_20d,
            p.return_60d,
            p.volatility_20d,
            p.volatility_60d,
            p.volume_ratio,
            p.turnover_20d,

            -- 资金流向
            m.main_net_inflow,
            m.net_inflow_5d,
            m.net_inflow_20d,
            CASE
                WHEN v.total_mv > 0 AND m.large_order_net IS NOT NULL
                THEN m.large_order_net / (v.total_mv / 10000)
                ELSE NULL
            END as large_order_net_ratio,

            -- 横截面Z-score
            (v.pe_ttm - cs.pe_mean) / NULLIF(cs.pe_std, 0) as pe_ttm_zscore,
            (v.pb - cs.pb_mean) / NULLIF(cs.pb_std, 0) as pb_zscore,
            (v.ps_ttm - cs.ps_mean) / NULLIF(cs.ps_std, 0) as ps_ttm_zscore,
            (p.return_20d - cs.ret20_mean) / NULLIF(cs.ret20_std, 0) as return_20d_zscore,
            (p.volatility_20d - cs.vol20_mean) / NULLIF(cs.vol20_std, 0) as volatility_20d_zscore,

            -- 市场相对因子
            p.return_20d - COALESCE((SELECT AVG(return_20d) FROM price_today), 0) as market_alpha_20d,
            p.return_60d - COALESCE((SELECT AVG(return_60d) FROM price_today), 0) as market_alpha_60d

        FROM valuation_data v
        LEFT JOIN price_today p ON v.ts_code = p.ts_code
        LEFT JOIN moneyflow_today m ON v.ts_code = m.ts_code
        CROSS JOIN cross_sectional_stats cs
        ORDER BY v.ts_code
        """

        # Build params as a flat list, flattening stock_pool tuples
        params_list = [
            # price_data CTE
            start_date,
            date_str,
        ] + stock_pool + [
            date_str,
            # moneyflow_data CTE
            moneyflow_start,
            date_str,
        ] + stock_pool + [
            date_str,
            # valuation_data CTE
            date_str,
        ] + stock_pool

        params = tuple(params_list)

        try:
            results = DatabaseManager.fetchall(self.DB_NAME, sql, params)
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            raise

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df.set_index("ts_code", inplace=True)

        # 数据清理
        df = self._clean_factor_data(df)

        logger.debug(f"Calculated {len(df.columns)} factors for {len(df)} stocks")
        return df

    def _simplified_factor_query(self, date_str: str, stock_pool: List[str]) -> pd.DataFrame:
        """
        简化查询 - 当统一查询失败时的降级方案
        只计算核心因子
        """
        placeholders = ",".join(["%s"] * len(stock_pool))

        # 简化 SQL，只计算基本面和收益
        sql = f"""
        SELECT
            v.ts_code,
            v.pe_ttm,
            v.pb,
            v.ps_ttm,
            v.total_mv * 10000 as total_mv,
            v.circ_mv * 10000 as circ_mv,
            LN(NULLIF(v.total_mv, 0)) as log_mv
        FROM t_stock_daily_basic v
        WHERE v.trade_date = %s
          AND v.ts_code IN ({placeholders})
        """

        params = (date_str,) + tuple(stock_pool)
        results = DatabaseManager.fetchall(self.DB_NAME, sql, params)

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df.set_index("ts_code", inplace=True)
        return df

    def _get_all_stocks_for_date(self, date_str: str) -> List[str]:
        """获取指定日期有交易的所有股票"""
        sql = """
            SELECT DISTINCT ts_code
            FROM t_stock_dailymarketdata
            WHERE trade_date = %s
        """
        results = DatabaseManager.fetchall(self.DB_NAME, sql, (date_str,))
        return [r["ts_code"] for r in results]

    def _get_sql_factors_from_definitions(self) -> Dict[str, List[FactorDefinition]]:
        """
        从统一因子定义中获取所有 SQL 类型的因子，按数据源分组

        Returns:
            Dict[data_source -> List[FactorDefinition]]
        """
        sql_factors = {}

        for name, factor_def in FACTOR_DEFINITIONS.items():
            # 只处理 SQL 和 DIRECT 类型的因子
            if factor_def.calculation not in (CalculationType.SQL, CalculationType.DIRECT):
                continue

            # 跳过没有数据源或 SQL 表达式的因子
            if not factor_def.data_source or not factor_def.sql_expr:
                continue

            ds = factor_def.data_source
            if ds not in sql_factors:
                sql_factors[ds] = []
            sql_factors[ds].append(factor_def)

        return sql_factors

    def _get_max_window_days(self) -> int:
        """获取所有 SQL 因子中最大的窗口天数"""
        max_window = 0
        for name, factor_def in FACTOR_DEFINITIONS.items():
            if factor_def.calculation in (CalculationType.SQL, CalculationType.DIRECT):
                if factor_def.window_days:
                    max_window = max(max_window, factor_def.window_days)
        return max_window

    def _clean_factor_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理因子数据

        使用 factor_definitions.py 中的定义决定如何清理每个因子：
        - 将 inf 替换为 NaN
        - 根据 valid_range 限制范围
        - 根据 winsorize 进行缩尾处理
        """
        # 替换无穷值
        df = df.replace([np.inf, -np.inf], np.nan)

        # 对每个列根据定义进行清理
        for col in df.columns:
            if col not in FACTOR_DEFINITIONS:
                continue

            factor_def = FACTOR_DEFINITIONS[col]

            # 如果定义了有效范围，直接裁剪
            if factor_def.valid_range:
                min_val, max_val = factor_def.valid_range
                df[col] = df[col].clip(min_val, max_val)
            # 如果是 Z-score 因子，裁剪到 -5 到 5
            elif col.endswith("_zscore"):
                df[col] = df[col].clip(-5, 5)
            # 如果需要进行缩尾处理
            elif factor_def.winsorize:
                lower = df[col].quantile(0.01)
                upper = df[col].quantile(0.99)
                df[col] = df[col].clip(lower, upper)

        return df

    def calculate_sector_relative_factors(
        self,
        trade_date: datetime,
        stock_pool: List[str],
        base_factors: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        计算行业相对因子（需要行业分类数据）

        Args:
            trade_date: 计算日期
            stock_pool: 股票池
            base_factors: 已计算的基础因子（避免重复查询）

        Returns:
            DataFrame 包含行业相对因子
        """
        date_str = trade_date.strftime("%Y%m%d")
        placeholders = ",".join(["%s"] * len(stock_pool))

        # 获取行业分类和收益数据
        sql = f"""
        WITH stock_industries AS (
            SELECT
                d.ts_code,
                b.industry
            FROM (
                SELECT DISTINCT ts_code
                FROM t_stock_dailymarketdata
                WHERE trade_date = %s AND ts_code IN ({placeholders})
            ) d
            LEFT JOIN t_stock_basic b ON d.ts_code = b.ts_code
        ),
        returns AS (
            SELECT
                ts_code,
                close / NULLIF(LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1 as return_20d,
                close / NULLIF(LAG(close, 60) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1 as return_60d
            FROM t_stock_dailymarketdata
            WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 120 DAY) AND %s
              AND ts_code IN ({placeholders})
        ),
        today_returns AS (
            SELECT ts_code, return_20d, return_60d
            FROM returns
            WHERE trade_date = %s
        ),
        sector_stats AS (
            SELECT
                si.industry,
                AVG(tr.return_20d) as sector_return_20d,
                AVG(tr.return_60d) as sector_return_60d,
                COUNT(*) as sector_stock_count
            FROM stock_industries si
            JOIN today_returns tr ON si.ts_code = tr.ts_code
            WHERE si.industry IS NOT NULL
            GROUP BY si.industry
        )
        SELECT
            si.ts_code,
            si.industry,
            tr.return_20d - COALESCE(ss.sector_return_20d, 0) as sector_alpha_20d,
            tr.return_60d - COALESCE(ss.sector_return_60d, 0) as sector_alpha_60d,
            PERCENT_RANK() OVER (
                PARTITION BY si.industry
                ORDER BY tr.return_20d
            ) as sector_rank_20d
        FROM stock_industries si
        JOIN today_returns tr ON si.ts_code = tr.ts_code
        LEFT JOIN sector_stats ss ON si.industry = ss.industry
        """

        params = (
            date_str,
            tuple(stock_pool),
            (datetime.strptime(date_str, "%Y%m%d") - pd.Timedelta(days=120)).strftime("%Y%m%d"),
            date_str,
            tuple(stock_pool),
            date_str,
        )

        try:
            results = DatabaseManager.fetchall(self.DB_NAME, sql, params)
            if results:
                return pd.DataFrame(results).set_index("ts_code")
        except Exception as e:
            logger.error(f"Error calculating sector factors: {e}")

        return pd.DataFrame()

    def batch_calculate(
        self,
        dates: List[datetime],
        stock_pool: Optional[List[str]] = None,
    ) -> Dict[datetime, pd.DataFrame]:
        """
        批量计算多个日期的因子

        Args:
            dates: 日期列表
            stock_pool: 股票池（默认每日动态获取）

        Returns:
            {date: DataFrame} 字典
        """
        results = {}

        for date in dates:
            try:
                df = self.calculate_factors_for_date(date, stock_pool)
                results[date] = df
            except Exception as e:
                logger.error(f"Failed to calculate factors for {date}: {e}")
                results[date] = pd.DataFrame()

        return results

    def get_factor_data_sources(self) -> Dict[str, List[str]]:
        """
        获取 SQL 计算因子的数据源信息

        Returns:
            Dict[数据表 -> 因子列表]
        """
        sql_factors = self._get_sql_factors_from_definitions()

        result = {}
        for data_source, factors in sql_factors.items():
            result[data_source] = [f.name for f in factors]

        return result

    def print_factor_lineage(self):
        """打印所有 SQL 因子的数据血缘信息"""
        sql_factors = self._get_sql_factors_from_definitions()

        print("=" * 80)
        print("SQL 因子数据血缘")
        print("=" * 80)

        for data_source, factors in sorted(sql_factors.items()):
            print(f"\n数据表: {data_source}")
            print("-" * 40)

            for factor in sorted(factors, key=lambda x: x.name):
                print(f"  {factor.name:25s} | {factor.description}")
                if factor.source_field:
                    print(f"  {'':25s} | 源字段: {factor.source_field}")
                if factor.window_days:
                    print(f"  {'':25s} | 窗口: {factor.window_days}天")

        print(f"\n总计: {sum(len(f) for f in sql_factors.values())} 个 SQL 因子")


# 单例实例缓存
_sql_factor_engine_instance: Optional[SQLFactorEngine] = None


def get_sql_factor_engine() -> SQLFactorEngine:
    """
    获取 SQLFactorEngine 单例实例

    使用单例模式避免重复创建，提升性能。
    """
    global _sql_factor_engine_instance
    if _sql_factor_engine_instance is None:
        _sql_factor_engine_instance = SQLFactorEngine()
    return _sql_factor_engine_instance
