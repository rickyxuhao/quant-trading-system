"""
Tushare 申万行业分类同步任务
接口: index_classify
数据范围: 全量
策略: 全量同步（行业分类不频繁变化，每次全量更新）
"""
import pandas as pd
from typing import Dict, Any

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client


class TushareSwClassifyTask(BaseTushareTask):
    """Tushare 申万行业分类同步任务"""

    def __init__(self, name: str = "sw_classify", check_after_sync: bool = True,
                 batch_size: int = 1000):
        super().__init__(
            name=name,
            table_name="t_sw_classify",
            db_name="tushare_biz",
            sync_type="full",  # 全量同步
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()

    def fetch_data(self) -> pd.DataFrame:
        """
        从 Tushare 获取申万行业分类数据
        """
        print("📥 从 Tushare 获取申万行业分类数据...")

        # 获取2021版申万行业分类
        df = self.tushare.pro.query(
            'index_classify',
            source='SW2021',  # 申万2021版
            limit=5000
        )

        if df.empty:
            print("⚠️ 无数据返回")
            return pd.DataFrame()

        print(f"   获取到 {len(df)} 条行业分类数据")

        # 添加级别字段
        # 行业代码长度：一级(4位如8010)、二级(6位如801010)、三级(8位如80101001)
        df['level'] = df['index_code'].apply(lambda x: len(str(x)) // 2 - 1)

        return df

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        同步数据到 MySQL
        """
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['ts_code', 'name', 'industry_type', 'parent_code', 'level']

        # 重命名列以匹配表结构
        df = df.rename(columns={
            'index_code': 'ts_code',
            'industry_name': 'name',
            'level': 'industry_type'
        })

        # 先清空表（全量同步）
        from core.storage.relational.connection import DatabaseManager
        DatabaseManager.execute(self.db_name, f"TRUNCATE TABLE {self.table_name}")
        print(f"   已清空表 {self.table_name}")

        # 插入数据
        result = self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code'],
            update_columns=['name', 'industry_type', 'parent_code', 'level']
        )

        print(f"   同步完成: {result['affected']} 条")
        return result
