#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基本信息同步脚本
表名: t_index_basic
数据来源: Tushare index_basic API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class IndexBasicSync(BaseSyncTask):
    """指数基本信息同步任务"""

    TABLE_NAME = "t_index_basic"
    API_NAME = "index_basic"
    COLUMNS = [
        'ts_code', 'name', 'market', 'publisher', 'category',
        'base_date', 'base_point', 'list_date'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    SYNC_TYPE = "full"
    
    # 分类信息
    CATEGORY = "index"
    DESCRIPTION = "指数基本信息"


def main():
    run_main(IndexBasicSync, "指数基本信息同步 - t_index_basic")


if __name__ == "__main__":
    main()
