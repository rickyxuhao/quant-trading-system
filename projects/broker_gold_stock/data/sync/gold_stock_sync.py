"""
券商金股数据同步任务
从Tushare获取券商每月金股推荐数据
"""
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from core.data_sync.tasks.base import BaseTushareTask
from core.data_access.tushare.client import TushareClient
from projects.broker_gold_stock.data.models import GoldStock
from projects.broker_gold_stock.data.repository import GoldStockRepository


class GoldStockSyncTask(BaseTushareTask):
    """
    券商金股数据同步任务

    同步Tushare的broker_recommend接口数据到broker_gold_stock表
    """

    def __init__(self):
        super().__init__(
            name="gold_stock_sync",
            table_name="broker_gold_stock",
            db_name="interface",
            sync_type="incremental",
            check_after_sync=True
        )
        self.ts_client = TushareClient()
        self._current_month = None

    def fetch_data(self) -> pd.DataFrame:
        """获取数据（实现抽象方法）"""
        month = self._current_month or datetime.now().strftime("%Y%m")
        return self._fetch_from_tushare(month)

    def sync_to_db(self, data: pd.DataFrame) -> Dict[str, int]:
        """同步数据到数据库（实现抽象方法）"""
        month = self._current_month or datetime.now().strftime("%Y%m")

        if data.empty:
            return {"affected": 0, "inserted": 0, "updated": 0}

        stocks = self._convert_to_models(data, month)
        return GoldStockRepository.save_many_gold_stocks(stocks)

    def sync_broker_recommend(self, month: str = None) -> Dict[str, Any]:
        """
        同步指定月份的券商金股推荐数据

        Args:
            month: 月份，格式YYYYMM，默认当前月

        Returns:
            同步结果统计
        """
        if month is None:
            month = datetime.now().strftime("%Y%m")

        self._current_month = month
        print(f"📊 开始同步 {month} 月券商金股数据...")

        try:
            # 使用父类的run方法执行同步
            result = self.run()

            # 转换为统一的返回格式
            return {
                "affected": result.get("rows_affected", 0),
                "inserted": result.get("rows_inserted", 0),
                "updated": result.get("rows_updated", 0)
            }

        except Exception as e:
            print(f"❌ 同步失败: {e}")
            raise

    def _fetch_from_tushare(self, month: str) -> pd.DataFrame:
        """
        从Tushare获取券商金股数据

        使用query接口调用broker_recommend
        """
        try:
            # 调用broker_recommend接口
            df = self.ts_client.query(
                'broker_recommend',
                month=month
            )
            return df
        except Exception as e:
            print(f"⚠️ broker_recommend接口调用失败: {e}")
            print("尝试使用通用query接口...")
            # 备用方案：使用通用查询
            df = self.ts_client.pro.query('broker_recommend', month=month)
            return df

    def _convert_to_models(self, df: pd.DataFrame, month: str) -> List[GoldStock]:
        """将DataFrame转换为GoldStock模型列表"""
        stocks = []

        for _, row in df.iterrows():
            stock = GoldStock(
                month=month,
                broker_name=row.get('broker', row.get('broker_name', '')),
                ts_code=row.get('ts_code', ''),
                name=row.get('name', row.get('stock_name', '')),
                industry=row.get('industry', ''),
                analyst=row.get('analyst', ''),
                logic=row.get('logic', row.get('recommend_reason', '')),
                target_price=self._safe_float(row.get('target_price')),
                previous_perf=self._safe_float(row.get('prev_perf', row.get('previous_perf')))
            )
            stocks.append(stock)

        return stocks

    @staticmethod
    def _safe_float(value) -> float:
        """安全转换为float"""
        if pd.isna(value) or value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def sync_recent_months(self, months: int = 3) -> Dict[str, Any]:
        """
        同步最近N个月的金股数据

        Args:
            months: 月数

        Returns:
            各月同步结果
        """
        results = {}
        now = datetime.now()

        for i in range(months):
            # 计算目标月份
            if now.month - i <= 0:
                target_month = (now.year - 1) * 100 + (now.month - i + 12)
            else:
                target_month = now.year * 100 + (now.month - i)

            month_str = str(target_month)
            print(f"\n📅 同步月份: {month_str}")

            try:
                result = self.sync_broker_recommend(month_str)
                results[month_str] = result
            except Exception as e:
                print(f"❌ {month_str} 月同步失败: {e}")
                results[month_str] = {"error": str(e)}

        return results

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行任务入口

        Args:
            **kwargs: 支持 month, months 参数

        Returns:
            执行结果
        """
        if 'month' in kwargs:
            return self.sync_broker_recommend(kwargs['month'])
        elif 'months' in kwargs:
            return self.sync_recent_months(kwargs['months'])
        else:
            # 默认只同步当前月
            return self.sync_recent_months(1)


class GoldStockPerformanceSync:
    """
    金股表现数据同步

    基于日线数据计算金股表现指标
    """

    def __init__(self):
        self.ts_client = TushareClient()

    def update_performance(self, month: str = None) -> Dict[str, Any]:
        """
        更新指定月份金股的表现数据

        Args:
            month: 月份，默认当前月

        Returns:
            更新统计
        """
        if month is None:
            month = datetime.now().strftime("%Y%m")

        print(f"📈 更新 {month} 月金股表现数据...")

        # 获取该月所有金股
        stocks = GoldStockRepository.get_gold_stocks_by_month(month)

        if not stocks:
            print(f"⚠️ {month} 月无金股数据")
            return {"updated": 0, "total": 0}

        updated = 0
        for stock in stocks:
            try:
                self._update_single_stock(stock, month)
                updated += 1
            except Exception as e:
                print(f"❌ 更新 {stock.ts_code} 失败: {e}")

        print(f"✅ 表现数据更新完成: {updated}/{len(stocks)}")
        return {"updated": updated, "total": len(stocks)}

    def _update_single_stock(self, stock: GoldStock, month: str):
        """更新单只股票的表现数据"""
        from projects.broker_gold_stock.data.models import GoldStockPerformance
        from projects.broker_gold_stock.data.repository import PerformanceRepository

        # 获取月份第一天和最后一天
        year = int(month[:4])
        mon = int(month[4:])

        from calendar import monthrange
        _, last_day = monthrange(year, mon)

        start_date = f"{month}01"
        end_date = f"{month}{last_day}"

        # 获取日线数据
        df = self.ts_client.get_daily(stock.ts_code, start_date, end_date)

        if df.empty:
            print(f"⚠️ {stock.ts_code} 无日线数据")
            return

        # 计算表现指标
        df = df.sort_values('trade_date')

        recommend_price = df.iloc[0]['close'] if not df.empty else None
        current_price = df.iloc[-1]['close'] if not df.empty else None
        max_price = df['high'].max() if not df.empty else None
        min_price = df['low'].min() if not df.empty else None

        # 计算收益率
        total_return = None
        if recommend_price and current_price:
            total_return = round((current_price - recommend_price) / recommend_price * 100, 4)

        # 计算波动率
        volatility = None
        if len(df) > 1:
            df['returns'] = df['close'].pct_change()
            volatility = round(df['returns'].std() * (252 ** 0.5) * 100, 4)  # 年化波动率

        # 计算日均成交额（万元）
        avg_volume = round(df['amount'].mean(), 4) if 'amount' in df.columns else None

        # 创建表现记录
        perf = GoldStockPerformance(
            month=month,
            ts_code=stock.ts_code,
            name=stock.name,
            recommend_date=start_date,
            end_date=end_date,
            recommend_price=recommend_price,
            current_price=current_price,
            max_price=max_price,
            min_price=min_price,
            total_return=total_return,
            volatility=volatility,
            avg_volume=avg_volume
        )

        # 保存到数据库
        PerformanceRepository.save_performance(perf)


# 便捷函数
def sync_gold_stock_data(month: str = None, months: int = None) -> Dict[str, Any]:
    """
    同步券商金股数据便捷函数

    Args:
        month: 指定月份 YYYYMM
        months: 同步最近N个月

    Returns:
        同步结果
    """
    task = GoldStockSyncTask()

    if month:
        return task.sync_broker_recommend(month)
    elif months:
        return task.sync_recent_months(months)
    else:
        # 默认只同步当前月
        return task.sync_recent_months(1)
