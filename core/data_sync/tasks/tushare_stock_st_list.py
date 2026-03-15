"""
Tushare ST股票列表同步任务
接口: stock_st
数据范围: 20160101至今
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.storage.relational.connection import DatabaseManager
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareStockStListTask(BaseTushareTask):
    """Tushare ST股票列表同步任务"""

    def __init__(self, name: str = "stock_st_list", check_after_sync: bool = True,
                 batch_size: int = 1000, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_stock_st_list",
            db_name="tushare_biz",
            sync_type="incremental",  # 增量同步
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()
        self.batch_size = batch_size  # 单次请求最大1000行
        self.rate_limiter = RateLimiter(max_requests_per_minute)

    def fetch_data(self) -> pd.DataFrame:
        """从 Tushare 获取ST股票列表"""
        print("📥 从 Tushare 获取ST股票列表...")

        # 获取数据库中最新日期
        last_date = self._get_last_trade_date()
        if last_date:
            start_date = last_date
            print(f"   增量同步: 从 {start_date} 开始")
        else:
            # 首次同步，从2016年开始
            start_date = "20160101"
            print(f"   全量同步: 从 {start_date} 开始")

        end_date = datetime.now().strftime("%Y%m%d")

        dfs = []
        request_count = 0
        offset = 0

        while True:
            # 速率控制
            self.rate_limiter.wait_if_needed()

            # 分页获取数据
            df = self.tushare.pro.query(
                'stock_st',
                start_date=start_date,
                end_date=end_date,
                limit=self.batch_size,
                offset=offset
            )

            request_count += 1

            if df.empty:
                break

            dfs.append(df)
            print(f"   第{request_count}次请求: {len(df)} 条 (offset={offset})")

            # 如果返回数据不足batch_size，说明已经取完
            if len(df) < self.batch_size:
                break

            offset += self.batch_size

        print(f"   总请求次数: {request_count}")

        # 合并数据
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            # 去重
            df = df.drop_duplicates(subset=['ts_code', 'trade_date'])
            print(f"   合计: {len(df)} 条")
        else:
            df = pd.DataFrame()
            print("   无新数据")

        return df

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """同步数据到 MySQL - 使用优化的批量插入"""
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['ts_code', 'name', 'trade_date', 'type', 'type_name']

        # 使用基类的批量插入方法
        # ts_code 和 trade_date 是复合唯一键
        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code', 'trade_date'],
            update_columns=['name', 'type', 'type_name']
        )

    def _get_last_trade_date(self) -> str:
        """获取数据库中最新交易日期"""
        result = DatabaseManager.fetchone(
            self.db_name,
            f"SELECT MAX(trade_date) as max_date FROM {self.table_name}"
        )
        return result['max_date'] if result and result['max_date'] else None
