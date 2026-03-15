#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股东增减持同步脚本
表名: t_stock_holder_trade
数据来源: Tushare stk_holdertrade API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class HolderTradeSync(BaseSyncTask):
    """股东增减持同步任务"""

    TABLE_NAME = "t_stock_holder_trade"
    API_NAME = "stk_holdertrade"
    COLUMNS = [
        'ts_code', 'ann_date', 'holder_name', 'holder_type',
        'in_de', 'change_vol', 'change_ratio', 'after_share',
        'after_ratio', 'avg_price', 'total_share', 'begin_date', 'close_date'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'ann_date', 'holder_name']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ann_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False  # stk_holdertrade API 不支持 start_date/end_date 参数


def main():
    parser = create_base_parser("股东增减持同步 - t_stock_holder_trade")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = HolderTradeSync(config, db, client)
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
