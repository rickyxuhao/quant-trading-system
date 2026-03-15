"""
技术分析器
计算技术指标和评分
"""
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from projects.broker_gold_stock.data.models import TechnicalScore
from core.data_access.tushare.client import TushareClient


class TechnicalAnalyzer:
    """技术分析器 - 计算技术指标和生成评分"""

    def __init__(self):
        self.ts_client = TushareClient()

    def analyze(self, ts_code: str, days: int = 60) -> tuple:
        """
        对股票进行技术分析

        Args:
            ts_code: 股票代码
            days: 分析天数

        Returns:
            (TechnicalScore对象, 数据源信息字典)
        """
        from datetime import datetime, timedelta

        # 获取日线数据
        df, data_source_info = self._get_price_data_with_source(ts_code, days)

        if df.empty or len(df) < 20:
            return TechnicalScore(total=50, signals=[{"warning": "数据不足"}]), data_source_info

        signals = []
        scores = {}

        # 1. 趋势分析 (权重30%)
        scores['trend'] = self._analyze_trend(df, signals)

        # 2. 支撑压力 (权重25%)
        scores['level'] = self._analyze_support_resistance(df, signals)

        # 3. 动量指标 (权重25%)
        scores['momentum'] = self._analyze_momentum(df, signals)

        # 4. 成交量分析 (权重20%)
        scores['volume'] = self._analyze_volume(df, signals)

        # 计算总分
        total = int(
            scores['trend'] * 0.30 +
            scores['level'] * 0.25 +
            scores['momentum'] * 0.25 +
            scores['volume'] * 0.20
        )

        # 更新数据源信息，添加实际使用的数据日期范围
        if not df.empty:
            data_source_info['data_date_range'] = f"{df.iloc[0]['trade_date']} ~ {df.iloc[-1]['trade_date']}"
            data_source_info['record_count'] = len(df)

        return TechnicalScore(
            total=min(100, max(0, total)),
            trend_score=scores['trend'],
            level_score=scores['level'],
            momentum_score=scores['momentum'],
            volume_score=scores['volume'],
            signals=signals
        ), data_source_info

    def _get_price_data_with_source(self, ts_code: str, days: int) -> tuple:
        """
        获取价格数据 - 优先从本地数据库读取

        Returns:
            (DataFrame, 数据源信息字典)
        """
        from datetime import datetime, timedelta
        from core.storage.relational.connection import DatabaseManager

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 20)
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        data_source_info = {
            'source_type': '',
            'table_name': '',
            'date_range': f"{start_str} ~ {end_str}",
            'record_count': 0,
            'data_date_range': ''
        }

        # 1. 优先从本地数据库读取
        try:
            df = self._get_local_price_data(ts_code, start_str, end_str)
            if not df.empty and len(df) >= days * 0.8:
                data_source_info['source_type'] = '本地数据库'
                data_source_info['table_name'] = 'tushare_biz.t_stock_dailymarketdata'
                data_source_info['record_count'] = len(df)
                print(f"   [数据源] 本地数据库: {len(df)} 条记录 ({start_str} ~ {end_str})")
                return df, data_source_info
        except Exception as e:
            print(f"   [数据源] 本地读取失败: {e}")

        # 2. 本地数据不足，调用Tushare API
        print(f"   [数据源] Tushare API: 获取 {ts_code} 数据...")
        df = self.ts_client.get_daily(ts_code, start_date=start_str, end_date=end_str)

        if not df.empty:
            df = df.sort_values('trade_date')
            df.reset_index(drop=True, inplace=True)
            data_source_info['source_type'] = 'Tushare API'
            data_source_info['table_name'] = 'tushare_api.t_stock_dailymarketdata'
            data_source_info['record_count'] = len(df)
            print(f"   [数据源] API返回: {len(df)} 条记录")

        return df, data_source_info

    def _get_local_price_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从本地数据库获取日线数据"""
        from core.storage.relational.connection import DatabaseManager

        sql = """
            SELECT trade_date, open, high, low, close, vol, amount
            FROM t_stock_dailymarketdata
            WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date
        """
        rows = DatabaseManager.fetchall('tushare_biz', sql, (ts_code, start_date, end_date))

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # 确保数值列为float类型
        numeric_cols = ['open', 'high', 'low', 'close', 'vol', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def _analyze_trend(self, df: pd.DataFrame, signals: List[Dict]) -> int:
        """
        趋势分析

        评分标准:
        - MA5 > MA10 > MA20: 多头排列 +30
        - 价格在MA20上方: +20
        - 价格在MA20下方: -10
        - 趋势强度(斜率): 0-20
        """
        score = 50

        # 计算均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()

        latest = df.iloc[-1]

        # 多头排列检查
        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            score += 25
            signals.append({"type": "trend", "name": "多头排列", "value": "MA5>MA10>MA20", "score": +25})
        elif latest['ma5'] < latest['ma10'] < latest['ma20']:
            score -= 15
            signals.append({"type": "trend", "name": "空头排列", "value": "MA5<MA10<MA20", "score": -15})

        # 价格在MA20上方
        if latest['close'] > latest['ma20']:
            score += 15
            signals.append({"type": "trend", "name": "站上MA20", "value": f"{latest['close']:.2f} > {latest['ma20']:.2f}", "score": +15})
        else:
            score -= 10
            signals.append({"type": "trend", "name": "跌破MA20", "value": f"{latest['close']:.2f} < {latest['ma20']:.2f}", "score": -10})

        # 趋势强度（20日均线斜率）
        if len(df) >= 25:
            ma20_slope = (df.iloc[-1]['ma20'] - df.iloc[-6]['ma20']) / df.iloc[-6]['ma20'] * 100
            if ma20_slope > 2:
                score += 10
                signals.append({"type": "trend", "name": "强势上涨", "value": f"+{ma20_slope:.2f}%", "score": +10})
            elif ma20_slope < -2:
                score -= 10
                signals.append({"type": "trend", "name": "趋势走弱", "value": f"{ma20_slope:.2f}%", "score": -10})

        return min(100, max(0, score))

    def _analyze_support_resistance(self, df: pd.DataFrame, signals: List[Dict]) -> int:
        """
        支撑压力分析

        基于近期高低点和布林带位置
        """
        score = 50

        # 计算布林带
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['upper'] = df['ma20'] + 2 * df['std20']
        df['lower'] = df['ma20'] - 2 * df['std20']

        latest = df.iloc[-1]

        # 布林带位置
        if latest['close'] > latest['upper']:
            score += 20
            signals.append({"type": "sr", "name": "突破布林上轨", "value": "强势", "score": +20})
        elif latest['close'] < latest['lower']:
            score -= 15
            signals.append({"type": "sr", "name": "跌破布林下轨", "value": "弱势", "score": -15})
        elif latest['close'] > latest['ma20']:
            score += 10
            signals.append({"type": "sr", "name": "布林中轨上方", "value": "偏多", "score": +10})

        # 近期高低点
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        current = latest['close']

        # 距离高点/低点的位置
        range_pct = (recent_high - recent_low) / recent_low * 100 if recent_low > 0 else 0
        position_pct = (current - recent_low) / (recent_high - recent_low) * 100 if recent_high > recent_low else 50

        if position_pct > 80:
            score += 15
            signals.append({"type": "sr", "name": "接近近期高点", "value": f"{position_pct:.1f}%", "score": +15})
        elif position_pct < 20:
            score += 10  # 接近低点可能是机会
            signals.append({"type": "sr", "name": "接近近期低点", "value": f"{position_pct:.1f}%", "score": +10})

        return min(100, max(0, score))

    def _analyze_momentum(self, df: pd.DataFrame, signals: List[Dict]) -> int:
        """
        动量指标分析

        MACD, RSI, KDJ
        """
        score = 50

        # MACD计算
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['hist'] = df['macd'] - df['signal']

        # RSI计算
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # MACD金叉/死叉
        if prev['macd'] < prev['signal'] and latest['macd'] > latest['signal']:
            score += 20
            signals.append({"type": "momentum", "name": "MACD金叉", "value": "买入信号", "score": +20})
        elif prev['macd'] > prev['signal'] and latest['macd'] < latest['signal']:
            score -= 15
            signals.append({"type": "momentum", "name": "MACD死叉", "value": "卖出信号", "score": -15})
        elif latest['macd'] > latest['signal']:
            score += 10
            signals.append({"type": "momentum", "name": "MACD多头", "value": "强势", "score": +10})

        # RSI判断
        rsi = latest['rsi']
        if not pd.isna(rsi):
            if rsi > 70:
                score -= 10
                signals.append({"type": "momentum", "name": "RSI超买", "value": f"{rsi:.1f}", "score": -10})
            elif rsi < 30:
                score += 15
                signals.append({"type": "momentum", "name": "RSI超卖", "value": f"{rsi:.1f}", "score": +15})
            elif 40 <= rsi <= 60:
                score += 5
                signals.append({"type": "momentum", "name": "RSI中性", "value": f"{rsi:.1f}", "score": +5})

        return min(100, max(0, score))

    def _analyze_volume(self, df: pd.DataFrame, signals: List[Dict]) -> int:
        """
        成交量分析

        量价配合、成交量趋势、OBV
        """
        score = 50

        # 计算OBV
        df['obv'] = 0
        for i in range(1, len(df)):
            if df.iloc[i]['close'] > df.iloc[i-1]['close']:
                df.loc[df.index[i], 'obv'] = df.iloc[i-1]['obv'] + df.iloc[i]['vol']
            elif df.iloc[i]['close'] < df.iloc[i-1]['close']:
                df.loc[df.index[i], 'obv'] = df.iloc[i-1]['obv'] - df.iloc[i]['vol']
            else:
                df.loc[df.index[i], 'obv'] = df.iloc[i-1]['obv']

        # 成交量均线
        df['vol_ma5'] = df['vol'].rolling(window=5).mean()
        df['vol_ma20'] = df['vol'].rolling(window=20).mean()

        latest = df.iloc[-1]

        # 量比
        if not pd.isna(latest['vol_ma5']) and latest['vol_ma5'] > 0:
            volume_ratio = latest['vol'] / latest['vol_ma5']

            if volume_ratio > 2:
                score += 20
                signals.append({"type": "volume", "name": "放量上涨", "value": f"量比{volume_ratio:.1f}", "score": +20})
            elif volume_ratio > 1.5:
                score += 10
                signals.append({"type": "volume", "name": "温和放量", "value": f"量比{volume_ratio:.1f}", "score": +10})
            elif volume_ratio < 0.5:
                score -= 10
                signals.append({"type": "volume", "name": "缩量", "value": f"量比{volume_ratio:.1f}", "score": -10})

        # 成交量趋势
        if len(df) >= 10:
            vol_trend = df['vol'].tail(5).mean() / df['vol'].tail(10).mean()
            if vol_trend > 1.2:
                score += 10
                signals.append({"type": "volume", "name": "量能增加", "value": f"+{(vol_trend-1)*100:.0f}%", "score": +10})

        return min(100, max(0, score))

    def detect_breakout(self, ts_code: str, days: int = 20) -> Optional[Dict[str, Any]]:
        """
        检测技术突破信号

        Args:
            ts_code: 股票代码
            days: 检测天数

        Returns:
            突破信号或None
        """
        df = self._get_price_data(ts_code, days)

        if df.empty or len(df) < 20:
            return None

        latest = df.iloc[-1]
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()

        # 突破近期高点
        if latest['close'] > recent_high * 0.98:  # 允许2%误差
            return {
                "type": "breakout_high",
                "ts_code": ts_code,
                "price": latest['close'],
                "break_level": recent_high,
                "strength": "strong" if latest['close'] > recent_high else "weak"
            }

        # 跌破近期低点
        if latest['close'] < recent_low * 1.02:
            return {
                "type": "breakdown_low",
                "ts_code": ts_code,
                "price": latest['close'],
                "break_level": recent_low,
                "strength": "strong" if latest['close'] < recent_low else "weak"
            }

        return None
