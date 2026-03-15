"""
量化因子分析器
多因子模型评分
"""
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from projects.broker_gold_stock.data.models import QuantFactorScore, FactorScore
from projects.broker_gold_stock.data.repository import QuantFactorRepository
from core.data_access.tushare.client import TushareClient


class QuantFactorAnalyzer:
    """量化因子分析器 - 计算多因子评分"""

    def __init__(self):
        self.ts_client = TushareClient()

    def analyze(self, ts_code: str, trade_date: str = None) -> tuple:
        """
        计算股票的量化因子评分

        Args:
            ts_code: 股票代码
            trade_date: 交易日期，默认最近交易日

        Returns:
            (FactorScore对象, 数据源信息字典)
        """
        from core.storage.relational.connection import DatabaseManager

        # 获取数据
        daily_data, daily_source_info = self._get_daily_data_with_source(ts_code, days=120)
        basic_data, basic_source_info = self._get_basic_data_with_source(ts_code)

        # 构建数据源信息
        data_source_info = {
            'daily_data': daily_source_info,
            'basic_data': basic_source_info
        }

        if daily_data.empty:
            return FactorScore(total=50), data_source_info

        factors = {}

        # 1. 估值因子
        factors['value'] = self._value_factor(ts_code, basic_data)

        # 2. 质量因子
        factors['quality'] = self._quality_factor(ts_code, basic_data)

        # 3. 成长因子
        factors['growth'] = self._growth_factor(ts_code, basic_data)

        # 4. 动量因子
        factors['momentum'] = self._momentum_factor(ts_code, daily_data)

        # 5. 波动率因子
        factors['volatility'] = self._volatility_factor(ts_code, daily_data)

        # 6. 流动性因子
        factors['liquidity'] = self._liquidity_factor(ts_code, daily_data)

        # 标准化因子得分到0-100范围
        for key in factors:
            if factors[key] is not None:
                factors[key] = min(100, max(0, factors[key] + 50))

        # 计算综合得分
        weights = {
            'value': 0.20,
            'quality': 0.20,
            'growth': 0.20,
            'momentum': 0.20,
            'volatility': 0.10,
            'liquidity': 0.10
        }

        total = 0
        weight_sum = 0
        for key, weight in weights.items():
            if factors.get(key) is not None:
                total += factors[key] * weight
                weight_sum += weight

        if weight_sum > 0:
            total = total / weight_sum

        # 保存到数据库
        self._save_score(ts_code, trade_date, factors, total)

        return FactorScore(
            value=factors.get('value'),
            quality=factors.get('quality'),
            growth=factors.get('growth'),
            momentum=factors.get('momentum'),
            volatility=factors.get('volatility'),
            liquidity=factors.get('liquidity'),
            total=round(total, 2)
        ), data_source_info

    def _get_daily_data_with_source(self, ts_code: str, days: int = 120) -> tuple:
        """获取日线数据（带数据源信息）"""
        from datetime import datetime, timedelta
        from core.storage.relational.connection import DatabaseManager

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 20)
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        source_info = {
            'source': '',
            'table': '',
            'date_range': f"{start_str} ~ {end_str}",
            'record_count': 0
        }

        # 尝试本地数据库
        try:
            sql = """
                SELECT trade_date, open, high, low, close, vol, amount
                FROM t_stock_dailymarketdata
                WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date
            """
            rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code, start_str, end_str))
            if rows and len(rows) >= days * 0.5:
                df = pd.DataFrame(rows)
                for col in ['open', 'high', 'low', 'close', 'vol', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                source_info['source'] = '本地数据库'
                source_info['table'] = 'tushare_biz.t_stock_dailymarketdata'
                source_info['record_count'] = len(df)
                if not df.empty:
                    source_info['date_range'] = f"{df.iloc[0]['trade_date']} ~ {df.iloc[-1]['trade_date']}"
                return df, source_info
        except Exception:
            pass

        # 使用API
        df = self.ts_client.get_daily(ts_code, start_date=start_str, end_date=end_str)
        if not df.empty:
            df = df.sort_values('trade_date')
            source_info['source'] = 'Tushare API'
            source_info['table'] = 'api.t_stock_dailymarketdata'
            source_info['record_count'] = len(df)
            if not df.empty:
                source_info['date_range'] = f"{df.iloc[0]['trade_date']} ~ {df.iloc[-1]['trade_date']}"
        return df, source_info

    def _get_basic_data_with_source(self, ts_code: str) -> tuple:
        """获取基本面数据（带数据源信息）"""
        from core.storage.relational.connection import DatabaseManager

        source_info = {
            'source': '',
            'table': '',
            'date': '',
            'record_count': 0
        }

        # 尝试本地数据库
        try:
            sql = """
                SELECT trade_date, pe, pe_ttm, pb, ps_ttm, total_mv
                FROM t_stock_daily_basic
                WHERE ts_code = %s
                ORDER BY trade_date DESC
                LIMIT 1
            """
            rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code,))
            if rows:
                df = pd.DataFrame(rows)
                source_info['source'] = '本地数据库'
                source_info['table'] = 'tushare_biz.t_stock_daily_basic'
                source_info['record_count'] = len(df)
                if not df.empty:
                    source_info['date'] = str(df.iloc[0].get('trade_date', ''))
                return df, source_info
        except Exception:
            pass

        # 使用API
        try:
            df = self.ts_client.get_daily_basic(ts_code=ts_code)
            if not df.empty:
                source_info['source'] = 'Tushare API'
                source_info['table'] = 'api.t_stock_daily_basic'
                source_info['record_count'] = len(df)
                source_info['date'] = str(df.iloc[0].get('trade_date', ''))
            return df, source_info
        except:
            return pd.DataFrame(), source_info

    def _value_factor(self, ts_code: str, basic_data: pd.DataFrame) -> float:
        """
        估值因子得分

        基于EP、BP、SP
        """
        score = 0

        if basic_data.empty:
            return 50

        latest = basic_data.iloc[0]

        # EP (盈利收益率 = 1/PE)
        pe = latest.get('pe_ttm')
        if pe and pe > 0:
            ep = 1 / pe
            if ep > 0.1:  # PE < 10
                score += 25
            elif ep > 0.06:  # PE < 16
                score += 15
            elif ep > 0.04:  # PE < 25
                score += 5
            else:
                score -= 10

        # BP (账面市值比 = 1/PB)
        pb = latest.get('pb')
        if pb and pb > 0:
            bp = 1 / pb
            if bp > 0.5:  # PB < 2
                score += 15
            elif bp > 0.33:  # PB < 3
                score += 5

        # SP (营收市值比)
        ps = latest.get('ps_ttm')
        if ps and ps > 0:
            sp = 1 / ps
            if sp > 0.5:
                score += 10

        return min(50, score) + 50  # 映射到50-100

    def _quality_factor(self, ts_code: str, basic_data: pd.DataFrame) -> float:
        """
        质量因子得分

        ROE稳定性、盈利波动性
        """
        score = 50

        if basic_data.empty:
            return score

        # 使用最新基本面数据
        latest = basic_data.iloc[0]

        # ROE
        roe = latest.get('roe')
        if roe and roe > 15:
            score += 20
        elif roe and roe > 10:
            score += 10
        elif roe and roe < 5:
            score -= 10

        # 净利润率
        profit_margin = latest.get('profit_dadt')  # 净利润同比
        if profit_margin and profit_margin > 20:
            score += 15
        elif profit_margin and profit_margin < -20:
            score -= 15

        return score

    def _growth_factor(self, ts_code: str, basic_data: pd.DataFrame) -> float:
        """
        成长因子得分

        营收增长、净利润增长
        """
        score = 50

        if basic_data.empty:
            return score

        latest = basic_data.iloc[0]

        # 营收同比
        revenue_growth = latest.get('or_yoy')
        if revenue_growth:
            if revenue_growth > 50:
                score += 25
            elif revenue_growth > 30:
                score += 15
            elif revenue_growth > 15:
                score += 5
            elif revenue_growth < 0:
                score -= 10

        # 净利润同比
        profit_growth = latest.get('profit_dadt')
        if profit_growth:
            if profit_growth > 50:
                score += 25
            elif profit_growth > 30:
                score += 15
            elif profit_growth > 15:
                score += 5
            elif profit_growth < 0:
                score -= 15

        return min(100, max(0, score))

    def _momentum_factor(self, ts_code: str, daily_data: pd.DataFrame) -> float:
        """
        动量因子得分

        20日、60日收益率
        """
        if daily_data.empty or len(daily_data) < 60:
            return 50

        score = 50

        # 计算收益率
        current = daily_data.iloc[-1]['close']

        # 20日收益
        if len(daily_data) >= 20:
            price_20d = daily_data.iloc[-20]['close']
            ret_20d = (current - price_20d) / price_20d * 100

            if ret_20d > 20:
                score += 20
            elif ret_20d > 10:
                score += 10
            elif ret_20d > 0:
                score += 5
            elif ret_20d < -10:
                score -= 10

        # 60日收益
        if len(daily_data) >= 60:
            price_60d = daily_data.iloc[-60]['close']
            ret_60d = (current - price_60d) / price_60d * 100

            if ret_60d > 30:
                score += 15
            elif ret_60d > 15:
                score += 5
            elif ret_60d < -15:
                score -= 10

        return min(100, max(0, score))

    def _volatility_factor(self, ts_code: str, daily_data: pd.DataFrame) -> float:
        """
        波动率因子得分

        低波动率通常更好（低风险）
        """
        if daily_data.empty or len(daily_data) < 20:
            return 50

        # 计算20日波动率
        daily_data['returns'] = daily_data['close'].pct_change()
        volatility = daily_data['returns'].tail(20).std() * np.sqrt(252) * 100

        if pd.isna(volatility):
            return 50

        # 低波动率得分更高（低风险偏好）
        if volatility < 20:
            return 80
        elif volatility < 35:
            return 65
        elif volatility < 50:
            return 50
        elif volatility < 70:
            return 35
        else:
            return 20

    def _liquidity_factor(self, ts_code: str, daily_data: pd.DataFrame) -> float:
        """
        流动性因子得分

        基于成交额
        """
        if daily_data.empty or len(daily_data) < 20:
            return 50

        # 计算平均成交额（万元）
        avg_amount = daily_data['amount'].tail(20).mean()

        if pd.isna(avg_amount):
            return 50

        # 成交额越大流动性越好
        if avg_amount > 100000:  # 10亿
            return 90
        elif avg_amount > 50000:  # 5亿
            return 80
        elif avg_amount > 20000:  # 2亿
            return 70
        elif avg_amount > 5000:  # 5000万
            return 60
        elif avg_amount > 1000:  # 1000万
            return 50
        else:
            return 40

    def _save_score(self, ts_code: str, trade_date: str, factors: Dict, total: float):
        """保存因子评分到数据库"""
        try:
            if trade_date is None:
                from datetime import datetime
                trade_date = datetime.now().strftime('%Y%m%d')

            score = QuantFactorScore(
                ts_code=ts_code,
                trade_date=trade_date,
                value_factor=round(factors.get('value'), 2) if factors.get('value') else None,
                quality_factor=round(factors.get('quality'), 2) if factors.get('quality') else None,
                growth_factor=round(factors.get('growth'), 2) if factors.get('growth') else None,
                momentum_factor=round(factors.get('momentum'), 2) if factors.get('momentum') else None,
                volatility_factor=round(factors.get('volatility'), 2) if factors.get('volatility') else None,
                liquidity_factor=round(factors.get('liquidity'), 2) if factors.get('liquidity') else None,
                total_score=round(total, 2)
            )

            QuantFactorRepository.save_factor_score(score)

        except Exception as e:
            print(f"保存因子评分失败 {ts_code}: {e}")
