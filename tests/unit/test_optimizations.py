"""
性能优化模块单元测试
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import tempfile
import time

import pandas as pd
import numpy as np

from pathlib import Path
from projects.quant_trading.backtest.optimizations.cache import (
    CacheManager,
    get_global_cache,
    cached,
)
from projects.quant_trading.backtest.optimizations.vectorized import (
    VectorizedBacktester,
    VectorizedResult,
)


class TestCacheManager:
    """测试缓存管理器"""

    def test_init(self):
        """测试初始化"""
        cache = CacheManager()
        assert cache.memory_size == 1000
        assert cache.ttl_seconds == 3600
        assert cache.disk_path is None

    def test_init_with_custom_params(self):
        """测试自定义参数初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(
                memory_size=500,
                disk_path=tmpdir,
                ttl_seconds=1800,
            )
            assert cache.memory_size == 500
            assert cache.ttl_seconds == 1800
            assert cache.disk_path == Path(tmpdir)

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        cache = CacheManager()
        cache.set("key1", {"data": "value1"})

        result = cache.get("key1")
        assert result == {"data": "value1"}

    def test_get_nonexistent(self):
        """测试获取不存在的缓存"""
        cache = CacheManager()
        result = cache.get("nonexistent")
        assert result is None

    def test_update_existing(self):
        """测试更新现有缓存"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key1", "value2")

        result = cache.get("key1")
        assert result == "value2"

    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = CacheManager(ttl_seconds=0)
        cache.set("key1", "value1")

        # 立即获取应该过期
        time.sleep(0.1)
        result = cache.get("key1")
        assert result is None

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        stats = cache.get_stats()
        assert stats["memory_entries"] == 2
        assert stats["memory_size"] == 1000

    def test_clear(self):
        """测试清空缓存"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestCachedDecorator:
    """测试缓存装饰器"""

    def test_cached_function(self):
        """测试缓存装饰的函数"""
        call_count = 0

        @cached(ttl_seconds=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == result2 == 10
        assert call_count == 1  # 只应被调用一次

    def test_cached_function_different_args(self):
        """测试不同参数的缓存"""
        import uuid
        call_count = {}
        func_name = f"test_func_{uuid.uuid4().hex[:8]}"

        def make_expensive_function():
            def expensive_function(x):
                call_count[x] = call_count.get(x, 0) + 1
                return x * 2
            return expensive_function

        # 使用不同缓存键的函数
        @cached(ttl_seconds=60)
        def expensive_function_1(x):
            call_count['a'] = call_count.get('a', 0) + 1
            return x * 2

        @cached(ttl_seconds=60)
        def expensive_function_2(x):
            call_count['b'] = call_count.get('b', 0) + 1
            return x * 2

        expensive_function_1(5)
        expensive_function_2(10)

        assert call_count.get('a', 0) >= 1
        assert call_count.get('b', 0) >= 1


class TestVectorizedBacktester:
    """测试向量化回测器"""

    def test_init(self):
        """测试初始化"""
        backtester = VectorizedBacktester(
            initial_cash=100000,
            commission_rate=0.00015,
            slippage_rate=0.0002,
        )
        assert backtester.initial_cash == 100000
        assert backtester.commission_rate == 0.00015
        assert backtester.slippage_rate == 0.0002

    def test_run_simple_backtest(self):
        """测试简单回测"""
        backtester = VectorizedBacktester(initial_cash=100000)

        dates = pd.date_range("2023-01-01", periods=30, freq="B")
        prices = pd.DataFrame(
            {"000001.SZ": 100 * (1 + np.random.randn(30) * 0.01).cumprod()},
            index=dates,
        )
        signals = pd.DataFrame(
            {"000001.SZ": [1] * 15 + [0] * 15},
            index=dates,
        )

        result = backtester.run(prices, signals)

        assert isinstance(result, VectorizedResult)
        assert len(result.nav_history) == 30
        assert result.metrics is not None

    def test_run_multi_stock_backtest(self):
        """测试多股票回测"""
        backtester = VectorizedBacktester(initial_cash=100000)

        dates = pd.date_range("2023-01-01", periods=30, freq="B")
        prices = pd.DataFrame(
            {
                "000001.SZ": 100 * (1 + np.random.randn(30) * 0.01).cumprod(),
                "000002.SZ": 50 * (1 + np.random.randn(30) * 0.01).cumprod(),
            },
            index=dates,
        )
        signals = pd.DataFrame(
            {
                "000001.SZ": [1] * 15 + [0] * 15,
                "000002.SZ": [0] * 15 + [1] * 15,
            },
            index=dates,
        )

        result = backtester.run(prices, signals)

        assert isinstance(result, VectorizedResult)
        assert len(result.nav_history) == 30

    def test_generate_trades(self):
        """测试生成交易记录"""
        backtester = VectorizedBacktester()

        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        prices = pd.DataFrame(
            {"000001.SZ": [100] * 10},
            index=dates,
        )
        signals = pd.DataFrame(
            {"000001.SZ": [0, 1, 1, 0, 0, -1, -1, 0, 1, 0]},
            index=dates,
        )

        trades = backtester._generate_trades(signals, prices)

        assert isinstance(trades, pd.DataFrame)
        assert "side" in trades.columns
        assert "ts_code" in trades.columns

    def test_optimize_position_size(self):
        """测试优化仓位大小"""
        backtester = VectorizedBacktester()

        dates = pd.date_range("2023-01-01", periods=30, freq="B")
        np.random.seed(42)
        prices = pd.DataFrame(
            {"000001.SZ": 100 * (1 + np.random.randn(30) * 0.01).cumprod()},
            index=dates,
        )
        signals = pd.DataFrame(
            {"000001.SZ": [1] * 15 + [0] * 15},
            index=dates,
        )

        best_size, best_result = backtester.optimize_position_size(
            prices, signals, size_range=np.linspace(0.1, 1.0, 5)
        )

        assert 0.1 <= best_size <= 1.0
        assert isinstance(best_result, VectorizedResult)
        assert best_result.metrics is not None

    def test_run_multi_strategy(self):
        """测试运行多个策略"""
        backtester = VectorizedBacktester()

        dates = pd.date_range("2023-01-01", periods=30, freq="B")
        prices = pd.DataFrame(
            {"000001.SZ": 100 * (1 + np.random.randn(30) * 0.01).cumprod()},
            index=dates,
        )

        strategy_signals = {
            "strategy1": pd.DataFrame({"000001.SZ": [1] * 15 + [0] * 15}, index=dates),
            "strategy2": pd.DataFrame({"000001.SZ": [0] * 15 + [1] * 15}, index=dates),
        }

        results = backtester.run_multi_strategy(prices, strategy_signals)

        assert "strategy1" in results
        assert "strategy2" in results
        assert isinstance(results["strategy1"], VectorizedResult)
        assert isinstance(results["strategy2"], VectorizedResult)


class TestGlobalCache:
    """测试全局缓存"""

    def test_get_global_cache(self):
        """测试获取全局缓存"""
        cache1 = get_global_cache()
        cache2 = get_global_cache()

        assert cache1 is cache2  # 应该是同一个实例

    def test_global_cache_persistence(self):
        """测试全局缓存持久性"""
        cache = get_global_cache()
        cache.set("test_key", "test_value")

        # 重新获取应该保留数据
        cache2 = get_global_cache()
        assert cache2.get("test_key") == "test_value"

        # 清理
        cache.clear()
