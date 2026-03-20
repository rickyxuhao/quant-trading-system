#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票更名历史同步脚本
表名: t_stock_name_history
数据来源: Tushare namechange API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class NameChangeSync(BaseSyncTask):
    """股票更名历史同步任务"""

    TABLE_NAME = "t_stock_name_history"
    API_NAME = "namechange"
    COLUMNS = ['ts_code', 'name', 'start_date', 'end_date', 'ann_date']
    UNIQUE_COLUMNS = ['ts_code', 'start_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "start_date"
    
    # 分类信息
    CATEGORY = "basic"
    DESCRIPTION = "股票更名历史"


def main():
    run_main(NameChangeSync, "股票更名历史同步 - t_stock_name_history")


if __name__ == "__main__":
    main()
