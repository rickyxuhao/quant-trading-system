"""
Tushare 资金流向数据同步任务
接口: moneyflow
数据范围: 2005年至今
策略: 每日增量同步
方式: 按交易日逐日获取当天全量数据
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.storage.relational.connection import DatabaseManager
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareMoneyflowTask(BaseTushareTask):
    """Tushare 资金流向数据同步任务"""

    def __init__(self, name: str = "moneyflow", check_after_sync: bool = True,
                 batch_size: int = 6000, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_stock_moneyflow",
            db_name="tushare_biz",
            sync_type="incremental",
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()
        self.fetch_batch_size = batch_size
        self.rate_limiter = RateLimiter(max_requests_per_minute)

    def _get_last_trade_date(self) -> str:
        """获取数据库中最新交易日"""
        sql = f"SELECT MAX(trade_date) as max_date FROM {self.table_name}"
        result = DatabaseManager.fetchall(self.db_name, sql)
        return result[0]["max_date"] if result and result[0]["max_date"] else None

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        from core.data_access.tushare.client import get_tushare_client
        pro = get_tushare_client()

        df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
        if df.empty:
            return []

        return df['cal_date'].tolist()

    def fetch_data(self) -> pd.DataFrame:
        """从 Tushare 获取资金流向数据"""
        print("📥 从 Tushare 获取资金流向数据...")

        # 确定日期范围
        last_date = self._get_last_trade_date()

        if last_date:
            start_date = (datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            if start_date > end_date:
                print("   已是最新数据，无需同步")
                return pd.DataFrame()

            print(f"   增量同步: {start_date} 至 {end_date}")
            dates_to_sync = self._get_trade_dates(start_date, end_date)
        else:
            # 首次全量 - 从最近一年开始
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            print(f"   首次同步: {start_date} 至 {end_date}")
            dates_to_sync = self._get_trade_dates(start_date, end_date)

        if not dates_to_sync:
            print("   无交易日需要同步")
            return pd.DataFrame()

        print(f"   需同步 {len(dates_to_sync)} 个交易日")

        # 逐日获取数据
        total_rows = 0
        success_days = 0
        failed_days = 0

        for i, trade_date in enumerate(dates_to_sync, 1):
            print(f"   [{i}/{len(dates_to_sync)}] 处理 {trade_date}...", end=" ")

            try:
                # 限制速率
                self.rate_limiter.acquire()

                # 获取当日数据
                df = self.tushare.moneyflow(trade_date=trade_date)

                if df.empty:
                    print("无数据")
                    continue

                # 同步到数据库
                stats = self.sync_to_db(df)

                total_rows += stats.get("affected", 0)
                success_days += 1
                print(f"✓ {stats.get('affected', 0)} 条")

            except Exception as e:
                failed_days += 1
                print(f"✗ 失败: {e}")
                continue

        print(f"\n   同步完成: {success_days} 天成功, {failed_days} 天失败, 共 {total_rows} 条记录")

        # 返回空 DataFrame（数据已写入数据库）
        return pd.DataFrame()

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """同步数据到数据库"""
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        # 列名映射 - 根据实际表结构
        columns = ['ts_code', 'trade_date', 'buy_sm_vol', 'buy_sm_amount',
                   'sell_sm_vol', 'sell_sm_amount', 'buy_md_vol', 'buy_md_amount',
                   'sell_md_vol', 'sell_md_amount', 'buy_lg_vol', 'buy_lg_amount',
                   'sell_lg_vol', 'sell_lg_amount', 'buy_elg_vol', 'buy_elg_amount']

        # 过滤掉 DataFrame 中没有的列
        available_cols = [col for col in columns if col in df.columns]

        # 使用批量插入
        return self.bulk_insert(
            df=df,
            columns=available_cols,
            unique_columns=['ts_code', 'trade_date']
        )
