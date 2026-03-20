#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金经理同步脚本
表名: t_fund_manager
数据来源: Tushare fund_manager API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundManagerSync(BaseSyncTask):
    """基金经理同步任务"""

    TABLE_NAME = "t_fund_manager"
    API_NAME = "fund_manager"
    COLUMNS = [
        'ts_code', 'ann_date', 'name', 'gender', 'birth_year',
        'edu', 'nationality', 'begin_date', 'end_date', 'resume'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'name', 'begin_date']
    SYNC_TYPE = "full"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "基金经理"


def main():
    run_main(FundManagerSync, "基金经理同步 - t_fund_manager")


if __name__ == "__main__":
    main()
