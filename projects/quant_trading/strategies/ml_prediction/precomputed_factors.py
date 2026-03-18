"""
预计算因子模块 - 基于 FactorRegistry 的实现

每日收盘后批量计算并存储，支持：
- 声明式因子定义（FactorRegistry）
- SQL 批量计算（高性能）
- 多进程并行处理
- 自动数据库迁移

存储表: t_precomputed_factors
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
from multiprocessing import Pool, cpu_count
import time

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager
from projects.quant_trading.strategies.ml_prediction.factor_registry import (
    FactorRegistry, get_full_registry, FactorDefinition, FactorType
)

logger = get_logger(__name__)


# 预计算因子 Schema（动态生成）
FACTOR_DB_TYPES = {
    FactorType.SQL: "FLOAT",
    FactorType.PYTHON: "FLOAT",
    FactorType.HYBRID: "FLOAT",
}


def get_factor_schema(registry: Optional[FactorRegistry] = None) -> Dict[str, str]:
    """动态生成因子 Schema"""
    if registry is None:
        registry = get_full_registry()

    schema = {}
    for name, factor in registry.get_all_factors().items():
        schema[name] = FACTOR_DB_TYPES.get(factor.factor_type, "FLOAT")
    return schema


@dataclass
class PrecomputeConfig:
    """预计算配置"""
    workers: int = 4                    # 并行工作数
    batch_size: int = 1000              # 每批处理股票数
    use_parallel: bool = True           # 是否使用多进程
    skip_existing: bool = True          # 跳过已存在的日期
    min_stock_count: int = 1000         # 最小股票数（用于完整性检查）


class FactorPrecomputer:
    """
    因子预计算器（FactorRegistry 版本）

    主要改进：
    - 基于 FactorRegistry，支持声明式因子定义
    - 自动 SQL 生成
    - 动态 Schema 管理
    """

    TABLE_NAME = "t_precomputed_factors"
    DB_NAME = "interface"

    def __init__(self, config: Optional[PrecomputeConfig] = None,
                 registry: Optional[FactorRegistry] = None):
        self.config = config or PrecomputeConfig()
        self.registry = registry or get_full_registry()
        self._schema = get_factor_schema(self.registry)
        self._ensure_table_exists()
        self._sync_table_schema()  # 同步表结构，添加新列

    def _ensure_table_exists(self):
        """确保预计算表存在（支持动态列）"""
        columns_def = [f"{name} {dtype}" for name, dtype in self._schema.items()]

        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
            trade_date VARCHAR(8) NOT NULL,
            ts_code VARCHAR(16) NOT NULL,
            {', '.join(columns_def)},
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (trade_date, ts_code),
            INDEX idx_trade_date (trade_date),
            INDEX idx_ts_code (ts_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """

        try:
            DatabaseManager.execute(self.DB_NAME, create_sql)
            logger.info(f"Table {self.TABLE_NAME} ready with {len(columns_def)} factor columns")
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            raise

    def _sync_table_schema(self):
        """同步表结构（添加新列）"""
        existing_cols = self._get_existing_columns()
        new_cols = []

        for col_name, col_type in self._schema.items():
            if col_name not in existing_cols:
                new_cols.append(f"ADD COLUMN {col_name} {col_type}")

        if new_cols:
            alter_sql = f"ALTER TABLE {self.TABLE_NAME} {', '.join(new_cols)}"
            try:
                DatabaseManager.execute(self.DB_NAME, alter_sql)
                logger.info(f"Added {len(new_cols)} new columns to {self.TABLE_NAME}")
            except Exception as e:
                logger.error(f"Error altering table: {e}")

    def _get_existing_columns(self) -> List[str]:
        """获取现有表列"""
        try:
            results = DatabaseManager.fetchall(
                self.DB_NAME,
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                (self.TABLE_NAME,)
            )
            return [r['COLUMN_NAME'] for r in results]
        except Exception as e:
            logger.error(f"Error getting columns: {e}")
            return []

    def get_missing_factor_columns(self) -> List[str]:
        """
        获取数据库中缺失的因子列

        Returns:
            缺失的因子列名列表
        """
        existing_cols = set(self._get_existing_columns())
        all_factor_cols = set(self._schema.keys())
        missing_cols = list(all_factor_cols - existing_cols)
        return missing_cols

    def update_missing_factors(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        增量更新：只为已有数据计算新增的因子列

        适用于：新增因子后，不需要重新计算所有因子
        只计算缺失的列，使用 UPDATE 更新现有记录

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计信息
        """
        # 1. 获取缺失的列
        missing_cols = self.get_missing_factor_columns()

        if not missing_cols:
            logger.info("No new factors to add")
            return {"status": "no_change", "missing_factors": []}

        logger.info(f"Found {len(missing_cols)} new factors to add: {sorted(missing_cols)}")

        # 2. 确保表结构已更新（添加新列）
        self._sync_table_schema()

        # 3. 获取日期范围内的交易日
        from projects.quant_trading.backtest.data_manager import DataManager
        trade_dates = DataManager().get_trade_dates(start_date, end_date)

        if not trade_dates:
            logger.warning("No trading dates in range")
            return {"status": "no_dates", "missing_factors": missing_cols}

        logger.info(f"Processing {len(trade_dates)} trading days")

        # 4. 为每个日期计算缺失因子并更新
        total_updated = 0
        success_dates = 0
        failed_dates = 0
        details = []

        for i, date in enumerate(trade_dates):
            date_str = date.strftime('%Y%m%d')
            logger.info(f"[{i+1}/{len(trade_dates)}] Updating factors for {date_str}")

            try:
                # 获取当天已存在的股票列表
                existing_stocks = self._get_stocks_for_date(date)

                if not existing_stocks:
                    logger.warning(f"No existing data for {date_str}, skipping")
                    continue

                # 只计算缺失的因子
                factors_df = self.registry.compute_factors(
                    date, existing_stocks, factor_names=missing_cols
                )

                if factors_df.empty:
                    logger.warning(f"No factors computed for {date_str}")
                    failed_dates += 1
                    continue

                # 使用 UPDATE 更新现有记录
                updated = self._update_factors_for_date(date, factors_df)
                total_updated += updated
                success_dates += 1
                details.append({
                    "date": date_str,
                    "status": "success",
                    "updated": updated,
                    "factors": len(missing_cols)
                })

            except Exception as e:
                logger.error(f"Failed to update {date_str}: {e}")
                failed_dates += 1
                details.append({
                    "date": date_str,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "status": "success",
            "new_factors": missing_cols,
            "dates_processed": len(trade_dates),
            "success_dates": success_dates,
            "failed_dates": failed_dates,
            "total_updated": total_updated,
            "details": details
        }

    def _get_stocks_for_date(self, trade_date: datetime) -> List[str]:
        """获取指定日期已有的股票列表"""
        date_str = trade_date.strftime('%Y%m%d')

        results = DatabaseManager.fetchall(
            self.DB_NAME,
            f"SELECT ts_code FROM {self.TABLE_NAME} WHERE trade_date = %s",
            (date_str,)
        )
        return [r['ts_code'] for r in results]

    def _update_factors_for_date(self, trade_date: datetime, factors_df: pd.DataFrame) -> int:
        """使用 UPDATE 更新指定日期的因子数据"""
        if factors_df.empty:
            return 0

        date_str = trade_date.strftime('%Y%m%d')
        factor_cols = [c for c in factors_df.columns if c not in ['trade_date', 'ts_code']]

        if not factor_cols:
            return 0

        # 构建 UPDATE SQL
        update_sql = f"""
        UPDATE {self.TABLE_NAME}
        SET {', '.join([f'{c} = %s' for c in factor_cols])}
        WHERE trade_date = %s AND ts_code = %s
        """

        # 准备数据
        values = []
        for ts_code, row in factors_df.iterrows():
            vals = [row.get(c, None) for c in factor_cols]
            vals.extend([date_str, ts_code])
            values.append(tuple(vals))

        # 执行批量更新
        if values:
            try:
                batch_size = 1000
                total_updated = 0
                for i in range(0, len(values), batch_size):
                    batch = values[i:i+batch_size]
                    DatabaseManager.executemany(self.DB_NAME, update_sql, batch)
                    total_updated += len(batch)
                logger.debug(f"Updated {total_updated} rows for {date_str}")
                return total_updated
            except Exception as e:
                logger.error(f"Error updating {date_str}: {e}")
                return 0
        return 0

    def precompute_for_date(
        self,
        trade_date: datetime,
        stock_pool: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        为指定日期预计算所有因子

        Args:
            trade_date: 交易日
            stock_pool: 股票池（默认全市场）

        Returns:
            统计信息
        """
        date_str = trade_date.strftime('%Y%m%d')
        logger.info(f"Precomputing factors for {date_str}")

        # 获取股票池
        if stock_pool is None:
            stock_pool = self._get_all_stocks(trade_date)

        if len(stock_pool) < self.config.min_stock_count:
            logger.warning(f"Insufficient stocks: {len(stock_pool)} < {self.config.min_stock_count}")
            return {"status": "insufficient_stocks", "count": len(stock_pool)}

        logger.info(f"Stock pool: {len(stock_pool)} stocks")

        try:
            # 使用 FactorRegistry 计算所有因子
            start_time = time.time()
            factors_df = self.registry.compute_factors(trade_date, stock_pool)
            compute_time = time.time() - start_time

            if factors_df.empty:
                logger.warning("No factors computed")
                return {"status": "empty", "rows": 0}

            logger.info(f"Computed {len(factors_df.columns)} factors in {compute_time:.2f}s")

            # 添加日期列
            factors_df['trade_date'] = date_str
            factors_df['ts_code'] = factors_df.index

            # 保存到数据库
            rows_inserted = self._save_to_db(factors_df)

            return {
                "status": "success",
                "trade_date": date_str,
                "stocks_processed": len(stock_pool),
                "rows_inserted": rows_inserted,
                "compute_time": compute_time,
                "factors_count": len(factors_df.columns) - 2  # 排除 trade_date, ts_code
            }

        except Exception as e:
            logger.error(f"Error precomputing {date_str}: {e}")
            return {"status": "error", "trade_date": date_str, "error": str(e)}

    def _get_all_stocks(self, date: datetime) -> List[str]:
        """获取全市场上市股票"""
        date_str = date.strftime('%Y%m%d')

        results = DatabaseManager.fetchall(
            'tushare_biz',
            """
            SELECT ts_code FROM t_stock_basic
            WHERE list_status = 'L'
            AND list_date <= %s
            AND (delist_date IS NULL OR delist_date > %s)
            """,
            (date_str, date_str)
        )
        return [r['ts_code'] for r in results]

    def _save_to_db(self, df: pd.DataFrame) -> int:
        """保存到数据库，使用批量插入"""
        if df.empty:
            return 0

        # 获取所有因子列
        factor_cols = [c for c in self._schema.keys() if c in df.columns]
        columns = ['trade_date', 'ts_code'] + factor_cols

        update_cols = [c for c in factor_cols if c not in ['trade_date', 'ts_code']]

        # 构建值列表
        values_list = []
        for _, row in df.iterrows():
            values = []
            for c in columns:
                val = row.get(c, None)
                if val is None:
                    values.append(None)
                elif isinstance(val, float):
                    if np.isnan(val) or np.isinf(val):
                        values.append(None)
                    else:
                        values.append(val)
                else:
                    values.append(val)
            values_list.append(tuple(values))

        # 构建 SQL
        placeholders = ', '.join(['%s'] * len(columns))
        update_clause = ', '.join([f"{c}=VALUES({c})" for c in update_cols])

        sql = f"""
        INSERT INTO {self.TABLE_NAME} ({', '.join(columns)})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
        """

        try:
            batch_size = 1000
            total_inserted = 0

            for i in range(0, len(values_list), batch_size):
                batch = values_list[i:i+batch_size]
                DatabaseManager.executemany(self.DB_NAME, sql, batch)
                total_inserted += len(batch)

            logger.info(f"Saved {total_inserted} rows to {self.TABLE_NAME}")
            return total_inserted

        except Exception as e:
            logger.error(f"Error saving to DB: {e}")
            return 0

    def get_precomputed_factors(
        self,
        trade_date: datetime,
        stock_pool: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """读取预计算因子"""
        date_str = trade_date.strftime('%Y%m%d')

        if stock_pool:
            placeholders = ', '.join(['%s'] * len(stock_pool))
            sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE trade_date = %s AND ts_code IN ({placeholders})
            """
            params = (date_str,) + tuple(stock_pool)
        else:
            sql = f"SELECT * FROM {self.TABLE_NAME} WHERE trade_date = %s"
            params = (date_str,)

        results = DatabaseManager.fetchall(self.DB_NAME, sql, params)

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df.set_index('ts_code', inplace=True)

        # 删除元数据列
        for col in ['updated_at']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        return df

    def batch_precompute(
        self,
        start_date: datetime,
        end_date: datetime,
        skip_existing: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        批量预计算一段日期范围的因子

        Args:
            start_date: 开始日期
            end_date: 结束日期
            skip_existing: 是否跳过已存在的日期（默认使用配置）

        Returns:
            统计信息
        """
        skip_existing = skip_existing if skip_existing is not None else self.config.skip_existing

        # 获取交易日历
        from projects.quant_trading.backtest.data_manager import DataManager
        trade_dates = DataManager().get_trade_dates(start_date, end_date)

        logger.info(f"Batch precompute: {len(trade_dates)} trading days from {start_date.date()} to {end_date.date()}")

        # 检查已存在的日期
        if skip_existing:
            trade_dates = self._filter_existing_dates(trade_dates)
            logger.info(f"After filtering: {len(trade_dates)} dates to process")

        if not trade_dates:
            return {
                "status": "skipped",
                "message": "All dates already computed",
                "total_dates": 0,
                "success": 0,
                "failed": 0,
                "details": []
            }

        # 执行批量处理
        if self.config.use_parallel and len(trade_dates) > 1:
            return self._batch_precompute_parallel(trade_dates)
        else:
            return self._batch_precompute_sequential(trade_dates)

    def _filter_existing_dates(self, dates: List[datetime]) -> List[datetime]:
        """过滤掉已计算过的日期"""
        result = []
        for date in dates:
            date_str = date.strftime('%Y%m%d')
            existing = DatabaseManager.fetchone(
                self.DB_NAME,
                f"SELECT COUNT(*) as cnt FROM {self.TABLE_NAME} WHERE trade_date = %s",
                (date_str,)
            )
            if not existing or existing['cnt'] < self.config.min_stock_count:
                result.append(date)
        return result

    def _batch_precompute_sequential(
        self, trade_dates: List[datetime]
    ) -> Dict[str, Any]:
        """串行批量预计算"""
        results = {
            "total_dates": len(trade_dates),
            "success": 0,
            "failed": 0,
            "details": []
        }

        for i, date in enumerate(trade_dates):
            logger.info(f"[{i+1}/{len(trade_dates)}] Processing {date.strftime('%Y%m%d')}")

            try:
                result = self.precompute_for_date(date)
                if result.get("status") == "success":
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append(result)

            except Exception as e:
                logger.error(f"Failed to precompute {date}: {e}")
                results["failed"] += 1
                results["details"].append({
                    "date": date.strftime('%Y%m%d'),
                    "status": "error",
                    "error": str(e)
                })

        logger.info(f"Batch complete: {results['success']} success, {results['failed']} failed")
        return results

    def _batch_precompute_parallel(
        self, trade_dates: List[datetime]
    ) -> Dict[str, Any]:
        """多进程并行批量预计算"""
        num_workers = min(self.config.workers, cpu_count(), len(trade_dates))
        logger.info(f"Using {num_workers} workers for parallel processing")

        # 准备任务参数
        task_args = [(date,) for date in trade_dates]

        results = {
            "total_dates": len(trade_dates),
            "success": 0,
            "failed": 0,
            "details": [],
            "parallel": True,
            "workers": num_workers
        }

        with Pool(processes=num_workers) as pool:
            parallel_results = pool.starmap(_precompute_single_date_worker, task_args)

        for result in parallel_results:
            if result.get("status") == "success":
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append(result)

        logger.info(f"Parallel batch complete: {results['success']} success, {results['failed']} failed")
        return results


def _precompute_single_date_worker(trade_date: datetime) -> Dict[str, Any]:
    """多进程工作函数"""
    try:
        precomputer = FactorPrecomputer()
        return precomputer.precompute_for_date(trade_date)
    except Exception as e:
        logger.error(f"Worker error for {trade_date}: {e}")
        return {
            "status": "error",
            "trade_date": trade_date.strftime('%Y%m%d'),
            "error": str(e)
        }


# 便捷函数
def backfill_factors(
    start_year: int = 2010,
    end_year: int = 2024,
    workers: int = 4
) -> Dict[str, Any]:
    """
    补齐历史因子数据

    Args:
        start_year: 开始年份
        end_year: 结束年份
        workers: 并行进程数

    Returns:
        执行结果统计
    """
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    config = PrecomputeConfig(
        workers=workers,
        use_parallel=workers > 1,
        skip_existing=True
    )

    precomputer = FactorPrecomputer(config=config)
    return precomputer.batch_precompute(start_date, end_date)


def update_existing_factors(
    start_year: int = 2010,
    end_year: int = 2024,
    workers: int = 4
) -> Dict[str, Any]:
    """
    增量更新：只为已有数据计算新增的因子列

    适用于：新增因子后，不需要重新计算所有因子
    只计算缺失的列，使用 UPDATE 更新现有记录

    Args:
        start_year: 开始年份
        end_year: 结束年份
        workers: 并行进程数（目前仅用于初始化配置，更新过程是串行的）

    Returns:
        执行结果统计
    """
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    config = PrecomputeConfig(
        workers=workers,
        use_parallel=False,  # 增量更新目前使用串行模式
        skip_existing=True
    )

    precomputer = FactorPrecomputer(config=config)
    return precomputer.update_missing_factors(start_date, end_date)


def check_factor_status() -> Dict[str, Any]:
    """
    检查当前因子覆盖状态

    Returns:
        包含数据库中已有因子和缺失因子的信息
    """
    precomputer = FactorPrecomputer()

    existing_cols = set(precomputer._get_existing_columns())
    all_factor_cols = set(precomputer._schema.keys())
    missing_cols = all_factor_cols - existing_cols

    # 获取基本统计信息
    stats = DatabaseManager.fetchone(
        precomputer.DB_NAME,
        f"""
        SELECT
            COUNT(DISTINCT trade_date) as total_dates,
            COUNT(*) as total_rows
        FROM {precomputer.TABLE_NAME}
        """
    )

    return {
        "status": "ok",
        "total_factors_defined": len(all_factor_cols),
        "factors_in_db": len(existing_cols - {'trade_date', 'ts_code', 'updated_at'}),
        "missing_factors": sorted(missing_cols),
        "new_factors_count": len(missing_cols),
        "database_stats": {
            "total_dates": stats.get('total_dates', 0) if stats else 0,
            "total_rows": stats.get('total_rows', 0) if stats else 0
        }
    }


# 全局单例
_precomputer_instance: Optional[FactorPrecomputer] = None


def get_factor_precomputer(config: Optional[PrecomputeConfig] = None) -> FactorPrecomputer:
    """获取 FactorPrecomputer 单例"""
    global _precomputer_instance
    if _precomputer_instance is None:
        _precomputer_instance = FactorPrecomputer(config=config)
    return _precomputer_instance


# 使用示例
if __name__ == "__main__":
    import sys

    # 检查因子状态
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        status = check_factor_status()
        print(f"因子状态检查:")
        print(f"  已定义因子: {status['total_factors_defined']}")
        print(f"  数据库已有: {status['factors_in_db']}")
        print(f"  缺失因子: {status['new_factors_count']}")
        if status['missing_factors']:
            print(f"  缺失列表: {status['missing_factors']}")
        print(f"  数据行数: {status['database_stats']['total_rows']}")
        print(f"  覆盖日期: {status['database_stats']['total_dates']}")
        sys.exit(0)

    # 增量更新模式
    if len(sys.argv) > 1 and sys.argv[1] == "--update-existing":
        print("开始增量更新...")
        result = update_existing_factors(start_year=2010, end_year=2024)
        print(f"增量更新结果: {result}")
        sys.exit(0)

    # 默认：补齐 2010 年以来的数据
    result = backfill_factors(start_year=2010, end_year=2024, workers=4)
    print(result)
