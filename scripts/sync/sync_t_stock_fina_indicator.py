#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务指标数据同步脚本
表名: t_stock_fina_indicator
数据来源: Tushare fina_indicator API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FinaIndicatorSync(BaseSyncTask):
    """财务指标数据同步任务"""

    TABLE_NAME = "t_stock_fina_indicator"
    API_NAME = "fina_indicator"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'roe', 'roe_diluted',
        'roe_avg', 'roa', 'roa_yearly', 'sales_margin', 'net_profit_margin',
        'gross_profit_margin', 'sales_to_admin_ratio', 'sales_to_sale_ratio',
        'asset_turnover', 'ca_turnover', 'fa_turnover', 'current_ratio',
        'quick_ratio', 'cash_ratio', 'inv_days', 'ar_days', 'debt_to_assets',
        'assets_to_eqt', 'debt_to_eqt', 'netdebt_to_eqt', 'ocf_to_shortdebt',
        'ocf_to_debt', 'ocf_to_interest', 'profit_to_op', 'basic_eps_yoy',
        'dt_eps_yoy', 'cfps_yoy', 'op_yoy', 'ebt_yoy', 'netprofit_yoy',
        'dt_netprofit_yoy', 'roe_yoy', 'bps_yoy', 'assets_yoy', 'eqt_yoy',
        'tr_yoy', 'or_yoy', 'q_sales_yoy', 'q_op_qoq', 'equity_yoy'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    
    # 分类信息
    CATEGORY = "financial"
    DESCRIPTION = "财务指标数据"


def main():
    run_main(FinaIndicatorSync, "财务指标数据同步 - t_stock_fina_indicator")


if __name__ == "__main__":
    main()
