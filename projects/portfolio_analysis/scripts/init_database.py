#!/usr/bin/env python3
"""
数据库初始化脚本

创建持仓分析系统所需的所有数据库表。

Usage:
    python projects/portfolio_analysis/scripts/init_database.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from projects.portfolio_analysis.database.models import init_database, get_engine
from sqlalchemy import text


def create_database_if_not_exists():
    """如果数据库不存在则创建"""
    import pymysql

    # 从环境变量获取配置
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', '3306'))
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME_INTERFACE', 'interface')

    if not password:
        print("❌ 错误: 未设置数据库密码。请设置 DB_PASSWORD 环境变量")
        sys.exit(1)

    try:
        # 连接MySQL（不指定数据库）
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            # 创建数据库（如果不存在）
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ 数据库 '{database}' 已创建或已存在")

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ 创建数据库失败: {e}")
        return False


def init_tables():
    """初始化所有表"""
    try:
        engine = get_engine()
        init_database(engine)
        print("✅ 所有表已创建成功")
        return True
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_tables():
    """验证表是否创建成功"""
    from sqlalchemy import inspect

    try:
        engine = get_engine()
        inspector = inspect(engine)

        expected_tables = [
            'positions',
            'transactions',
            'portfolio_snapshots',
            'position_history',
            'fund_info',
            'fund_net_values',
            'sip_plans',
            'sip_transactions'
        ]

        existing_tables = inspector.get_table_names()

        print("\n📋 表创建状态:")
        print("-" * 40)

        all_created = True
        for table in expected_tables:
            status = "✅" if table in existing_tables else "❌"
            print(f"  {status} {table}")
            if table not in existing_tables:
                all_created = False

        print("-" * 40)

        if all_created:
            print("\n🎉 所有表创建成功！")
        else:
            print("\n⚠️ 部分表未创建")

        return all_created

    except Exception as e:
        print(f"❌ 验证表失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("持仓分析系统 - 数据库初始化")
    print("=" * 60)

    # 步骤1: 创建数据库
    print("\n[1/3] 检查并创建数据库...")
    if not create_database_if_not_exists():
        sys.exit(1)

    # 步骤2: 创建表
    print("\n[2/3] 创建数据表...")
    if not init_tables():
        sys.exit(1)

    # 步骤3: 验证
    print("\n[3/3] 验证表结构...")
    if not verify_tables():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("数据库初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
