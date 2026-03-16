"""
数据管理器单元测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.backtest.data_manager import (
    DataManager, MissingDataError, DatabaseError,
    StockData, IndexData
)


class TestDataManagerInit:
    """测试DataManager初始化"""

    def test_default_init(self):
        """测试默认初始化"""
        dm = DataManager()
        assert dm.db_name == "tushare_biz"
        assert dm.max_cache_size == 128
        assert len(dm._cache) == 0

    def test_custom_init(self):
        """测试自定义参数初始化"""
        dm = DataManager(db_name="test_db", max_cache_size=50)
        assert dm.db_name == "test_db"
        assert dm.max_cache_size == 50


class TestCacheOperations:
    """测试缓存操作"""

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        dm = DataManager()
        key = dm._get_cache_key("stock", "000001.SZ", "20230101", "20231231", True)
        assert key == "stock_000001.SZ_20230101_20231231_True"

    def test_lru_cache_behavior(self):
        """测试LRU缓存行为"""
        dm = DataManager(max_cache_size=3)

        # 添加3个条目
        for i in range(3):
            dm._set_cache(f"key_{i}", pd.DataFrame({"data": [i]}))

        assert len(dm._cache) == 3

        # 访问第一个条目
        _ = dm._get_from_cache("key_0")

        # 添加第4个条目，应该淘汰key_1（因为key_0被访问过）
        dm._set_cache("key_3", pd.DataFrame({"data": [3]}))

        assert len(dm._cache) == 3
        assert "key_0" in dm._cache
        assert "key_1" not in dm._cache

    def test_cache_update_existing(self):
        """测试更新已存在的缓存项"""
        dm = DataManager()
        df1 = pd.DataFrame({"data": [1]})
        df2 = pd.DataFrame({"data": [2]})

        dm._set_cache("key_1", df1)
        dm._set_cache("key_1", df2)

        cached = dm._get_from_cache("key_1")
        assert cached["data"].iloc[0] == 2

    def test_clear_cache(self):
        """测试清空缓存"""
        dm = DataManager()
        dm._set_cache("key_1", pd.DataFrame({"data": [1]}))
        dm._set_cache("key_2", pd.DataFrame({"data": [2]}))

        dm.clear_cache()

        assert len(dm._cache) == 0
        assert len(dm._stock_info_cache) == 0


class TestGetTradeDates:
    """测试获取交易日"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_trade_dates_success(self, mock_db):
        """测试成功获取交易日"""
        mock_db.fetchall.return_value = [
            {"cal_date": "20230103"},
            {"cal_date": "20230104"},
            {"cal_date": "20230105"},
        ]

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        dates = dm.get_trade_dates(start, end)

        assert len(dates) == 3
        assert dates[0] == datetime(2023, 1, 3)
        mock_db.fetchall.assert_called_once()

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_trade_dates_empty(self, mock_db):
        """测试无交易日数据"""
        mock_db.fetchall.return_value = []

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        with pytest.raises(MissingDataError) as exc_info:
            dm.get_trade_dates(start, end)

        assert "未找到交易日数据" in str(exc_info.value)


class TestGetStockData:
    """测试获取股票数据"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_stock_data_with_adjust(self, mock_db):
        """测试获取前复权股票数据"""
        # 模拟日线数据
        mock_db.fetchall.side_effect = [
            # 日线数据
            [
                {"trade_date": "20230103", "open": 100.0, "high": 101.0,
                 "low": 99.0, "close": 100.5, "pre_close": 100.0,
                 "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000},
            ],
            # 复权因子数据
            [{"trade_date": "20230103", "adj_factor": 1.0}]
        ]

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        df = dm.get_stock_data("000001.SZ", start, end, adjust=True)

        assert isinstance(df, pd.DataFrame)
        assert "adj_close" in df.columns
        assert "adj_open" in df.columns

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_stock_data_no_adjust(self, mock_db):
        """测试获取不复权股票数据"""
        mock_db.fetchall.return_value = [
            {"trade_date": "20230103", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.5, "pre_close": 100.0,
             "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000},
        ]

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        df = dm.get_stock_data("000001.SZ", start, end, adjust=False)

        assert isinstance(df, pd.DataFrame)
        assert "adj_close" not in df.columns or df["adj_close"].iloc[0] == df["close"].iloc[0]

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_stock_data_missing(self, mock_db):
        """测试获取缺失的股票数据"""
        mock_db.fetchall.return_value = []

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        with pytest.raises(MissingDataError) as exc_info:
            dm.get_stock_data("000001.SZ", start, end)

        assert "无数据" in str(exc_info.value)
        assert exc_info.value.ts_code == "000001.SZ"

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_stock_data_cache_hit(self, mock_db):
        """测试缓存命中"""
        mock_db.fetchall.return_value = [
            {"trade_date": "20230103", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.5, "pre_close": 100.0,
             "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000},
        ]

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        # 第一次查询
        df1 = dm.get_stock_data("000001.SZ", start, end, adjust=False)

        # 第二次查询（应该命中缓存）
        df2 = dm.get_stock_data("000001.SZ", start, end, adjust=False)

        # 只查询一次数据库
        assert mock_db.fetchall.call_count == 1

        # 返回的数据副本应该独立
        assert df1 is not df2


class TestBatchStockData:
    """测试批量获取股票数据"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_batch_stock_data(self, mock_db):
        """测试批量获取数据"""
        mock_db.fetchall.side_effect = [
            # 日线数据 - 需要包含 pre_close 字段用于复权计算
            [
                {"ts_code": "000001.SZ", "trade_date": "20230103", "open": 100.0,
                 "high": 101.0, "low": 99.0, "close": 100.5, "pre_close": 100.0},
                {"ts_code": "000002.SZ", "trade_date": "20230103", "open": 50.0,
                 "high": 51.0, "low": 49.0, "close": 50.5, "pre_close": 50.0},
            ],
            # 复权因子数据
            [
                {"ts_code": "000001.SZ", "trade_date": "20230103", "adj_factor": 1.0},
                {"ts_code": "000002.SZ", "trade_date": "20230103", "adj_factor": 2.0},
            ]
        ]

        dm = DataManager()
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)

        result = dm.get_batch_stock_data(
            ["000001.SZ", "000002.SZ"], start, end, adjust=True
        )

        assert len(result) == 2
        assert "000001.SZ" in result
        assert "000002.SZ" in result
        # 批量查询只调用一次fetchall（而不是每只股一次）
        assert mock_db.fetchall.call_count == 2  # 日线 + 复权因子


class TestIndexData:
    """测试获取指数数据"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_index_data(self, mock_db):
        """测试获取指数数据"""
        mock_db.fetchall.return_value = [
            {"trade_date": "20230103", "open": 4000.0, "high": 4050.0,
             "low": 3980.0, "close": 4020.0, "pre_close": 4000.0,
             "change": 20.0, "pct_chg": 0.5, "vol": 1000000, "amount": 100000000},
        ]

        dm = DataManager()
        df = dm.get_index_data("000300.SH", datetime(2023, 1, 1), datetime(2023, 1, 31))

        assert isinstance(df, pd.DataFrame)
        assert "close" in df.columns


class TestDataIntegrity:
    """测试数据完整性检查"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_check_data_integrity_complete(self, mock_db):
        """测试数据完整性检查 - 完整数据"""
        mock_db.fetchall.return_value = [
            {"trade_date": f"202301{day:02d}", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.5, "pre_close": 100.0,
             "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000}
            for day in [3, 4, 5]  # 3个交易日
        ]

        dm = DataManager()
        # 使用 pandas Timestamp 以支持 normalize() 方法
        trade_dates = pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"])

        is_complete, missing = dm.check_data_integrity(
            "000001.SZ", datetime(2023, 1, 1), datetime(2023, 1, 31), trade_dates
        )

        assert is_complete is True
        assert len(missing) == 0

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_check_data_integrity_missing(self, mock_db):
        """测试数据完整性检查 - 缺失数据"""
        mock_db.fetchall.return_value = [
            {"trade_date": "20230103", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.5, "pre_close": 100.0,
             "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000},
            {"trade_date": "20230105", "open": 102.0, "high": 103.0,
             "low": 101.0, "close": 102.5, "pre_close": 102.0,
             "t_change": 0.5, "pct_chg": 0.5, "vol": 100000, "amount": 10000000},
        ]

        dm = DataManager()
        # 使用 pandas Timestamp 以支持 normalize() 方法
        trade_dates = pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"])

        is_complete, missing = dm.check_data_integrity(
            "000001.SZ", datetime(2023, 1, 1), datetime(2023, 1, 31), trade_dates
        )

        assert is_complete is False
        assert len(missing) == 1
        assert missing[0] == pd.Timestamp("2023-01-04")


class TestSTStocks:
    """测试ST股票列表"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_st_stocks(self, mock_db):
        """测试获取ST股票列表"""
        mock_db.fetchall.return_value = [
            {"ts_code": "000001.SZ"},
            {"ts_code": "000002.SZ"},
        ]

        dm = DataManager()
        st_set = dm.get_st_stocks(datetime(2023, 1, 15))

        assert len(st_set) == 2
        assert "000001.SZ" in st_set
        assert "000002.SZ" in st_set


class TestTradeDateNavigation:
    """测试交易日导航"""

    def test_get_prev_trade_date(self):
        """测试获取前一个交易日"""
        dm = DataManager()
        # 使用 pd.Timestamp 以支持 normalize() 方法
        dm._trade_dates = pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"]).tolist()

        result = dm.get_prev_trade_date(datetime(2023, 1, 5), n=1)
        assert result == pd.Timestamp("2023-01-04")

        result = dm.get_prev_trade_date(datetime(2023, 1, 5), n=2)
        assert result == pd.Timestamp("2023-01-03")

    def test_get_next_trade_date(self):
        """测试获取后一个交易日"""
        dm = DataManager()
        # 使用 pd.Timestamp 以支持 normalize() 方法
        dm._trade_dates = pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"]).tolist()

        result = dm.get_next_trade_date(datetime(2023, 1, 3), n=1)
        assert result == pd.Timestamp("2023-01-04")

        result = dm.get_next_trade_date(datetime(2023, 1, 3), n=2)
        assert result == pd.Timestamp("2023-01-05")

    def test_get_prev_trade_date_not_found(self):
        """测试获取不存在的前一个交易日"""
        dm = DataManager()
        dm._trade_dates = pd.to_datetime(["2023-01-03"]).tolist()

        result = dm.get_prev_trade_date(datetime(2023, 1, 3), n=1)
        assert result is None


class TestGetAllStocks:
    """测试获取全市场股票"""

    @patch("projects.quant_trading.backtest.data_manager.DatabaseManager")
    def test_get_all_stocks(self, mock_db):
        """测试获取所有股票列表"""
        mock_db.fetchall.return_value = [
            {"ts_code": "000001.SZ"},
            {"ts_code": "000002.SZ"},
            {"ts_code": "600000.SH"},
        ]

        dm = DataManager()
        stocks = dm.get_all_stocks(datetime(2023, 1, 15))

        assert len(stocks) == 3
        assert "000001.SZ" in stocks


class TestMissingDataError:
    """测试MissingDataError异常"""

    def test_error_message(self):
        """测试错误消息"""
        error = MissingDataError(
            "数据缺失",
            ts_code="000001.SZ",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31)
        )

        message = str(error)
        assert "数据缺失" in message
        assert "000001.SZ" in message
