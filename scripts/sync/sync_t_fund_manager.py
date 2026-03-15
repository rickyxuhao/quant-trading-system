#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金经理同步脚本
表名: t_fund_manager
数据来源: Tushare fund_manager API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class FundManagerSync(BaseSyncTask):
    """基金经理同步任务"""

    TABLE_NAME = "t_fund_manager"
    API_NAME = "fund_manager"
    COLUMNS = [
        'ts_code', 'ann_date', 'name', 'gender', 'birth_year',
        'edu', 'nationality', 'begin_date', 'end_date', 'resume'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'name', 'begin_date']
    SYNC_TYPE = "full"


def main():
    parser = create_base_parser("基金经理同步 - t_fund_manager")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = FundManagerSync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
