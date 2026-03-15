#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深股通成分股同步脚本
表名: t_stock_hs_const
数据来源: Tushare hs_const API
"""

import sys
import os
from typing import Dict, Any

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class HSConstSync(BaseSyncTask):
    """沪深股通成分股同步任务"""

    TABLE_NAME = "t_stock_hs_const"
    API_NAME = "hs_const"
    COLUMNS = ['ts_code', 'hs_type', 'in_date', 'out_date', 'is_new']
    UNIQUE_COLUMNS = ['ts_code', 'hs_type']
    SYNC_TYPE = "full"

    def sync_full(self, mode: str = "full") -> Dict[str, Any]:
        """全量同步 - 分别获取沪股通(SH)和深股通(SZ)数据并合并"""
        import pandas as pd

        self.logger.info(f"📥 从 Tushare 获取沪深股通成分股数据...")

        all_data = []
        hs_types = [('SH', '沪股通'), ('SZ', '深股通')]

        for hs_type, hs_name in hs_types:
            self.logger.info(f"   获取 {hs_name} ({hs_type}) 数据...")
            try:
                df = self.client.query(self.API_NAME, hs_type=hs_type)
                if df is not None and not df.empty:
                    all_data.append(df)
                    self.logger.info(f"   ✓ {hs_name}: 获取 {len(df)} 条记录")
                else:
                    self.logger.warning(f"   ⚠️ {hs_name}: 无数据返回")
            except Exception as e:
                self.logger.error(f"   ✗ {hs_name}: 获取失败 - {e}")
                raise

        if not all_data:
            self.logger.info("⚠️ 无数据返回")
            return {"status": "success", "rows": 0}

        # 合并数据
        df = pd.concat(all_data, ignore_index=True)
        self.logger.info(f"✅ 总共获取 {len(df)} 条记录")

        # 清理数据
        df = self.clean_dataframe(df)
        rows = df.values.tolist()

        # UPSERT
        self.logger.info(f"💾 写入数据库...")
        result = self.db.upsert(
            self.TABLE_NAME, self.COLUMNS, rows,
            self.UNIQUE_COLUMNS, self.get_update_columns()
        )

        self.logger.info(f"✅ 同步完成: 插入 {result['inserted']}, 更新 {result['updated']}")

        return {
            "status": "success",
            "table": self.TABLE_NAME,
            "rows_fetched": len(df),
            "rows_inserted": result['inserted'],
            "rows_updated": result['updated']
        }


def main():
    parser = create_base_parser("沪深股通成分股同步 - t_stock_hs_const")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = HSConstSync(config, db, client)
    result = sync_task.execute(mode=args.mode)

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
