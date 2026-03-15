#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新股上市信息同步脚本
表名: t_stock_ipo
数据来源: Tushare new_share API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class NewShareSync(BaseSyncTask):
    """新股上市信息同步任务"""

    TABLE_NAME = "t_stock_ipo"
    API_NAME = "new_share"
    COLUMNS = [
        'ts_code', 'sub_code', 'name', 'ipo_date', 'issue_date',
        'amount', 'market_amount', 'price', 'pe', 'limit_amount',
        'funds', 'ballot'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ipo_date"


def main():
    parser = create_base_parser("新股上市信息同步 - t_stock_ipo")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = NewShareSync(config, db, client)
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
