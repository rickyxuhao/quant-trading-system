"""
数据同步日志记录
"""
from datetime import datetime
from typing import Optional, Dict, Any

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


class SyncLogger:
    """同步日志记录器"""
    
    DB_NAME = "interface"
    LOG_TABLE = "sync_log"
    STATE_TABLE = "sync_state"
    
    @classmethod
    def init_tables(cls):
        """初始化日志表（如果不存在）"""
        # 同步日志表
        create_log_sql = """
        CREATE TABLE IF NOT EXISTS sync_log (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
            table_name VARCHAR(100) NOT NULL COMMENT '表名',
            sync_type VARCHAR(20) COMMENT '同步类型：full/incremental',
            start_time TIMESTAMP NOT NULL COMMENT '开始时间',
            end_time TIMESTAMP NULL COMMENT '结束时间',
            duration_seconds INT COMMENT '耗时秒数',
            status VARCHAR(20) COMMENT '状态：success/failed/running',
            rows_affected INT COMMENT '影响行数',
            rows_inserted INT COMMENT '插入行数',
            rows_updated INT COMMENT '更新行数',
            error_message TEXT COMMENT '错误信息',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_task_name (task_name),
            INDEX idx_table_name (table_name),
            INDEX idx_start_time (start_time),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据同步日志';
        """
        
        # 同步状态表
        create_state_sql = """
        CREATE TABLE IF NOT EXISTS sync_state (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_name VARCHAR(100) NOT NULL UNIQUE COMMENT '任务名称',
            table_name VARCHAR(100) NOT NULL COMMENT '表名',
            last_sync_time TIMESTAMP NULL COMMENT '最后同步时间',
            last_sync_date VARCHAR(8) COMMENT '最后同步日期YYYYMMDD',
            last_success_time TIMESTAMP NULL COMMENT '最后成功时间',
            last_success_date VARCHAR(8) COMMENT '最后成功日期',
            total_rows INT COMMENT '当前表记录数',
            consecutive_failures INT DEFAULT 0 COMMENT '连续失败次数',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_table_name (table_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据同步状态';
        """
        
        DatabaseManager.execute(cls.DB_NAME, create_log_sql)
        DatabaseManager.execute(cls.DB_NAME, create_state_sql)
    
    @classmethod
    def start_log(cls, task_name: str, table_name: str, sync_type: str) -> int:
        """
        开始记录同步日志
        
        Returns:
            日志ID
        """
        sql = f"""
            INSERT INTO {cls.LOG_TABLE} 
            (task_name, table_name, sync_type, start_time, status)
            VALUES (%s, %s, %s, NOW(), 'running')
        """
        DatabaseManager.execute(cls.DB_NAME, sql, (task_name, table_name, sync_type))
        
        # 获取刚插入的ID
        result = DatabaseManager.fetchone(
            cls.DB_NAME, 
            f"SELECT id FROM {cls.LOG_TABLE} WHERE task_name=%s ORDER BY id DESC LIMIT 1",
            (task_name,)
        )
        return result['id']
    
    @classmethod
    def end_log(cls, log_id: int, status: str, rows_affected: int = 0, 
                rows_inserted: int = 0, rows_updated: int = 0, 
                error_message: str = None):
        """结束记录同步日志"""
        sql = f"""
            UPDATE {cls.LOG_TABLE} 
            SET end_time = NOW(),
                duration_seconds = TIMESTAMPDIFF(SECOND, start_time, NOW()),
                status = %s,
                rows_affected = %s,
                rows_inserted = %s,
                rows_updated = %s,
                error_message = %s
            WHERE id = %s
        """
        DatabaseManager.execute(
            cls.DB_NAME, sql, 
            (status, rows_affected, rows_inserted, rows_updated, error_message, log_id)
        )
    
    @classmethod
    def update_state(cls, task_name: str, table_name: str, 
                     success: bool, total_rows: int = None, sync_date: str = None):
        """更新同步状态"""
        # 先检查记录是否存在
        result = DatabaseManager.fetchone(
            cls.DB_NAME,
            f"SELECT id FROM {cls.STATE_TABLE} WHERE task_name = %s",
            (task_name,)
        )
        
        if success:
            if result:
                sql = f"""
                    UPDATE {cls.STATE_TABLE} 
                    SET last_sync_time = NOW(),
                        last_sync_date = %s,
                        last_success_time = NOW(),
                        last_success_date = %s,
                        total_rows = %s,
                        consecutive_failures = 0,
                        updated_at = NOW()
                    WHERE task_name = %s
                """
                DatabaseManager.execute(cls.DB_NAME, sql, 
                    (sync_date, sync_date, total_rows, task_name))
            else:
                sql = f"""
                    INSERT INTO {cls.STATE_TABLE} 
                    (task_name, table_name, last_sync_time, last_sync_date,
                     last_success_time, last_success_date, total_rows)
                    VALUES (%s, %s, NOW(), %s, NOW(), %s, %s)
                """
                DatabaseManager.execute(cls.DB_NAME, sql,
                    (task_name, table_name, sync_date, sync_date, total_rows))
        else:
            # 失败，增加连续失败计数
            if result:
                sql = f"""
                    UPDATE {cls.STATE_TABLE} 
                    SET last_sync_time = NOW(),
                        last_sync_date = %s,
                        consecutive_failures = consecutive_failures + 1,
                        updated_at = NOW()
                    WHERE task_name = %s
                """
                DatabaseManager.execute(cls.DB_NAME, sql, (sync_date, task_name))
            else:
                sql = f"""
                    INSERT INTO {cls.STATE_TABLE} 
                    (task_name, table_name, last_sync_time, last_sync_date, consecutive_failures)
                    VALUES (%s, %s, NOW(), %s, 1)
                """
                DatabaseManager.execute(cls.DB_NAME, sql, (task_name, table_name, sync_date))
    
    @classmethod
    def get_last_sync_date(cls, task_name: str) -> Optional[str]:
        """获取最后同步日期"""
        result = DatabaseManager.fetchone(
            cls.DB_NAME,
            f"SELECT last_success_date FROM {cls.STATE_TABLE} WHERE task_name = %s",
            (task_name,)
        )
        return result['last_success_date'] if result else None
    
    @classmethod
    def get_recent_logs(cls, task_name: str = None, limit: int = 10) -> list:
        """获取最近同步日志"""
        if task_name:
            sql = f"""
                SELECT * FROM {cls.LOG_TABLE} 
                WHERE task_name = %s 
                ORDER BY start_time DESC 
                LIMIT %s
            """
            return DatabaseManager.fetchall(cls.DB_NAME, sql, (task_name, limit))
        else:
            sql = f"""
                SELECT * FROM {cls.LOG_TABLE} 
                ORDER BY start_time DESC 
                LIMIT %s
            """
            return DatabaseManager.fetchall(cls.DB_NAME, sql, (limit,))
