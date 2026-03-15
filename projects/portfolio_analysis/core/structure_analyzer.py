"""
持仓结构分析器

提供行业分布、市值风格、集中度等分析功能。

Example:
    >>> from projects.portfolio_analysis import StructureAnalyzer
    >>> analyzer = StructureAnalyzer()
    >>> sector_dist = analyzer.analyze_sector_distribution()
    >>> concentration = analyzer.calculate_concentration()
"""

from datetime import date
from typing import Dict, List, Optional, Tuple
import logging

import pandas as pd
import numpy as np

from projects.portfolio_analysis.database.models import Position, PositionHistory
from projects.portfolio_analysis.database.repository import PositionRepository
from projects.portfolio_analysis.core.analyzer import PositionPnl
from core.data_access.tushare.client import TushareClient
from core.storage.relational.connection import DatabaseManager

logger = logging.getLogger(__name__)


class StructureAnalyzer:
    """持仓结构分析器

    分析持仓的行业分布、市值风格、集中度等指标。
    """

    # 市值风格分类阈值（亿元）
    MARKET_CAP_THRESHOLDS = {
        'large': 500,    # 大盘股: > 500亿
        'mid': 100,      # 中盘股: 100-500亿
        'small': 0,      # 小盘股: < 100亿
    }

    def __init__(self):
        """初始化分析器"""
        self.repo = PositionRepository()
        self.ts_client = TushareClient()

    def analyze_sector_distribution(
        self,
        date: Optional[date] = None
    ) -> pd.DataFrame:
        """行业分布分析

        Args:
            date: 分析日期，默认当前持仓

        Returns:
            行业分布DataFrame，包含金额和占比
        """
        if date is None:
            # 分析当前持仓
            positions = self.repo.get_all_positions()
        else:
            # 分析历史持仓
            positions = self.repo.get_position_history_by_date(date)

        if not positions:
            return pd.DataFrame()

        # 获取最新价格计算市值
        if date is None:
            codes = [p.code for p in positions]
            prices = self._get_current_prices(codes)

            sector_data = []
            for pos in positions:
                price = prices.get(pos.code, float(pos.cost_price) if pos.cost_price else 0)
                market_value = float(pos.volume) * price
                sector = pos.sector or "未知"
                sector_data.append({
                    'sector': sector,
                    'code': pos.code,
                    'market_value': market_value,
                })
        else:
            # 历史持仓已有市值数据
            sector_data = [
                {
                    'sector': p.sector or "未知",
                    'code': p.code,
                    'market_value': float(p.market_value) if p.market_value else 0,
                }
                for p in positions
            ]

        df = pd.DataFrame(sector_data)
        if df.empty:
            return pd.DataFrame()

        # 按行业汇总
        sector_summary = df.groupby('sector')['market_value'].agg([
            ('amount', 'sum'),
            ('count', 'count')
        ]).reset_index()

        total_value = sector_summary['amount'].sum()
        sector_summary['weight'] = sector_summary['amount'] / total_value if total_value > 0 else 0
        sector_summary = sector_summary.sort_values('weight', ascending=False)

        return sector_summary

    def analyze_market_cap_style(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> Dict[str, float]:
        """市值风格分析（大盘/中盘/小盘）

        Args:
            positions: 持仓列表，默认查询当前持仓

        Returns:
            市值风格分布字典
        """
        if positions is None:
            positions = self._get_current_positions_with_pnl()

        if not positions:
            return {'large': 0, 'mid': 0, 'small': 0}

        # 获取市值数据
        codes = [p.code for p in positions]
        market_caps = self._get_market_caps(codes)

        # 分类统计
        style_amounts = {'large': 0, 'mid': 0, 'small': 0}

        for p in positions:
            market_cap = market_caps.get(p.code, 0)  # 亿元
            style = self._classify_market_cap(market_cap)
            style_amounts[style] += p.market_value

        total = sum(style_amounts.values())
        if total > 0:
            return {k: v / total for k, v in style_amounts.items()}
        return style_amounts

    def calculate_concentration(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> Dict[str, float]:
        """集中度分析

        Args:
            positions: 持仓列表，默认查询当前持仓

        Returns:
            集中度指标字典，包含：
            - hhi: 赫芬达尔指数
            - top1_weight: 最大持仓占比
            - top3_weight: 前3大持仓占比
            - top5_weight: 前5大持仓占比
            - top10_weight: 前10大持仓占比
        """
        if positions is None:
            positions = self._get_current_positions_with_pnl()

        if not positions:
            return {
                'hhi': 0.0,
                'top1_weight': 0.0,
                'top3_weight': 0.0,
                'top5_weight': 0.0,
                'top10_weight': 0.0,
            }

        weights = [p.weight for p in positions]
        sorted_weights = sorted(weights, reverse=True)

        # HHI指数（赫芬达尔指数）= sum(w^2)
        hhi = sum(w ** 2 for w in weights)

        return {
            'hhi': hhi,
            'top1_weight': sum(sorted_weights[:1]),
            'top3_weight': sum(sorted_weights[:3]),
            'top5_weight': sum(sorted_weights[:5]),
            'top10_weight': sum(sorted_weights[:10]),
        }

    def calculate_turnover(
        self,
        days: int = 30
    ) -> Dict[str, float]:
        """换手率计算

        Args:
            days: 计算周期（交易日）

        Returns:
            换手率指标字典
        """
        end_date = date.today()
        start_date = end_date - pd.Timedelta(days=days * 1.5)  # 留一些余量

        # 获取交易记录
        transactions = self.repo.get_transactions(start_date, end_date)

        if not transactions:
            return {
                'turnover_rate': 0.0,
                'buy_amount': 0.0,
                'sell_amount': 0.0,
                'total_amount': 0.0,
            }

        buy_amount = sum(
            float(t.amount) for t in transactions if t.trade_type == 'buy'
        )
        sell_amount = sum(
            float(t.amount) for t in transactions if t.trade_type == 'sell'
        )

        # 获取期间平均资产
        snapshots = self.repo.get_snapshots(start_date, end_date)
        if snapshots:
            avg_asset = sum(
                float(s.total_asset) for s in snapshots if s.total_asset
            ) / len(snapshots)
        else:
            avg_asset = 0

        # 换手率 = (买入金额 + 卖出金额) / (2 * 平均资产)
        turnover_rate = 0
        if avg_asset > 0:
            turnover_rate = (buy_amount + sell_amount) / (2 * avg_asset)

        return {
            'turnover_rate': turnover_rate,
            'buy_amount': buy_amount,
            'sell_amount': sell_amount,
            'total_amount': buy_amount + sell_amount,
            'avg_asset': avg_asset,
        }

    def analyze_style_exposure(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> Dict[str, float]:
        """风格暴露分析

        分析持仓在以下维度的暴露：
        - 价值/成长
        - 大盘/小盘
        - 动量/反转

        Args:
            positions: 持仓列表

        Returns:
            风格暴露字典
        """
        if positions is None:
            positions = self._get_current_positions_with_pnl()

        if not positions:
            return {}

        codes = [p.code for p in positions]

        # 获取估值数据
        valuations = self._get_valuation_data(codes)

        # 计算加权平均估值
        total_value = sum(p.market_value for p in positions)

        if total_value == 0:
            return {}

        weighted_pe = 0
        weighted_pb = 0

        for p in positions:
            weight = p.market_value / total_value
            val = valuations.get(p.code, {})
            weighted_pe += weight * val.get('pe', 0)
            weighted_pb += weight * val.get('pb', 0)

        # 简单的价值/成长判断
        # PE < 20: 偏价值，PE > 40: 偏成长
        value_score = 0.5
        if weighted_pe > 0:
            if weighted_pe < 20:
                value_score = 0.2  # 偏价值
            elif weighted_pe > 40:
                value_score = 0.8  # 偏成长

        return {
            'pe': weighted_pe,
            'pb': weighted_pb,
            'value_score': value_score,  # 0-1，越低越价值，越高越成长
        }

    def analyze_geographic_distribution(
        self,
        positions: Optional[List[PositionPnl]] = None
    ) -> Dict[str, float]:
        """地域分布分析

        Args:
            positions: 持仓列表

        Returns:
            地域分布字典
        """
        if positions is None:
            positions = self._get_current_positions_with_pnl()

        if not positions:
            return {}

        # 从股票代码判断交易所
        exchange_amounts = {'SH': 0, 'SZ': 0, 'BJ': 0}

        for p in positions:
            if '.SH' in p.code:
                exchange_amounts['SH'] += p.market_value
            elif '.SZ' in p.code:
                exchange_amounts['SZ'] += p.market_value
            elif '.BJ' in p.code:
                exchange_amounts['BJ'] += p.market_value

        total = sum(exchange_amounts.values())
        if total > 0:
            return {k: v / total for k, v in exchange_amounts.items()}
        return exchange_amounts

    def get_position_history_analysis(
        self,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """持仓历史变化分析

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            持仓变化DataFrame
        """
        history = self.repo.get_position_history(start_date, end_date)

        if not history:
            return pd.DataFrame()

        records = []
        for h in history:
            records.append({
                'date': h.date,
                'code': h.code,
                'name': h.name,
                'volume': h.volume,
                'market_value': float(h.market_value) if h.market_value else 0,
                'weight': float(h.weight) if h.weight else 0,
                'pnl': float(h.pnl) if h.pnl else 0,
                'pnl_pct': float(h.pnl_pct) if h.pnl_pct else 0,
            })

        df = pd.DataFrame(records)
        return df

    # ========== Private Methods ==========

    def _get_current_positions_with_pnl(self) -> List[PositionPnl]:
        """获取当前持仓（带盈亏）"""
        from projects.portfolio_analysis.core.analyzer import PortfolioAnalyzer

        analyzer = PortfolioAnalyzer()
        return analyzer.get_current_positions_with_price()

    def _get_current_prices(self, codes: List[str]) -> Dict[str, float]:
        """获取当前价格"""
        prices = {}
        try:
            date_str = date.today().strftime('%Y%m%d')
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, close
                FROM t_stock_dailymarketdata
                WHERE ts_code IN ({placeholders})
                  AND trade_date <= %s
                ORDER BY trade_date DESC
            """
            params = codes + [date_str]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            # 取最新价格
            seen = set()
            for r in results:
                code = r['ts_code']
                if code not in seen:
                    prices[code] = float(r['close'])
                    seen.add(code)

        except Exception as e:
            logger.error(f"获取价格失败: {e}")

        return prices

    def _get_market_caps(self, codes: List[str]) -> Dict[str, float]:
        """获取股票市值（亿元）"""
        market_caps = {}
        try:
            date_str = date.today().strftime('%Y%m%d')
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, total_mv
                FROM t_stock_dailybasic
                WHERE ts_code IN ({placeholders})
                  AND trade_date = %s
            """
            params = codes + [date_str]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            for r in results:
                # total_mv 单位是万元，转换为亿元
                market_caps[r['ts_code']] = float(r['total_mv']) / 10000 if r['total_mv'] else 0

        except Exception as e:
            logger.error(f"获取市值数据失败: {e}")

        return market_caps

    def _classify_market_cap(self, market_cap: float) -> str:
        """根据市值分类"""
        if market_cap >= self.MARKET_CAP_THRESHOLDS['large']:
            return 'large'
        elif market_cap >= self.MARKET_CAP_THRESHOLDS['mid']:
            return 'mid'
        else:
            return 'small'

    def _get_valuation_data(self, codes: List[str]) -> Dict[str, Dict[str, float]]:
        """获取估值数据"""
        valuations = {}
        try:
            date_str = date.today().strftime('%Y%m%d')
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""
                SELECT ts_code, pe, pb
                FROM t_stock_dailybasic
                WHERE ts_code IN ({placeholders})
                  AND trade_date = %s
            """
            params = codes + [date_str]
            results = DatabaseManager.fetchall("tushare_biz", sql, tuple(params))

            for r in results:
                valuations[r['ts_code']] = {
                    'pe': float(r['pe']) if r['pe'] else 0,
                    'pb': float(r['pb']) if r['pb'] else 0,
                }

        except Exception as e:
            logger.error(f"获取估值数据失败: {e}")

        return valuations


if __name__ == "__main__":
    # 测试结构分析器
    logging.basicConfig(level=logging.INFO)

    analyzer = StructureAnalyzer()

    print("\n" + "=" * 60)
    print("持仓结构分析")
    print("=" * 60)

    # 行业分布
    sector_df = analyzer.analyze_sector_distribution()
    if not sector_df.empty:
        print("\n行业分布:")
        print(sector_df.to_string(index=False))

    # 市值风格
    market_cap = analyzer.analyze_market_cap_style()
    print(f"\n市值风格分布:")
    for style, weight in market_cap.items():
        style_name = {'large': '大盘', 'mid': '中盘', 'small': '小盘'}.get(style, style)
        print(f"  {style_name}: {weight*100:.1f}%")

    # 集中度
    concentration = analyzer.calculate_concentration()
    print(f"\n集中度分析:")
    print(f"  HHI指数: {concentration['hhi']:.4f}")
    print(f"  Top1占比: {concentration['top1_weight']*100:.1f}%")
    print(f"  Top3占比: {concentration['top3_weight']*100:.1f}%")
    print(f"  Top5占比: {concentration['top5_weight']*100:.1f}%")

    # 换手率
    turnover = analyzer.calculate_turnover(30)
    print(f"\n换手率分析（近30日）:")
    print(f"  换手率: {turnover['turnover_rate']*100:.1f}%")
    print(f"  买入金额: ¥{turnover['buy_amount']:,.0f}")
    print(f"  卖出金额: ¥{turnover['sell_amount']:,.0f}")
