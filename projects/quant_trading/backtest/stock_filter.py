"""
前置筛选模块 - 负责股票池过滤（去ST、板块筛选、流动性筛选）
支持板块筛选和预设配置
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Set, Optional, Callable, Dict
from enum import Enum
import logging

import pandas as pd

from projects.quant_trading.backtest.data_manager import DataManager

# 配置日志
logger = logging.getLogger(__name__)


class Sector(Enum):
    """板块枚举"""

    MAIN_BOARD = "主板"  # 主板
    GEM = "创业板"  # 创业板
    STAR_MARKET = "科创板"  # 科创板
    NORTH_BOUND = "北交所"  # 北交所


class Industry(Enum):
    """行业枚举（申万一级行业示例）"""

    BANK = "银行"
    NON_BANK_FINANCE = "非银金融"
    REAL_ESTATE = "房地产"
    STEEL = "钢铁"
    COAL = "煤炭"
    PETROLEUM = "石油石化"
    CHEMICAL = "基础化工"
    BUILDING_MATERIALS = "建筑材料"
    CONSTRUCTION = "建筑装饰"
    ELECTRICAL_EQUIPMENT = "电力设备"
    MACHINERY = "机械设备"
    DEFENSE = "国防军工"
    AUTOMOBILE = "汽车"
    ELECTRONICS = "电子"
    COMPUTER = "计算机"
    COMMUNICATION = "通信"
    MEDIA = "传媒"
    FOOD_BEVERAGE = "食品饮料"
    PHARMACEUTICAL = "医药生物"
    AGRICULTURE = "农林牧渔"
    TEXTILE_APPAREL = "纺织服饰"
    LIGHT_INDUSTRY = "轻工制造"
    HOME_APPLIANCES = "家用电器"
    RETAIL = "商贸零售"
    SOCIAL_SERVICES = "社会服务"
    BEAUTY_CARE = "美容护理"
    ENVIRONMENTAL = "环保"
    UTILITIES = "公用事业"
    TRANSPORTATION = "交通运输"


@dataclass
class FilterCriteria:
    """筛选条件配置

    Attributes:
        exclude_st: 是否排除ST股票
        exclude_suspended: 是否排除停牌股票
        exclude_new_listing: 是否排除新股
        min_listing_days: 最小上市天数
        min_market_cap: 最小市值（元）
        max_market_cap: 最大市值（元）
        min_avg_volume: 最小日均成交量
        min_avg_amount: 最小日均成交额
        lookback_days: 计算平均值的回看天数
        industries: 限定行业列表
        industries_exclude: 排除行业列表
        sectors: 限定板块列表
        markets: 限定市场列表
        concept_stocks: 限定概念股票列表
        price_min: 最低价格
        price_max: 最高价格
        turn_over_min: 最低换手率
        turn_over_max: 最高换手率
    """

    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_new_listing: bool = True
    min_listing_days: int = 60
    min_market_cap: float = 1e8
    max_market_cap: Optional[float] = None
    min_avg_volume: float = 1e6
    min_avg_amount: float = 1e7
    lookback_days: int = 20
    industries: Optional[List[str]] = None
    industries_exclude: Optional[List[str]] = None
    sectors: Optional[List[Sector]] = None
    markets: Optional[List[str]] = None
    concept_stocks: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    turn_over_min: Optional[float] = None
    turn_over_max: Optional[float] = None


@dataclass
class FilterConfig:
    """筛选配置预设"""

    name: str
    criteria: FilterCriteria
    description: str = ""


class StockFilter:
    """股票过滤器 - 负责根据各种条件筛选股票池

    Attributes:
        data_manager: 数据管理器实例
        _st_cache: ST股票缓存
        _liquidity_cache: 流动性数据缓存
        _new_listing_cache: 新股缓存
    """

    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self._st_cache: Dict[datetime, Set[str]] = {}
        self._liquidity_cache: Dict[str, pd.DataFrame] = {}
        self._new_listing_cache: Dict[datetime, Set[str]] = {}

    def filter_stocks(
        self, date: datetime, stock_pool: List[str], criteria: FilterCriteria
    ) -> List[str]:
        """根据条件筛选股票

        Args:
            date: 筛选日期
            stock_pool: 初始股票池
            criteria: 筛选条件

        Returns:
            筛选后的股票代码列表
        """
        """根据条件筛选股票"""
        filtered = stock_pool.copy()

        # 1. 排除ST股票
        if criteria.exclude_st:
            filtered = self._filter_st(date, filtered)

        # 2. 排除停牌股票
        if criteria.exclude_suspended:
            filtered = self._filter_suspended(date, filtered)

        # 3. 排除新股
        if criteria.exclude_new_listing:
            filtered = self._filter_new_listing(date, filtered, criteria.min_listing_days)

        # 4. 流动性筛选
        if criteria.min_avg_volume > 0 or criteria.min_avg_amount > 0:
            filtered = self._filter_liquidity(date, filtered, criteria)

        # 5. 行业筛选（包含）
        if criteria.industries is not None:
            filtered = self._filter_by_industry(filtered, criteria.industries)

        # 6. 行业筛选（排除）
        if criteria.industries_exclude is not None:
            filtered = self._filter_by_industry_exclude(filtered, criteria.industries_exclude)

        # 7. 板块筛选
        if criteria.sectors is not None:
            filtered = self._filter_by_sector(filtered, criteria.sectors)

        # 8. 市场筛选
        if criteria.markets is not None:
            filtered = self._filter_by_market(filtered, criteria.markets)

        # 9. 市值筛选
        filtered = self._filter_by_market_cap(date, filtered, criteria)

        # 10. 价格筛选
        filtered = self._filter_by_price(date, filtered, criteria)

        # 11. 换手率筛选
        filtered = self._filter_by_turnover(date, filtered, criteria)

        logger.debug(
            f"股票筛选完成: {date.strftime('%Y%m%d')} "
            f"初始{len(stock_pool)}只 -> 筛选后{len(filtered)}只"
        )
        return filtered

    def _filter_st(self, date: datetime, stocks: List[str]) -> List[str]:
        """排除ST股票

        Args:
            date: 筛选日期
            stocks: 股票列表

        Returns:
            非ST股票列表
        """
        if date not in self._st_cache:
            self._st_cache[date] = self.data_manager.get_st_stocks(date)

        st_stocks = self._st_cache[date]
        filtered = [s for s in stocks if s not in st_stocks]
        if len(filtered) < len(stocks):
            logger.debug(f"排除ST股票: {len(stocks) - len(filtered)} 只")
        return filtered

    def _filter_suspended(self, date: datetime, stocks: List[str]) -> List[str]:
        """排除停牌股票

        Args:
            date: 筛选日期
            stocks: 股票列表

        Returns:
            非停牌股票列表
        """
        try:
            df = self.data_manager.get_market_data_for_date(date, ["ts_code", "vol"])
        except Exception as e:
            logger.warning(f"获取市场数据失败: {e}，返回空列表")
            return []

        if df.empty:
            logger.warning(f"无市场数据: {date.strftime('%Y%m%d')}")
            return []

        trading_stocks = set(df[df["vol"] > 0]["ts_code"].tolist())
        filtered = [s for s in stocks if s in trading_stocks]
        if len(filtered) < len(stocks):
            logger.debug(f"排除停牌股票: {len(stocks) - len(filtered)} 只")
        return filtered

    def _filter_new_listing(
        self, date: datetime, stocks: List[str], min_listing_days: int
    ) -> List[str]:
        """排除新股（上市天数不足）

        Args:
            date: 筛选日期
            stocks: 股票列表
            min_listing_days: 最小上市天数

        Returns:
            非新股列表
        """
        # 使用批量查询优化性能
        lookback_start = date - pd.Timedelta(days=min_listing_days * 3)

        try:
            batch_data = self.data_manager.get_batch_stock_data(
                stocks, lookback_start, date, adjust=False
            )
        except Exception as e:
            logger.warning(f"批量获取股票数据失败: {e}，跳过新股筛选")
            return stocks

        result = []
        for ts_code, df in batch_data.items():
            if len(df) >= min_listing_days:
                result.append(ts_code)

        if len(result) < len(stocks):
            logger.debug(f"排除新股: {len(stocks) - len(result)} 只")
        return result

    def _filter_liquidity(
        self, date: datetime, stocks: List[str], criteria: FilterCriteria
    ) -> List[str]:
        """根据流动性筛选 - 使用批量查询优化

        Args:
            date: 筛选日期
            stocks: 股票列表
            criteria: 筛选条件

        Returns:
            满足流动性条件的股票列表
        """
        lookback_start = date - pd.Timedelta(days=criteria.lookback_days * 2)

        # 批量获取数据
        try:
            batch_data = self.data_manager.get_batch_stock_data(
                stocks, lookback_start, date, adjust=False
            )
        except Exception as e:
            logger.warning(f"批量获取流动性数据失败: {e}，跳过流动性筛选")
            return stocks

        qualified_stocks = []
        for ts_code, df in batch_data.items():
            if len(df) < criteria.lookback_days * 0.8:
                continue

            df = df.tail(criteria.lookback_days)
            avg_volume = df["vol"].mean()
            avg_amount = df["amount"].mean()

            if avg_volume >= criteria.min_avg_volume and avg_amount >= criteria.min_avg_amount:
                qualified_stocks.append(ts_code)

        if len(qualified_stocks) < len(stocks):
            logger.debug(f"流动性筛选: {len(stocks)} -> {len(qualified_stocks)} 只")
        return qualified_stocks

    def _filter_by_industry(self, stocks: List[str], industries: List[str]) -> List[str]:
        """按行业筛选（包含）

        Args:
            stocks: 股票列表
            industries: 目标行业列表

        Returns:
            属于目标行业的股票列表
        """
        info_dict = self.data_manager.get_batch_stock_info(stocks)
        filtered = [
            s for s in stocks if s in info_dict and info_dict[s].get("industry") in industries
        ]
        logger.debug(f"行业筛选: {len(stocks)} -> {len(filtered)} 只")
        return filtered

    def _filter_by_industry_exclude(self, stocks: List[str], industries: List[str]) -> List[str]:
        """按行业筛选（排除）

        Args:
            stocks: 股票列表
            industries: 要排除的行业列表

        Returns:
            不属于排除行业的股票列表
        """
        info_dict = self.data_manager.get_batch_stock_info(stocks)
        filtered = [
            s
            for s in stocks
            if s not in info_dict or info_dict[s].get("industry") not in industries
        ]
        if len(filtered) < len(stocks):
            logger.debug(f"排除行业: {len(stocks) - len(filtered)} 只")
        return filtered

    def _filter_by_sector(self, stocks: List[str], sectors: List[Sector]) -> List[str]:
        """按板块筛选

        Args:
            stocks: 股票列表
            sectors: 目标板块列表

        Returns:
            属于目标板块的股票列表
        """
        sector_names = [s.value for s in sectors]
        info_dict = self.data_manager.get_batch_stock_info(stocks)

        result = []
        for ts_code in stocks:
            if ts_code not in info_dict:
                continue
            info = info_dict[ts_code]
            market = info.get("market", "")
            # 根据market字段判断板块
            if "科创板" in sector_names and market == "科创板":
                result.append(ts_code)
            elif "创业板" in sector_names and market == "创业板":
                result.append(ts_code)
            elif "主板" in sector_names and market in ["主板", "深圳主板", "上海主板"]:
                result.append(ts_code)
            elif "北交所" in sector_names and market == "北交所":
                result.append(ts_code)
        logger.debug(f"板块筛选: {len(stocks)} -> {len(result)} 只")
        return result

    def _filter_by_market(self, stocks: List[str], markets: List[str]) -> List[str]:
        """按市场筛选

        Args:
            stocks: 股票列表
            markets: 目标市场列表

        Returns:
            属于目标市场的股票列表
        """
        info_dict = self.data_manager.get_batch_stock_info(stocks)
        filtered = [s for s in stocks if s in info_dict and info_dict[s].get("market") in markets]
        logger.debug(f"市场筛选: {len(stocks)} -> {len(filtered)} 只")
        return filtered

    def _filter_by_market_cap(
        self, date: datetime, stocks: List[str], criteria: FilterCriteria
    ) -> List[str]:
        """按市值筛选

        Args:
            date: 筛选日期
            stocks: 股票列表
            criteria: 筛选条件

        Returns:
            满足市值条件的股票列表
        """
        try:
            df = self.data_manager.get_market_data_for_date(
                date, ["ts_code", "total_mv", "circ_mv"]
            )
        except Exception as e:
            logger.warning(f"获取市值数据失败: {e}，跳过市值筛选")
            return stocks

        if df.empty:
            logger.warning(f"无市值数据: {date.strftime('%Y%m%d')}")
            return []

        df = df[df["ts_code"].isin(stocks)]

        if criteria.min_market_cap > 0:
            df = df[df["total_mv"] >= criteria.min_market_cap / 10000]  # 转换为万元

        if criteria.max_market_cap is not None:
            df = df[df["total_mv"] <= criteria.max_market_cap / 10000]

        filtered = df["ts_code"].tolist()
        logger.debug(f"市值筛选: {len(stocks)} -> {len(filtered)} 只")
        return filtered

    def _filter_by_price(
        self, date: datetime, stocks: List[str], criteria: FilterCriteria
    ) -> List[str]:
        """按价格筛选

        Args:
            date: 筛选日期
            stocks: 股票列表
            criteria: 筛选条件

        Returns:
            满足价格条件的股票列表
        """
        if criteria.price_min is None and criteria.price_max is None:
            return stocks

        try:
            df = self.data_manager.get_market_data_for_date(date, ["ts_code", "close"])
        except Exception as e:
            logger.warning(f"获取价格数据失败: {e}，跳过价格筛选")
            return stocks

        if df.empty:
            logger.warning(f"无价格数据: {date.strftime('%Y%m%d')}")
            return []

        df = df[df["ts_code"].isin(stocks)]

        if criteria.price_min is not None:
            df = df[df["close"] >= criteria.price_min]
        if criteria.price_max is not None:
            df = df[df["close"] <= criteria.price_max]

        return df["ts_code"].tolist()

    def _filter_by_turnover(
        self, date: datetime, stocks: List[str], criteria: FilterCriteria
    ) -> List[str]:
        """按换手率筛选

        Args:
            date: 筛选日期
            stocks: 股票列表
            criteria: 筛选条件

        Returns:
            满足换手率条件的股票列表
        """
        if criteria.turn_over_min is None and criteria.turn_over_max is None:
            return stocks

        try:
            df = self.data_manager.get_market_data_for_date(date, ["ts_code", "turnover_rate"])
        except Exception as e:
            logger.warning(f"获取换手率数据失败: {e}，跳过换手率筛选")
            return stocks

        if df.empty or "turnover_rate" not in df.columns:
            logger.warning(f"无换手率数据: {date.strftime('%Y%m%d')}")
            return stocks

        df = df[df["ts_code"].isin(stocks)]

        if criteria.turn_over_min is not None:
            df = df[df["turnover_rate"] >= criteria.turn_over_min]
        if criteria.turn_over_max is not None:
            df = df[df["turnover_rate"] <= criteria.turn_over_max]

        return df["ts_code"].tolist()

    def filter_limit_up_down(
        self,
        date: datetime,
        stocks: List[str],
        exclude_limit_up: bool = True,
        exclude_limit_down: bool = True,
    ) -> List[str]:
        """过滤涨跌停股票

        Args:
            date: 筛选日期
            stocks: 股票列表
            exclude_limit_up: 是否排除涨停股票
            exclude_limit_down: 是否排除跌停股票

        Returns:
            过滤后的股票列表
        """
        try:
            df = self.data_manager.get_market_data_for_date(
                date, ["ts_code", "close", "pre_close", "pct_chg"]
            )
        except Exception as e:
            logger.warning(f"获取涨跌停数据失败: {e}")
            return stocks

        if df.empty:
            logger.warning(f"无涨跌停数据: {date.strftime('%Y%m%d')}")
            return stocks

        result = []
        excluded_count = 0
        for ts_code in stocks:
            row = df[df["ts_code"] == ts_code]
            if row.empty:
                continue

            pct_chg = row["pct_chg"].values[0]

            # 判断涨跌停
            is_limit_up = pct_chg >= 9.5
            is_limit_down = pct_chg <= -9.5

            if exclude_limit_up and is_limit_up:
                excluded_count += 1
                continue
            if exclude_limit_down and is_limit_down:
                excluded_count += 1
                continue

            result.append(ts_code)

        if excluded_count > 0:
            logger.debug(f"过滤涨跌停: 排除 {excluded_count} 只")
        return result

    def get_top_liquid_stocks(
        self, date: datetime, stock_pool: List[str], top_n: int = 100, sort_by: str = "amount"
    ) -> List[str]:
        """获取流动性最好的N只股票"""
        df = self.data_manager.get_market_data_for_date(date, ["ts_code", "vol", "amount"])

        if df.empty:
            return []

        df = df[df["ts_code"].isin(stock_pool)]

        if df.empty:
            return []

        df = df.sort_values(by=sort_by, ascending=False)
        return df.head(top_n)["ts_code"].tolist()

    def create_dynamic_filter(
        self, date: datetime, criteria: FilterCriteria
    ) -> Callable[[List[str]], List[str]]:
        """创建动态筛选函数"""

        def filter_func(stocks: List[str]) -> List[str]:
            return self.filter_stocks(date, stocks, criteria)

        return filter_func

    def clear_cache(self):
        """清除缓存"""
        self._st_cache.clear()
        self._liquidity_cache.clear()
        self._new_listing_cache.clear()


class FilterPresets:
    """预设筛选配置"""

    @staticmethod
    def ultra_conservative() -> FilterCriteria:
        """超保守型 - 大盘蓝筹"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=252,
            min_market_cap=50e8,  # 50亿
            max_market_cap=500e8,  # 500亿以内
            min_avg_volume=1e7,  # 1000万股
            min_avg_amount=1e8,  # 1亿成交额
            lookback_days=20,
            sectors=[Sector.MAIN_BOARD],
        )

    @staticmethod
    def conservative() -> FilterCriteria:
        """保守型 - 高流动性要求"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=120,
            min_market_cap=20e8,  # 20亿
            min_avg_volume=5e6,  # 500万股
            min_avg_amount=5e7,  # 5000万
            lookback_days=20,
            sectors=[Sector.MAIN_BOARD, Sector.GEM],
        )

    @staticmethod
    def moderate() -> FilterCriteria:
        """稳健型 - 中等流动性要求"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=60,
            min_market_cap=5e8,  # 5亿
            min_avg_volume=1e6,  # 100万股
            min_avg_amount=1e7,  # 1000万
            lookback_days=20,
            sectors=[Sector.MAIN_BOARD, Sector.GEM, Sector.STAR_MARKET],
        )

    @staticmethod
    def aggressive() -> FilterCriteria:
        """激进型 - 低流动性要求，允许小盘股"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=20,
            min_market_cap=1e8,  # 1亿
            min_avg_volume=3e5,  # 30万股
            min_avg_amount=3e6,  # 300万
            lookback_days=20,
            sectors=[Sector.MAIN_BOARD, Sector.GEM, Sector.STAR_MARKET, Sector.NORTH_BOUND],
        )

    @staticmethod
    def small_cap() -> FilterCriteria:
        """小盘股策略 - 专注小市值"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=60,
            min_market_cap=5e7,  # 5000万
            max_market_cap=50e8,  # 50亿以内
            min_avg_volume=2e5,  # 20万股
            min_avg_amount=2e6,  # 200万
            lookback_days=20,
            industries_exclude=[
                Industry.BANK.value,
                Industry.NON_BANK_FINANCE.value,
                Industry.REAL_ESTATE.value,
            ],
        )

    @staticmethod
    def blue_chip() -> FilterCriteria:
        """蓝筹股策略 - 大盘优质"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=252,
            min_market_cap=100e8,  # 100亿
            min_avg_volume=5e6,  # 500万股
            min_avg_amount=5e7,  # 5000万
            lookback_days=20,
            sectors=[Sector.MAIN_BOARD],
            industries=[
                Industry.FOOD_BEVERAGE.value,
                Industry.PHARMACEUTICAL.value,
                Industry.HOME_APPLIANCES.value,
                Industry.BANK.value,
                Industry.NON_BANK_FINANCE.value,
            ],
        )

    @staticmethod
    def tech_focus() -> FilterCriteria:
        """科技股策略 - 专注科技"""
        return FilterCriteria(
            exclude_st=True,
            exclude_suspended=True,
            exclude_new_listing=True,
            min_listing_days=60,
            min_market_cap=1e8,
            min_avg_volume=5e5,
            min_avg_amount=5e6,
            lookback_days=20,
            industries=[
                Industry.ELECTRONICS.value,
                Industry.COMPUTER.value,
                Industry.COMMUNICATION.value,
                Industry.MEDIA.value,
                Industry.ELECTRICAL_EQUIPMENT.value,
                Industry.MACHINERY.value,
            ],
        )

    @staticmethod
    def no_filter() -> FilterCriteria:
        """不过滤"""
        return FilterCriteria(
            exclude_st=False,
            exclude_suspended=False,
            exclude_new_listing=False,
            min_market_cap=0,
            min_avg_volume=0,
            min_avg_amount=0,
        )
