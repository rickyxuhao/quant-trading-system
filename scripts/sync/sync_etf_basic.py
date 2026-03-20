#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 基本信息同步脚本
表名: etf_basic
数据来源: Tushare fund_basic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class ETFBasicSync(BaseSyncTask):
    """ETF 基本信息同步任务"""

    TABLE_NAME = "etf_basic"
    API_NAME = "fund_basic"
    COLUMNS = [
        'ts_code', 'name', 'management', 'custodian', 'fund_type',
        'found_date', 'list_date', 'issue_amount', 'investment_style',
        'nv', 'accum_nav', 'update_date'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "full"
    DATE_COLUMN = None
    FETCH_PARAMS = {'market': 'E'}  # 只获取ETF
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "ETF基本信息"


def main():
    run_main(ETFBasicSync, "ETF 基本信息同步 - etf_basic")


if __name__ == "__main__":
    main()
