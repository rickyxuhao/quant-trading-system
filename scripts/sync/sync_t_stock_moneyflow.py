#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股资金流向同步脚本
表名: t_stock_moneyflow
数据来源: Tushare moneyflow API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class MoneyFlowSync(BaseSyncTask):
    """个股资金流向同步任务"""

    TABLE_NAME = "t_stock_moneyflow"
    API_NAME = "moneyflow"
    COLUMNS = [
        'ts_code', 'trade_date', 'buy_sm_vol', 'buy_sm_amount',
        'sell_sm_vol', 'sell_sm_amount', 'buy_md_vol', 'buy_md_amount',
        'sell_md_vol', 'sell_md_amount', 'buy_lg_vol', 'buy_lg_amount',
        'sell_lg_vol', 'sell_lg_amount', 'buy_elg_vol', 'buy_elg_amount'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"


def main():
    parser = create_base_parser("个股资金流向同步 - t_stock_moneyflow")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = MoneyFlowSync(config, db, client)
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
