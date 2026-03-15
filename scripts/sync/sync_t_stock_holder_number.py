#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股东人数同步脚本
表名: t_stock_holder_number
数据来源: Tushare stk_holdernumber API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class HolderNumberSync(BaseSyncTask):
    """股东人数同步任务"""

    TABLE_NAME = "t_stock_holder_number"
    API_NAME = "stk_holdernumber"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'holder_num',
        'holder_num_change', 'holder_num_ratio'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True


def main():
    parser = create_base_parser("股东人数同步 - t_stock_holder_number")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = HolderNumberSync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
