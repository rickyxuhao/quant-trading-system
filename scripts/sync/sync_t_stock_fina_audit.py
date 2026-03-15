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

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


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
    SUPPORTS_DATE_FILTER = False  # fina_audit API 不支持 start_date/end_date 参数


def main():
    parser = create_base_parser("财务审计意见同步 - t_stock_fina_audit")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = FinaAuditSync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
