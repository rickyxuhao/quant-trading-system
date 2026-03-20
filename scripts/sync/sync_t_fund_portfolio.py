#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金持仓同步脚本
表名: t_fund_portfolio
数据来源: Tushare fund_portfolio API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundPortfolioSync(BaseSyncTask):
    """基金持仓同步任务"""

    TABLE_NAME = "t_fund_portfolio"
    API_NAME = "fund_portfolio"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'symbol', 'name',
        'mkv', 'amount', 'stk_mkv_ratio', 'stk_float_ratio'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'symbol']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "基金持仓"


def main():
    run_main(FundPortfolioSync, "基金持仓同步 - t_fund_portfolio")


if __name__ == "__main__":
    main()
