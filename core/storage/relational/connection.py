"""
数据库连接管理 - 使用连接池
支持多库：tushare_biz（原始数据）、interface（加工数据）
"""
import os
from contextlib import contextmanager
from typing import Generator, Dict, Any

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class DatabaseConfig:
    """数据库配置管理 - 从环境变量读取"""

    @staticmethod
    def get_config(db_name: str) -> Dict[str, Any]:
        """
        获取数据库配置

        Args:
            db_name: 数据库名称，'tushare_biz' 或 'interface'

        Returns:
            数据库配置字典
        """
        # 从环境变量获取数据库名称，或使用默认值
        db_names = {
            "tushare_biz": os.getenv("DB_NAME_TUSHARE", "tushare_biz"),
            "interface": os.getenv("DB_NAME_INTERFACE", "interface"),
        }

        config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": db_names.get(db_name, db_name),
            "charset": os.getenv("DB_CHARSET", "utf8mb4"),
        }

        if not config["password"]:
            raise ValueError(
                f"数据库密码未配置。请设置 DB_PASSWORD 环境变量，"
                f"或创建 .env 文件（参考 .env.example）"
            )

        return config

    @staticmethod
    def get_pool_config() -> Dict[str, int]:
        """获取连接池配置"""
        return {
            "mincached": 2,  # 初始化时创建的连接数
            "maxcached": int(os.getenv("DB_POOL_SIZE", "10")),  # 池中最大连接数
            "maxshared": 0,  # 共享连接数（0表示不共享）
            "maxconnections": int(os.getenv("DB_MAX_OVERFLOW", "20")),  # 最大连接数
            "blocking": True,  # 连接池满时阻塞等待
            "maxusage": 0,  # 连接最大使用次数（0表示无限制）
            "setsession": [],  # 可选的SQL命令列表
            "reset": True,  # 返回连接前重置
        }


class DatabasePool:
    """数据库连接池管理器"""

    _pools: Dict[str, PooledDB] = {}

    @classmethod
    def get_pool(cls, db_name: str) -> PooledDB:
        """
        获取或创建连接池

        Args:
            db_name: 数据库名称

        Returns:
            PooledDB 连接池实例
        """
        if db_name not in cls._pools:
            config = DatabaseConfig.get_config(db_name)
            pool_config = DatabaseConfig.get_pool_config()

            cls._pools[db_name] = PooledDB(
                creator=pymysql,
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                database=config["database"],
                charset=config["charset"],
                cursorclass=DictCursor,
                **pool_config
            )

        return cls._pools[db_name]

    @classmethod
    def close_all(cls):
        """关闭所有连接池"""
        for pool in cls._pools.values():
            pool.close()
        cls._pools.clear()


class DatabaseManager:
    """数据库连接管理器 - 使用连接池"""

    @staticmethod
    @contextmanager
    def get_connection(db_name: str) -> Generator[Any, None, None]:
        """
        获取数据库连接（上下文管理器）

        Args:
            db_name: 数据库名称，'tushare_biz' 或 'interface'

        Yields:
            数据库连接对象
        """
        pool = DatabasePool.get_pool(db_name)
        conn = None
        try:
            conn = pool.connection()
            yield conn
        finally:
            if conn:
                conn.close()

    @staticmethod
    @contextmanager
    def get_cursor(db_name: str, dict_cursor: bool = True):
        """
        获取数据库游标（上下文管理器）

        Args:
            db_name: 数据库名称
            dict_cursor: 是否返回字典格式结果

        Yields:
            pymysql Cursor 对象
        """
        with DatabaseManager.get_connection(db_name) as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    @staticmethod
    def execute(db_name: str, sql: str, params: tuple = None) -> int:
        """
        执行 SQL 语句

        Args:
            db_name: 数据库名称
            sql: SQL 语句
            params: 参数

        Returns:
            受影响的行数
        """
        with DatabaseManager.get_cursor(db_name) as cursor:
            return cursor.execute(sql, params)

    @staticmethod
    def executemany(db_name: str, sql: str, params: list) -> int:
        """
        批量执行 SQL 语句

        Args:
            db_name: 数据库名称
            sql: SQL 语句
            params: 参数列表

        Returns:
            受影响的行数
        """
        with DatabaseManager.get_cursor(db_name) as cursor:
            return cursor.executemany(sql, params)

    @staticmethod
    def fetchall(db_name: str, sql: str, params: tuple = None) -> list:
        """
        查询所有结果

        Args:
            db_name: 数据库名称
            sql: SQL 语句
            params: 参数

        Returns:
            查询结果列表
        """
        with DatabaseManager.get_cursor(db_name) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    @staticmethod
    def fetchone(db_name: str, sql: str, params: tuple = None) -> dict:
        """
        查询单条结果

        Args:
            db_name: 数据库名称
            sql: SQL 语句
            params: 参数

        Returns:
            单条记录字典
        """
        with DatabaseManager.get_cursor(db_name) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    @staticmethod
    def insert_many(db_name: str, table: str, columns: list, rows: list,
                    batch_size: int = 1000, on_duplicate: str = None) -> Dict[str, int]:
        """
        批量插入数据，支持分批处理和 ON DUPLICATE KEY UPDATE

        Args:
            db_name: 数据库名称
            table: 表名
            columns: 列名列表
            rows: 数据行列表
            batch_size: 每批处理的行数
            on_duplicate: ON DUPLICATE KEY UPDATE 子句（可选）

        Returns:
            统计信息字典
        """
        if not rows:
            return {"affected": 0, "inserted": 0, "updated": 0}

        # 处理列名中的反引号
        clean_columns = [col.strip('`') for col in columns]
        escaped_columns = [f"`{col}`" if not col.startswith('`') else col for col in clean_columns]

        placeholders = ', '.join(['%s'] * len(columns))
        sql = f"INSERT INTO {table} ({', '.join(escaped_columns)}) VALUES ({placeholders})"

        if on_duplicate:
            # MySQL 8.0.19+ / 9.x: 使用 AS new 别名语法替代 VALUES()
            # on_duplicate 应该包含类似 "`col` = new.col" 的格式
            sql += f" AS new ON DUPLICATE KEY UPDATE {on_duplicate}"

        total_affected = 0

        with DatabaseManager.get_connection(db_name) as conn:
            cursor = conn.cursor()
            try:
                # 分批处理
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    affected = cursor.executemany(sql, batch)
                    total_affected += affected

                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

        return {
            "affected": total_affected,
            "inserted": len(rows),
            "updated": total_affected  # MySQL 的 affected rows 包含更新
        }


# 便捷函数
def get_tushare_connection():
    """获取 Tushare 原始数据库连接"""
    return DatabaseManager.get_connection("tushare_biz")


def get_interface_connection():
    """获取接口层数据库连接"""
    return DatabaseManager.get_connection("interface")
