"""
持仓分析器

将真实持仓数据转换为回测引擎格式，并调用MetricsCalculator计算绩效指标。

Example:
    >>> from projects.portfolio_analysis import PortfolioAnalyzer
    >>> analyzer = PortfolioAnalyzer()
    >>> result = analyzer.analyze(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
    >>> print(result.metrics.sharpe_ratio)
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any
import logging

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.metrics import (
    MetricsCalculator, PerformanceMetrics
)
from projects.portfolio_analysis.database.models import (
    Position, PortfolioSnapshot, PositionHistory
)
from projects.portfolio_analysis.database.repository import PositionRepository
from core.data_access.tushare.client import TushareClient
from core.storage.relational.connection import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class PositionPnl:
    """个股盈亏信息"""
    code: str
    name: str
    volume: int
    cost: float
    cost_price: float
    market_value: float
    current_price: float
    pnl: float
    pnl_pct: float
    weight: float = 0.0
    sector: str = ""


@dataclass
class PortfolioStructure:
    """持仓结构分析结果"""
    sector_distribution: Dict[str, float] = field(default_factory=dict)
    market_cap_distribution: Dict[str, float] = field(default_factory=dict)
    top_holdings: List[PositionPnl] = field(default_factory=list)
    concentration_hhi: float = 0.0
    top3_weight: float = 0.0
    top10_weight: float = 0.0
    position_count: int = 0
    cash_ratio: float = 0.0


@dataclass
class RiskAlert:
    """风险预警"""
    level: str  # warning, critical
    category: str  # drawdown, concentration, single_stock, sector, st
    message: str
    code: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class RiskReport:
    """风险报告"""
    alerts: List[RiskAlert] = field(default_factory=list)
    risk_score: float = 0.0  # 0-100，越高风险越大

    @property
    def has_critical(self) -> bool:
        """是否有严重风险"""
        return any(a.level == "critical" for a in self.alerts)

    @property
    def warning_count(self) -> int:
        """预警数量"""
        return len([a for a in self.alerts if a.level == "warning"])


@dataclass
class PortfolioAnalysisResult:
    """持仓分析结果"""
    # 绩效指标（直接复用现有PerformanceMetrics）
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    # 持仓结构
    structure: PortfolioStructure = field(default_factory=PortfolioStructure)

    # 风险报告
    risks: RiskReport = field(default_factory=RiskReport)

    # 快照数据
    snapshots: List[PortfolioSnapshot] = field(default_factory=list)

    # 持仓明细
    positions: List[PositionPnl] = field(default_factory=list)

    # 日期范围
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'metrics': self.metrics.to_dict() if self.metrics else {},
            'structure': {
                'sector_distribution': self.structure.sector_distribution,
                'market_cap_distribution': self.structure.market_cap_distribution,
                'concentration_hhi': self.structure.concentration_hhi,
                'top3_weight': self.structure.top3_weight,
                'top10_weight': self.structure.top10_weight,
                'position_count': self.structure.position_count,
                'cash_ratio': self.structure.cash_ratio,
            },
            'risks': {
                'alerts': [
                    {
                        'level': a.level,
                        'category': a.category,
                        'message': a.message,
                        'code': a.code,
                        'value': a.value,
                        'threshold': a.threshold,
                    }
                    for a in self.risks.alerts
                ],
                'risk_score': self.risks.risk_score,
                'has_critical': self.risks.has_critical,
            },
            'positions': [
                {
                    'code': p.code,
                    'name': p.name,
                    'volume': p.volume,
                    'cost': p.cost,
                    'market_value': p.market_value,
                    'pnl': p.pnl,
                    'pnl_pct': p.pnl_pct,
                    'weight': p.weight,
                    'sector': p.sector,
                }
                for p in self.positions
            ],
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
        }


class PortfolioAnalyzer:
    """真实持仓分析器

    将SQLAlchemy持仓数据转换为MetricsCalculator所需格式，
    计算完整的绩效指标、持仓结构和风险诊断。

    Attributes:
        metrics_calc: 绩效指标计算器（复用现有）
        ts_client: Tushare数据客户端
        repo: 数据仓库
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        benchmark_code: str = "000300.SH"
    ):
        """初始化分析器

        Args:
            risk_free_rate: 无风险利率
            benchmark_code: 基准指数代码，默认沪深300
        """
        self.metrics_calc = MetricsCalculator(risk_free_rate=risk_free_rate)
        self.ts_client = TushareClient()
        self.repo = PositionRepository()
        self.benchmark_code = benchmark_code

        logger.info(f"PortfolioAnalyzer initialized: rf={risk_free_rate}, benchmark={benchmark_code}")

    def analyze(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        with_current_positions: bool = True
    ) -> PortfolioAnalysisResult:
        """分析持仓表现

        Args:
            start_date: 开始日期，默认使用最早快照日期
            end_date: 结束日期，默认今天
            with_current_positions: 是否分析当前持仓

        Returns:
            完整的分析结果
        """
        # 默认日期
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            # 尝试获取最早快照日期
            earliest = self._get_earliest_snapshot_date()
            if earliest:
                start_date = earliest
            else:
                start_date = end_date - pd.Timedelta(days=30)

        logger.info(f"Analyzing portfolio: {start_date} ~ {end_date}")

        result = PortfolioAnalysisResult(
            start_date=start_date,
            end_date=end_date
        )

        # 1. 获取净值快照
        snapshots = self.repo.get_snapshots(start_date, end_date)
        if not snapshots:
            logger.warning("No portfolio snapshots found for the period")
            return result

        result.snapshots = snapshots

        # 2. 转换为MetricsCalculator格式并计算指标
        nav_history = self._convert_snapshots_to_nav(snapshots)
        benchmark_nav = self._get_benchmark_data(start_date, end_date)

        # 获取交易记录用于计算交易指标
        trades_df = self._get_trades_df(start_date, end_date)

        result.metrics = self.metrics_calc.calculate(nav_history, benchmark_nav, trades_df)

        # 3. 分析当前持仓结构
        if with_current_positions:
            result.positions = self._analyze_current_positions(snapshots[-1] if snapshots else None)
            result.structure = self._analyze_structure(result.positions, snapshots[-1] if snapshots else None)

        # 4. 风险诊断
        result.risks = self._diagnose_risks(result.positions, snapshots)

        logger.info(
            f"Analysis completed: return={result.metrics.total_return*100:.2f}%, "
            f"sharpe={result.metrics.sharpe_ratio:.2f}, "
            f"alerts={len(result.risks.alerts)}"
        )

        return result

    def calculate_position_pnl(
        self,
        position: Position,
        current_price: float
    ) -> PositionPnl:
        """计算个股盈亏

        Args:
            position: 持仓对象
            current_price: 当前价格

        Returns:
            个股盈亏信息
        """
        cost = float(position.cost_price) * float(position.volume) if position.cost_price else 0
        market_value = current_price * float(position.volume)
        pnl = market_value - cost
        pnl_pct = (current_price / float(position.cost_price) - 1) if position.cost_price and position.cost_price > 0 else 0

        return PositionPnl(
            code=position.code,
            name=position.name or "",
            volume=position.volume,
            cost=cost,
            cost_price=float(position.cost_price) if position.cost_price else 0,
            market_value=market_value,
            current_price=current_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            sector=position.sector or ""
        )

    def get_current_positions_with_price(self) -> List[PositionPnl]:
        """获取当前持仓（带最新价格）

        Returns:
            持仓列表（含最新盈亏）
        """
        positions = self.repo.get_all_positions()
        if not positions:
            return []

        # 获取最新价格
        codes = [p.code for p in positions]
        prices = self._get_current_prices(codes)

        result = []
        for pos in positions:
            price = prices.get(pos.code, 0)
            pnl = self.calculate_position_pnl(pos, price)

            # 计算权重（需要总资产）
            latest_snapshot = self.repo.get_latest_snapshot()
            if latest_snapshot and latest_snapshot.total_asset:
                pnl.weight = pnl.market_value / float(latest_snapshot.total_asset)

            result.append(pnl)

        # 按权重排序
        result.sort(key=lambda x: x.weight, reverse=True)
        return result

    def get_daily_returns_df(self, start_date: date, end_date: date) -> pd.DataFrame:
        """获取日收益率DataFrame

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含日收益率的DataFrame
        """
        snapshots = self.repo.get_snapshots(start_date, end_date)
        if not snapshots:
            return pd.DataFrame()

        nav_data = self._convert_snapshots_to_nav(snapshots)
        df = pd.DataFrame(nav_data, columns=['date', 'nav'])
        df['daily_return'] = df['nav'].pct_change()
        return df

    # ========== Private Methods ==========

    def _convert_snapshots_to_nav(
        self,
        snapshots: List[PortfolioSnapshot]
    ) -> List[Tuple[datetime, float]]:
        """将快照转换为净值历史"""
        return [
            (datetime.combine(s.date, datetime.min.time()), float(s.net_value))
            for s in snapshots
            if s.net_value is not None
        ]

    def _get_benchmark_data(
        self,
        start_date: date,
        end_date: date
    ) -> Optional[List[Tuple[datetime, float]]]:
        """获取基准数据"""
        try:
            # 从数据库获取指数数据
            sql = """
                SELECT trade_date, close
                FROM t_index_dailymarketdata
                WHERE ts_code = %s
                  AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date ASC
            """
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')

            results = DatabaseManager.fetchall(
                "tushare_biz", sql, (self.benchmark_code, start_str, end_str)
            )

            if not results:
                return None

            # 计算净值（首日归一化为1）
            base_price = float(results[0]['close'])
            return [
                (datetime.strptime(r['trade_date'], '%Y%m%d'), float(r['close']) / base_price)
                for r in results
            ]

        except Exception as e:
            logger.error(f"获取基准数据失败: {e}")
            return None

    def _get_trades_df(self, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
        """获取交易记录DataFrame"""
        try:
            transactions = self.repo.get_transactions(start_date, end_date)
            if not transactions:
                return None

            records = []
            for t in transactions:
                records.append({
                    'date': datetime.combine(t.trade_date, datetime.min.time()),
                    'ts_code': t.code,
                    'side': t.trade_type,
                    'quantity': t.volume,
                    'price': float(t.price) if t.price else 0,
                    'amount': float(t.amount) if t.amount else 0,
                    'commission': float(t.fee) if t.fee else 0,
                })

            return pd.DataFrame(records)
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return None

    def _analyze_current_positions(
        self,
        latest_snapshot: Optional[PortfolioSnapshot]
    ) -> List[PositionPnl]:
        """分析当前持仓"""
        positions = self.get_current_positions_with_price()

        # 更新权重
        if latest_snapshot and latest_snapshot.total_asset:
            total_value = float(latest_snapshot.total_asset)
            for p in positions:
                p.weight = p.market_value / total_value if total_value > 0 else 0

        return positions

    def _analyze_structure(
        self,
        positions: List[PositionPnl],
        latest_snapshot: Optional[PortfolioSnapshot]
    ) -> PortfolioStructure:
        """分析持仓结构"""
        structure = PortfolioStructure()

        if not positions:
            return structure

        # 行业分布
        sector_amounts: Dict[str, float] = {}
        for p in positions:
            sector = p.sector or "未知"
            sector_amounts[sector] = sector_amounts.get(sector, 0) + p.market_value

        total_value = sum(sector_amounts.values())
        if total_value > 0:
            structure.sector_distribution = {
                k: v / total_value for k, v in sector_amounts.items()
            }

        # 集中度分析
        weights = [p.weight for p in positions]
        structure.concentration_hhi = sum(w ** 2 for w in weights) if weights else 0

        # Top持仓占比
        sorted_weights = sorted(weights, reverse=True)
        structure.top3_weight = sum(sorted_weights[:3])
        structure.top10_weight = sum(sorted_weights[:10])

        # Top持仓列表
        structure.top_holdings = positions[:10]

        # 持仓数量
        structure.position_count = len(positions)

        # 现金比例
        if latest_snapshot and latest_snapshot.total_asset:
            cash = float(latest_snapshot.cash) if latest_snapshot.cash else 0
            total = float(latest_snapshot.total_asset)
            structure.cash_ratio = cash / total if total > 0 else 0

        return structure

    def _diagnose_risks(
        self,
        positions: List[PositionPnl],
        snapshots: List[PortfolioSnapshot]
    ) -> RiskReport:
        """风险诊断"""
        report = RiskReport()
        alerts = []

        # 阈值配置
        THRESHOLDS = {
            'single_stock_loss': -0.15,
            'sector_concentration': 0.30,
            'drawdown_warning': -0.10,
            'drawdown_critical': -0.20,
            'single_stock_weight': 0.20,
        }

        # 1. 检查个股亏损
        for p in positions:
            if p.pnl_pct < THRESHOLDS['single_stock_loss']:
                alerts.append(RiskAlert(
                    level="warning",
                    category="single_stock",
                    message=f"个股亏损超15%: {p.name} ({p.code})",
                    code=p.code,
                    value=p.pnl_pct,
                    threshold=THRESHOLDS['single_stock_loss']
                ))

            # 检查个股权重
            if p.weight > THRESHOLDS['single_stock_weight']:
                alerts.append(RiskAlert(
                    level="warning",
                    category="concentration",
                    message=f"个股权重过高: {p.name} ({p.code}) 占比{p.weight*100:.1f}%",
                    code=p.code,
                    value=p.weight,
                    threshold=THRESHOLDS['single_stock_weight']
                ))

        # 2. 检查行业集中度
        if positions:
            structure = self._analyze_structure(positions, snapshots[-1] if snapshots else None)
            for sector, weight in structure.sector_distribution.items():
                if weight > THRESHOLDS['sector_concentration']:
                    alerts.append(RiskAlert(
                        level="warning",
                        category="sector",
                        message=f"行业集中度过高: {sector} 占比{weight*100:.1f}%",
                        value=weight,
                        threshold=THRESHOLDS['sector_concentration']
                    ))

        # 3. 检查回撤
        if len(snapshots) >= 2:
            nav_values = [float(s.net_value) for s in snapshots if s.net_value]
            if nav_values:
                peak = nav_values[0]
                max_dd = 0
                for nav in nav_values:
                    if nav > peak:
                        peak = nav
                    dd = (peak - nav) / peak
                    max_dd = max(max_dd, dd)

                if max_dd > abs(THRESHOLDS['drawdown_critical']):
                    alerts.append(RiskAlert(
                        level="critical",
                        category="drawdown",
                        message=f"最大回撤超过20%: {max_dd*100:.1f}%",
                        value=-max_dd,
                        threshold=THRESHOLDS['drawdown_critical']
                    ))
                elif max_dd > abs(THRESHOLDS['drawdown_warning']):
                    alerts.append(RiskAlert(
                        level="warning",
                        category="drawdown",
                        message=f"最大回撤超过10%: {max_dd*100:.1f}%",
                        value=-max_dd,
                        threshold=THRESHOLDS['drawdown_warning']
                    ))

        # 4. 检查ST股票
        try:
            latest_date = datetime.now()
            st_stocks = self._get_st_stocks(latest_date)
            for p in positions:
                if p.code in st_stocks:
                    alerts.append(RiskAlert(
                        level="critical",
                        category="st",
                        message=f"持有ST股票: {p.name} ({p.code})",
                        code=p.code
                    ))
        except Exception as e:
            logger.warning(f"ST股票检查失败: {e}")

        report.alerts = alerts

        # 计算风险分数 (0-100)
        if alerts:
            critical_count = len([a for a in alerts if a.level == "critical"])
            warning_count = len([a for a in alerts if a.level == "warning"])
            report.risk_score = min(100, critical_count * 30 + warning_count * 10)

        return report

    def _get_current_prices(self, codes: List[str]) -> Dict[str, float]:
        """获取当前价格（使用最新可用交易日数据）"""
        prices = {}
        try:
            # 获取最新交易日
            latest_date_result = DatabaseManager.fetchone(
                "tushare_biz",
                "SELECT MAX(trade_date) as max_date FROM t_stock_dailymarketdata"
            )
            latest_date = latest_date_result['max_date'] if latest_date_result else None

            if not latest_date:
                logger.warning("No trade date found in market data")
                return prices

            # 从数据库获取最新行情
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, close
                FROM t_stock_dailymarketdata
                WHERE ts_code IN ({placeholders})
                  AND trade_date = %s
            """
            params = codes + [latest_date]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            for r in results:
                prices[r['ts_code']] = float(r['close'])

            # 记录缺失的股票
            missing_codes = [c for c in codes if c not in prices]
            if missing_codes:
                logger.debug(f"Missing prices for {len(missing_codes)} stocks: {missing_codes[:5]}...")

        except Exception as e:
            logger.error(f"获取价格失败: {e}")

        return prices

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

    def _get_earliest_snapshot_date(self) -> Optional[date]:
        """获取最早快照日期"""
        try:
            sql = "SELECT MIN(date) as min_date FROM portfolio_snapshots"
            result = DatabaseManager.fetchone("interface", sql)
            if result and result.get('min_date'):
                if isinstance(result['min_date'], str):
                    return datetime.strptime(result['min_date'], '%Y-%m-%d').date()
                return result['min_date']
        except Exception as e:
            logger.error(f"获取最早快照日期失败: {e}")
        return None


if __name__ == "__main__":
    # 测试分析器
    logging.basicConfig(level=logging.INFO)

    analyzer = PortfolioAnalyzer()

    # 测试分析
    try:
        result = analyzer.analyze()
        print("\n" + "=" * 60)
        print("持仓分析结果")
        print("=" * 60)
        print(result.metrics)
        print(f"\n持仓数量: {result.structure.position_count}")
        print(f"风险预警: {len(result.risks.alerts)} 条")
        for alert in result.risks.alerts:
            print(f"  [{alert.level}] {alert.message}")
    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
