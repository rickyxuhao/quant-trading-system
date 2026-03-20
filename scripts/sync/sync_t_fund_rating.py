#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金评级同步脚本
表名: t_fund_rating
数据来源: Tushare fund_rating API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class FundRatingSync(BaseSyncTask):
    """基金评级同步任务"""

    TABLE_NAME = "t_fund_rating"
    API_NAME = "fund_rating"
    COLUMNS = [
        'ts_code', 'ann_date', 'rating_agency', 'rating_date',
        'fund_rating', 'manager_rating'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'rating_agency', 'rating_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "rating_date"
    
    # 分类信息
    CATEGORY = "fund"
    DESCRIPTION = "基金评级"


def main():
    run_main(FundRatingSync, "基金评级同步 - t_fund_rating")


if __name__ == "__main__":
    main()
