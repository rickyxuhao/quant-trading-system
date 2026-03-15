#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业绩快报同步脚本
表名: t_stock_express
数据来源: Tushare express API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class ExpressSync(BaseSyncTask):
    """业绩快报同步任务"""

    TABLE_NAME = "t_stock_express"
    API_NAME = "express"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'revenue', 'operate_profit',
        'total_profit', 'n_income', 'total_assets', 'total_hldr_eqy_exc_min_int',
        'diluted_eps', 'dps', 'yoy_sales', 'yoy_op', 'yoy_tp', 'yoy_netprofit',
        'growth_assets', 'yoy_equity', 'growth_bps', 'or_last_year',
        'op_last_year', 'tp_last_year', 'np_last_year', 'assets_last_year',
        'equity_last_year', 'bps_last_year', 'update_flag'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ann_date"  # 使用公告日期作为增量判断
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False  # express API 不支持 start_date/end_date 参数
    # 预期数据量: 约5500只股票 * 20年 * 4季度 * 0.3(不是所有股票都发快报) ≈ 13万条
    MIN_EXPECTED_ROWS = 100000


def main():
    parser = create_base_parser("业绩快报同步 - t_stock_express")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = ExpressSync(config, db, client)
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
