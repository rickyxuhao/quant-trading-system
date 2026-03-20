#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 复权因子同步脚本
表名: etf_adj_factor
数据来源: Tushare fund_adj API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class ETFAdjFactorSync(BaseSyncTask):
    """ETF 复权因子同步任务"""

    TABLE_NAME = "etf_adj_factor"
    API_NAME = "fund_adj"
    COLUMNS = [
        'ts_code', 'trade_date', 'adj_factor'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "ETF复权因子"


def main():
    run_main(ETFAdjFactorSync, "ETF 复权因子同步 - etf_adj_factor")


if __name__ == "__main__":
    main()
