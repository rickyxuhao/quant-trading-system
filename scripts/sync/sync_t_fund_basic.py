#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公募基金基本信息同步脚本
表名: t_fund_basic
数据来源: Tushare fund_basic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundBasicSync(BaseSyncTask):
    """公募基金基本信息同步任务"""

    TABLE_NAME = "t_fund_basic"
    API_NAME = "fund_basic"
    COLUMNS = [
        'ts_code', 'name', 'management', 'custodian', 'fund_type',
        'found_date', 'list_date', 'issue_date', 'issue_amount',
        'invest_type', 'type', 'status', 'redemp_date', 
        'purc_startdate', 'redemp_startdate', 'market', 'update_date'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "full"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "公募基金基本信息"


def main():
    run_main(FundBasicSync, "公募基金基本信息同步 - t_fund_basic")


if __name__ == "__main__":
    main()
