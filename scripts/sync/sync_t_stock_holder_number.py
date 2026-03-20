#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股东人数同步脚本
表名: t_stock_holder_number
数据来源: Tushare stk_holdernumber API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class HolderNumberSync(BaseSyncTask):
    """股东人数同步任务"""

    TABLE_NAME = "t_stock_holder_number"
    API_NAME = "stk_holdernumber"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'holder_num',
        'holder_num_change', 'holder_num_ratio'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    
    # 分类信息
    CATEGORY = "holder"
    DESCRIPTION = "股东人数"


def main():
    run_main(HolderNumberSync, "股东人数同步 - t_stock_holder_number")


if __name__ == "__main__":
    main()
