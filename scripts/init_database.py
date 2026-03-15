#!/usr/bin/env python3
"""
数据库初始化脚本
创建 tushare_biz 和 interface 两个数据库及表结构
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.storage.relational.connection import DatabaseManager
from core.storage.relational.models_tushare import TUSHARE_TABLES
from core.storage.relational.models_interface import INTERFACE_TABLES


def init_database(db_name: str, tables: list) -> None:
    """
    初始化数据库，创建所有表
    
    Args:
        db_name: 数据库名称
        tables: 建表语句列表
    """
    print(f"\n{'='*60}")
    print(f"初始化数据库: {db_name}")
    print(f"{'='*60}")
    
    try:
        with DatabaseManager.get_connection(db_name) as conn:
            cursor = conn.cursor()
            
            for i, table_sql in enumerate(tables, 1):
                # 提取表名（用于显示）
                table_name = "未知"
                if "CREATE TABLE IF NOT EXISTS" in table_sql:
                    table_name = table_sql.split("CREATE TABLE IF NOT EXISTS")[1].split()[0].strip()
                
                print(f"[{i}/{len(tables)}] 创建表: {table_name} ...", end=" ")
                
                try:
                    cursor.execute(table_sql)
                    print("✅ 成功")
                except Exception as e:
                    print(f"❌ 失败: {e}")
                    raise
            
            conn.commit()
            print(f"\n✅ 数据库 {db_name} 初始化完成！")
            
    except Exception as e:
        print(f"\n❌ 数据库 {db_name} 初始化失败: {e}")
        raise


def check_connection():
    """测试数据库连接"""
    print("\n测试数据库连接...")
    
    for db_name in ["tushare_biz", "interface"]:
        try:
            with DatabaseManager.get_connection(db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                print(f"  ✅ {db_name}: 连接成功")
        except Exception as e:
            print(f"  ❌ {db_name}: 连接失败 - {e}")
            return False
    
    return True


def main():
    """主函数"""
    print("="*60)
    print("Stock Trading Project - 数据库初始化")
    print("="*60)
    
    # 检查连接
    if not check_connection():
        print("\n❌ 数据库连接失败，请检查:")
        print("  1. MySQL 服务是否启动")
        print("  2. 数据库 tushare_biz 和 interface 是否已创建")
        print("  3. 环境变量 MYSQL_USER / MYSQL_PASSWORD 是否正确设置")
        print("\n创建数据库命令:")
        print("  CREATE DATABASE tushare_biz CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print("  CREATE DATABASE interface CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        sys.exit(1)
    
    # 初始化 Tushare 数据库
    init_database("tushare_biz", TUSHARE_TABLES)
    
    # 初始化 Interface 数据库
    init_database("interface", INTERFACE_TABLES)
    
    print("\n" + "="*60)
    print("🎉 所有数据库初始化完成！")
    print("="*60)


if __name__ == "__main__":
    main()
