#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数日线行情同步脚本
表名: t_index_daily
数据来源: Tushare index_daily API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class IndexDailySync(BaseSyncTask):
    """指数日线行情同步任务 - 仅同步核心指数"""

    TABLE_NAME = "t_index_daily"
    API_NAME = "index_daily"
    COLUMNS = [
        'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 'chng', 'pct_chg', 'vol', 'amount'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"
    
    # 核心指数列表（约20个主要指数）
    CORE_INDEX_CODES = [
        '000001.SH',   # 上证指数
        '399001.SZ',   # 深证成指
        '000300.SH',   # 沪深300
        '399006.SZ',   # 创业板指
        '000688.SH',   # 科创50
        '000016.SH',   # 上证50
        '000010.SH',   # 上证180
        '399005.SZ',   # 中小100
        '000905.SH',   # 中证500
        '000852.SH',   # 中证1000
        '000906.SH',   # 中证800
        '000009.SH',   # 上证380
        '399303.SZ',   # 国证2000
        '000903.SH',   # 中证A100
        '399324.SZ',   # 深证红利
        '000991.SH',   # 全指医药
        '000992.SH',   # 金融地产
        '000993.SH',   # 全指信息
        '399809.SZ',   # 保险主题
        '399810.SZ',   # CSSW传媒
    ]
    
    def sync_by_date(self, mode="incremental", start_date=None, end_date=None):
        """按日期同步 - 只同步核心指数"""
        from datetime import datetime, timedelta
        import pandas as pd
        
        start_date, end_date = self.determine_date_range(mode, start_date, end_date, is_full_history=(mode=='full'))
        
        if start_date > end_date:
            self.logger.info("✅ 数据已是最新，无需同步")
            return {"status": "skipped", "reason": "up_to_date"}
        
        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")
        self.logger.info(f"📊 核心指数: {len(self.CORE_INDEX_CODES)} 个")
        
        # 获取交易日列表
        trade_dates = self.get_trade_dates(start_date, end_date)
        if not trade_dates:
            self.logger.info("⚠️ 无交易日需要同步")
            return {"status": "skipped", "reason": "no_trade_dates"}
        
        self.logger.info(f"📅 需要同步 {len(trade_dates)} 个交易日")
        
        # 逐日同步核心指数
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_dates = []
        
        for i, trade_date in enumerate(trade_dates, 1):
            try:
                self.logger.info(f"   [{i}/{len(trade_dates)}] 处理 {trade_date}...")
                
                day_fetched = 0
                day_inserted = 0
                day_updated = 0
                
                # 逐个指数获取数据
                for ts_code in self.CORE_INDEX_CODES:
                    try:
                        df = self.client.query(self.API_NAME, ts_code=ts_code, trade_date=trade_date)
                        
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
                        
                        day_fetched += len(df)
                        day_inserted += result['inserted']
                        day_updated += result['updated']
                        
                    except Exception as e:
                        continue
                
                total_fetched += day_fetched
                total_inserted += day_inserted
                total_updated += day_updated
                
                if day_fetched > 0:
                    self.logger.info(f"   ✓ {day_fetched} 条")
                
            except Exception as e:
                self.logger.error(f"   ✗ 失败: {e}")
                failed_dates.append(trade_date)
                continue
        
        self.logger.info(f"\n✅ 同步完成: 获取 {total_fetched} 条, 插入 {total_inserted}, 更新 {total_updated}")
        if failed_dates:
            self.logger.warning(f"⚠️ 失败日期: {failed_dates}")
        
        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": total_fetched,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "failed_dates": failed_dates
        }


def main():
    parser = create_base_parser("指数日线行情同步 - t_index_daily")
    args = parser.parse_args()

    config, db, client, logger = init_sync_env(args.log_file)

    sync_task = IndexDailySync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
