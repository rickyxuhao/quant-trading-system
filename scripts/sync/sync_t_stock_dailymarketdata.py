#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票日线行情同步脚本
表名: t_stock_dailymarketdata
数据来源: Tushare daily API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class DailyMarketDataSync(BaseSyncTask):
    """股票日线行情同步任务"""

    TABLE_NAME = "t_stock_dailymarketdata"
    API_NAME = "daily"
    # API返回的字段名
    API_COLUMNS = [
        'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 'change', 'pct_chg', 'vol', 'amount'
    ]
    # 数据库表字段名（change -> t_change 避开MySQL关键字）
    COLUMNS = [
        'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 't_change', 'pct_chg', 'vol', 'amount'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    UPDATE_COLUMNS = [
        'open', 'high', 'low', 'close', 'pre_close',
        't_change', 'pct_chg', 'vol', 'amount'
    ]
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "market"
    DESCRIPTION = "股票日线行情"

    def clean_dataframe(self, df):
        """清理数据并映射字段名"""
        import pandas as pd
        import numpy as np

        # 重命名 change -> t_change
        if 'change' in df.columns:
            df = df.rename(columns={'change': 't_change'})

        # 确保所有列都存在
        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[self.COLUMNS]

        # 处理 NaN 值
        df = df.replace({np.nan: None, 'NaN': None, 'nan': None, '': None})
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].where(df[col].notna(), None)
            else:
                mask = df[col].isna()
                if mask.any():
                    df.loc[mask, col] = None

        return df


def main():
    run_main(DailyMarketDataSync, "股票日线行情同步 - t_stock_dailymarketdata")


if __name__ == "__main__":
    main()
