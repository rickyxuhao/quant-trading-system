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

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
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
    DATE_COLUMN = "ann_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    MIN_EXPECTED_ROWS = 100000
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "业绩快报"


def main():
    run_main(ExpressSync, "业绩快报同步 - t_stock_express")


if __name__ == "__main__":
    main()
