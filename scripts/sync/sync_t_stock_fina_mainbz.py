#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主营业务构成同步脚本
表名: t_stock_fina_mainbz
数据来源: Tushare fina_mainbz API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FinaMainBZSync(BaseSyncTask):
    """主营业务构成同步任务"""

    TABLE_NAME = "t_stock_fina_mainbz"
    API_NAME = "fina_mainbz"
    COLUMNS = [
        'ts_code', 'end_date', 'bz_item', 'bz_sales',
        'bz_profit', 'bz_cost', 'curr_type', 'update_flag'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'bz_item']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "主营业务构成"


def main():
    run_main(FinaMainBZSync, "主营业务构成同步 - t_stock_fina_mainbz")


if __name__ == "__main__":
    main()
