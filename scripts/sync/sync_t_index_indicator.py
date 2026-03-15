#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大盘指数每日指标同步脚本
表名: t_index_indicator
数据来源: Tushare index_dailybasic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class IndexIndicatorSync(BaseSyncTask):
    """大盘指数每日指标同步任务"""

    TABLE_NAME = "t_index_indicator"
    API_NAME = "index_dailybasic"
    COLUMNS = [
        'ts_code', 'trade_date', 'total_mv', 'float_mv', 'total_share',
        'float_share', 'free_share', 'turnover_rate', 'turnover_rate_f',
        'pe', 'pe_ttm', 'pb'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"


def main():
    parser = create_base_parser("大盘指数每日指标同步 - t_index_indicator")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = IndexIndicatorSync(config, db, client)
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
