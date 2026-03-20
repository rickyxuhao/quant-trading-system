#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 份额规模同步脚本
表名: etf_share
数据来源: Tushare fund_share API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class ETFShareSync(BaseSyncTask):
    """ETF 份额规模同步任务"""

    TABLE_NAME = "etf_share"
    API_NAME = "fund_share"
    COLUMNS = [
        'ts_code', 'trade_date', 'share', 'nav_date'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "ETF份额规模"


def main():
    run_main(ETFShareSync, "ETF 份额规模同步 - etf_share")


if __name__ == "__main__":
    main()
