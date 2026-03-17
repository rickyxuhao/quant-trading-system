"""
股票池选择器 - 支持多种选股标准和动态筛选

功能：
- 指数成分股筛选（CSI 300, CSI 500, CSI 1000等）
- 行业/板块筛选
- 流动性筛选
- 质量筛选（去除ST、停牌、新股）
- 动态股票池构建
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime
from enum import Enum, auto
from abc import ABC, abstractmethod
import logging

import pandas as pd
import numpy as np

from core.logger import get_logger

logger = get_logger(__name__)


class UniverseType(Enum):
    """股票池类型"""
    CSI_300 = "csi300"  # 沪深300
    CSI_500 = "csi500"  # 中证500
    CSI_1000 = "csi1000"  # 中证1000
    CSI_2000 = "csi2000"  # 中证2000
    CSI_ALL = "csi_all"  # 全A股（非ST）
    SECTOR_SPECIFIC = "sector"  # 特定行业
    CUSTOM = "custom"  # 自定义


@dataclass
class UniverseConfig:
    """股票池配置"""

    universe_type: UniverseType = UniverseType.CSI_ALL

    # 基础筛选
    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_new_listing: bool = True
    min_listing_days: int = 60

    # 流动性筛选
    min_avg_volume: float = 1e6  # 最小日均成交量
    min_avg_amount: float = 1e7  # 最小日均成交额
    lookback_days: int = 20

    # 市值筛选
    min_market_cap: float = 5e8  # 最小市值5亿
    max_market_cap: Optional[float] = None

    # 行业筛选
    include_industries: Optional[List[str]] = None
    exclude_industries: Optional[List[str]] = None

    # 特定行业配置（当universe_type=SECTOR_SPECIFIC时）
    target_sectors: List[str] = field(default_factory=list)

    # 自定义股票列表（当universe_type=CUSTOM时）
    custom_stocks: List[str] = field(default_factory=list)

    # 动态调整
    dynamic_rebalance: bool = True
    rebalance_frequency: str = "monthly"  # daily, weekly, monthly


class BaseUniverseSelector(ABC):
    """股票池选择器基类"""

    def __init__(self, config: UniverseConfig):
        self.config = config

    @abstractmethod
    def select(
        self, date: datetime, data_manager: Optional[Any] = None
    ) -> List[str]:
        """选择股票池"""
        pass

    def filter_quality(
        self,
        date: datetime,
        stock_pool: List[str],
        data_manager: Any,
    ) -> List[str]:
        """质量筛选（去除ST、停牌、新股）"""
        filtered = stock_pool.copy()

        # 去除ST股票
        if self.config.exclude_st:
            st_stocks = data_manager.get_st_stocks(date)
            filtered = [s for s in filtered if s not in st_stocks]

        # 去除停牌股票
        if self.config.exclude_suspended:
            try:
                market_data = data_manager.get_market_data_for_date(date, ["ts_code", "vol"])
                trading_stocks = set(market_data[market_data["vol"] > 0]["ts_code"].tolist())
                filtered = [s for s in filtered if s in trading_stocks]
            except Exception as e:
                logger.warning(f"Failed to filter suspended stocks: {e}")

        # 去除新股
        if self.config.exclude_new_listing:
            filtered = self._filter_new_listing(date, filtered, data_manager)

        return filtered

    def filter_liquidity(
        self,
        date: datetime,
        stock_pool: List[str],
        data_manager: Any,
    ) -> List[str]:
        """流动性筛选"""
        if self.config.min_avg_volume <= 0 and self.config.min_avg_amount <= 0:
            return stock_pool

        lookback_start = date - pd.Timedelta(days=self.config.lookback_days * 2)

        try:
            batch_data = data_manager.get_batch_stock_data(
                stock_pool, lookback_start, date, adjust=False
            )
        except Exception as e:
            logger.warning(f"Failed to get data for liquidity filter: {e}")
            return stock_pool

        qualified = []
        for ts_code, df in batch_data.items():
            if len(df) < self.config.lookback_days * 0.8:
                continue

            df = df.tail(self.config.lookback_days)
            avg_volume = df["vol"].mean()
            avg_amount = df["amount"].mean()

            if (
                avg_volume >= self.config.min_avg_volume
                and avg_amount >= self.config.min_avg_amount
            ):
                qualified.append(ts_code)

        return qualified

    def filter_market_cap(
        self,
        date: datetime,
        stock_pool: List[str],
        data_manager: Any,
    ) -> List[str]:
        """市值筛选"""
        try:
            market_data = data_manager.get_market_data_for_date(
                date, ["ts_code", "total_mv"]
            )

            if market_data.empty:
                return stock_pool

            market_data = market_data[market_data["ts_code"].isin(stock_pool)]

            # 转换市值单位（数据库通常是万元）
            if self.config.min_market_cap > 0:
                min_mv = self.config.min_market_cap / 10000  # 转换为万元
                market_data = market_data[market_data["total_mv"] >= min_mv]

            if self.config.max_market_cap is not None:
                max_mv = self.config.max_market_cap / 10000
                market_data = market_data[market_data["total_mv"] <= max_mv]

            return market_data["ts_code"].tolist()

        except Exception as e:
            logger.warning(f"Failed to filter by market cap: {e}")
            return stock_pool

    def filter_industry(
        self,
        stock_pool: List[str],
        data_manager: Any,
    ) -> List[str]:
        """行业筛选"""
        if not self.config.include_industries and not self.config.exclude_industries:
            return stock_pool

        try:
            stock_info = data_manager.get_batch_stock_info(stock_pool)

            filtered = []
            for ts_code in stock_pool:
                if ts_code not in stock_info:
                    continue

                industry = stock_info[ts_code].get("industry", "")

                # 包含筛选
                if self.config.include_industries:
                    if industry not in self.config.include_industries:
                        continue

                # 排除筛选
                if self.config.exclude_industries:
                    if industry in self.config.exclude_industries:
                        continue

                filtered.append(ts_code)

            return filtered

        except Exception as e:
            logger.warning(f"Failed to filter by industry: {e}")
            return stock_pool

    def _filter_new_listing(
        self, date: datetime, stock_pool: List[str], data_manager: Any
    ) -> List[str]:
        """过滤新股"""
        lookback_start = date - pd.Timedelta(days=self.config.min_listing_days * 3)

        try:
            batch_data = data_manager.get_batch_stock_data(
                stock_pool, lookback_start, date, adjust=False
            )

            result = []
            for ts_code, df in batch_data.items():
                if len(df) >= self.config.min_listing_days:
                    result.append(ts_code)

            return result

        except Exception as e:
            logger.warning(f"Failed to filter new listings: {e}")
            return stock_pool


class IndexUniverseSelector(BaseUniverseSelector):
    """指数成分股选择器"""

    INDEX_CODES = {
        UniverseType.CSI_300: "000300.SH",
        UniverseType.CSI_500: "000905.SH",
        UniverseType.CSI_1000: "000852.SH",
        UniverseType.CSI_2000: "932000.CSI",
    }

    def select(
        self, date: datetime, data_manager: Optional[Any] = None
    ) -> List[str]:
        """选择指数成分股"""
        if data_manager is None:
            logger.error("DataManager is required for index universe selection")
            return []

        # 获取指数成分股
        index_code = self.INDEX_CODES.get(self.config.universe_type)
        if index_code is None:
            logger.error(f"Unknown index type: {self.config.universe_type}")
            return []

        try:
            constituents = self._fetch_index_constituents(index_code, date, data_manager)
        except Exception as e:
            logger.error(f"Failed to fetch index constituents: {e}")
            return []

        # 应用质量筛选
        constituents = self.filter_quality(date, constituents, data_manager)

        # 应用流动性筛选
        constituents = self.filter_liquidity(date, constituents, data_manager)

        # 应用市值筛选
        constituents = self.filter_market_cap(date, constituents, data_manager)

        # 应用行业筛选
        constituents = self.filter_industry(constituents, data_manager)

        logger.info(
            f"Index universe {self.config.universe_type.value}: "
            f"selected {len(constituents)} stocks on {date.strftime('%Y%m%d')}"
        )

        return constituents

    def _fetch_index_constituents(
        self, index_code: str, date: datetime, data_manager: Any
    ) -> List[str]:
        """获取指数成分股列表"""
        try:
            from core.storage.relational.connection import DatabaseManager

            date_str = date.strftime("%Y%m%d")

            # 尝试获取指定日期的成分股
            sql = """
                SELECT con_code as ts_code
                FROM t_index_weight
                WHERE index_code = %s AND trade_date = %s
            """

            results = DatabaseManager.fetchall("tushare_biz", sql, (index_code, date_str))

            if results:
                return [r["ts_code"] for r in results]

            # 如果没有精确匹配，获取最近的
            sql_recent = """
                SELECT con_code as ts_code
                FROM t_index_weight
                WHERE index_code = %s AND trade_date <= %s
                ORDER BY trade_date DESC
                LIMIT 300
            """

            results = DatabaseManager.fetchall(
                "tushare_biz", sql_recent, (index_code, date_str)
            )

            if results:
                # 去重
                stocks = list(set([r["ts_code"] for r in results]))
                return stocks

        except Exception as e:
            logger.error(f"Error fetching index constituents: {e}")

        return []


class AllAShareSelector(BaseUniverseSelector):
    """全A股选择器（去除ST）"""

    def select(
        self, date: datetime, data_manager: Optional[Any] = None
    ) -> List[str]:
        """选择全A股"""
        if data_manager is None:
            logger.error("DataManager is required for all A-share selection")
            return []

        # 获取当日所有股票
        try:
            all_stocks = data_manager.get_all_stocks(date)
        except Exception as e:
            logger.error(f"Failed to get all stocks: {e}")
            return []

        # 应用质量筛选
        all_stocks = self.filter_quality(date, all_stocks, data_manager)

        # 应用流动性筛选
        all_stocks = self.filter_liquidity(date, all_stocks, data_manager)

        # 应用市值筛选
        all_stocks = self.filter_market_cap(date, all_stocks, data_manager)

        # 应用行业筛选
        all_stocks = self.filter_industry(all_stocks, data_manager)

        logger.info(
            f"All A-share universe: selected {len(all_stocks)} stocks "
            f"on {date.strftime('%Y%m%d')}"
        )

        return all_stocks


class SectorUniverseSelector(BaseUniverseSelector):
    """行业特定股票池选择器"""

    def select(
        self, date: datetime, data_manager: Optional[Any] = None
    ) -> List[str]:
        """选择特定行业股票"""
        if data_manager is None:
            logger.error("DataManager is required for sector universe selection")
            return []

        if not self.config.target_sectors:
            logger.error("target_sectors must be specified for sector universe")
            return []

        # 获取当日所有股票
        try:
            all_stocks = data_manager.get_all_stocks(date)
        except Exception as e:
            logger.error(f"Failed to get all stocks: {e}")
            return []

        # 获取行业信息
        stock_info = data_manager.get_batch_stock_info(all_stocks)

        # 筛选目标行业
        sector_stocks = [
            ts_code
            for ts_code, info in stock_info.items()
            if info.get("industry") in self.config.target_sectors
        ]

        # 应用质量筛选
        sector_stocks = self.filter_quality(date, sector_stocks, data_manager)

        # 应用流动性筛选
        sector_stocks = self.filter_liquidity(date, sector_stocks, data_manager)

        # 应用市值筛选
        sector_stocks = self.filter_market_cap(date, sector_stocks, data_manager)

        logger.info(
            f"Sector universe {self.config.target_sectors}: "
            f"selected {len(sector_stocks)} stocks on {date.strftime('%Y%m%d')}"
        )

        return sector_stocks


class CustomUniverseSelector(BaseUniverseSelector):
    """自定义股票池选择器"""

    def select(
        self, date: datetime, data_manager: Optional[Any] = None
    ) -> List[str]:
        """选择自定义股票池"""
        if not self.config.custom_stocks:
            logger.error("custom_stocks must be specified for custom universe")
            return []

        stocks = self.config.custom_stocks.copy()

        if data_manager:
            # 应用质量筛选
            stocks = self.filter_quality(date, stocks, data_manager)

            # 应用流动性筛选
            stocks = self.filter_liquidity(date, stocks, data_manager)

        logger.info(
            f"Custom universe: selected {len(stocks)} stocks on {date.strftime('%Y%m%d')}"
        )

        return stocks


class DynamicUniverseSelector:
    """
    动态股票池选择器

    支持定期调整股票池，并缓存结果
    """

    def __init__(
        self,
        config: UniverseConfig,
        data_manager: Any,
        rebalance_frequency: str = "monthly",
    ):
        self.config = config
        self.data_manager = data_manager
        self.rebalance_frequency = rebalance_frequency

        # 选择底层选择器
        self.selector = self._create_selector(config)

        # 缓存
        self._universe_cache: Dict[str, List[str]] = {}
        self._last_rebalance_date: Optional[datetime] = None

    def _create_selector(self, config: UniverseConfig) -> BaseUniverseSelector:
        """创建底层选择器"""
        if config.universe_type in IndexUniverseSelector.INDEX_CODES:
            return IndexUniverseSelector(config)
        elif config.universe_type == UniverseType.CSI_ALL:
            return AllAShareSelector(config)
        elif config.universe_type == UniverseType.SECTOR_SPECIFIC:
            return SectorUniverseSelector(config)
        elif config.universe_type == UniverseType.CUSTOM:
            return CustomUniverseSelector(config)
        else:
            raise ValueError(f"Unknown universe type: {config.universe_type}")

    def get_universe(self, date: datetime) -> List[str]:
        """获取指定日期的股票池"""
        cache_key = date.strftime("%Y%m%d")

        # 检查缓存
        if cache_key in self._universe_cache:
            return self._universe_cache[cache_key]

        # 检查是否需要重新平衡
        if self._should_rebalance(date):
            universe = self.selector.select(date, self.data_manager)
            self._universe_cache[cache_key] = universe
            self._last_rebalance_date = date
        else:
            # 使用最近的股票池
            if self._last_rebalance_date:
                last_key = self._last_rebalance_date.strftime("%Y%m%d")
                universe = self._universe_cache.get(last_key, [])
            else:
                universe = self.selector.select(date, self.data_manager)
                self._universe_cache[cache_key] = universe
                self._last_rebalance_date = date

        return universe

    def _should_rebalance(self, date: datetime) -> bool:
        """判断是否需要重新平衡"""
        if self._last_rebalance_date is None:
            return True

        if self.rebalance_frequency == "daily":
            return date != self._last_rebalance_date

        elif self.rebalance_frequency == "weekly":
            return date.isocalendar()[1] != self._last_rebalance_date.isocalendar()[1]

        elif self.rebalance_frequency == "monthly":
            return date.month != self._last_rebalance_date.month

        return True

    def clear_cache(self):
        """清除缓存"""
        self._universe_cache.clear()
        self._last_rebalance_date = None


class UniverseFilter:
    """
    股票池过滤器

    提供额外的过滤条件
    """

    def __init__(self, data_manager: Any):
        self.data_manager = data_manager

    def filter_by_price_limit(
        self,
        date: datetime,
        stock_pool: List[str],
        exclude_limit_up: bool = True,
        exclude_limit_down: bool = True,
    ) -> List[str]:
        """过滤涨跌停股票"""
        try:
            market_data = self.data_manager.get_market_data_for_date(
                date, ["ts_code", "pct_chg"]
            )

            if market_data.empty:
                return stock_pool

            result = []
            for ts_code in stock_pool:
                row = market_data[market_data["ts_code"] == ts_code]
                if row.empty:
                    continue

                pct_chg = row["pct_chg"].values[0]

                # 判断涨跌停（简化处理，考虑ST股票）
                is_limit_up = pct_chg >= 9.5
                is_limit_down = pct_chg <= -9.5

                if exclude_limit_up and is_limit_up:
                    continue
                if exclude_limit_down and is_limit_down:
                    continue

                result.append(ts_code)

            return result

        except Exception as e:
            logger.warning(f"Failed to filter by price limit: {e}")
            return stock_pool

    def filter_by_technical_signal(
        self,
        date: datetime,
        stock_pool: List[str],
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_turnover: Optional[float] = None,
    ) -> List[str]:
        """基于技术指标过滤"""
        try:
            fields = ["ts_code"]
            if min_price is not None or max_price is not None:
                fields.append("close")
            if min_turnover is not None:
                fields.append("turnover_rate")

            market_data = self.data_manager.get_market_data_for_date(date, fields)

            if market_data.empty:
                return stock_pool

            market_data = market_data[market_data["ts_code"].isin(stock_pool)]

            if min_price is not None:
                market_data = market_data[market_data["close"] >= min_price]

            if max_price is not None:
                market_data = market_data[market_data["close"] <= max_price]

            if min_turnover is not None and "turnover_rate" in market_data.columns:
                market_data = market_data[market_data["turnover_rate"] >= min_turnover]

            return market_data["ts_code"].tolist()

        except Exception as e:
            logger.warning(f"Failed to filter by technical signal: {e}")
            return stock_pool


def create_csi300_universe(
    min_market_cap: float = 5e8, exclude_st: bool = True
) -> UniverseConfig:
    """创建沪深300股票池配置"""
    return UniverseConfig(
        universe_type=UniverseType.CSI_300,
        exclude_st=exclude_st,
        exclude_suspended=True,
        exclude_new_listing=True,
        min_listing_days=60,
        min_market_cap=min_market_cap,
        min_avg_amount=1e8,  # 更高的流动性要求
        lookback_days=20,
    )


def create_csi500_universe(
    min_market_cap: float = 2e8, exclude_st: bool = True
) -> UniverseConfig:
    """创建中证500股票池配置"""
    return UniverseConfig(
        universe_type=UniverseType.CSI_500,
        exclude_st=exclude_st,
        exclude_suspended=True,
        exclude_new_listing=True,
        min_listing_days=60,
        min_market_cap=min_market_cap,
        min_avg_amount=5e7,
        lookback_days=20,
    )


def create_all_a_share_universe(
    min_market_cap: float = 5e8, exclude_st: bool = True
) -> UniverseConfig:
    """创建全A股股票池配置"""
    return UniverseConfig(
        universe_type=UniverseType.CSI_ALL,
        exclude_st=exclude_st,
        exclude_suspended=True,
        exclude_new_listing=True,
        min_listing_days=60,
        min_market_cap=min_market_cap,
        min_avg_amount=1e7,
        lookback_days=20,
    )


def create_tech_sector_universe() -> UniverseConfig:
    """创建科技行业股票池配置"""
    tech_industries = [
        "电子",
        "计算机",
        "通信",
        "传媒",
        "电力设备",
        "机械设备",
    ]

    return UniverseConfig(
        universe_type=UniverseType.SECTOR_SPECIFIC,
        target_sectors=tech_industries,
        exclude_st=True,
        exclude_suspended=True,
        exclude_new_listing=True,
        min_listing_days=60,
        min_market_cap=1e8,
        min_avg_amount=5e6,
        lookback_days=20,
    )


def create_consumption_sector_universe() -> UniverseConfig:
    """创建消费行业股票池配置"""
    consumption_industries = [
        "食品饮料",
        "医药生物",
        "家用电器",
        "商贸零售",
        "社会服务",
        "美容护理",
        "轻工制造",
        "纺织服饰",
    ]

    return UniverseConfig(
        universe_type=UniverseType.SECTOR_SPECIFIC,
        target_sectors=consumption_industries,
        exclude_st=True,
        exclude_suspended=True,
        exclude_new_listing=True,
        min_listing_days=60,
        min_market_cap=5e8,
        min_avg_amount=1e7,
        lookback_days=20,
    )
