#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 基本信息同步脚本
表名: etf_basic
数据来源: Tushare fund_basic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class ETFBasicSync(BaseSyncTask):
    """ETF 基本信息同步任务"""

    TABLE_NAME = "etf_basic"
    API_NAME = "fund_basic"
    COLUMNS = [
        'ts_code', 'name', 'management', 'custodian', 'fund_type',
        'found_date', 'list_date', 'issue_amount', 'investment_style',
        'nv', 'accum_nav', 'update_date'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "full"
    DATE_COLUMN = None
    FETCH_PARAMS = {'market': 'E'}  # 只获取ETF


def main():
    parser = create_base_parser("ETF 基本信息同步 - etf_basic")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = ETFBasicSync(config, db, client)
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
