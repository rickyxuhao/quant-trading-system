"""
Tushare 股票日线行情同步任务
接口: daily
数据范围: 2005年至今
策略: 首次全量(2005起)，后续每日增量
方式: 按交易日逐日获取当天全量数据，边获取边写入（流式处理）
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import get_tushare_client
from core.storage.relational.connection import DatabaseManager
from core.data_sync.tasks.rate_limiter import RateLimiter


class TushareStockDailyMarketDataTask(BaseTushareTask):
    """Tushare 股票日线行情同步任务 - 流式处理版本"""

    def __init__(self, name: str = "stock_daily_market_data", check_after_sync: bool = True,
                 batch_size: int = 6000, max_requests_per_minute: int = 500):
        super().__init__(
            name=name,
            table_name="t_stock_dailymarketdata",
            db_name="tushare_biz",
            sync_type="incremental",  # 实际逻辑: 首次全量，后续增量
            check_after_sync=check_after_sync,
            batch_size=batch_size
        )
        self.tushare = get_tushare_client()
        self.fetch_batch_size = batch_size  # 单次请求最大6000条
        self.rate_limiter = RateLimiter(max_requests_per_minute)
        self.full_sync_start_date = "20050101"  # 全量同步起始日期

    def fetch_data(self) -> pd.DataFrame:
        """
        从 Tushare 获取日线行情 - 流式处理版本
        每天获取后立即写入数据库，不再返回大 DataFrame
        """
        print("📥 从 Tushare 获取日线行情（流式处理）...")

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
                # 获取单日数据
                df = self._fetch_single_date(trade_date)
                total_requests += 1

                if df.empty:
                    print("无数据")
                    continue

                # 立即写入数据库
                day_stats = self._sync_single_day(df, trade_date)
                total_rows += day_stats.get("affected", 0)
                success_days += 1

                print(f"✓ {len(df)} 条 (累计 {total_rows} 条)")

            except Exception as e:
                failed_days += 1
                print(f"✗ 失败: {e}")
                # 继续处理下一天（断点续传：已写入的数据保留）
                continue

        print(f"\n   处理完成: {success_days} 天成功, {failed_days} 天失败")
        print(f"   总请求次数: {total_requests}, 总写入: {total_rows} 条")

        # 返回空 DataFrame，因为数据已经实时写入了
        # 但为了兼容接口，返回一个标记用的 DataFrame
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

        columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                  'pre_close', 't_change', 'pct_chg', 'vol', 'amount']

        update_columns = ['open', 'high', 'low', 'close', 'pre_close',
                         't_change', 'pct_chg', 'vol', 'amount']

        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code', 'trade_date'],
            update_columns=update_columns
        )

    def _fetch_single_date(self, trade_date: str) -> pd.DataFrame:
        """获取单日所有股票数据"""
        dfs = []
        offset = 0

        while True:
            # 速率控制
            self.rate_limiter.wait_if_needed()

            # 获取数据
            df = self.tushare.pro.query(
                'daily',
                trade_date=trade_date,
                limit=self.fetch_batch_size,
                offset=offset
            )

            if df.empty:
                break

            dfs.append(df)

            # 如果返回数据不足batch_size，说明已经取完
            if len(df) < self.fetch_batch_size:
                break

            offset += self.fetch_batch_size

        if dfs:
            return pd.concat(dfs, ignore_index=True)
        return pd.DataFrame()

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取日期范围内的交易日"""
        # 从交易日历表中查询
        results = DatabaseManager.fetchall(
            'tushare_biz',
            f"""
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

        注意：在流式处理模式下，数据已经在 fetch_data 中实时写入，
        此方法只需要返回统计信息即可。
        """
        # 流式处理模式：数据已实时写入
        if not df.empty and 'streaming_sync' in df.columns:
            total_rows = int(df.iloc[0].get('total_rows', 0))
            return {
                "affected": total_rows,
                "inserted": total_rows,
                "updated": 0
            }

        # 非流式模式（兼容旧逻辑）
        if df.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                  'pre_close', 'change_amount', 'pct_chg', 'vol', 'amount']

        # 使用基类的批量插入方法
        # ts_code 和 trade_date 是复合唯一键
        update_columns = ['open', 'high', 'low', 'close', 'pre_close',
                         'change_amount', 'pct_chg', 'vol', 'amount']

        return self.bulk_insert(
            df=df,
            columns=columns,
            unique_columns=['ts_code', 'trade_date'],
            update_columns=update_columns
        )
