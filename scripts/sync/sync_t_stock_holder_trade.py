#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股东增减持同步脚本
表名: t_stock_holder_trade
数据来源: Tushare stk_holdertrade API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class HolderTradeSync(BaseSyncTask):
    """股东增减持同步任务"""

    TABLE_NAME = "t_stock_holder_trade"
    API_NAME = "stk_holdertrade"
    COLUMNS = [
        'ts_code', 'ann_date', 'holder_name', 'holder_type',
        'in_de', 'change_vol', 'change_ratio', 'after_share',
        'after_ratio', 'avg_price', 'total_share', 'begin_date', 'close_date'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'ann_date', 'holder_name']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "ann_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    
    # 分类信息
    CATEGORY = "holder"
    DESCRIPTION = "股东增减持"


def main():
    run_main(HolderTradeSync, "股东增减持同步 - t_stock_holder_trade")


if __name__ == "__main__":
    main()
