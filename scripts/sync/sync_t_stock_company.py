#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司基本信息同步脚本
表名: t_stock_company
数据来源: Tushare stock_company API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class StockCompanySync(BaseSyncTask):
    """上市公司基本信息同步任务"""

    TABLE_NAME = "t_stock_company"
    API_NAME = "stock_company"
    COLUMNS = [
        'ts_code', 'exchange', 'chairman', 'manager', 'secretary',
        'reg_capital', 'setup_date', 'province', 'city', 'introduction',
        'website', 'email', 'office', 'employees', 'main_business',
        'business_scope'
    ]
    UNIQUE_COLUMNS = ['ts_code']
    UPDATE_COLUMNS = [
        'exchange', 'chairman', 'manager', 'secretary',
        'reg_capital', 'setup_date', 'province', 'city', 'introduction',
        'website', 'email', 'office', 'employees', 'main_business',
        'business_scope'
    ]
    SYNC_TYPE = "full"
    
    # 分类信息
    CATEGORY = "basic"
    DESCRIPTION = "上市公司基本信息"


def main():
    run_main(StockCompanySync, "上市公司基本信息同步 - t_stock_company")


if __name__ == "__main__":
    main()
