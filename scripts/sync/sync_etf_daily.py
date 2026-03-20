#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 日线行情同步脚本
表名: etf_daily
数据来源: Tushare fund_daily API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class ETFDailySync(BaseSyncTask):
    """ETF 日线行情同步任务"""

    TABLE_NAME = "etf_daily"
    API_NAME = "fund_daily"
    COLUMNS = [
        'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 'chng', 'pct_chg', 'vol', 'amount'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "ETF日线行情"


def main():
    run_main(ETFDailySync, "ETF 日线行情同步 - etf_daily")


if __name__ == "__main__":
    main()
