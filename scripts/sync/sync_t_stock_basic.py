#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票基础信息同步脚本
表名: t_stock_basic
数据来源: Tushare stock_basic API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class StockBasicSync(BaseSyncTask):
    """股票基础信息同步任务"""

    TABLE_NAME = "t_stock_basic"
    API_NAME = "stock_basic"
    COLUMNS = [
        'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname',
        'enname', 'cnspell', 'market', 'exchange', 'curr_type',
        'list_status', 'list_date', 'delist_date', 'is_hs',
        'act_name', 'act_ent_type'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    UPDATE_COLUMNS = [
        'symbol', 'name', 'area', 'industry', 'fullname',
        'enname', 'cnspell', 'market', 'exchange', 'curr_type',
        'list_status', 'list_date', 'delist_date', 'is_hs',
        'act_name', 'act_ent_type'
    ]
    SYNC_TYPE = "full"
    FETCH_PARAMS = {"list_status": ""}  # 空字符串表示获取全部
    
    # 分类信息
    CATEGORY = "basic"
    DESCRIPTION = "股票基础信息"


def main():
    run_main(StockBasicSync, "股票基础信息同步 - t_stock_basic")


if __name__ == "__main__":
    main()
