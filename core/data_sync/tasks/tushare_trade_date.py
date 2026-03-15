"""
Tushare 交易日历同步任务
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareTradeDateTask(BaseTushareTask):
    """Tushare 交易日历同步任务"""

    def __init__(self, name: str = "trade_date", check_after_sync: bool = True,
                 batch_size: int = 0, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_stock_tradedate",
            db_name="tushare_biz",
            sync_type="full",
            check_after_sync=check_after_sync,
            batch_size=1000
        )
        self.tushare = get_tushare_client()
        self.batch_size = batch_size  # 0表示按年获取
        self.rate_limiter = RateLimiter(max_requests_per_minute)

    def fetch_data(self) -> pd.DataFrame:
        """从 Tushare 获取交易日历"""
        print("📥 从 Tushare 获取交易日历...")

        current_year = datetime.now().year
        start_year = current_year - 3
        end_year = current_year + 1

        dfs = []
        request_count = 0

        # 只获取上海证券交易所数据
        for exchange in ['SSE']:
            for year in range(start_year, end_year + 1):
                # 速率控制
                self.rate_limiter.wait_if_needed()

                df = self.tushare.pro.query('trade_cal',
                    exchange=exchange,
                    start_date=f'{year}0101',
                    end_date=f'{year}1231')

                request_count += 1

                if not df.empty:
                    dfs.append(df)
                    print(f"   {exchange} {year}年: {len(df)} 条")

        print(f"   请求次数: {request_count}")

        # 合并
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            df = df.drop_duplicates(subset=['exchange', 'cal_date'])
            print(f"   合计: {len(df)} 条")
        else:
            df = pd.DataFrame()

        return df

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """同步数据到 MySQL - 使用优化的批量插入"""
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['exchange', 'cal_date', 'is_open', 'pretrade_date']

        # 定义 is_open 字段的转换器
        transformers = {
            'is_open': lambda x: int(x) if pd.notna(x) else None
        }

        # 使用基类的批量插入方法
        # exchange 和 cal_date 是复合唯一键
        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['exchange', 'cal_date'],
            update_columns=['is_open', 'pretrade_date'],
            transformers=transformers
        )
