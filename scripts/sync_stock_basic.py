#!/usr/bin/env python3
"""
t_stock_basic 数据同步脚本
从 Tushare 获取股票基础信息并同步到 MySQL
支持全量同步和增量更新
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from core.data_access.tushare.client import get_tushare_client
from core.storage.relational.connection import DatabaseManager


class StockBasicSync:
    """股票基础信息同步器"""
    
    def __init__(self):
        self.tushare = get_tushare_client()
        self.db_name = "tushare_biz"
        self.table_name = "t_stock_basic"
    
    def fetch_from_tushare(self) -> pd.DataFrame:
        """
        从 Tushare 获取股票基础信息
        
        Returns:
            DataFrame 包含所有股票基础信息
        """
        print("📥 从 Tushare 获取数据...")
        
        # 指定需要的所有字段
        fields = 'ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'
        
        # 获取上市股票
        df_l = self.tushare.pro.query('stock_basic', list_status='L', fields=fields)
        print(f"   上市股票: {len(df_l)} 条")
        
        # 获取退市股票
        df_d = self.tushare.pro.query('stock_basic', list_status='D', fields=fields)
        print(f"   退市股票: {len(df_d)} 条")
        
        # 获取暂停上市股票
        df_p = self.tushare.pro.query('stock_basic', list_status='P', fields=fields)
        print(f"   暂停上市: {len(df_p)} 条")
        
        # 合并
        df = pd.concat([df_l, df_d, df_p], ignore_index=True)
        print(f"   合计: {len(df)} 条")
        
        return df
    
    def sync_to_mysql(self, df: pd.DataFrame) -> dict:
        """
        同步数据到 MySQL
        
        Args:
            df: Tushare 数据 DataFrame
            
        Returns:
            同步结果统计
        """
        print(f"\n📤 同步到 MySQL 表 {self.table_name}...")
        
        # 字段映射（Tushare字段 -> 数据库字段）
        # 字段名一致，无需映射
        # 日期字段保留 str 类型，不做转换
        
        # 获取现有数据（用于计算增量）
        existing_count = self._get_existing_count()
        print(f"   数据库现有记录: {existing_count} 条")
        
        # 使用 REPLACE INTO 实现 upsert
        stats = {"inserted": 0, "updated": 0, "failed": 0}
        
        with DatabaseManager.get_connection(self.db_name) as conn:
            cursor = conn.cursor()
            
            # 准备 SQL
            columns = [
                'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname',
                'enname', 'cnspell', 'market', 'exchange', 'curr_type',
                'list_status', 'list_date', 'delist_date', 'is_hs',
                'act_name', 'act_ent_type'
            ]
            
            placeholders = ', '.join(['%s'] * len(columns))
            # MySQL 8.0.19+ / 9.x: 使用 AS new 别名语法替代 VALUES()
            update_clause = ', '.join([f"{col}=new.{col}" for col in columns if col != 'ts_code'])

            sql = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                AS new ON DUPLICATE KEY UPDATE {update_clause}
            """
            
            # 一次性插入所有数据
            rows = []
            for _, row in df.iterrows():
                row_data = []
                for col in columns:
                    val = row.get(col)
                    # 处理 NaN 和 None
                    if pd.isna(val):
                        row_data.append(None)
                    else:
                        row_data.append(val)
                rows.append(row_data)
            
            try:
                cursor.executemany(sql, rows)
                conn.commit()
                stats["inserted"] = len(rows)
                print(f"   同步完成: {len(rows)} 条")
                
            except Exception as e:
                print(f"   ❌ 插入失败: {e}")
                stats["failed"] = len(rows)
            
            cursor.close()
        
        # 计算实际更新数
        new_count = self._get_existing_count()
        stats["updated"] = stats["inserted"] - (new_count - existing_count)
        stats["inserted"] = new_count - existing_count
        
        return stats
    
    def _get_existing_count(self) -> int:
        """获取表中现有记录数"""
        result = DatabaseManager.fetchone(
            self.db_name,
            f"SELECT COUNT(*) as cnt FROM {self.table_name}"
        )
        return result['cnt'] if result else 0
    
    def run(self) -> dict:
        """
        执行同步
        
        Returns:
            同步结果
        """
        print("="*60)
        print("t_stock_basic 数据同步")
        print("="*60)
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. 获取数据
        df = self.fetch_from_tushare()
        
        if df.empty:
            print("❌ 未获取到数据，同步中止")
            return {"status": "failed", "reason": "no_data"}
        
        # 2. 同步到 MySQL
        stats = self.sync_to_mysql(df)
        
        # 3. 输出结果
        print()
        print("="*60)
        print("同步完成")
        print("="*60)
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"新增记录: {stats['inserted']}")
        print(f"更新记录: {stats['updated']}")
        print(f"失败记录: {stats['failed']}")
        print(f"总计: {stats['inserted'] + stats['updated']}")
        
        return {
            "status": "success",
            "stats": stats,
            "total": len(df)
        }


def main():
    """主函数"""
    sync = StockBasicSync()
    result = sync.run()
    
    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
