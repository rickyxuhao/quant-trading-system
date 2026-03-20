#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare 同步基础模块 - MySQL 版本
包含公共配置、数据库连接、日志、重试机制等
使用项目统一的 DatabaseManager 进行数据库操作
"""

import os
import sys
import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from contextlib import contextmanager

import pandas as pd
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入项目统一的数据库连接管理
try:
    from core.storage.relational.connection import DatabaseManager
except ImportError:
    print("⚠️ 警告: 无法导入 core.storage.relational.connection.DatabaseManager")
    DatabaseManager = None

# 尝试导入 Tushare 客户端
try:
    from core.data_access.tushare.client import get_tushare_client
except ImportError:
    print("⚠️ 警告: 无法导入 core.data_access.tushare.client，将使用内置 Tushare 客户端")
    get_tushare_client = None


# ========================================================
# 配置和日志
# ========================================================

@dataclass
class SyncConfig:
    """同步配置"""
    db_name: str = "tushare_biz"
    tushare_token: str = ""
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: int = 5
    rate_limit_per_minute: int = 500
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> 'SyncConfig':
        """从环境变量加载配置"""
        return cls(
            db_name=os.getenv("DB_NAME_TUSHARE", "tushare_biz"),
            tushare_token=os.getenv("TUSHARE_TOKEN", ""),
            batch_size=int(os.getenv("SYNC_BATCH_SIZE", "1000")),
            max_retries=int(os.getenv("SYNC_MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("SYNC_RETRY_DELAY", "5")),
            rate_limit_per_minute=int(os.getenv("TUSHARE_RATE_LIMIT", "500")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """配置日志"""
    logger = logging.getLogger("tushare_sync")
    logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有处理器
    logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ========================================================
# 速率限制器
# ========================================================

class RateLimiter:
    """API 速率限制器"""

    def __init__(self, max_requests_per_minute: int = 500):
        self.max_requests = max_requests_per_minute
        self.interval = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.logger = logging.getLogger("tushare_sync")

    def wait_if_needed(self):
        """根据需要等待以符合速率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.interval:
            sleep_time = self.interval - elapsed
            time.sleep(sleep_time)

        self.last_request_time = time.time()


# ========================================================
# Tushare 客户端包装
# ========================================================

class TushareSyncClient:
    """Tushare 同步客户端"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit_per_minute)
        self.logger = logging.getLogger("tushare_sync")
        self._pro = None

        # 尝试使用项目内置客户端
        if get_tushare_client:
            try:
                client = get_tushare_client()
                self._pro = client.pro
                self.logger.info("✅ 使用项目内置 Tushare 客户端")
                return
            except Exception as e:
                self.logger.warning(f"⚠️ 内置客户端初始化失败: {e}")

        # 使用独立 Tushare 连接
        try:
            import tushare as ts
            if not config.tushare_token:
                raise ValueError("TUSHARE_TOKEN 环境变量未设置")
            ts.set_token(config.tushare_token)
            self._pro = ts.pro_api()
            self.logger.info("✅ Tushare 客户端初始化成功")
        except Exception as e:
            self.logger.error(f"❌ Tushare 客户端初始化失败: {e}")
            raise

    def query(self, api_name: str, fields: str = None, **kwargs) -> pd.DataFrame:
        """查询 Tushare API，带重试机制"""
        for attempt in range(self.config.max_retries):
            try:
                self.rate_limiter.wait_if_needed()

                params = kwargs.copy()
                if fields:
                    params['fields'] = fields

                df = self._pro.query(api_name, **params)
                return df if df is not None else pd.DataFrame()

            except Exception as e:
                self.logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise

        return pd.DataFrame()


# ========================================================
# 数据库操作包装类 - 使用项目 DatabaseManager
# ========================================================

class SyncDatabaseManager:
    """同步数据库管理器 - 包装项目的 DatabaseManager"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.db_name = config.db_name
        self.logger = logging.getLogger("tushare_sync")

        if DatabaseManager is None:
            raise ImportError("无法导入 DatabaseManager，请确保 core.storage.relational.connection 可用")

    def execute(self, sql: str, params: tuple = None) -> int:
        """执行 SQL 语句"""
        return DatabaseManager.execute(self.db_name, sql, params)

    def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询单条记录"""
        return DatabaseManager.fetchone(self.db_name, sql, params)

    def fetchall(self, sql: str, params: tuple = None) -> List[Dict]:
        """查询所有记录"""
        return DatabaseManager.fetchall(self.db_name, sql, params)

    def upsert(self, table: str, columns: List[str], rows: List[List],
               unique_columns: List[str], update_columns: List[str] = None) -> Dict[str, int]:
        """
        UPSERT 操作 - MySQL 使用 ON DUPLICATE KEY UPDATE

        Args:
            table: 表名
            columns: 列名列表
            rows: 数据行列表
            unique_columns: 唯一键列名（用于匹配冲突）
            update_columns: 冲突时需要更新的列，None则更新所有非唯一列

        Returns:
            统计信息字典
        """
        if not rows:
            return {"inserted": 0, "updated": 0, "total": 0}

        # 确定需要更新的列
        if update_columns is None:
            update_columns = [col for col in columns if col not in unique_columns]

        # 构建 ON DUPLICATE KEY UPDATE 子句
        # MySQL 8.0.19+ / 9.x: 使用 AS new 别名语法替代 VALUES()
        if update_columns:
            update_clause = ', '.join([f"`{col}` = new.`{col}`" for col in update_columns])
            on_duplicate = update_clause
        else:
            on_duplicate = None

        # 使用 DatabaseManager.insert_many 进行批量插入
        result = DatabaseManager.insert_many(
            db_name=self.db_name,
            table=table,
            columns=columns,
            rows=rows,
            batch_size=self.config.batch_size,
            on_duplicate=on_duplicate
        )

        return {
            "inserted": result.get("inserted", 0),
            "updated": result.get("updated", 0),
            "total": len(rows)
        }

    def get_max_date(self, table: str, date_column: str = 'trade_date',
                     where_clause: str = None) -> Optional[str]:
        """获取表中最大日期"""
        sql = f"SELECT MAX(`{date_column}`) as max_date FROM `{table}`"
        if where_clause:
            sql += f" WHERE {where_clause}"

        result = self.fetchone(sql)
        return result['max_date'] if result and result['max_date'] else None

    def get_count(self, table: str, where_clause: str = None) -> int:
        """获取表记录数"""
        sql = f"SELECT COUNT(*) as cnt FROM `{table}`"
        if where_clause:
            sql += f" WHERE {where_clause}"

        result = self.fetchone(sql)
        return result['cnt'] if result else 0


# ========================================================
# 基础同步类
# ========================================================

class BaseSyncTask:
    """基础同步任务类"""

    # 子类需要覆盖这些属性
    TABLE_NAME: str = ""  # 数据库表名
    API_NAME: str = ""    # Tushare API 名称
    COLUMNS: List[str] = []  # 列名列表
    UNIQUE_COLUMNS: List[str] = []  # 唯一键列名
    UPDATE_COLUMNS: Optional[List[str]] = None  # 更新列名，None表示更新所有非唯一列
    SYNC_TYPE: str = "incremental"  # 同步类型: full/incremental
    DATE_COLUMN: Optional[str] = None  # 日期列名（用于增量同步判断）
    API_DATE_COLUMN: Optional[str] = None  # API查询用的日期参数名（如start_date/end_date或ann_date）
    TS_CODE_REQUIRED: bool = False  # 是否需要按股票代码循环
    MIN_EXPECTED_ROWS: int = 0  # 最小预期数据条数，用于验证
    SUPPORTS_DATE_FILTER: bool = True  # API是否支持start_date/end_date参数过滤
    
    # 新增：分类和描述（用于统一注册表）
    CATEGORY: str = "other"  # 分类: market/financial/holder/basic/index/etc
    DESCRIPTION: str = ""    # 任务描述

    def __init__(self, config: SyncConfig, db: SyncDatabaseManager, client: TushareSyncClient):
        self.config = config
        self.db = db
        self.client = client
        self.logger = logging.getLogger("tushare_sync")

    def get_update_columns(self) -> List[str]:
        """获取需要更新的列"""
        if self.UPDATE_COLUMNS is not None:
            return self.UPDATE_COLUMNS
        return [c for c in self.COLUMNS if c not in self.UNIQUE_COLUMNS]

    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        df = self.client.query("stock_basic", list_status='L', fields='ts_code')
        if df.empty:
            return []
        return df['ts_code'].tolist()

    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        results = self.db.fetchall(
            f"""
            SELECT `cal_date` FROM `t_stock_tradedate`
            WHERE `cal_date` BETWEEN %s AND %s
            AND `is_open` = 1
            ORDER BY `cal_date`
            """,
            (start_date, end_date)
        )
        return [r['cal_date'] for r in results]

    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理数据框"""
        import numpy as np

        # 确保所有列都存在
        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[self.COLUMNS]

        # 处理 NaN 值 - 将 NaN/None/空值统一转换为 None
        # 使用 replace 处理各种缺失值标记
        df = df.replace({np.nan: None, 'NaN': None, 'nan': None, '': None})

        # 额外处理：遍历每一列，确保所有缺失值都被转换为 None
        for col in df.columns:
            if df[col].dtype == 'object':
                # 对于 object 类型列，使用 pandas 的 where 方法
                df[col] = df[col].where(df[col].notna(), None)
            else:
                # 对于数值类型，先转换为 object 类型以支持 None
                df[col] = df[col].apply(lambda x: None if pd.isna(x) else x)

        return df

    def determine_date_range(self, mode: str, start_date: Optional[str], end_date: Optional[str],
                             is_full_history: bool = False) -> tuple:
        """
        确定日期范围

        Args:
            mode: 同步模式 (full/incremental)
            start_date: 指定的开始日期
            end_date: 指定的结束日期
            is_full_history: 是否获取完整历史数据（用于财务数据首次同步）
        """
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if not start_date:
            if mode == 'full' or is_full_history:
                # 全量模式或需要完整历史：从2005年开始
                start_date = '20050101'
                self.logger.info("🆕 全量同步模式，从 2005-01-01 开始获取完整历史数据")
            elif mode == 'incremental' and self.DATE_COLUMN:
                # 增量模式：获取数据库中最新日期
                max_date = self.db.get_max_date(self.TABLE_NAME, self.DATE_COLUMN)
                if max_date:
                    start_date = (datetime.strptime(max_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                    self.logger.info(f"📅 增量同步，从上次最后日期 {max_date} 的次日开始")
                else:
                    # 首次同步，从2005年开始
                    start_date = '20050101'
                    self.logger.info("🆕 首次同步，从 2005-01-01 开始获取完整历史数据")
            else:
                start_date = '20050101'

        return start_date, end_date

    def sync_full(self, mode: str = "full") -> Dict[str, Any]:
        """全量同步（一次性获取所有数据）"""
        self.logger.info(f"📥 从 Tushare 获取数据...")

        # 构建查询参数
        params = {}
        if hasattr(self, 'FETCH_PARAMS'):
            params.update(self.FETCH_PARAMS)

        df = self.client.query(self.API_NAME, **params)

        if df.empty:
            self.logger.info("⚠️ 无数据返回")
            return {"status": "success", "rows": 0}

        self.logger.info(f"✅ 获取 {len(df)} 条记录")

        # 清理数据
        df = self.clean_dataframe(df)
        rows = df.values.tolist()

        # UPSERT
        self.logger.info(f"💾 写入数据库...")
        result = self.db.upsert(
            self.TABLE_NAME, self.COLUMNS, rows,
            self.UNIQUE_COLUMNS, self.get_update_columns()
        )

        self.logger.info(f"✅ 同步完成: 插入 {result['inserted']}, 更新 {result['updated']}")

        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": len(df),
            "rows_inserted": result['inserted'],
            "rows_updated": result['updated']
        }

    def sync_by_date(self, mode: str = "incremental",
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Dict[str, Any]:
        """按日期同步"""
        start_date, end_date = self.determine_date_range(mode, start_date, end_date, is_full_history=(mode=='full'))

        # 检查是否需要同步
        if start_date > end_date:
            self.logger.info("✅ 数据已是最新，无需同步")
            return {"status": "skipped", "reason": "up_to_date"}

        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")

        # 获取交易日列表
        trade_dates = self.get_trade_dates(start_date, end_date)
        if not trade_dates:
            self.logger.info("⚠️ 无交易日需要同步")
            return {"status": "skipped", "reason": "no_trade_dates"}

        self.logger.info(f"📊 需要同步 {len(trade_dates)} 个交易日")

        # 逐日同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_dates = []

        for i, trade_date in enumerate(trade_dates, 1):
            try:
                self.logger.info(f"   [{i}/{len(trade_dates)}] 处理 {trade_date}...")

                # 获取单日数据
                df = self.client.query(self.API_NAME, trade_date=trade_date)

                if df.empty:
                    continue

                # 清理数据
                df = self.clean_dataframe(df)
                rows = df.values.tolist()

                # UPSERT
                result = self.db.upsert(
                    self.TABLE_NAME, self.COLUMNS, rows,
                    self.UNIQUE_COLUMNS, self.get_update_columns()
                )

                total_fetched += len(df)
                total_inserted += result['inserted']
                total_updated += result['updated']

                self.logger.info(f"   ✓ {len(df)} 条")

            except Exception as e:
                self.logger.error(f"   ✗ 失败: {e}")
                failed_dates.append(trade_date)
                continue

        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_dates:
            self.logger.warning(f"⚠️ 失败日期: {failed_dates}")

        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_dates": failed_dates
        }

    def sync_by_stock_code(self, mode: str = "incremental",
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        按股票代码循环同步（用于财务数据）

        关键改进:
        1. 全量模式下获取完整历史数据（2005年至今）
        2. 支持按报告期（end_date）过滤，这对于财务数据很重要
        3. 添加数据验证和进度报告
        """
        # 获取股票列表（包括上市和退市股票，以获取完整历史）
        stock_list = self._get_all_stock_codes()
        if not stock_list:
            return {"status": "error", "reason": "no_stocks"}

        self.logger.info(f"📈 需要处理 {len(stock_list)} 只股票")

        # 检查是否首次同步（表中无数据）
        current_count = self.db.get_count(self.TABLE_NAME)
        is_first_sync = current_count == 0
        self.logger.info(f"📊 当前表数据量: {current_count} 条")

        # 确定是否需要获取完整历史
        is_full_history = mode == 'full' or is_first_sync

        # 日期范围
        start_date, end_date = self.determine_date_range(mode, start_date, end_date, is_full_history)

        if start_date > end_date:
            self.logger.info("✅ 数据已是最新")
            return {"status": "skipped", "reason": "up_to_date"}

        self.logger.info(f"📅 查询日期范围: {start_date} - {end_date}")

        # 对于财务数据，我们使用报告期（end_date）作为过滤条件
        # 这样可以获取完整的季度报告数据
        report_period_filter = self._build_report_period_filter(start_date, end_date)

        # 逐股票同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_stocks = []
        stocks_with_data = 0

        for i, ts_code in enumerate(stock_list, 1):
            try:
                if i % 100 == 0 or i == 1:
                    self.logger.info(f"   进度: {i}/{len(stock_list)} ({i*100//len(stock_list)}%) - "
                                   f"已获取 {total_fetched} 条")

                # 获取数据 - 只传 ts_code，对于不支持日期过滤的 API 不传递日期参数
                params = {'ts_code': ts_code}
                if self.SUPPORTS_DATE_FILTER:
                    params.update(report_period_filter)

                df = self.client.query(self.API_NAME, **params)

                # 对于不支持日期过滤的 API，在 Python 端进行日期过滤
                if not self.SUPPORTS_DATE_FILTER and self.DATE_COLUMN and not df.empty:
                    df = self._filter_by_date(df, start_date, end_date)

                if df.empty:
                    continue

                stocks_with_data += 1

                # 清理数据
                df = self.clean_dataframe(df)
                rows = df.values.tolist()

                # UPSERT
                result = self.db.upsert(
                    self.TABLE_NAME, self.COLUMNS, rows,
                    self.UNIQUE_COLUMNS, self.get_update_columns()
                )

                total_fetched += len(df)
                total_inserted += result['inserted']
                total_updated += result['updated']

            except Exception as e:
                self.logger.error(f"   ✗ {ts_code} 失败: {e}")
                failed_stocks.append(ts_code)
                continue

        # 数据验证
        final_count = self.db.get_count(self.TABLE_NAME)
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"✅ 同步完成统计:")
        self.logger.info(f"   - 处理股票数: {len(stock_list)}")
        self.logger.info(f"   - 有数据的股票: {stocks_with_data}")
        self.logger.info(f"   - 获取记录数: {total_fetched}")
        self.logger.info(f"   - 插入记录数: {total_inserted}")
        self.logger.info(f"   - 更新记录数: {total_updated}")
        self.logger.info(f"   - 失败股票数: {len(failed_stocks)}")
        self.logger.info(f"   - 表最终数据量: {final_count}")

        if failed_stocks:
            self.logger.warning(f"⚠️ 失败股票: {failed_stocks[:10]}{'...' if len(failed_stocks) > 10 else ''}")

        # 验证数据量是否合理
        self._validate_sync_result(total_fetched, final_count, is_first_sync)

        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "stocks_processed": len(stock_list),
            "stocks_with_data": stocks_with_data,
            "failed_stocks": len(failed_stocks),
            "final_count": final_count
        }

    def _get_all_stock_codes(self) -> List[str]:
        """获取所有股票代码（包括上市和退市股票）"""
        all_stocks = set()

        # 获取上市股票
        try:
            df_listed = self.client.query("stock_basic", list_status='L', fields='ts_code')
            if not df_listed.empty:
                all_stocks.update(df_listed['ts_code'].tolist())
        except Exception as e:
            self.logger.warning(f"获取上市股票列表失败: {e}")

        # 获取退市股票（为了获取完整历史财务数据）
        try:
            df_delisted = self.client.query("stock_basic", list_status='D', fields='ts_code')
            if not df_delisted.empty:
                all_stocks.update(df_delisted['ts_code'].tolist())
                self.logger.info(f"   包含 {len(df_delisted)} 只退市股票")
        except Exception as e:
            self.logger.warning(f"获取退市股票列表失败: {e}")

        return sorted(list(all_stocks))

    def _build_report_period_filter(self, start_date: str, end_date: str) -> Dict[str, str]:
        """
        构建报告期过滤参数

        对于财务数据，Tushare API 使用 start_date 和 end_date 作为报告期（end_date）范围
        """
        return {
            'start_date': start_date,
            'end_date': end_date
        }

    def _filter_by_date(self, df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """
        在 Python 端按日期过滤数据（用于不支持日期过滤参数的 API）

        Args:
            df: 原始数据框
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            过滤后的数据框
        """
        if df.empty or not self.DATE_COLUMN:
            return df

        date_col = self.DATE_COLUMN
        if date_col not in df.columns:
            return df

        # 将日期列转换为字符串格式便于比较
        df_copy = df.copy()
        df_copy[date_col] = df_copy[date_col].astype(str)

        # 过滤日期范围
        filtered = df_copy[(df_copy[date_col] >= start_date) & (df_copy[date_col] <= end_date)]

        return filtered

    def _validate_sync_result(self, fetched: int, final_count: int, is_first_sync: bool):
        """验证同步结果"""
        if fetched == 0:
            self.logger.warning("⚠️ 警告: 未获取到任何数据，请检查API参数或数据源")
            return

        if is_first_sync and self.MIN_EXPECTED_ROWS > 0:
            if final_count < self.MIN_EXPECTED_ROWS:
                self.logger.warning(
                    f"⚠️ 警告: 首次同步数据量 ({final_count}) 低于预期 ({self.MIN_EXPECTED_ROWS})"
                )
            else:
                self.logger.info(f"✅ 数据量验证通过: {final_count} >= {self.MIN_EXPECTED_ROWS}")

    def execute(self, mode: str = "auto",
                start_date: Optional[str] = None,
                end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        执行同步任务

        Args:
            mode: 同步模式 (full/incremental/auto)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            同步结果统计
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 开始同步: {self.TABLE_NAME}")
        self.logger.info(f"📌 同步模式: {mode}")

        # 确定同步模式
        if mode == "auto":
            mode = self.SYNC_TYPE

        try:
            # 根据配置选择同步方式
            if self.TS_CODE_REQUIRED:
                return self.sync_by_stock_code(mode, start_date, end_date)
            elif self.DATE_COLUMN:
                return self.sync_by_date(mode, start_date, end_date)
            else:
                return self.sync_full(mode)
        except Exception as e:
            self.logger.error(f"❌ 同步失败: {e}")
            raise


def create_base_parser(description: str) -> argparse.ArgumentParser:
    """创建基础参数解析器"""
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--mode', type=str, choices=['full', 'incremental', 'auto'],
                       default='auto', help='同步模式 (默认: auto)')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYYMMDD)')
    parser.add_argument('--log-file', type=str, help='日志文件路径')
    return parser


def init_sync_env(log_file: Optional[str] = None) -> tuple:
    """
    初始化同步环境

    Returns:
        (config, db, client, logger) 元组
    """
    # 加载配置
    config = SyncConfig.from_env()

    # 设置日志
    logger = setup_logging(config.log_level, log_file)
    logger.info("=" * 60)
    logger.info("🚀 Tushare 数据同步工具启动 (MySQL版本)")
    logger.info(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化组件
    try:
        db = SyncDatabaseManager(config)
        client = TushareSyncClient(config)
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        sys.exit(1)

    return config, db, client, logger


def run_main(task_class: type, description: str) -> None:
    """
    通用同步任务入口函数
    
    用法:
        if __name__ == "__main__":
            run_main(StockBasicSync, "股票基础信息同步")
    """
    parser = create_base_parser(description)
    args = parser.parse_args()
    config, db, client, logger = init_sync_env(args.log_file)
    sync_task = task_class(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result.get('rows_fetched', 0)} 条, "
                   f"插入 {result.get('rows_inserted', 0)}, 更新 {result.get('rows_updated', 0)}")
    elif result['status'] == 'skipped':
        logger.info(f"⏭️  {result.get('reason', '已跳过')}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


# ============================================================================
# 同步任务注册表（用于统一入口）
# ============================================================================

from typing import Dict, Type


class SyncRegistry:
    """同步任务统一注册表"""
    
    _tasks: Dict[str, Type[BaseSyncTask]] = {}
    _categories: Dict[str, list] = {}
    
    @classmethod
    def register(cls, task_class: Type[BaseSyncTask]) -> Type[BaseSyncTask]:
        """
        装饰器：自动注册同步任务
        
        用法:
            @SyncRegistry.register
            class StockBasicSync(BaseSyncTask):
                TABLE_NAME = "t_stock_basic"
                CATEGORY = "basic"
        """
        name = task_class.TABLE_NAME
        cls._tasks[name] = task_class
        category = task_class.CATEGORY
        if category not in cls._categories:
            cls._categories[category] = []
        cls._categories[category].append(name)
        return task_class
    
    @classmethod
    def get_by_category(cls, category: str) -> list:
        """按分类获取任务类列表"""
        return [cls._tasks[name] for name in cls._categories.get(category, [])]
    
    @classmethod
    def list_categories(cls) -> list:
        """列出所有分类"""
        return list(cls._categories.keys())
    
    @classmethod
    def list_tasks(cls, category: str = None) -> list:
        """列出所有任务名称"""
        if category:
            return cls._categories.get(category, [])
        return list(cls._tasks.keys())
    
    @classmethod
    def run_task(cls, name: str, mode: str = "incremental", 
                 start_date: str = None, end_date: str = None,
                 log_file: str = None) -> dict:
        """运行单个任务"""
        if name not in cls._tasks:
            raise ValueError(f"未知任务: {name}, 可用任务: {list(cls._tasks.keys())}")
        
        task_class = cls._tasks[name]
        config, db, client, logger = init_sync_env(log_file)
        task = task_class(config, db, client)
        return task.execute(mode=mode, start_date=start_date, end_date=end_date)
