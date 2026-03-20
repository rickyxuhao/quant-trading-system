#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务审计意见同步脚本
表名: t_stock_fina_audit
数据来源: Tushare fina_audit API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FinaAuditSync(BaseSyncTask):
    """财务审计意见同步任务"""

    TABLE_NAME = "t_stock_fina_audit"
    API_NAME = "fina_audit"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'audit_result',
        'audit_fees', 'audit_agency', 'sign_account'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    SUPPORTS_DATE_FILTER = False
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "财务审计意见"


def main():
    run_main(FinaAuditSync, "财务审计意见同步 - t_stock_fina_audit")


if __name__ == "__main__":
    main()
