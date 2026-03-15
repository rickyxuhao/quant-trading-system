#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司基本信息同步脚本
表名: t_stock_company
数据来源: Tushare stock_company API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class StockCompanySync(BaseSyncTask):
    """上市公司基本信息同步任务"""

    TABLE_NAME = "t_stock_company"
    API_NAME = "stock_company"
    COLUMNS = [
        'ts_code', 'exchange', 'chairman', 'manager', 'secretary',
        'reg_capital', 'setup_date', 'province', 'city', 'introduction',
        'website', 'email', 'office', 'employees', 'main_business',
        'business_scope'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    UPDATE_COLUMNS = [
        'exchange', 'chairman', 'manager', 'secretary',
        'reg_capital', 'setup_date', 'province', 'city', 'introduction',
        'website', 'email', 'office', 'employees', 'main_business',
        'business_scope'
    ]
    SYNC_TYPE = "full"


def main():
    parser = create_base_parser("上市公司基本信息同步 - t_stock_company")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = StockCompanySync(config, db, client)
    result = sync_task.execute(mode=args.mode)

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
