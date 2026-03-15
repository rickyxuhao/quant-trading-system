#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金持仓同步脚本
表名: t_fund_portfolio
数据来源: Tushare fund_portfolio API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class FundPortfolioSync(BaseSyncTask):
    """基金持仓同步任务"""

    TABLE_NAME = "t_fund_portfolio"
    API_NAME = "fund_portfolio"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'symbol', 'name',
        'mkv', 'amount', 'stk_mkv_ratio', 'stk_float_ratio'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'symbol']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True


def main():
    parser = create_base_parser("基金持仓同步 - t_fund_portfolio")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = FundPortfolioSync(config, db, client)
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
