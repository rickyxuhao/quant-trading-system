#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分红送股同步脚本
表名: t_stock_dividend
数据来源: Tushare dividend API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class DividendSync(BaseSyncTask):
    """分红送股同步任务"""

    TABLE_NAME = "t_stock_dividend"
    API_NAME = "dividend"
    COLUMNS = [
        'ts_code', 'end_date', 'ann_date', 'div_proc', 'stk_div',
        'stk_bo_rate', 'stk_co_rate', 'cash_div', 'cash_div_tax',
        'record_date', 'ex_date', 'pay_date', 'div_listdate', 'imp_ann_date',
        'base_date', 'base_share'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ann_date"  # 使用公告日期作为增量判断
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False  # dividend API 不支持 start_date/end_date 参数
    # 预期数据量: 约5500只股票 * 20年(平均每年1次分红) ≈ 11万条
    MIN_EXPECTED_ROWS = 80000


def main():
    parser = create_base_parser("分红送股同步 - t_stock_dividend")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = DividendSync(config, db, client)
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
