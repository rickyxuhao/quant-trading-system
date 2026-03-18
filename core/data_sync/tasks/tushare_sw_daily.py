"""
Tushare 申万行业指数日线行情同步任务
接口: sw_daily
数据范围: 2005年至今
策略: 首次全量(2005起)，后续每日增量
方式: 按交易日逐日获取申万行业指数数据，边获取边写入（流式处理）
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.storage.relational.connection import DatabaseManager
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareSwDailyTask(BaseTushareTask):
    """Tushare 申万行业指数日线行情同步任务 - 流式处理版本"""

    def __init__(self, name: str = "sw_daily", check_after_sync: bool = True,
                 batch_size: int = 6000, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_sw_daily",
            db_name="tushare_biz",
            sync_type="incremental",
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()
        self.fetch_batch_size = batch_size
        self.rate_limiter = RateLimiter(max_requests_per_minute)
        self.full_sync_start_date = "20050101"

    def fetch_data(self) -> pd.DataFrame:
        """
        从 Tushare 获取申万行业指数日线行情 - 流式处理版本
        每天获取后立即写入数据库，不再返回大 DataFrame
        """
        print("📥 从 Tushare 获取申万行业指数日线行情（流式处理）...")

        # 确定日期范围
        last_date = self._get_last_trade_date()

        if last_date:
            # 增量同步: 从最后一天+1开始
            start_date = (datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            if start_date > end_date:
                print(f"   已是最新数据，无需同步")
                return pd.DataFrame()

            print(f"   增量同步: {start_date} 至 {end_date}")
            dates_to_sync = self._get_trade_dates(start_date, end_date)
        else:
            # 首次全量同步: 从2005年开始
            start_date = self.full_sync_start_date
            end_date = datetime.now().strftime("%Y%m%d")
            print(f"   首次全量同步: {start_date} 至 {end_date}")
            dates_to_sync = self._get_trade_dates(start_date, end_date)

        if not dates_to_sync:
            print("   无交易日需要同步")
            return pd.DataFrame()

        print(f"   需同步 {len(dates_to_sync)} 个交易日")
        print("   每天获取后将立即写入数据库（支持断点续传）")

        # 流式处理：逐日获取并写入
        total_rows = 0
        total_requests = 0
        success_days = 0
        failed_days = 0

        for i, trade_date in enumerate(dates_to_sync, 1):
            print(f"   [{i}/{len(dates_to_sync)}] 处理 {trade_date}...", end=" ")

            try:
                # 获取单日数据（所有申万行业指数）
                df = self._fetch_single_date(trade_date)
                total_requests += 1

                if df.empty:
                    print("无数据")
                    continue

                # 立即写入数据库
                day_stats = self._sync_single_day(df, trade_date)
                total_rows += day_stats.get("affected", 0)
                success_days += 1

                print(f"✓ {len(df)} 条行业指数 (累计 {total_rows} 条)")

            except Exception as e:
                failed_days += 1
                print(f"✗ 失败: {e}")
                continue

        print(f"\n   处理完成: {success_days} 天成功, {failed_days} 天失败")
        print(f"   总请求次数: {total_requests}, 总写入: {total_rows} 条")

        return pd.DataFrame({"streaming_sync": [True], "total_rows": [total_rows]})

    def _sync_single_day(self, df: pd.DataFrame, trade_date: str) -> Dict[str, int]:
        """
        同步单日数据到数据库

        Args:
            df: 单日数据 DataFrame
            trade_date: 交易日期

        Returns:
            统计信息字典
        """
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['ts_code', 'trade_date', 'name', 'open', 'high', 'low', 'close',
                   'chng', 'pct_chg', 'vol', 'amount', 'pe', 'pb', 'float_mv', 'total_mv']

        update_columns = ['name', 'open', 'high', 'low', 'close', 'chng', 'pct_chg',
                         'vol', 'amount', 'pe', 'pb', 'float_mv', 'total_mv']

        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code', 'trade_date'],
            update_columns=update_columns
        )

    def _fetch_single_date(self, trade_date: str) -> pd.DataFrame:
        """获取单日所有申万行业指数数据"""
        self.rate_limiter.wait_if_needed()

        # 获取数据 - 申万行业指数日线接口
        # 不指定ts_code，获取所有行业指数
        df = self.tushare.pro.query(
            'sw_daily',
            trade_date=trade_date,
            limit=self.fetch_batch_size
        )

        return df if not df.empty else pd.DataFrame()

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取日期范围内的交易日"""
        results = DatabaseManager.fetchall(
            'tushare_biz',
            """
            SELECT cal_date FROM t_stock_tradedate
            WHERE cal_date BETWEEN %s AND %s
            AND is_open = 1
            ORDER BY cal_date
            """,
            (start_date, end_date)
        )
        return [r['cal_date'] for r in results]

    def _get_last_trade_date(self) -> str:
        """获取数据库中最新交易日期"""
        result = DatabaseManager.fetchone(
            self.db_name,
            f"SELECT MAX(trade_date) as max_date FROM {self.table_name}"
        )
        return result['max_date'] if result and result['max_date'] else None

    def sync_to_db(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        同步数据到 MySQL - 流式处理版本
        """
        if not df.empty and 'streaming_sync' in df.columns:
            total_rows = int(df.iloc[0].get('total_rows', 0))
            return {
                "affected": total_rows,
                "inserted": total_rows,
                "updated": 0
            }

        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['ts_code', 'trade_date', 'name', 'open', 'high', 'low', 'close',
                   'chng', 'pct_chg', 'vol', 'amount', 'pe', 'pb', 'float_mv', 'total_mv']

        update_columns = ['name', 'open', 'high', 'low', 'close', 'chng', 'pct_chg',
                         'vol', 'amount', 'pe', 'pb', 'float_mv', 'total_mv']

        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code', 'trade_date'],
            update_columns=update_columns
        )
