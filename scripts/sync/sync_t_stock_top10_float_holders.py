#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前十大流通股东同步脚本
表名: t_stock_top10_float_holders
数据来源: Tushare top10_fh API
"""

import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class Top10FloatHoldersSync(BaseSyncTask):
    """前十大流通股东同步任务"""

    TABLE_NAME = "t_stock_top10_float_holders"
    API_NAME = "top10_floatholders"
    COLUMNS = [
        'ts_code', 'ann_date', 'end_date', 'holder_name',
        'hold_amount', 'hold_ratio', 'hold_float_ratio', 'hold_change', 'holder_type'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'end_date', 'holder_name']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "end_date"
    TS_CODE_REQUIRED = True
    
    # 分类信息
    CATEGORY = "holder"
    DESCRIPTION = "前十大流通股东"

    def get_periods(self, start_year: int, end_year: int) -> List[str]:
        """生成季度报告期列表 (格式: YYYYMMDD)"""
        periods = []
        quarter_ends = ['0331', '0630', '0930', '1231']
        for year in range(start_year, end_year + 1):
            for qe in quarter_ends:
                periods.append(f"{year}{qe}")
        return periods

    def sync_by_stock_code(self, mode: str = "incremental",
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> Dict[str, Any]:
        """按股票代码和报告期同步"""
        import pandas as pd

        # 获取股票列表
        stock_list = self.get_stock_list()
        if not stock_list:
            return {"status": "error", "reason": "no_stocks"}

        self.logger.info(f"📈 需要处理 {len(stock_list)} 只股票")

        # 确定年份范围
        if not end_date:
            end_year = datetime.now().year
        else:
            end_year = int(end_date[:4])

        if mode == 'incremental' and not start_date and self.DATE_COLUMN:
            max_date = self.db.get_max_date(self.TABLE_NAME, self.DATE_COLUMN)
            if max_date:
                start_year = int(max_date[:4])
            else:
                start_year = 2005
                self.logger.info("🆕 首次全量同步，从 2005 年开始")
        else:
            start_year = int(start_date[:4]) if start_date else 2005

        # 生成报告期列表
        periods = self.get_periods(start_year, end_year)
        self.logger.info(f"📅 报告期范围: {periods[0]} - {periods[-1]}, 共 {len(periods)} 个报告期")

        # 逐股票逐报告期同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_combos = []

        for i, ts_code in enumerate(stock_list, 1):
            try:
                if i % 100 == 0:
                    self.logger.info(f"   进度: {i}/{len(stock_list)} ({i*100//len(stock_list)}%)")

                for period in periods:
                    try:
                        # 获取数据 - top10_fh 需要 ts_code 和 period 参数
                        df = self.client.query(
                            self.API_NAME, ts_code=ts_code, period=period
                        )

                        if df.empty:
                            continue

                        # 清理数据
                        df = self.clean_dataframe(df)
                        rows = df.values.tolist()

                        # UPSERT
                        result = self.db.upsert(
                            self.TABLE_NAME, self.COLUMNS, rows,
                            self.UNIQUE_COLUMNS, self.get_update_columns()
                        )

                        total_fetched += len(df)
                        total_inserted += result['inserted']
                        total_updated += result['updated']

                    except Exception as e:
                        # 单个报告期失败继续下一个
                        continue

            except Exception as e:
                self.logger.error(f"   ✗ {ts_code} 失败: {e}")
                failed_combos.append(ts_code)
                continue

        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_combos:
            self.logger.warning(f"⚠️ 失败股票数: {len(failed_combos)}")

        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_stocks": len(failed_combos)
        }


def main():
    run_main(Top10FloatHoldersSync, "前十大流通股东同步 - t_stock_top10_float_holders")


if __name__ == "__main__":
    main()
