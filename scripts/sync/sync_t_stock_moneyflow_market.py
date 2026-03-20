#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深港通资金流向同步脚本
表名: t_stock_moneyflow_market
数据来源: Tushare moneyflow_hsgt API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class MoneyFlowMarketSync(BaseSyncTask):
    """沪深港通资金流向同步任务"""

    TABLE_NAME = "t_stock_moneyflow_market"
    API_NAME = "moneyflow_hsgt"
    COLUMNS = [
        'trade_date', 'ggt_ss', 'ggt_sz', 'hgt', 'sgt',
        'north_money', 'south_money'
    ]
    UNIQUE_COLUMNS = ['trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "market"
    DESCRIPTION = "沪深港通资金流向"


def main():
    run_main(MoneyFlowMarketSync, "沪深港通资金流向同步 - t_stock_moneyflow_market")


if __name__ == "__main__":
    main()
