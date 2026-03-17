"""
MySQL DataFeed模块

实现Backtrader与MySQL数据库的集成，支持：
- 从daily_kline表读取数据
- 前复权/后复权/不复权切换
- 停牌日处理（跳过或前向填充）
- 多数据源支持

Example:
    >>> from projects.quant_trading.backtest.data_feed import MySQLDataFeed
    >>>
    >>> data = MySQLDataFeed(
    ...     symbol='000001.SZ',
    ...     fromdate=datetime(2024, 1, 1),
    ...     todate=datetime(2024, 12, 31),
    ...     adj_type='qfq'  # 前复权
    ... )
    >>> cerebro.adddata(data)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd
import backtrader as bt

from core.logger import get_logger
from projects.quant_trading.backtest.data_manager import DataManager, MissingDataError

logger = get_logger(__name__)


class MySQLDataFeed(bt.feeds.PandasData):
    """
    MySQL数据源

    从MySQL数据库的daily_kline表读取K线数据，支持复权设置和停牌处理。

    Parameters:
        symbol (str): 股票代码，如'000001.SZ'
        fromdate (datetime): 开始日期
        todate (datetime): 结束日期
        adj_type (str): 复权类型，'qfq'前复权/'bfq'后复权/'none'不复权
        handle_suspend (str): 停牌处理方式，'skip'跳过/'ffill'前向填充
        fetch_kwargs (dict): 传递给DataManager的额外参数

    Lines:
        - datetime: 日期时间
        - open: 开盘价
        - high: 最高价
        - low: 最低价
        - close: 收盘价
        - volume: 成交量
        - openinterest: 持仓量（期货等，股票为0）

    Params:
        - symbol (None): 股票代码
        - fromdate (None): 开始日期
        - todate (None): 结束日期
        - adj_type ('qfq'): 复权类型
        - handle_suspend ('skip'): 停牌处理方式
        - fetch_kwargs ({})：数据获取额外参数
    """

    params = (
        ("symbol", None),
        ("fromdate", None),
        ("todate", None),
        ("adj_type", "qfq"),  # qfq:前复权, bfq:后复权, none:不复权
        ("handle_suspend", "skip"),  # skip:跳过, ffill:前向填充
        ("fetch_kwargs", {}),
    )

    # 定义lines
    lines = ("adj_factor",)  # 额外添加复权因子line

    def __init__(self):
        super().__init__()

        # 参数验证
        if self.p.symbol is None:
            raise ValueError("必须指定symbol参数")

        if self.p.adj_type not in ["qfq", "bfq", "none"]:
            raise ValueError(f"无效的adj_type: {self.p.adj_type}, 必须是'qfq', 'bfq'或'none'")

        if self.p.handle_suspend not in ["skip", "ffill"]:
            raise ValueError(
                f"无效的handle_suspend: {self.p.handle_suspend}, 必须是'skip'或'ffill'"
            )

        # 初始化DataManager
        self._data_manager = DataManager()

        # 数据缓存
        self._df: Optional[pd.DataFrame] = None
        self._data_iter = None

        # 停牌日记录
        self._suspended_dates: set = set()

        # 前向填充数据（用于ffill模式）
        self._last_valid_data: Optional[Dict[str, Any]] = None

    def _load_data(self) -> pd.DataFrame:
        """
        从MySQL加载数据

        Returns:
            包含K线数据的DataFrame
        """
        logger.info(
            f"[MySQLDataFeed] 加载数据: {self.p.symbol}, "
            f"{self.p.fromdate.date()} ~ {self.p.todate.date()}, "
            f"复权={self.p.adj_type}"
        )

        try:
            # 调用DataManager获取数据
            adjust = self.p.adj_type == "qfq"  # 是否前复权

            df = self._data_manager.get_stock_data(
                ts_code=self.p.symbol,
                start_date=self.p.fromdate,
                end_date=self.p.todate,
                adjust=adjust,
                **self.p.fetch_kwargs,
            )

            if df is None or df.empty:
                raise MissingDataError(
                    f"{self.p.symbol} 在指定时间段无数据",
                    ts_code=self.p.symbol,
                    start_date=self.p.fromdate,
                    end_date=self.p.todate,
                )

            # 处理数据格式
            df = self._process_dataframe(df)

            logger.info(f"[MySQLDataFeed] 加载完成: {len(df)} 条记录")
            return df

        except MissingDataError:
            raise
        except Exception as e:
            logger.error(f"[MySQLDataFeed] 加载数据失败: {e}")
            raise

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理DataFrame格式

        Args:
            df: 原始DataFrame

        Returns:
            处理后的DataFrame
        """
        # 确保必要的列存在
        required_cols = ["open", "high", "low", "close", "vol"]
        for col in required_cols:
            adj_col = f"adj_{col}" if col != "vol" and self.p.adj_type == "qfq" else col
            if adj_col in df.columns:
                if col == "vol":
                    df["volume"] = df[col]
                else:
                    df[col] = df[adj_col]
            elif col not in df.columns:
                raise ValueError(f"数据缺少必要列: {col}")

        # 添加openinterest列（股票为0）
        df["openinterest"] = 0

        # 确保复权因子列存在
        if "adj_factor" not in df.columns:
            df["adj_factor"] = 1.0

        # 重置索引，确保日期列为datetime类型
        if "trade_date" in df.columns:
            df = df.reset_index()
        elif not isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()

        # 确保datetime列存在
        if "datetime" not in df.columns:
            if "trade_date" in df.columns:
                df["datetime"] = pd.to_datetime(df["trade_date"])
            elif isinstance(df.index, pd.DatetimeIndex):
                df["datetime"] = df.index
            else:
                raise ValueError("无法确定日期列")

        # 选择需要的列
        cols = ["datetime", "open", "high", "low", "close", "volume", "openinterest", "adj_factor"]
        df = df[[c for c in cols if c in df.columns]]

        # 按日期排序
        df = df.sort_values("datetime")

        # 处理停牌日
        if self.p.handle_suspend == "skip":
            df = self._handle_suspended_days_skip(df)
        elif self.p.handle_suspend == "ffill":
            df = self._handle_suspended_days_ffill(df)

        return df

    def _handle_suspended_days_skip(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        跳过停牌日（删除停牌数据）

        Args:
            df: 原始DataFrame

        Returns:
            处理后的DataFrame
        """
        # 停牌判断：成交量为0或价格无变化
        if "vol" in df.columns and "volume" not in df.columns:
            df["volume"] = df["vol"]

        if "volume" in df.columns:
            # 成交量为0视为停牌
            suspended = df["volume"] == 0
            if suspended.any():
                suspended_dates = df.loc[suspended, "datetime"].tolist()
                self._suspended_dates = set(suspended_dates)
                logger.warning(
                    f"[MySQLDataFeed] {self.p.symbol} 跳过 {len(suspended_dates)} 个停牌日"
                )
                df = df[~suspended].copy()

        return df

    def _handle_suspended_days_ffill(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        前向填充停牌日

        Args:
            df: 原始DataFrame

        Returns:
            处理后的DataFrame
        """
        if "vol" in df.columns and "volume" not in df.columns:
            df["volume"] = df["vol"]

        if "volume" in df.columns:
            # 识别停牌日
            suspended = df["volume"] == 0
            if suspended.any():
                # 对OHLC进行前向填充
                price_cols = ["open", "high", "low", "close"]
                for col in price_cols:
                    if col in df.columns:
                        df[col] = df[col].replace(0, pd.NA).ffill()

                # 成交量填充为0
                df.loc[suspended, "volume"] = 0

                suspended_count = suspended.sum()
                logger.warning(
                    f"[MySQLDataFeed] {self.p.symbol} 前向填充 {suspended_count} 个停牌日"
                )

        return df

    def start(self):
        """Backtrader回调：开始加载数据"""
        super().start()

        # 加载数据
        self._df = self._load_data()

        # 转换为Backtrader需要的格式
        self._data_iter = self._df.iterrows()

    def _load(self):
        """
        Backtrader回调：加载下一条数据

        Returns:
            True: 数据加载成功
            False: 数据加载结束
        """
        try:
            idx, row = next(self._data_iter)

            # 设置数据
            self.lines.datetime[0] = bt.date2num(row["datetime"])
            self.lines.open[0] = row["open"]
            self.lines.high[0] = row["high"]
            self.lines.low[0] = row["low"]
            self.lines.close[0] = row["close"]
            self.lines.volume[0] = row["volume"]
            self.lines.openinterest[0] = row.get("openinterest", 0)

            # 复权因子
            if "adj_factor" in row:
                self.lines.adj_factor[0] = row["adj_factor"]

            return True

        except StopIteration:
            return False
        except Exception as e:
            logger.error(f"[MySQLDataFeed] 加载数据错误: {e}")
            return False

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """获取底层DataFrame"""
        return self._df

    def get_suspended_dates(self) -> set:
        """获取停牌日期集合"""
        return self._suspended_dates


class MultiSymbolDataFeed:
    """
    多标的DataFeed管理器

    简化多标的回测的数据加载。

    Example:
        >>> manager = MultiSymbolDataFeed(
        ...     symbols=['000001.SZ', '000002.SZ'],
        ...     fromdate=datetime(2024, 1, 1),
        ...     todate=datetime(2024, 12, 31)
        ... )
        >>> manager.add_to_cerebro(cerebro)
    """

    def __init__(
        self,
        symbols: List[str],
        fromdate: datetime,
        todate: datetime,
        adj_type: str = "qfq",
        handle_suspend: str = "skip",
        name_mapping: Optional[Dict[str, str]] = None,
    ):
        """
        初始化多标的管理器

        Args:
            symbols: 股票代码列表
            fromdate: 开始日期
            todate: 结束日期
            adj_type: 复权类型
            handle_suspend: 停牌处理方式
            name_mapping: 代码到名称的映射字典
        """
        self.symbols = symbols
        self.fromdate = fromdate
        self.todate = todate
        self.adj_type = adj_type
        self.handle_suspend = handle_suspend
        self.name_mapping = name_mapping or {}

        self._data_feeds: List[MySQLDataFeed] = []

    def load_all(self) -> List[MySQLDataFeed]:
        """
        加载所有标的的数据

        Returns:
            MySQLDataFeed列表
        """
        self._data_feeds = []

        for symbol in self.symbols:
            try:
                data_feed = MySQLDataFeed(
                    symbol=symbol,
                    fromdate=self.fromdate,
                    todate=self.todate,
                    adj_type=self.adj_type,
                    handle_suspend=self.handle_suspend,
                )

                # 设置数据名称（用于策略中识别）
                name = self.name_mapping.get(symbol, symbol)
                data_feed._name = name

                self._data_feeds.append(data_feed)
                logger.debug(f"[MultiSymbolDataFeed] 加载 {symbol} 成功")

            except Exception as e:
                logger.error(f"[MultiSymbolDataFeed] 加载 {symbol} 失败: {e}")

        logger.info(
            f"[MultiSymbolDataFeed] 成功加载 {len(self._data_feeds)}/{len(self.symbols)} 个标的"
        )
        return self._data_feeds

    def add_to_cerebro(self, cerebro: bt.Cerebro):
        """
        将所有数据添加到Cerebro

        Args:
            cerebro: Backtrader Cerebro实例
        """
        if not self._data_feeds:
            self.load_all()

        for data_feed in self._data_feeds:
            cerebro.adddata(data_feed)
            logger.debug(f"[MultiSymbolDataFeed] 添加到Cerebro: {data_feed._name}")

    def get_data_feed(self, symbol: str) -> Optional[MySQLDataFeed]:
        """
        获取指定标的的DataFeed

        Args:
            symbol: 股票代码

        Returns:
            MySQLDataFeed或None
        """
        for df in self._data_feeds:
            if df.p.symbol == symbol or df._name == symbol:
                return df
        return None


class PandasDataFeed(bt.feeds.PandasData):
    """
    增强版Pandas数据源

    在标准PandasData基础上增加功能。
    """

    params = (
        ("symbol", None),
        ("adj_type", "none"),
    )

    lines = ("adj_factor",)

    def __init__(self, dataframe: pd.DataFrame, **kwargs):
        """
        初始化

        Args:
            dataframe: 包含OHLCV数据的DataFrame
            **kwargs: 额外参数
        """
        # 预处理DataFrame
        df = self._preprocess_dataframe(dataframe)

        super().__init__(dataname=df, **kwargs)

        self._name = kwargs.get("symbol", "data")

    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """预处理DataFrame"""
        # 确保必要的列存在
        required_cols = ["open", "high", "low", "close", "volume"]

        # 列名映射（处理大小写问题）
        col_mapping = {}
        for req_col in required_cols:
            if req_col not in df.columns:
                # 尝试大写
                if req_col.upper() in df.columns:
                    col_mapping[req_col.upper()] = req_col
                # 尝试首字母大写
                elif req_col.capitalize() in df.columns:
                    col_mapping[req_col.capitalize()] = req_col
                elif req_col == "volume" and "vol" in df.columns:
                    col_mapping["vol"] = "volume"

        if col_mapping:
            df = df.rename(columns=col_mapping)

        # 检查必要列
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(f"DataFrame缺少必要列: {missing_cols}")

        # 添加openinterest列
        if "openinterest" not in df.columns:
            df["openinterest"] = 0

        # 处理日期索引
        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime")
            elif "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")
            elif "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")

        # 确保索引是DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame需要DatetimeIndex或包含date/datetime列")

        return df


# 便捷函数
def create_data_feed(
    symbol: str, fromdate: datetime, todate: datetime, adj_type: str = "qfq", **kwargs
) -> MySQLDataFeed:
    """
    创建MySQL数据源

    Args:
        symbol: 股票代码
        fromdate: 开始日期
        todate: 结束日期
        adj_type: 复权类型
        **kwargs: 额外参数

    Returns:
        MySQLDataFeed
    """
    return MySQLDataFeed(
        symbol=symbol, fromdate=fromdate, todate=todate, adj_type=adj_type, **kwargs
    )


def load_stock_data(
    symbols: List[str], fromdate: datetime, todate: datetime, adj_type: str = "qfq"
) -> Dict[str, pd.DataFrame]:
    """
    批量加载股票数据

    Args:
        symbols: 股票代码列表
        fromdate: 开始日期
        todate: 结束日期
        adj_type: 复权类型

    Returns:
        {symbol: DataFrame} 字典
    """
    data_manager = DataManager()
    result = {}

    for symbol in symbols:
        try:
            adjust = adj_type == "qfq"
            df = data_manager.get_stock_data(
                ts_code=symbol, start_date=fromdate, end_date=todate, adjust=adjust
            )
            result[symbol] = df
            logger.debug(f"[load_stock_data] 加载 {symbol} 成功")
        except Exception as e:
            logger.error(f"[load_stock_data] 加载 {symbol} 失败: {e}")

    return result


if __name__ == "__main__":
    # 测试代码
    print("=== MySQL DataFeed 测试 ===\n")

    from datetime import datetime, timedelta

    # 测试1: 单只股票DataFeed
    print("1. 测试单只股票DataFeed")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        data_feed = MySQLDataFeed(
            symbol="000001.SZ",
            fromdate=start_date,
            todate=end_date,
            adj_type="qfq",
            handle_suspend="skip",
        )

        print(f"   创建成功: {data_feed.p.symbol}")
        print(f"   参数: 复权={data_feed.p.adj_type}, 停牌处理={data_feed.p.handle_suspend}")

        # 模拟start加载
        data_feed.start()
        df = data_feed.get_dataframe()

        if df is not None:
            print(f"   数据记录数: {len(df)}")
            print(f"   列: {list(df.columns)}")
            print(f"   日期范围: {df['datetime'].min()} ~ {df['datetime'].max()}")
            print()

    except Exception as e:
        print(f"   测试失败: {e}\n")

    # 测试2: 多标的管理器
    print("2. 测试多标的管理器")
    try:
        symbols = ["000001.SZ", "000002.SZ"]

        manager = MultiSymbolDataFeed(
            symbols=symbols, fromdate=start_date, todate=end_date, adj_type="qfq"
        )

        data_feeds = manager.load_all()
        print(f"   成功加载 {len(data_feeds)} 个标的")

        for df in data_feeds:
            print(f"   - {df.p.symbol}: {len(df.get_dataframe() or [])} 条记录")

    except Exception as e:
        print(f"   测试失败: {e}")

    print("\n测试完成!")
