"""
系统指标采集模块单元测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

from projects.quant_trading.monitoring.metrics import (
    SystemMetrics,
    SystemMetricsCollector,
)


class TestSystemMetrics:
    """测试系统指标数据类"""

    def test_default_init(self):
        """测试默认初始化"""
        metrics = SystemMetrics()
        assert metrics.data_freshness_minutes == 0.0
        assert metrics.data_completeness_pct == 100.0
        assert metrics.sync_failure_rate_pct == 0.0
        assert metrics.rolling_ic == 0.0
        assert metrics.ic_ir == 0.0
        assert metrics.prediction_accuracy_pct == 0.0
        assert metrics.backtest_time_seconds == 0.0
        assert metrics.memory_usage_mb == 0.0
        assert metrics.cache_hit_rate_pct == 0.0
        assert metrics.dashboard_load_time_ms == 0.0
        assert isinstance(metrics.timestamp, datetime)
        assert metrics.extra_metrics == {}

    def test_custom_init(self):
        """测试自定义初始化"""
        metrics = SystemMetrics(
            data_freshness_minutes=150.5,
            data_completeness_pct=95.0,
            rolling_ic=0.05,
            ic_ir=0.6,
            prediction_accuracy_pct=55.0,
            extra_metrics={"custom_key": "custom_value"},
        )
        assert metrics.data_freshness_minutes == 150.5
        assert metrics.data_completeness_pct == 95.0
        assert metrics.rolling_ic == 0.05
        assert metrics.ic_ir == 0.6
        assert metrics.prediction_accuracy_pct == 55.0
        assert metrics.extra_metrics == {"custom_key": "custom_value"}

    def test_to_dict(self):
        """测试转换为字典"""
        metrics = SystemMetrics(
            data_freshness_minutes=30.0,
            memory_usage_mb=1024.5,
            extra_metrics={"cpu_usage": 45.0},
        )
        data = metrics.to_dict()

        assert data["data_freshness_minutes"] == 30.0
        assert data["memory_usage_mb"] == 1024.5
        assert data["cpu_usage"] == 45.0
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "data_freshness_minutes": 60.0,
            "data_completeness_pct": 98.5,
            "rolling_ic": 0.03,
            "custom_metric": 123.45,
        }
        metrics = SystemMetrics.from_dict(data)

        assert metrics.data_freshness_minutes == 60.0
        assert metrics.data_completeness_pct == 98.5
        assert metrics.rolling_ic == 0.03
        assert metrics.extra_metrics == {"custom_metric": 123.45}

    def test_from_dict_with_defaults(self):
        """测试从字典创建使用默认值"""
        data = {"timestamp": datetime.now().isoformat()}
        metrics = SystemMetrics.from_dict(data)

        assert metrics.data_freshness_minutes == 0.0
        assert metrics.data_completeness_pct == 100.0
        assert metrics.rolling_ic == 0.0


class TestSystemMetricsCollector:
    """测试系统指标采集器"""

    def test_init(self):
        """测试初始化"""
        collector = SystemMetricsCollector()
        assert collector.max_history == 1000
        assert len(collector.get_history()) == 0

    def test_init_with_custom_size(self):
        """测试自定义历史大小初始化"""
        collector = SystemMetricsCollector(max_history=100)
        assert collector.max_history == 100

    def test_collect(self):
        """测试采集指标"""
        collector = SystemMetricsCollector()
        metrics = collector.collect()

        assert isinstance(metrics, SystemMetrics)
        assert isinstance(metrics.timestamp, datetime)
        # 内存占用应该大于0
        assert metrics.memory_usage_mb > 0

    def test_collect_stores_history(self):
        """测试采集存储历史"""
        collector = SystemMetricsCollector()
        collector.collect()
        collector.collect()

        history = collector.get_history()
        assert len(history) == 2

    def test_get_history_n(self):
        """测试获取最近n条历史"""
        collector = SystemMetricsCollector()
        for _ in range(5):
            collector.collect()

        history = collector.get_history(n=3)
        assert len(history) == 3

    def test_get_history_df(self):
        """测试获取历史DataFrame"""
        collector = SystemMetricsCollector()
        collector.collect()
        collector.collect()

        df = collector.get_history_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "timestamp" in df.columns
        assert "memory_usage_mb" in df.columns

    def test_get_history_df_empty(self):
        """测试获取空历史DataFrame"""
        collector = SystemMetricsCollector()
        df = collector.get_history_df()
        assert df.empty

    def test_clear_history(self):
        """测试清空历史"""
        collector = SystemMetricsCollector()
        collector.collect()
        collector.collect()

        assert len(collector.get_history()) == 2
        collector.clear_history()
        assert len(collector.get_history()) == 0

    def test_record_backtest_time(self):
        """测试记录回测时间"""
        collector = SystemMetricsCollector()
        collector.record_backtest_time(30.5)
        collector.record_backtest_time(45.2)

        metrics = collector.collect()
        # 平均回测时间应该是 (30.5 + 45.2) / 2 = 37.85
        assert metrics.backtest_time_seconds == pytest.approx(37.85, 0.1)

    def test_record_cache_hit(self):
        """测试记录缓存命中"""
        collector = SystemMetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        metrics = collector.collect()
        # 命中率应该是 2 / 3 = 66.67%
        assert metrics.cache_hit_rate_pct == pytest.approx(66.67, 0.1)

    def test_record_cache_miss(self):
        """测试记录缓存未命中"""
        collector = SystemMetricsCollector()
        collector.record_cache_miss()
        collector.record_cache_miss()

        metrics = collector.collect()
        # 命中率应该是 0%
        assert metrics.cache_hit_rate_pct == 0.0

    def test_record_dashboard_load_time(self):
        """测试记录Dashboard加载时间"""
        collector = SystemMetricsCollector()
        collector.record_dashboard_load_time(1500.0)
        collector.record_dashboard_load_time(2000.0)

        metrics = collector.collect()
        # 平均加载时间应该是 1750.0
        assert metrics.dashboard_load_time_ms == pytest.approx(1750.0, 0.1)

    def test_get_summary(self):
        """测试获取摘要"""
        collector = SystemMetricsCollector()
        collector.collect()
        collector.collect()

        summary = collector.get_summary()
        assert summary["records_count"] == 2
        assert "time_range" in summary
        assert "avg_memory_usage" in summary

    def test_get_summary_empty(self):
        """测试获取空摘要"""
        collector = SystemMetricsCollector()
        summary = collector.get_summary()
        assert summary == {}

    @patch("psutil.Process")
    def test_collect_system_resources_error(self, mock_process):
        """测试采集系统资源错误处理"""
        mock_process.side_effect = Exception("Test error")
        collector = SystemMetricsCollector()

        # 不应该抛出异常
        metrics = collector.collect()
        assert isinstance(metrics, SystemMetrics)


class TestSystemMetricsCollectorIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        collector = SystemMetricsCollector(max_history=10)

        # 模拟多次采集
        for i in range(5):
            collector.record_backtest_time(20.0 + i * 5)
            collector.record_cache_hit()
            collector.collect()

        # 验证历史
        history = collector.get_history()
        assert len(history) == 5

        # 验证DataFrame
        df = collector.get_history_df()
        assert len(df) == 5
        # 平均回测时间 (20+25+30+35+40)/5 = 30.0, 但最后一条可能没有包含记录
        assert df["backtest_time_seconds"].mean() > 0

        # 验证摘要
        summary = collector.get_summary()
        assert summary["records_count"] == 5

    def test_history_limit(self):
        """测试历史记录限制"""
        collector = SystemMetricsCollector(max_history=3)

        # 采集超过限制的数据
        for _ in range(5):
            collector.collect()

        # 历史应该只保留最近的3条
        history = collector.get_history()
        assert len(history) == 3
