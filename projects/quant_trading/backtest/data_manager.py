"""
数据管理模块 - 负责MySQL数据查询、前复权计算、数据完整性检测
使用LRU缓存和批量获取优化性能
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple, Union, Any
from functools import lru_cache
from collections import OrderedDict
import logging

import pandas as pd
import numpy as np

from core.storage.relational.connection import DatabaseManager

# 配置日志
logger = logging.getLogger(__name__)


class MissingDataError(Exception):
    """数据缺失异常

    Attributes:
        message: 错误消息
        ts_code: 缺失数据的股票代码（可选）
        start_date: 查询的开始日期（可选）
        end_date: 查询的结束日期（可选）
    """

    def __init__(
        self,
        message: str,
        ts_code: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        super().__init__(message)
        self.message = message
        self.ts_code = ts_code
        self.start_date = start_date
        self.end_date = end_date

    def __str__(self) -> str:
        parts = [self.message]
        if self.ts_code:
            parts.append(f"股票代码: {self.ts_code}")
        if self.start_date:
            parts.append(f"开始日期: {self.start_date}")
        if self.end_date:
            parts.append(f"结束日期: {self.end_date}")
        return " | ".join(parts)


@dataclass
class StockData:
    """个股日线数据"""
    ts_code: str
    trade_date: datetime
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    change: float
    pct_chg: float
    vol: float
    amount: float
    adj_factor: float = 1.0
    adj_close: float = 0.0
    adj_open: float = 0.0
    adj_high: float = 0.0
    adj_low: float = 0.0


@dataclass
class IndexData:
    """指数日线数据"""
    ts_code: str
    trade_date: datetime
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    change: float
    pct_chg: float
    vol: float
    amount: float


class DataManager:
    """
    数据管理器
    负责从MySQL获取股票数据、处理前复权、数据完整性检查
    使用LRU缓存和批量查询优化性能

    Attributes:
        db_name: 数据库名称
        max_cache_size: 最大缓存条目数
    """

    def __init__(self, db_name: str = "tushare_biz", max_cache_size: int = 128):
        self.db_name = db_name
        self.max_cache_size = max_cache_size
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._trade_dates: List[datetime] = []
        self._stocks_pool: List[str] = []
        self._stock_info_cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, prefix: str, *args: Any) -> str:
        """生成缓存键

        Args:
            prefix: 缓存键前缀
            *args: 缓存键参数

        Returns:
            组合后的缓存键字符串
        """
        return f"{prefix}_{'_'.join(str(a) for a in args)}"

    def _get_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """从缓存获取数据（LRU更新）

        Args:
            key: 缓存键

        Returns:
            缓存的数据，如果不存在返回None
        """
        if key in self._cache:
            # 移动到末尾（最近使用）
            df = self._cache.pop(key)
            self._cache[key] = df
            return df
        return None

    def _set_cache(self, key: str, df: pd.DataFrame) -> None:
        """设置缓存，LRU淘汰

        Args:
            key: 缓存键
            df: 要缓存的DataFrame
        """
        if key in self._cache:
            # 更新已存在的键
            self._cache.pop(key)
        elif len(self._cache) >= self.max_cache_size:
            # LRU淘汰: 移除最早添加的
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"缓存LRU淘汰: {oldest_key}")

        self._cache[key] = df.copy()

    def clear_cache(self) -> None:
        """清除数据缓存"""
        cache_size = len(self._cache)
        self._cache.clear()
        self._stock_info_cache.clear()
        logger.debug(f"缓存已清除，清空 {cache_size} 条缓存")

    def get_trade_dates(self, start_date: datetime, end_date: datetime) -> List[datetime]:
        """获取指定日期范围内的交易日列表

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日列表

        Raises:
            MissingDataError: 未找到交易日数据
            DatabaseError: 数据库连接异常
        """
        sql = """
            SELECT cal_date
            FROM t_stock_tradedate
            WHERE cal_date BETWEEN %s AND %s
              AND is_open = 1
            ORDER BY cal_date ASC
        """
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        try:
            results = DatabaseManager.fetchall(self.db_name, sql, (start_str, end_str))
        except Exception as e:
            logger.error(f"获取交易日数据失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        if not results:
            raise MissingDataError(
                f"未找到交易日数据: {start_str} 至 {end_str}",
                start_date=start_date,
                end_date=end_date
            )

        trade_dates = [datetime.strptime(r['cal_date'], '%Y%m%d') for r in results]
        self._trade_dates = trade_dates
        logger.debug(f"获取交易日数据: {start_str} 至 {end_str}, 共 {len(trade_dates)} 天")
        return trade_dates

    def get_stock_data(
        self,
        ts_code: str,
        start_date: datetime,
        end_date: datetime,
        adjust: bool = True
    ) -> pd.DataFrame:
        """获取个股日线数据，支持前复权，使用LRU缓存

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adjust: 是否进行前复权

        Returns:
            包含日线数据的DataFrame

        Raises:
            MissingDataError: 未找到股票数据
            DatabaseError: 数据库连接异常
        """
        cache_key = self._get_cache_key(
            "stock", ts_code,
            start_date.strftime('%Y%m%d'),
            end_date.strftime('%Y%m%d'),
            adjust
        )

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug(f"缓存命中: {ts_code} ({start_date.date()} ~ {end_date.date()})")
            return cached.copy()

        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # 查询日线数据
        sql_daily = """
            SELECT
                ts_code, trade_date, open, high, low, close,
                pre_close, t_change as `change`, pct_chg, vol, amount
            FROM t_stock_dailymarketdata
            WHERE ts_code = %s
              AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date ASC
        """
        try:
            daily_results = DatabaseManager.fetchall(
                self.db_name, sql_daily, (ts_code, start_str, end_str)
            )
        except Exception as e:
            logger.error(f"获取股票数据失败 {ts_code}: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        if not daily_results:
            raise MissingDataError(
                f"股票 {ts_code} 在 {start_str} 至 {end_str} 期间无数据",
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

        logger.debug(f"数据库查询: {ts_code} ({start_str} ~ {end_str}), 返回 {len(daily_results)} 条记录")

        df = pd.DataFrame(daily_results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

        # 查询复权因子
        if adjust:
            sql_adj = """
                SELECT trade_date, adj_factor
                FROM t_stock_adjfactor
                WHERE ts_code = %s
                  AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date ASC
            """
            try:
                adj_results = DatabaseManager.fetchall(
                    self.db_name, sql_adj, (ts_code, start_str, end_str)
                )
            except Exception as e:
                logger.warning(f"获取复权因子失败 {ts_code}: {e}，将使用不复权数据")
                adj_results = []

            if adj_results:
                adj_df = pd.DataFrame(adj_results)
                adj_df['trade_date'] = pd.to_datetime(adj_df['trade_date'], format='%Y%m%d')
                df = df.merge(adj_df, on='trade_date', how='left')
                df['adj_factor'] = df['adj_factor'].fillna(1.0)

                latest_adj = df['adj_factor'].iloc[-1]
                df['adj_factor_ratio'] = df['adj_factor'] / latest_adj

                df['adj_open'] = df['open'] * df['adj_factor_ratio']
                df['adj_high'] = df['high'] * df['adj_factor_ratio']
                df['adj_low'] = df['low'] * df['adj_factor_ratio']
                df['adj_close'] = df['close'] * df['adj_factor_ratio']
                df['adj_pre_close'] = df['pre_close'] * df['adj_factor_ratio']
                df = df.drop(columns=['adj_factor_ratio'])
            else:
                df['adj_factor'] = 1.0
                df['adj_open'] = df['open']
                df['adj_high'] = df['high']
                df['adj_low'] = df['low']
                df['adj_close'] = df['close']
                df['adj_pre_close'] = df['pre_close']
        else:
            df['adj_factor'] = 1.0
            df['adj_open'] = df['open']
            df['adj_high'] = df['high']
            df['adj_low'] = df['low']
            df['adj_close'] = df['close']
            df['adj_pre_close'] = df['pre_close']

        df = df.set_index('trade_date')
        df = df.sort_index()

        self._set_cache(cache_key, df)
        return df.copy()

    def get_batch_stock_data(
        self,
        ts_codes: List[str],
        start_date: datetime,
        end_date: datetime,
        adjust: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票数据

        使用批量SQL查询提高效率，同时利用缓存避免重复查询。

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust: 是否前复权

        Returns:
            {ts_code: DataFrame} 字典

        Raises:
            DatabaseError: 数据库连接异常
        """
        if not ts_codes:
            return {}

        result: Dict[str, pd.DataFrame] = {}
        missing_codes: List[str] = []

        # 先从缓存查找
        for ts_code in ts_codes:
            cache_key = self._get_cache_key(
                "stock", ts_code,
                start_date.strftime('%Y%m%d'),
                end_date.strftime('%Y%m%d'),
                adjust
            )
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                result[ts_code] = cached.copy()
            else:
                missing_codes.append(ts_code)

        cache_hit = len(ts_codes) - len(missing_codes)
        if cache_hit > 0:
            logger.debug(f"批量查询缓存命中: {cache_hit}/{len(ts_codes)}")

        if not missing_codes:
            return result

        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # 批量查询日线数据
        placeholders = ','.join(['%s'] * len(missing_codes))
        sql_daily = f"""
            SELECT
                ts_code, trade_date, open, high, low, close,
                pre_close, t_change as `change`, pct_chg, vol, amount
            FROM t_stock_dailymarketdata
            WHERE ts_code IN ({placeholders})
              AND trade_date BETWEEN %s AND %s
            ORDER BY ts_code, trade_date ASC
        """
        params = missing_codes + [start_str, end_str]

        try:
            daily_results = DatabaseManager.fetchall(self.db_name, sql_daily, tuple(params))
        except Exception as e:
            logger.error(f"批量获取股票数据失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        if not daily_results:
            logger.warning(f"批量查询无数据返回: {len(missing_codes)} 只股票")
            return result

        logger.debug(f"批量查询数据库: {len(missing_codes)} 只股票, 返回 {len(daily_results)} 条记录")

        # 批量查询复权因子
        adj_dict: Dict[str, List[Dict]] = {}
        if adjust:
            sql_adj = f"""
                SELECT ts_code, trade_date, adj_factor
                FROM t_stock_adjfactor
                WHERE ts_code IN ({placeholders})
                  AND trade_date BETWEEN %s AND %s
                ORDER BY ts_code, trade_date ASC
            """
            try:
                adj_results = DatabaseManager.fetchall(self.db_name, sql_adj, tuple(params))
                for r in adj_results:
                    key = r['ts_code']
                    if key not in adj_dict:
                        adj_dict[key] = []
                    adj_dict[key].append(r)
            except Exception as e:
                logger.warning(f"批量获取复权因子失败: {e}，将使用不复权数据")

        # 按股票分组处理
        df_dict: Dict[str, List[Dict]] = {}
        for r in daily_results:
            key = r['ts_code']
            if key not in df_dict:
                df_dict[key] = []
            df_dict[key].append(r)

        for ts_code, records in df_dict.items():
            df = pd.DataFrame(records)
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

            if adjust and ts_code in adj_dict:
                adj_df = pd.DataFrame(adj_dict[ts_code])
                adj_df['trade_date'] = pd.to_datetime(adj_df['trade_date'], format='%Y%m%d')
                df = df.merge(adj_df, on='trade_date', how='left')
                df['adj_factor'] = df['adj_factor'].fillna(1.0)

                latest_adj = df['adj_factor'].iloc[-1]
                df['adj_factor_ratio'] = df['adj_factor'] / latest_adj

                df['adj_open'] = df['open'] * df['adj_factor_ratio']
                df['adj_high'] = df['high'] * df['adj_factor_ratio']
                df['adj_low'] = df['low'] * df['adj_factor_ratio']
                df['adj_close'] = df['close'] * df['adj_factor_ratio']
                df['adj_pre_close'] = df['pre_close'] * df['adj_factor_ratio']
                df = df.drop(columns=['adj_factor_ratio'])
            else:
                df['adj_factor'] = 1.0
                df['adj_open'] = df['open']
                df['adj_high'] = df['high']
                df['adj_low'] = df['low']
                df['adj_close'] = df['close']
                df['adj_pre_close'] = df['pre_close']

            df = df.set_index('trade_date')
            df = df.sort_index()

            cache_key = self._get_cache_key(
                "stock", ts_code,
                start_date.strftime('%Y%m%d'),
                end_date.strftime('%Y%m%d'),
                adjust
            )
            self._set_cache(cache_key, df)
            result[ts_code] = df.copy()

        logger.debug(f"批量查询处理完成: {len(df_dict)} 只股票")
        return result

    def get_index_data(
        self,
        ts_code: str = "000300.SH",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """获取指数日线数据（沪深300等），使用LRU缓存

        Args:
            ts_code: 指数代码，默认沪深300
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            包含指数日线数据的DataFrame

        Raises:
            MissingDataError: 未找到指数数据
            DatabaseError: 数据库连接异常
        """
        cache_key = self._get_cache_key(
            "index", ts_code,
            start_date.strftime('%Y%m%d') if start_date else "all",
            end_date.strftime('%Y%m%d') if end_date else "all"
        )

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug(f"指数缓存命中: {ts_code}")
            return cached.copy()

        sql = """
            SELECT
                ts_code, trade_date, open, high, low, close,
                pre_close, `change`, pct_chg, vol, amount
            FROM t_index_dailymarketdata
            WHERE ts_code = %s
        """
        params: List[Any] = [ts_code]

        if start_date:
            sql += " AND trade_date >= %s"
            params.append(start_date.strftime('%Y%m%d'))
        if end_date:
            sql += " AND trade_date <= %s"
            params.append(end_date.strftime('%Y%m%d'))

        sql += " ORDER BY trade_date ASC"

        try:
            results = DatabaseManager.fetchall(self.db_name, sql, tuple(params))
        except Exception as e:
            logger.error(f"获取指数数据失败 {ts_code}: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        if not results:
            raise MissingDataError(
                f"指数 {ts_code} 无数据",
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df = df.set_index('trade_date')
        df = df.sort_index()

        self._set_cache(cache_key, df)
        logger.debug(f"指数数据已缓存: {ts_code}, {len(results)} 条记录")
        return df.copy()

    def get_st_stocks(self, date: datetime) -> Set[str]:
        """获取指定日期的ST股票列表，使用缓存

        Args:
            date: 查询日期

        Returns:
            ST股票代码集合

        Raises:
            DatabaseError: 数据库连接异常
        """
        cache_key = self._get_cache_key("st", date.strftime('%Y%m%d'))
        cached = self._stock_info_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"ST列表缓存命中: {date.strftime('%Y%m%d')}")
            return cached

        date_str = date.strftime('%Y%m%d')
        sql = """
            SELECT ts_code
            FROM t_stock_st_list
            WHERE start_date <= %s
              AND (end_date >= %s OR end_date IS NULL OR end_date = '')
        """
        try:
            results = DatabaseManager.fetchall(self.db_name, sql, (date_str, date_str))
        except Exception as e:
            logger.error(f"获取ST列表失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        st_set: Set[str] = set(r['ts_code'] for r in results)
        self._stock_info_cache[cache_key] = st_set
        logger.debug(f"ST列表已缓存: {date_str}, 共 {len(st_set)} 只")
        return st_set

    def get_all_stocks(self, date: datetime) -> List[str]:
        """获取指定日期有交易数据的所有股票列表

        Args:
            date: 查询日期

        Returns:
            股票代码列表

        Raises:
            DatabaseError: 数据库连接异常
        """
        date_str = date.strftime('%Y%m%d')
        sql = """
            SELECT DISTINCT ts_code
            FROM t_stock_dailymarketdata
            WHERE trade_date = %s
        """
        try:
            results = DatabaseManager.fetchall(self.db_name, sql, (date_str,))
        except Exception as e:
            logger.error(f"获取全市场股票列表失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        stocks = [r['ts_code'] for r in results]
        logger.debug(f"全市场股票数量: {len(stocks)} ({date_str})")
        return stocks

    def get_batch_stock_info(self, ts_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取股票基本信息

        Args:
            ts_codes: 股票代码列表

        Returns:
            {ts_code: info_dict} 股票信息字典

        Raises:
            DatabaseError: 数据库连接异常
        """
        result: Dict[str, Dict[str, Any]] = {}
        missing_codes = [c for c in ts_codes if c not in self._stock_info_cache]

        # 返回缓存的数据
        for ts_code in ts_codes:
            if ts_code in self._stock_info_cache:
                result[ts_code] = self._stock_info_cache[ts_code]

        cache_hit = len(ts_codes) - len(missing_codes)
        if cache_hit > 0:
            logger.debug(f"股票信息缓存命中: {cache_hit}/{len(ts_codes)}")

        if not missing_codes:
            return result

        # 批量查询
        placeholders = ','.join(['%s'] * len(missing_codes))
        sql = f"""
            SELECT ts_code, name, industry, market, area
            FROM t_stock_basic
            WHERE ts_code IN ({placeholders})
        """
        try:
            results = DatabaseManager.fetchall(self.db_name, sql, tuple(missing_codes))
        except Exception as e:
            logger.error(f"批量获取股票信息失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        for r in results:
            self._stock_info_cache[r['ts_code']] = r
            result[r['ts_code']] = r

        logger.debug(f"批量获取股票信息: {len(results)}/{len(missing_codes)} 只")
        return result

    def get_stock_info(self, ts_code: str) -> Dict[str, Any]:
        """获取单个股票基本信息

        Args:
            ts_code: 股票代码

        Returns:
            股票信息字典，如果未找到返回空字典
        """
        if ts_code in self._stock_info_cache:
            return self._stock_info_cache[ts_code]

        sql = """
            SELECT ts_code, name, industry, market, area
            FROM t_stock_basic
            WHERE ts_code = %s
        """
        try:
            result = DatabaseManager.fetchone(self.db_name, sql, (ts_code,))
        except Exception as e:
            logger.error(f"获取股票信息失败 {ts_code}: {e}")
            return {}

        if result:
            self._stock_info_cache[ts_code] = result
        return result or {}

    def get_market_data_for_date(
        self,
        date: datetime,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取指定日期的全市场数据

        Args:
            date: 查询日期
            fields: 字段列表，默认常用字段

        Returns:
            包含市场数据的DataFrame

        Raises:
            DatabaseError: 数据库连接异常
        """
        date_str = date.strftime('%Y%m%d')

        if fields is None:
            fields = ['ts_code', 'open', 'high', 'low', 'close',
                     'pre_close', 'vol', 'amount', 'pct_chg']

        sql = f"""
            SELECT {', '.join(fields)}
            FROM t_stock_dailymarketdata
            WHERE trade_date = %s
        """
        try:
            results = DatabaseManager.fetchall(self.db_name, sql, (date_str,))
        except Exception as e:
            logger.error(f"获取市场数据失败 {date_str}: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        if not results:
            logger.warning(f"无市场数据: {date_str}")
            return pd.DataFrame()

        logger.debug(f"获取市场数据: {date_str}, {len(results)} 只股票")
        return pd.DataFrame(results)

    def get_batch_market_data(
        self,
        dates: List[datetime],
        fields: Optional[List[str]] = None
    ) -> Dict[datetime, pd.DataFrame]:
        """
        批量获取多个日期的市场数据

        Args:
            dates: 日期列表
            fields: 字段列表

        Returns:
            {date: DataFrame} 字典

        Raises:
            DatabaseError: 数据库连接异常
        """
        if not dates:
            return {}

        if fields is None:
            fields = ['ts_code', 'open', 'high', 'low', 'close',
                     'pre_close', 'vol', 'amount', 'pct_chg']

        date_strs = [d.strftime('%Y%m%d') for d in dates]
        placeholders = ','.join(['%s'] * len(date_strs))

        sql = f"""
            SELECT trade_date, {', '.join(fields)}
            FROM t_stock_dailymarketdata
            WHERE trade_date IN ({placeholders})
        """
        try:
            results = DatabaseManager.fetchall(self.db_name, sql, tuple(date_strs))
        except Exception as e:
            logger.error(f"批量获取市场数据失败: {e}")
            raise DatabaseError(f"数据库查询失败: {e}") from e

        result_dict: Dict[datetime, pd.DataFrame] = {d: pd.DataFrame() for d in dates}

        if not results:
            logger.warning(f"批量市场数据无结果: {len(dates)} 个日期")
            return result_dict

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

        for date in dates:
            date_data = df[df['trade_date'] == date]
            if not date_data.empty:
                result_dict[date] = date_data.drop(columns=['trade_date'])

        logger.debug(f"批量市场数据: {len(results)} 条记录，{len(dates)} 个日期")
        return result_dict

    def check_data_integrity(
        self,
        ts_code: str,
        start_date: datetime,
        end_date: datetime,
        trade_dates: List[datetime]
    ) -> Tuple[bool, List[datetime]]:
        """检查股票数据完整性

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            trade_dates: 期望的交易日列表

        Returns:
            (是否完整, 缺失日期列表)
        """
        try:
            df = self.get_stock_data(ts_code, start_date, end_date, adjust=False)
            actual_dates = set(pd.Timestamp(d).normalize() for d in df.index)
            expected_dates = set(pd.Timestamp(d).normalize() for d in trade_dates)
            missing_dates = expected_dates - actual_dates

            if missing_dates:
                return False, sorted(list(missing_dates))
            return True, []
        except MissingDataError:
            logger.warning(f"数据完整性检查失败: {ts_code} 无数据")
            return False, trade_dates
        except Exception as e:
            logger.error(f"数据完整性检查异常 {ts_code}: {e}")
            return False, trade_dates

    def validate_data_requirements(
        self,
        stock_list: List[str],
        start_date: datetime,
        end_date: datetime,
        min_data_ratio: float = 0.95
    ) -> Tuple[List[str], Dict[str, List[datetime]]]:
        """验证多只股票的数据完整性

        Args:
            stock_list: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            min_data_ratio: 最小数据比例要求

        Returns:
            (有效股票列表, 缺失数据字典)
        """
        trade_dates = self.get_trade_dates(start_date, end_date)
        valid_stocks: List[str] = []
        missing_data: Dict[str, List[datetime]] = {}

        for ts_code in stock_list:
            is_complete, missing = self.check_data_integrity(
                ts_code, start_date, end_date, trade_dates
            )

            data_ratio = 1 - len(missing) / len(trade_dates) if trade_dates else 0

            if data_ratio >= min_data_ratio:
                valid_stocks.append(ts_code)
                if missing:
                    missing_data[ts_code] = missing
            else:
                missing_data[ts_code] = missing
                logger.debug(f"数据不足剔除: {ts_code}, 完整率 {data_ratio:.1%}")

        logger.info(f"数据完整性验证: {len(valid_stocks)}/{len(stock_list)} 只股票通过")
        return valid_stocks, missing_data

    def get_prev_trade_date(self, date: datetime, n: int = 1) -> Optional[datetime]:
        """获取前N个交易日

        Args:
            date: 当前日期
            n: 回退天数

        Returns:
            前N个交易日，如果不存在返回None
        """
        if not self._trade_dates:
            return None

        # 支持 datetime 和 pd.Timestamp
        date_normalized = pd.Timestamp(date).normalize()
        valid_dates = [d for d in self._trade_dates if pd.Timestamp(d).normalize() < date_normalized]

        if len(valid_dates) >= n:
            return valid_dates[-n]
        return None

    def get_next_trade_date(self, date: datetime, n: int = 1) -> Optional[datetime]:
        """获取后N个交易日

        Args:
            date: 当前日期
            n: 前进天数

        Returns:
            后N个交易日，如果不存在返回None
        """
        if not self._trade_dates:
            return None

        # 支持 datetime 和 pd.Timestamp
        date_normalized = pd.Timestamp(date).normalize()
        valid_dates = [d for d in self._trade_dates if pd.Timestamp(d).normalize() > date_normalized]

        if len(valid_dates) >= n:
            return valid_dates[n - 1]
        return None


class DatabaseError(Exception):
    """数据库连接异常

    Attributes:
        message: 错误消息
        original_error: 原始异常
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_error = original_error

    def __str__(self) -> str:
        if self.original_error:
            return f"{self.message} (原始错误: {self.original_error})"
        return self.message
