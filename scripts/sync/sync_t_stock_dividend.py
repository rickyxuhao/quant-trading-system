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

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
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
    DATE_COLUMN = "ann_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    MIN_EXPECTED_ROWS = 80000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "分红送股"


def main():
    run_main(DividendSync, "分红送股同步 - t_stock_dividend")


if __name__ == "__main__":
    main()
