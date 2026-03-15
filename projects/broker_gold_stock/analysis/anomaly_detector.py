"""
异动检测引擎
检测股票价格和成交量异动
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from projects.broker_gold_stock.data.models import StockAnomaly, AnomalyType, AnomalySeverity
from projects.broker_gold_stock.data.repository import AnomalyRepository
from core.data_access.tushare.client import TushareClient


class AnomalyDetector:
    """异动检测引擎 - 检测价格、成交量异动"""

    def __init__(self):
        self.ts_client = TushareClient()

    def detect(self, ts_code: str, name: str = "", days: int = 5) -> List[StockAnomaly]:
        """
        检测股票异动

        Args:
            ts_code: 股票代码
            name: 股票名称
            days: 检测天数

        Returns:
            异动列表
        """
        anomalies = []

        # 获取日线数据
        df = self._get_price_data(ts_code, days + 20)

        if df.empty or len(df) < 5:
            return anomalies

        # 检测价格异动
        price_anomaly = self._detect_price_anomaly(ts_code, name, df)
        if price_anomaly:
            anomalies.append(price_anomaly)

        # 检测成交量异动
        volume_anomaly = self._detect_volume_anomaly(ts_code, name, df)
        if volume_anomaly:
            anomalies.append(volume_anomaly)

        # 检测涨跌停
        limit_anomaly = self._detect_limit_price(ts_code, name, df)
        if limit_anomaly:
            anomalies.append(limit_anomaly)

        # 保存到数据库
        for anomaly in anomalies:
            AnomalyRepository.save_anomaly(anomaly)

        return anomalies

    def detect_batch(self, ts_codes: List[str], names: Dict[str, str] = None) -> Dict[str, List[StockAnomaly]]:
        """
        批量检测异动

        Args:
            ts_codes: 股票代码列表
            names: 代码到名称的映射

        Returns:
            各股票的异动字典
        """
        results = {}
        names = names or {}

        for ts_code in ts_codes:
            name = names.get(ts_code, "")
            try:
                anomalies = self.detect(ts_code, name)
                if anomalies:
                    results[ts_code] = anomalies
            except Exception as e:
                print(f"检测 {ts_code} 异动失败: {e}")

        return results

    def _get_price_data(self, ts_code: str, days: int) -> pd.DataFrame:
        """获取价格数据"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)

        df = self.ts_client.get_daily(
            ts_code,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=end_date.strftime('%Y%m%d')
        )

        if not df.empty:
            df = df.sort_values('trade_date')
            df.reset_index(drop=True, inplace=True)

        return df

    def _detect_price_anomaly(self, ts_code: str, name: str, df: pd.DataFrame) -> Optional[StockAnomaly]:
        """检测价格异动"""
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 计算涨跌幅
        price_change = (latest['close'] - prev['close']) / prev['close'] * 100

        # 阈值
        if abs(price_change) < 5:
            return None

        # 确定严重程度和类型
        if price_change >= 7:
            severity = AnomalySeverity.HIGH
            anomaly_type = AnomalyType.PRICE_SPIKE.value
        elif price_change >= 5:
            severity = AnomalySeverity.MEDIUM
            anomaly_type = AnomalyType.PRICE_SPIKE.value
        elif price_change <= -7:
            severity = AnomalySeverity.CRITICAL
            anomaly_type = AnomalyType.PRICE_SPIKE.value
        else:
            severity = AnomalySeverity.MEDIUM
            anomaly_type = AnomalyType.PRICE_SPIKE.value

        return StockAnomaly(
            ts_code=ts_code,
            name=name,
            detect_date=str(latest['trade_date']),
            anomaly_type=anomaly_type,
            severity=severity,
            trigger_price=latest['close'],
            price_change=round(price_change, 2),
            volume_ratio=None
        )

    def _detect_volume_anomaly(self, ts_code: str, name: str, df: pd.DataFrame) -> Optional[StockAnomaly]:
        """检测成交量异动"""
        if len(df) < 20:
            return None

        latest = df.iloc[-1]

        # 计算20日均量
        avg_volume = df['vol'].tail(20).mean()

        if avg_volume == 0:
            return None

        # 量比
        volume_ratio = latest['vol'] / avg_volume

        # 阈值
        if volume_ratio < 2:
            return None

        # 确定严重程度
        if volume_ratio >= 5:
            severity = AnomalySeverity.HIGH
        elif volume_ratio >= 3:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW

        return StockAnomaly(
            ts_code=ts_code,
            name=name,
            detect_date=str(latest['trade_date']),
            anomaly_type=AnomalyType.VOLUME_SURGE.value,
            severity=severity,
            trigger_price=latest['close'],
            price_change=None,
            volume_ratio=round(volume_ratio, 2)
        )

    def _detect_limit_price(self, ts_code: str, name: str, df: pd.DataFrame) -> Optional[StockAnomaly]:
        """检测涨跌停"""
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['close']

        # 计算涨跌幅
        change_pct = (latest['close'] - prev_close) / prev_close * 100

        # 涨停检测 (约10%或20%)
        if change_pct >= 9.5:
            # 科创板/创业板可能为20%
            limit_pct = 20 if latest['close'] >= prev_close * 1.19 else 10

            return StockAnomaly(
                ts_code=ts_code,
                name=name,
                detect_date=str(latest['trade_date']),
                anomaly_type=AnomalyType.LIMIT_UP.value,
                severity=AnomalySeverity.HIGH,
                trigger_price=latest['close'],
                price_change=round(change_pct, 2),
                volume_ratio=None
            )

        # 跌停检测
        if change_pct <= -9.5:
            return StockAnomaly(
                ts_code=ts_code,
                name=name,
                detect_date=str(latest['trade_date']),
                anomaly_type=AnomalyType.LIMIT_DOWN.value,
                severity=AnomalySeverity.CRITICAL,
                trigger_price=latest['close'],
                price_change=round(change_pct, 2),
                volume_ratio=None
            )

        return None

    def get_recent_anomalies(self, days: int = 7, severity: str = None) -> List[StockAnomaly]:
        """
        获取近期异动

        Args:
            days: 最近N天
            severity: 严重程度过滤

        Returns:
            异动列表
        """
        from datetime import datetime, timedelta

        detect_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 查询数据库
        return AnomalyRepository.get_anomalies_by_date(detect_date, severity)
