#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金份额同步脚本
表名: t_fund_share
数据来源: Tushare fund_share API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundShareSync(BaseSyncTask):
    """基金份额同步任务"""

    TABLE_NAME = "t_fund_share"
    API_NAME = "fund_share"
    COLUMNS = [
        'ts_code', 'trade_date', 'fd_share'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "基金份额"


def main():
    run_main(FundShareSync, "基金份额同步 - t_fund_share")


if __name__ == "__main__":
    main()
