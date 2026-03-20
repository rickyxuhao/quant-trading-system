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

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
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
    DATE_COLUMN = "ann_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    MIN_EXPECTED_ROWS = 150000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "业绩预告"


def main():
    run_main(ForecastSync, "业绩预告同步 - t_stock_forecast")


if __name__ == "__main__":
    main()
