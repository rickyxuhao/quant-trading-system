"""
Tushare 股票基础信息同步任务
"""
import pandas as pd
from typing import Dict, Any

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareStockBasicTask(BaseTushareTask):
    """Tushare 股票基础信息同步任务"""

    def __init__(self, name: str = "stock_basic", check_after_sync: bool = True,
                 batch_size: int = 0, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_stock_basic",
            db_name="tushare_biz",
            sync_type="full",
            check_after_sync=check_after_sync,
            batch_size=1000
        )
        self.tushare = get_tushare_client()
        self.batch_size = batch_size  # 0表示一次获取全部
        self.rate_limiter = RateLimiter(max_requests_per_minute)

    def fetch_data(self) -> pd.DataFrame:
        """从 Tushare 获取股票基础信息"""
        print("📥 从 Tushare 获取数据...")

        fields = 'ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'

        request_count = 0
        dfs = []

        # 获取上市股票
        self.rate_limiter.wait_if_needed()
        df_l = self.tushare.pro.query('stock_basic', list_status='L', fields=fields)
        request_count += 1
        print(f"   上市股票: {len(df_l)} 条")
        dfs.append(df_l)

        # 获取退市股票
        self.rate_limiter.wait_if_needed()
        df_d = self.tushare.pro.query('stock_basic', list_status='D', fields=fields)
        request_count += 1
        print(f"   退市股票: {len(df_d)} 条")
        dfs.append(df_d)

        # 获取暂停上市股票
        self.rate_limiter.wait_if_needed()
        df_p = self.tushare.pro.query('stock_basic', list_status='P', fields=fields)
        request_count += 1
        print(f"   暂停上市: {len(df_p)} 条")
        dfs.append(df_p)

        print(f"   请求次数: {request_count}")

        # 合并
        df = pd.concat(dfs, ignore_index=True)
        print(f"   合计: {len(df)} 条")

        return df

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """同步数据到 MySQL - 使用优化的批量插入"""
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = [
            'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname',
            'enname', 'cnspell', 'market', 'exchange', 'curr_type',
            'list_status', 'list_date', 'delist_date', 'is_hs',
            'act_name', 'act_ent_type'
        ]

        # 使用基类的批量插入方法
        # ts_code 是唯一键，其他字段在重复时更新
        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code'],
            update_columns=[col for col in columns if col != 'ts_code']
        )
