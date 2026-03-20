#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心指数日线行情同步脚本 - 高效版本
表名: t_index_daily
数据来源: Tushare index_daily API
优化: 按指数批量获取，而非按日循环
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, SyncRegistry, run_main


@SyncRegistry.register
class CoreIndexDailySyncV2(BaseSyncTask):
    """核心指数日线行情同步任务 - 高效版本（按指数批量获取）"""

    TABLE_NAME = "t_index_daily"
    API_NAME = "index_daily"
    COLUMNS = [
        'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 'chng', 'pct_chg', 'vol', 'amount'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 分类信息
    CATEGORY = "index"
    DESCRIPTION = "核心指数日线行情（沪深300/中证500/上证50/中证1000/创业板指/中证2000）"
    
    # 用户关心的核心指数（6个）
    CORE_INDEX_CODES = [
        ('000300.SH', '沪深300'),
        ('000905.SH', '中证500'),
        ('000016.SH', '上证50'),
        ('000852.SH', '中证1000'),
        ('399006.SZ', '创业板指'),
        ('932000.SH', '中证2000'),
    ]
    
    def sync_by_date(self, mode="incremental", start_date=None, end_date=None):
        """按指数批量同步 - 高效版本"""
        start_date, end_date = self.determine_date_range(mode, start_date, end_date, is_full_history=(mode=='full'))
        
        if start_date > end_date:
            self.logger.info("✅ 数据已是最新，无需同步")
            return {"status": "skipped", "reason": "up_to_date"}
        
        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")
        self.logger.info(f"📊 核心指数: {len(self.CORE_INDEX_CODES)} 个")
        for code, name in self.CORE_INDEX_CODES:
            self.logger.info(f"   - {code} ({name})")
        
        # 逐个指数批量获取数据
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_indices = []
        
        for i, (ts_code, name) in enumerate(self.CORE_INDEX_CODES, 1):
            try:
                self.logger.info(f"\n[{i}/{len(self.CORE_INDEX_CODES)}] 同步 {ts_code} ({name})...")
                
                # 批量获取该指数的全部历史数据
                df = self.client.query(
                    self.API_NAME, 
                    ts_code=ts_code, 
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df.empty:
                    self.logger.info(f"   ⚠️ 无数据")
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
                
                self.logger.info(f"   ✓ 获取 {len(df)} 条, 插入 {result['inserted']}, 更新 {result['updated']}")
                
            except Exception as e:
                self.logger.error(f"   ✗ 失败: {e}")
                failed_indices.append((ts_code, name))
                continue
        
        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_indices:
            self.logger.warning(f"⚠️ 失败指数: {failed_indices}")
        
        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_indices": failed_indices
        }


def main():
    run_main(CoreIndexDailySyncV2, "核心指数日线行情同步V2 - 沪深300/中证500/上证50/中证1000/创业板指/中证2000")


if __name__ == "__main__":
    main()
