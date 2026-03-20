#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票每日基本面同步脚本
表名: t_stock_daily_basic
数据来源: Tushare daily_basic API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class DailyBasicSync(BaseSyncTask):
    """股票每日基本面同步任务"""

    TABLE_NAME = "t_stock_daily_basic"
    API_NAME = "daily_basic"
    COLUMNS = [
        'ts_code', 'trade_date', 'close', 'turnover_rate',
        'turnover_rate_f', 'volume_ratio', 'pe', 'pe_ttm', 'pb',
        'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share',
        'float_share', 'free_share', 'total_mv', 'circ_mv'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "market"
    DESCRIPTION = "股票每日基本面"


def main():
    run_main(DailyBasicSync, "股票每日基本面同步 - t_stock_daily_basic")


if __name__ == "__main__":
    main()
