"""
每日数据同步模块

收盘后自动同步持仓数据：
1. 获取当日收盘价
2. 计算个股盈亏
3. 记录持仓历史
4. 计算并记录净值快照
5. 风险检查

Example:
    >>> from projects.portfolio_analysis import DailySync
    >>> sync = DailySync()
    >>> sync.run_eod_sync()  # 收盘后同步
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import logging

import pandas as pd

from projects.portfolio_analysis.database.models import (
    Position, PortfolioSnapshot, PositionHistory
)
from projects.portfolio_analysis.database.repository import PositionRepository
from projects.portfolio_analysis.core.risk_diagnostic import RiskDiagnostic
from core.storage.relational.connection import DatabaseManager
from core.data_access.tushare.client import TushareClient

logger = logging.getLogger(__name__)


class DailySync:
    """每日收盘后数据同步

    自动完成收盘后的数据更新和记录工作。
    """

    def __init__(self):
        """初始化同步器"""
        self.repo = PositionRepository()
        self.ts_client = TushareClient()

    def run_eod_sync(self, trade_date: Optional[date] = None) -> Dict[str, any]:
        """收盘后同步任务

        Args:
            trade_date: 交易日期，默认今天

        Returns:
            同步结果统计
        """
        if trade_date is None:
            trade_date = date.today()

        logger.info(f"开始收盘后同步: {trade_date}")

        result = {
            'date': trade_date.isoformat(),
            'success': True,
            'positions_synced': 0,
            'snapshot_created': False,
            'risks_found': 0,
            'errors': []
        }

        try:
            # 1. 获取当前持仓
            positions = self.repo.get_all_positions()
            if not positions:
                logger.info("当前无持仓，跳过同步")
                return result

            logger.info(f"当前持仓数量: {len(positions)}")

            # 2. 获取当日收盘价
            prices = self._get_close_prices([p.code for p in positions], trade_date)
            result['prices_fetched'] = len(prices)

            # 3. 计算并记录持仓历史
            total_market_value = 0
            total_cost = 0

            for pos in positions:
                price = prices.get(pos.code)
                if price is None:
                    logger.warning(f"未获取到价格: {pos.code}")
                    continue

                # 记录持仓历史
                try:
                    history = self._create_position_history(pos, price, trade_date)
                    self.repo.record_position_history(history)
                except Exception as e:
                    if "Duplicate entry" in str(e):
                        logger.debug(f"持仓历史已存在: {pos.code} on {trade_date}")
                    else:
                        raise

                vol = float(pos.volume) if pos.volume else 0
                total_market_value += price * vol
                total_cost += float(pos.cost_price) * vol if pos.cost_price else 0
                result['positions_synced'] += 1

            # 4. 获取当前现金（从最新快照）
            latest_snapshot = self.repo.get_latest_snapshot()
            cash = float(latest_snapshot.cash) if latest_snapshot and latest_snapshot.cash else 0.0

            # 5. 计算净值快照
            total_asset = cash + total_market_value

            # 计算收益率
            daily_return = 0.0
            cumulative_return = 0.0
            net_value = 1.0

            if latest_snapshot and latest_snapshot.net_value:
                prev_nav = float(latest_snapshot.net_value)
                prev_total = float(latest_snapshot.total_asset) if latest_snapshot.total_asset else total_asset
                if prev_nav > 0 and prev_total > 0:
                    daily_return = (total_asset / prev_total) - 1
                    net_value = prev_nav * (1 + daily_return)
                    cumulative_return = net_value - 1

            # 获取基准收益率
            benchmark_return = self._get_benchmark_return(trade_date)

            snapshot = PortfolioSnapshot(
                date=trade_date,
                total_asset=Decimal(str(total_asset)),
                cash=cash,
                market_value=Decimal(str(total_market_value)),
                net_value=Decimal(str(net_value)),
                daily_return=Decimal(str(daily_return)),
                cumulative_return=Decimal(str(cumulative_return)),
                benchmark_return=Decimal(str(benchmark_return)) if benchmark_return else None,
                notes=f"Synced at {datetime.now().strftime('%H:%M:%S')}"
            )

            self.repo.record_snapshot(snapshot)
            result['snapshot_created'] = True
            logger.info(f"净值快照已记录: nav={net_value:.4f}, return={daily_return*100:.2f}%")

            # 6. 风险检查
            diagnostic = RiskDiagnostic()
            risk_report = diagnostic.check_all()
            result['risks_found'] = len(risk_report.alerts)

            if risk_report.alerts:
                logger.warning(f"发现 {len(risk_report.alerts)} 条风险预警")
                for alert in risk_report.alerts:
                    logger.warning(f"  [{alert.level}] {alert.message}")

            logger.info(f"收盘后同步完成: {trade_date}")

        except Exception as e:
            logger.error(f"收盘后同步失败: {e}")
            result['success'] = False
            result['errors'].append(str(e))
            raise

        return result

    def sync_market_data(self, codes: List[str]) -> Dict[str, any]:
        """同步持仓股票行情到本地缓存

        Args:
            codes: 股票代码列表

        Returns:
            同步结果
        """
        # 这里可以实现将数据缓存到Redis或其他缓存系统的逻辑
        logger.info(f"同步行情数据: {len(codes)} 只股票")
        return {'codes': len(codes), 'status': 'skipped'}

    def backfill_snapshots(self, start_date: date, end_date: date) -> Dict[str, any]:
        """回补历史净值快照

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            回补结果
        """
        # 获取交易日历
        trade_dates = self._get_trade_dates(start_date, end_date)

        synced = 0
        for trade_date in trade_dates:
            # 检查是否已有快照
            existing = self.repo.get_snapshot_by_date(trade_date)
            if existing:
                continue

            try:
                self.run_eod_sync(trade_date)
                synced += 1
            except Exception as e:
                logger.error(f"回补 {trade_date} 失败: {e}")

        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'trade_dates': len(trade_dates),
            'synced': synced
        }

    def init_portfolio(
        self,
        initial_cash: float,
        start_date: Optional[date] = None
    ) -> PortfolioSnapshot:
        """初始化组合（首次使用）

        Args:
            initial_cash: 初始资金
            start_date: 开始日期

        Returns:
            初始快照
        """
        if start_date is None:
            start_date = date.today()

        snapshot = PortfolioSnapshot(
            date=start_date,
            total_asset=Decimal(str(initial_cash)),
            cash=Decimal(str(initial_cash)),
            market_value=Decimal('0'),
            net_value=Decimal('1.0'),
            daily_return=Decimal('0'),
            cumulative_return=Decimal('0'),
            notes="Portfolio initialization"
        )

        self.repo.record_snapshot(snapshot)
        logger.info(f"组合已初始化: cash={initial_cash:,.2f}, date={start_date}")

        return snapshot

    # ========== Private Methods ==========

    def _get_close_prices(
        self,
        codes: List[str],
        trade_date: date
    ) -> Dict[str, float]:
        """获取收盘价"""
        prices = {}
        date_str = trade_date.strftime('%Y%m%d')

        try:
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, close
                FROM t_stock_dailymarketdata
                WHERE ts_code IN ({placeholders})
                  AND trade_date = %s
            """
            params = codes + [date_str]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            for r in results:
                prices[r['ts_code']] = float(r['close'])

        except Exception as e:
            logger.error(f"获取收盘价失败: {e}")

        return prices

    def _create_position_history(
        self,
        position: Position,
        close_price: float,
        trade_date: date
    ) -> PositionHistory:
        """创建持仓历史记录"""
        vol = float(position.volume) if position.volume else 0
        cost = float(position.cost_price) * vol if position.cost_price else 0
        market_value = close_price * vol
        pnl = market_value - cost
        pnl_pct = (close_price / float(position.cost_price) - 1) if position.cost_price and float(position.cost_price) > 0 else 0

        # 获取总资产用于计算权重
        latest_snapshot = self.repo.get_latest_snapshot()
        total_asset = float(latest_snapshot.total_asset) if latest_snapshot else market_value
        weight = market_value / total_asset if total_asset > 0 else 0

        return PositionHistory(
            date=trade_date,
            code=position.code,
            name=position.name,
            volume=vol,
            cost_price=position.cost_price,
            close_price=Decimal(str(close_price)),
            market_value=Decimal(str(market_value)),
            pnl=Decimal(str(pnl)),
            pnl_pct=Decimal(str(pnl_pct)),
            weight=Decimal(str(weight))
        )

    def _get_benchmark_return(self, trade_date: date) -> Optional[float]:
        """获取基准日收益率"""
        try:
            date_str = trade_date.strftime('%Y%m%d')

            # 沪深300
            sql = """
                SELECT pct_chg
                FROM t_index_dailymarketdata
                WHERE ts_code = '000300.SH'
                  AND trade_date = %s
            """
            result = DatabaseManager.fetchone("tushare_biz", sql, (date_str,))

            if result and result.get('pct_chg'):
                return float(result['pct_chg']) / 100

        except Exception as e:
            logger.warning(f"获取基准收益失败: {e}")

        return None

    def _get_trade_dates(self, start_date: date, end_date: date) -> List[date]:
        """获取交易日列表"""
        sql = """
            SELECT cal_date
            FROM t_stock_tradedate
            WHERE cal_date BETWEEN %s AND %s
              AND is_open = 1
            ORDER BY cal_date ASC
        """
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        results = DatabaseManager.fetchall("tushare_biz", sql, (start_str, end_str))

        return [
            datetime.strptime(r['cal_date'], '%Y%m%d').date()
            for r in results
        ]


if __name__ == "__main__":
    # 测试每日同步
    logging.basicConfig(level=logging.INFO)

    sync = DailySync()

    print("\n" + "=" * 60)
    print("每日收盘同步测试")
    print("=" * 60)

    try:
        result = sync.run_eod_sync()
        print(f"\n同步结果:")
        print(f"  日期: {result['date']}")
        print(f"  持仓同步: {result['positions_synced']} 只")
        print(f"  快照创建: {'✅' if result['snapshot_created'] else '❌'}")
        print(f"  风险预警: {result['risks_found']} 条")
        print(f"  状态: {'✅ 成功' if result['success'] else '❌ 失败'}")
    except Exception as e:
        print(f"\n❌ 同步失败: {e}")
