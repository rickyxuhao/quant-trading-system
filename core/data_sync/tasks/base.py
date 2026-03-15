"""
同步任务基类 - 提供通用的批量插入功能
"""
import pandas as pd
from typing import Dict, Any, List, Optional
from abc import abstractmethod

from core.data_sync.task import SyncTask
from core.storage.relational.connection import DatabaseManager


class BaseTushareTask(SyncTask):
    """Tushare 同步任务基类 - 提供优化的批量插入"""

    # 默认批量插入批次大小
    DEFAULT_BATCH_SIZE = 1000

    def __init__(self, name: str, table_name: str, db_name: str,
                 sync_type: str = "full", check_after_sync: bool = True,
                 batch_size: int = 1000):
        super().__init__(name, table_name, db_name, sync_type, check_after_sync)
        self.insert_batch_size = batch_size or self.DEFAULT_BATCH_SIZE

    @staticmethod
    def _prepare_row_data(row: pd.Series, columns: List[str]) -> List[Any]:
        """
        准备单行数据，处理 NaN 值

        Args:
            row: DataFrame 行
            columns: 列名列表

        Returns:
            处理后的数据列表
        """
        row_data = []
        for col in columns:
            # 处理带反引号的列名
            col_name = col.strip('`')
            val = row.get(col_name)
            # 将 NaN 转换为 None
            if pd.isna(val):
                row_data.append(None)
            else:
                row_data.append(val)
        return row_data

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        同步数据到 MySQL - 使用优化的批量插入

        Args:
            df: 待同步的 DataFrame

        Returns:
            统计信息字典
        """
        raise NotImplementedError("子类必须实现此方法或使用通用实现")

    def bulk_insert(self, df: pd.DataFrame, columns: List[str],
                    unique_columns: List[str] = None,
                    update_columns: List[str] = None,
                    transformers: Dict[str, callable] = None) -> Dict[str, int]:
        """
        批量插入数据 - 优化的通用方法

        Args:
            df: 待插入的 DataFrame
            columns: 需要插入的列名列表（支持带反引号的列名如 `change`）
            unique_columns: 用于判断重复的唯一列（用于 ON DUPLICATE KEY）
            update_columns: 重复时需要更新的列（None 表示更新所有非唯一列）
            transformers: 列值转换函数字典 {列名: 转换函数}

        Returns:
            统计信息字典
        """
        stats = {"affected": 0, "inserted": 0, "updated": 0}

        if df.empty:
            print("⚠️ 无数据需要同步")
            return stats

        # 准备数据行
        rows = []
        for _, row in df.iterrows():
            row_data = []
            for col in columns:
                col_name = col.strip('`')
                val = row.get(col_name)

                # 应用自定义转换器
                if transformers and col_name in transformers:
                    val = transformers[col_name](val)
                elif pd.isna(val):
                    val = None

                row_data.append(val)
            rows.append(row_data)

        # 构建 ON DUPLICATE KEY UPDATE 子句
        on_duplicate = None
        if unique_columns:
            # 确定需要更新的列
            if update_columns is None:
                # 默认更新所有非唯一列
                update_cols = [
                    col for col in columns
                    if col.strip('`') not in unique_columns
                ]
            else:
                update_cols = update_columns

            # MySQL 8.0.19+ / 9.x: 使用 AS new 别名语法替代 VALUES()
            if update_cols:
                on_duplicate = ', '.join([
                    f"{col}=new.{col}" for col in update_cols
                ])

        # 使用 DatabaseManager 的批量插入
        result = DatabaseManager.insert_many(
            db_name=self.db_name,
            table=self.table_name,
            columns=columns,
            rows=rows,
            batch_size=self.insert_batch_size,
            on_duplicate=on_duplicate
        )

        return result

    def build_stats(self, total_rows: int, affected: int = None) -> Dict[str, int]:
        """
        构建统计信息

        Args:
            total_rows: 总行数
            affected: 受影响的行数（None 时等于 total_rows）

        Returns:
            统计信息字典
        """
        affected = affected or total_rows
        return {
            "affected": affected,
            "inserted": total_rows,
            "updated": affected
        }
