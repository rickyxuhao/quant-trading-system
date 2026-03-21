"""
Tushare 数据访问客户端
封装 Tushare API，提供统一的数据获取接口
包含重试机制和线程安全单例
"""
import os
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, List, Dict, Any, Callable

import tushare as ts
import pandas as pd
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志 - 使用 loguru
from core.logger import get_logger
logger = get_logger(__name__)


# 需要重试的异常类型
class TushareAPIError(Exception):
    """Tushare API 错误"""
    pass


def tushare_retry(**kwargs):
    """
    Tushare API 重试装饰器
    使用指数退避策略

    默认配置:
    - 最多重试 3 次
    - 等待时间: 1s, 2s, 4s (指数退避)
    """
    defaults = {
        'stop': stop_after_attempt(3),
        'wait': wait_exponential(multiplier=1, min=1, max=10),
        'retry': retry_if_exception_type((Exception,)),
        'before_sleep': before_sleep_log(logger, 30),  # WARNING level = 30
        'reraise': True,
    }
    defaults.update(kwargs)
    return retry(**defaults)


class TushareClientMeta(type):
    """
    线程安全的单例元类
    使用双重检查锁定模式
    """
    _instances: Dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                # 双重检查
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class TushareClient(metaclass=TushareClientMeta):
    """Tushare 数据客户端 - 线程安全单例"""

    def __init__(self):
        # 每个实例只初始化一次
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 从环境变量获取 Token
        token = os.getenv("TUSHARE_TOKEN")

        if not token:
            raise ValueError(
                "Tushare Token 未配置。请设置 TUSHARE_TOKEN 环境变量，"
                "或创建 .env 文件（参考 .env.example）。"
                "可从 https://tushare.pro 注册获取 Token。"
            )

        ts.set_token(token)
        self.pro = ts.pro_api()
        self._initialized = True
        self._lock = threading.RLock()  # 用于线程安全的操作
        print("✅ Tushare 客户端初始化成功")

    def __getattr__(self, name):
        """转发所有未定义属性到 self.pro，兼容直接访问 pro 的接口"""
        # 避免初始化期间的递归问题
        if name in ('_initialized', 'pro', '_lock'):
            raise AttributeError(name)
        return getattr(self.pro, name)

    def _safe_api_call(self, api_func: Callable, *args, **kwargs) -> pd.DataFrame:
        """
        线程安全的 API 调用包装器

        Args:
            api_func: Tushare API 函数
            *args, **kwargs: 传递给 API 的参数

        Returns:
            DataFrame 结果
        """
        with self._lock:
            return api_func(*args, **kwargs)

    # ==================== 基础数据接口 =====================

    @tushare_retry()
    def get_stock_basic(self, exchange: Optional[str] = None,
                       list_status: str = "L") -> pd.DataFrame:
        """
        获取股票基础信息

        Args:
            exchange: 交易所代码 SSE/SZSE
            list_status: 上市状态 L上市 D退市 P暂停

        Returns:
            DataFrame 包含股票基础信息
        """
        params = {"list_status": list_status}
        if exchange:
            params["exchange"] = exchange

        return self._safe_api_call(self.pro.stock_basic, **params)

    @tushare_retry()
    def get_trade_calendar(self, start_date: str, end_date: str,
                          exchange: str = "SSE") -> pd.DataFrame:
        """
        获取交易日历

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            exchange: 交易所

        Returns:
            DataFrame 包含交易日历
        """
        return self._safe_api_call(
            self.pro.trade_cal,
            exchange=exchange, start_date=start_date, end_date=end_date
        )

    # ==================== 行情数据接口 =====================

    @tushare_retry()
    def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线行情

        Args:
            ts_code: 股票代码 000001.SZ
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame 包含日线数据
        """
        return self._safe_api_call(
            self.pro.daily,
            ts_code=ts_code, start_date=start_date, end_date=end_date
        )

    @tushare_retry()
    def get_daily_all(self, trade_date: str) -> pd.DataFrame:
        """
        获取某交易日全部股票日线数据

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame 包含当日全部股票数据
        """
        return self._safe_api_call(self.pro.daily, trade_date=trade_date)

    @tushare_retry()
    def get_adj_factor(self, ts_code: Optional[str] = None,
                       trade_date: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取复权因子

        Args:
            ts_code: 股票代码
            trade_date: 交易日期（与起止日期二选一）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含复权因子
        """
        params = {}
        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return self._safe_api_call(self.pro.adj_factor, **params)

    @tushare_retry()
    def get_daily_basic(self, ts_code: Optional[str] = None,
                       trade_date: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取每日指标（估值、换手率等）

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含每日指标
        """
        params = {}
        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return self._safe_api_call(self.pro.daily_basic, **params)

    # ==================== 财务数据接口 =====================

    @tushare_retry()
    def get_income(self, ts_code: str, start_date: str, end_date: str,
                   report_type: Optional[str] = None) -> pd.DataFrame:
        """
        获取利润表

        Args:
            ts_code: 股票代码
            start_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报告类型 1合并报表 2单季 3调整单季 4调整合并报表

        Returns:
            DataFrame 包含利润表数据
        """
        params = {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        }
        if report_type:
            params["report_type"] = report_type

        return self._safe_api_call(self.pro.income, **params)

    @tushare_retry()
    def get_balance_sheet(self, ts_code: str, start_date: str, end_date: str,
                          report_type: Optional[str] = None) -> pd.DataFrame:
        """
        获取资产负债表

        Args:
            ts_code: 股票代码
            start_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报告类型

        Returns:
            DataFrame 包含资产负债表数据
        """
        params = {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        }
        if report_type:
            params["report_type"] = report_type

        return self._safe_api_call(self.pro.balancesheet, **params)

    @tushare_retry()
    def get_cash_flow(self, ts_code: str, start_date: str, end_date: str,
                      report_type: Optional[str] = None) -> pd.DataFrame:
        """
        获取现金流量表

        Args:
            ts_code: 股票代码
            start_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报告类型

        Returns:
            DataFrame 包含现金流量表数据
        """
        params = {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        }
        if report_type:
            params["report_type"] = report_type

        return self._safe_api_call(self.pro.cashflow, **params)

    # ==================== 通用查询接口 =====================

    @tushare_retry()
    def query(self, api_name: str, fields: str = None, **kwargs) -> pd.DataFrame:
        """
        通用查询接口

        Args:
            api_name: API 名称
            fields: 字段列表
            **kwargs: 其他参数

        Returns:
            DataFrame 结果
        """
        params = kwargs.copy()
        if fields:
            params["fields"] = fields

        return self._safe_api_call(self.pro.query, api_name, **params)

    # ==================== 辅助方法 =====================

    @staticmethod
    def format_date(date_str: str) -> str:
        """格式化日期为 YYYYMMDD"""
        if len(date_str) == 8 and date_str.isdigit():
            return date_str

        # 尝试解析其他格式
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y%m%d")
            except ValueError:
                continue

        raise ValueError(f"无法解析日期格式: {date_str}")

    @staticmethod
    def get_last_trade_date(offset: int = 0) -> str:
        """
        获取最近交易日

        Args:
            offset: 偏移量，0=今天/最近交易日，1=昨天，-1=明天

        Returns:
            交易日期 YYYYMMDD
        """
        today = datetime.now()
        target_date = today - timedelta(days=offset)
        return target_date.strftime("%Y%m%d")


# 便捷函数
def get_tushare_client() -> TushareClient:
    """获取 Tushare 客户端实例"""
    return TushareClient()
