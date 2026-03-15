"""
风险诊断器

提供持仓风险检查和预警功能。

Example:
    >>> from projects.portfolio_analysis import RiskDiagnostic
    >>> diagnostic = RiskDiagnostic()
    >>> report = diagnostic.check_all()
    >>> for alert in report.alerts:
    ...     print(f"[{alert.level}] {alert.message}")
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Any
import logging

import pandas as pd
import numpy as np

from projects.portfolio_analysis.database.models import Position, PortfolioSnapshot
from projects.portfolio_analysis.database.repository import PositionRepository
from projects.portfolio_analysis.core.analyzer import PositionPnl, RiskAlert, RiskReport
from core.storage.relational.connection import DatabaseManager

logger = logging.getLogger(__name__)


class RiskDiagnostic:
    """持仓风险诊断器

    提供全面的风险检查功能，包括：
    - 个股风险检查（亏损、ST等）
    - 集中度风险检查
    - 回撤风险检查
    - 行业集中度检查
    - 流动性风险检查
    """

    # 风险阈值配置
    THRESHOLDS = {
        'single_stock_loss_warning': -0.15,     # 个股亏损15%预警
        'single_stock_loss_critical': -0.25,    # 个股亏损25%严重
        'sector_concentration_warning': 0.30,    # 行业集中度30%预警
        'sector_concentration_critical': 0.50,   # 行业集中度50%严重
        'drawdown_warning': -0.10,               # 回撤10%预警
        'drawdown_critical': -0.20,              # 回撤20%严重
        'single_stock_weight_warning': 0.15,     # 个股权重15%预警
        'single_stock_weight_critical': 0.25,    # 个股权重25%严重
        'cash_ratio_warning': 0.05,              # 现金比例低于5%预警
        'turnover_warning': 2.0,                 # 月换手率超过200%预警
        'volatility_warning': 0.30,              # 年化波动率30%预警
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """初始化诊断器

        Args:
            thresholds: 自定义阈值配置
        """
        self.thresholds = self.THRESHOLDS.copy()
        if thresholds:
            self.thresholds.update(thresholds)

        self.repo = PositionRepository()

    def check_all(
        self,
        positions: Optional[List[PositionPnl]] = None,
        snapshots: Optional[List[PortfolioSnapshot]] = None
    ) -> RiskReport:
        """运行所有风险检查

        Args:
            positions: 持仓列表，默认查询当前持仓
            snapshots: 净值快照列表，默认查询最近快照

        Returns:
            完整的风险报告
        """
        report = RiskReport()
        alerts = []

        # 获取数据
        if positions is None:
            positions = self._get_current_positions()

        if snapshots is None:
            end_date = date.today()
            start_date = end_date - pd.Timedelta(days=90)
            snapshots = self.repo.get_snapshots(start_date, end_date)

        # 运行各项检查
        alerts.extend(self.check_single_stock_loss(positions))
        alerts.extend(self.check_single_stock_weight(positions))
        alerts.extend(self.check_sector_concentration(positions))
        alerts.extend(self.check_drawdown(snapshots))
        alerts.extend(self.check_st_stocks(positions))
        alerts.extend(self.check_cash_ratio(snapshots))
        alerts.extend(self.check_turnover())
        alerts.extend(self.check_volatility(snapshots))

        report.alerts = alerts
        report.risk_score = self._calculate_risk_score(alerts)

        return report

    def check_single_stock_loss(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> List[RiskAlert]:
        """检查个股亏损

        Args:
            positions: 持仓列表

        Returns:
            风险预警列表
        """
        alerts = []

        if positions is None:
            positions = self._get_current_positions()

        for p in positions:
            if p.pnl_pct <= self.thresholds['single_stock_loss_critical']:
                alerts.append(RiskAlert(
                    level="critical",
                    category="single_stock_loss",
                    message=f"个股严重亏损: {p.name} ({p.code}) 亏损 {abs(p.pnl_pct)*100:.1f}%",
                    code=p.code,
                    value=p.pnl_pct,
                    threshold=self.thresholds['single_stock_loss_critical']
                ))
            elif p.pnl_pct <= self.thresholds['single_stock_loss_warning']:
                alerts.append(RiskAlert(
                    level="warning",
                    category="single_stock_loss",
                    message=f"个股亏损超15%: {p.name} ({p.code}) 亏损 {abs(p.pnl_pct)*100:.1f}%",
                    code=p.code,
                    value=p.pnl_pct,
                    threshold=self.thresholds['single_stock_loss_warning']
                ))

        return alerts

    def check_single_stock_weight(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> List[RiskAlert]:
        """检查个股权重集中

        Args:
            positions: 持仓列表

        Returns:
            风险预警列表
        """
        alerts = []

        if positions is None:
            positions = self._get_current_positions()

        for p in positions:
            if p.weight >= self.thresholds['single_stock_weight_critical']:
                alerts.append(RiskAlert(
                    level="critical",
                    category="concentration",
                    message=f"个股权重过高: {p.name} ({p.code}) 占比 {p.weight*100:.1f}%",
                    code=p.code,
                    value=p.weight,
                    threshold=self.thresholds['single_stock_weight_critical']
                ))
            elif p.weight >= self.thresholds['single_stock_weight_warning']:
                alerts.append(RiskAlert(
                    level="warning",
                    category="concentration",
                    message=f"个股权重偏高: {p.name} ({p.code}) 占比 {p.weight*100:.1f}%",
                    code=p.code,
                    value=p.weight,
                    threshold=self.thresholds['single_stock_weight_warning']
                ))

        return alerts

    def check_sector_concentration(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> List[RiskAlert]:
        """检查行业集中度

        Args:
            positions: 持仓列表

        Returns:
            风险预警列表
        """
        alerts = []

        if positions is None:
            positions = self._get_current_positions()

        if not positions:
            return alerts

        # 计算行业分布
        sector_weights: Dict[str, float] = {}
        for p in positions:
            sector = p.sector or "未知"
            sector_weights[sector] = sector_weights.get(sector, 0) + p.weight

        for sector, weight in sector_weights.items():
            if weight >= self.thresholds['sector_concentration_critical']:
                alerts.append(RiskAlert(
                    level="critical",
                    category="sector_concentration",
                    message=f"行业过度集中: {sector} 占比 {weight*100:.1f}%",
                    value=weight,
                    threshold=self.thresholds['sector_concentration_critical']
                ))
            elif weight >= self.thresholds['sector_concentration_warning']:
                alerts.append(RiskAlert(
                    level="warning",
                    category="sector_concentration",
                    message=f"行业集中度偏高: {sector} 占比 {weight*100:.1f}%",
                    value=weight,
                    threshold=self.thresholds['sector_concentration_warning']
                ))

        return alerts

    def check_drawdown(
        self,
        snapshots: Optional[List[PortfolioSnapshot]] = None
    ) -> List[RiskAlert]:
        """检查回撤

        Args:
            snapshots: 净值快照列表

        Returns:
            风险预警列表
        """
        alerts = []

        if snapshots is None:
            end_date = date.today()
            start_date = end_date - pd.Timedelta(days=90)
            snapshots = self.repo.get_snapshots(start_date, end_date)

        if len(snapshots) < 2:
            return alerts

        nav_values = [float(s.net_value) for s in snapshots if s.net_value]
        if not nav_values:
            return alerts

        # 计算最大回撤
        peak = nav_values[0]
        max_dd = 0
        current_dd = 0

        for nav in nav_values:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak
            max_dd = max(max_dd, dd)

        # 当前回撤
        if nav_values:
            current_dd = (peak - nav_values[-1]) / peak

        if max_dd >= abs(self.thresholds['drawdown_critical']):
            alerts.append(RiskAlert(
                level="critical",
                category="drawdown",
                message=f"最大回撤超过20%: {max_dd*100:.1f}%",
                value=-max_dd,
                threshold=self.thresholds['drawdown_critical']
            ))
        elif max_dd >= abs(self.thresholds['drawdown_warning']):
            alerts.append(RiskAlert(
                level="warning",
                category="drawdown",
                message=f"最大回撤超过10%: {max_dd*100:.1f}%",
                value=-max_dd,
                threshold=self.thresholds['drawdown_warning']
            ))

        return alerts

    def check_st_stocks(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> List[RiskAlert]:
        """检查ST股票

        Args:
            positions: 持仓列表

        Returns:
            风险预警列表
        """
        alerts = []

        if positions is None:
            positions = self._get_current_positions()

        if not positions:
            return alerts

        try:
            st_stocks = self._get_st_stocks(datetime.now())

            for p in positions:
                if p.code in st_stocks:
                    alerts.append(RiskAlert(
                        level="critical",
                        category="st_stock",
                        message=f"持有ST股票: {p.name} ({p.code})",
                        code=p.code
                    ))
        except Exception as e:
            logger.warning(f"ST股票检查失败: {e}")

        return alerts

    def check_cash_ratio(
        self,
        snapshots: Optional[List[PortfolioSnapshot]] = None
    ) -> List[RiskAlert]:
        """检查现金比例

        Args:
            snapshots: 净值快照列表

        Returns:
            风险预警列表
        """
        alerts = []

        latest = None
        if snapshots:
            latest = snapshots[-1]
        else:
            latest = self.repo.get_latest_snapshot()

        if not latest or not latest.total_asset:
            return alerts

        cash = float(latest.cash) if latest.cash else 0
        total = float(latest.total_asset)
        cash_ratio = cash / total if total > 0 else 0

        if cash_ratio < self.thresholds['cash_ratio_warning']:
            alerts.append(RiskAlert(
                level="warning",
                category="cash_ratio",
                message=f"现金比例过低: {cash_ratio*100:.1f}%",
                value=cash_ratio,
                threshold=self.thresholds['cash_ratio_warning']
            ))

        return alerts

    def check_turnover(self, days: int = 30) -> List[RiskAlert]:
        """检查换手率

        Args:
            days: 检查周期

        Returns:
            风险预警列表
        """
        alerts = []

        try:
            end_date = date.today()
            start_date = end_date - pd.Timedelta(days=days * 2)

            transactions = self.repo.get_transactions(start_date, end_date)

            if not transactions:
                return alerts

            # 计算期间总交易金额
            total_amount = sum(
                float(t.amount) for t in transactions if t.amount
            )

            # 获取期间平均资产
            snapshots = self.repo.get_snapshots(start_date, end_date)
            if not snapshots:
                return alerts

            avg_asset = sum(
                float(s.total_asset) for s in snapshots if s.total_asset
            ) / len(snapshots)

            if avg_asset > 0:
                turnover = total_amount / avg_asset

                if turnover > self.thresholds['turnover_warning']:
                    alerts.append(RiskAlert(
                        level="warning",
                        category="turnover",
                        message=f"换手率过高: {turnover*100:.0f}% (近{days}日)",
                        value=turnover,
                        threshold=self.thresholds['turnover_warning']
                    ))

        except Exception as e:
            logger.warning(f"换手率检查失败: {e}")

        return alerts

    def check_volatility(
        self,
        snapshots: Optional[List[PortfolioSnapshot]] = None
    ) -> List[RiskAlert]:
        """检查波动率

        Args:
            snapshots: 净值快照列表

        Returns:
            风险预警列表
        """
        alerts = []

        if snapshots is None:
            end_date = date.today()
            start_date = end_date - pd.Timedelta(days=60)
            snapshots = self.repo.get_snapshots(start_date, end_date)

        if len(snapshots) < 20:
            return alerts

        nav_values = [float(s.net_value) for s in snapshots if s.net_value]
        if len(nav_values) < 20:
            return alerts

        # 计算日收益率
        returns = pd.Series(nav_values).pct_change().dropna()

        if len(returns) < 10:
            return alerts

        # 年化波动率
        volatility = returns.std() * np.sqrt(252)

        if volatility > self.thresholds['volatility_warning']:
            alerts.append(RiskAlert(
                level="warning",
                category="volatility",
                message=f"波动率过高: {volatility*100:.1f}%",
                value=volatility,
                threshold=self.thresholds['volatility_warning']
            ))

        return alerts

    def check_limit_up_down(
        self,
        positions: Optional[List[PositionPnl]] = None,
        target_date: Optional[date] = None
    ) -> List[RiskAlert]:
        """检查涨跌停股票

        Args:
            positions: 持仓列表
            target_date: 检查日期

        Returns:
            风险预警列表
        """
        alerts = []

        if positions is None:
            positions = self._get_current_positions()

        if not positions:
            return alerts

        if target_date is None:
            target_date = date.today()

        try:
            codes = [p.code for p in positions]
            limit_info = self._get_limit_info(codes, target_date)

            for p in positions:
                info = limit_info.get(p.code, {})
                if info.get('is_limit_up'):
                    alerts.append(RiskAlert(
                        level="info",
                        category="limit_up",
                        message=f"涨停: {p.name} ({p.code})",
                        code=p.code
                    ))
                elif info.get('is_limit_down'):
                    alerts.append(RiskAlert(
                        level="warning",
                        category="limit_down",
                        message=f"跌停: {p.name} ({p.code})",
                        code=p.code
                    ))

        except Exception as e:
            logger.warning(f"涨跌停检查失败: {e}")

        return alerts

    # ========== Private Methods ==========

    def _get_current_positions(self) -> List[PositionPnl]:
        """获取当前持仓"""
        from projects.portfolio_analysis.core.analyzer import PortfolioAnalyzer

        analyzer = PortfolioAnalyzer()
        return analyzer.get_current_positions_with_price()

    def _get_st_stocks(self, target_date: datetime) -> set:
        """获取ST股票列表"""
        date_str = target_date.strftime('%Y%m%d')
        sql = """
            SELECT ts_code
            FROM t_stock_st_list
            WHERE start_date <= %s
              AND (end_date >= %s OR end_date IS NULL OR end_date = '')
        """
        results = DatabaseManager.fetchall("tushare_biz", sql, (date_str, date_str))
        return set(r['ts_code'] for r in results)

    def _get_limit_info(
        self,
        codes: List[str],
        target_date: date
    ) -> Dict[str, Dict[str, bool]]:
        """获取涨跌停信息"""
        info = {}
        try:
            date_str = target_date.strftime('%Y%m%d')
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, close, pre_close, pct_chg
                FROM t_stock_dailymarketdata
                WHERE ts_code IN ({placeholders})
                  AND trade_date = %s
            """
            params = codes + [date_str]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            for r in results:
                pct_chg = float(r['pct_chg']) if r['pct_chg'] else 0
                info[r['ts_code']] = {
                    'is_limit_up': pct_chg >= 9.9,
                    'is_limit_down': pct_chg <= -9.9,
                    'pct_chg': pct_chg,
                }

        except Exception as e:
            logger.error(f"获取涨跌停信息失败: {e}")

        return info

    def _calculate_risk_score(self, alerts: List[RiskAlert]) -> float:
        """计算风险分数 (0-100)"""
        if not alerts:
            return 0.0

        critical_count = len([a for a in alerts if a.level == "critical"])
        warning_count = len([a for a in alerts if a.level == "warning"])
        info_count = len([a for a in alerts if a.level == "info"])

        score = critical_count * 30 + warning_count * 10 + info_count * 2
        return min(100, score)


if __name__ == "__main__":
    # 测试风险诊断器
    logging.basicConfig(level=logging.INFO)

    diagnostic = RiskDiagnostic()

    print("\n" + "=" * 60)
    print("风险诊断报告")
    print("=" * 60)

    report = diagnostic.check_all()

    print(f"\n风险分数: {report.risk_score}/100")
    print(f"预警数量: {len(report.alerts)} 条")

    if report.alerts:
        print("\n详细预警:")
        for alert in report.alerts:
            emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert.level, "⚪")
            print(f"  {emoji} [{alert.level.upper()}] {alert.category}: {alert.message}")
    else:
        print("\n✅ 未发现明显风险")
