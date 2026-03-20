#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金净值同步脚本
表名: t_fund_nav
数据来源: Tushare fund_nav API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundNavSync(BaseSyncTask):
    """基金净值同步任务"""

    TABLE_NAME = "t_fund_nav"
    API_NAME = "fund_nav"
    COLUMNS = [
        'ts_code', 'ann_date', 'nav_date', 'unit_nav', 'accum_nav',
        'accum_div', 'net_asset', 'total_netasset', 'adj_nav'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'nav_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "nav_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "基金净值"


def main():
    run_main(FundNavSync, "基金净值同步 - t_fund_nav")


if __name__ == "__main__":
    main()
