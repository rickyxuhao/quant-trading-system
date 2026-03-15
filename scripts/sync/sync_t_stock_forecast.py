#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业绩预告同步脚本
表名: t_stock_forecast
数据来源: Tushare forecast API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class ForecastSync(BaseSyncTask):
    """业绩预告同步任务"""

    TABLE_NAME = "t_stock_forecast"
    API_NAME = "forecast"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'type', 'p_change_min',
        'p_change_max', 'net_profit_min', 'net_profit_max',
        'last_parent_net', 'first_ann_date', 'summary', 'change_reason'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ann_date"  # 使用公告日期作为增量判断
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False  # forecast API 不支持 start_date/end_date 参数
    # 预期数据量: 约5500只股票 * 20年 * 4季度 * 0.5(不是所有股票都发预告) ≈ 22万条
    MIN_EXPECTED_ROWS = 150000


def main():
    parser = create_base_parser("业绩预告同步 - t_stock_forecast")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = ForecastSync(config, db, client)
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
