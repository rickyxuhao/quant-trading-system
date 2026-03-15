#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日涨跌停价格同步脚本
表名: t_stock_dailylimitprice
数据来源: Tushare limit_list_d API

注意: 2023-06-22 后 limit_list 接口停止更新，改用 limit_list_d
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class DailyLimitPriceSync(BaseSyncTask):
    """每日涨跌停价格同步任务"""

    TABLE_NAME = "t_stock_dailylimitprice"
    API_NAME = "limit_list_d"  # 改用 limit_list_d 接口
    COLUMNS = [
        'ts_code', 'trade_date', 'name', 'close', 'pct_chg',
        'amp', 'up_limit', 'down_limit'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'trade_date']
    SYNC_TYPE = "incremental"
    DATE_COLUMN = "trade_date"

    def get_amp_from_daily(self, trade_date):
        """从日线数据获取振幅"""
        sql = """
            SELECT ts_code, (high - low) / pre_close * 100 as amp
            FROM t_stock_dailymarketdata
            WHERE trade_date = %s
        """
        results = self.db.fetchall(sql, (trade_date,))
        return {r['ts_code']: r['amp'] for r in results}

    def sync_by_date(self, mode="incremental",
                     start_date=None, end_date=None):
        """按日期同步，覆盖父类方法以支持 amp 字段补充"""
        from datetime import datetime, timedelta
        import pandas as pd

        start_date, end_date = self.determine_date_range(mode, start_date, end_date, is_full_history=(mode=='full'))

        # 检查是否需要同步
        if start_date > end_date:
            self.logger.info("✅ 数据已是最新，无需同步")
            return {"status": "skipped", "reason": "up_to_date"}

        self.logger.info(f"📅 日期范围: {start_date} - {end_date}")

        # 获取交易日列表
        trade_dates = self.get_trade_dates(start_date, end_date)
        if not trade_dates:
            self.logger.info("⚠️ 无交易日需要同步")
            return {"status": "skipped", "reason": "no_trade_dates"}

        self.logger.info(f"📊 需要同步 {len(trade_dates)} 个交易日")

        # 逐日同步
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        failed_dates = []

        for i, trade_date in enumerate(trade_dates, 1):
            try:
                self.logger.info(f"   [{i}/{len(trade_dates)}] 处理 {trade_date}...")

                # 获取单日数据
                df = self.client.query(self.API_NAME, trade_date=trade_date)

                if df.empty:
                    continue

                # 获取 amp 数据
                amp_map = self.get_amp_from_daily(trade_date)

                # 确保所有列都存在
                for col in self.COLUMNS:
                    if col not in df.columns:
                        df[col] = None

                # 从 limit_list_d 映射字段
                if 'limit' in df.columns and 'limit' not in self.COLUMNS:
                    # limit_list_d 有 limit 字段，但我们不需要存储
                    pass

                # 补充 amp 字段
                df['amp'] = df['ts_code'].map(lambda x: amp_map.get(x, 0))

                # 确保字段顺序正确
                df = df[self.COLUMNS]

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

                self.logger.info(f"   ✓ {len(df)} 条")

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
    parser = create_base_parser("每日涨跌停价格同步 - t_stock_dailylimitprice")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = DailyLimitPriceSync(config, db, client)
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
