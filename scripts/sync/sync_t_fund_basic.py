#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公募基金基本信息同步脚本
表名: t_fund_basic
数据来源: Tushare fund_basic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class FundBasicSync(BaseSyncTask):
    """公募基金基本信息同步任务"""

    TABLE_NAME = "t_fund_basic"
    API_NAME = "fund_basic"
    COLUMNS = [
        'ts_code', 'name', 'management', 'custodian', 'fund_type',
        'found_date', 'list_date', 'issue_date', 'issue_amount',
        'invest_type', 'type', 'status', 'redemp_date', 
        'purc_startdate', 'redemp_startdate', 'market', 'update_date'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "full"


def main():
    parser = create_base_parser("公募基金基本信息同步 - t_fund_basic")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = FundBasicSync(config, db, client)
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
