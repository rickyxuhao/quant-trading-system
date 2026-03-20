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

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
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
    
    # 分类信息
    CATEGORY = "index"
    DESCRIPTION = "大盘指数每日指标"


def main():
    run_main(IndexIndicatorSync, "大盘指数每日指标同步 - t_index_indicator")


if __name__ == "__main__":
    main()
