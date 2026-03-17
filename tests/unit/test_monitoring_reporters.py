"""
指标报告模块单元测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

import pandas as pd
import numpy as np

from projects.quant_trading.monitoring.reporters import MetricsReporter
from projects.quant_trading.monitoring.metrics import SystemMetrics, SystemMetricsCollector
from projects.quant_trading.monitoring.alerts import AlertManager, Alert, AlertLevel


class TestMetricsReporter:
    """测试指标报告生成器"""

    def test_init(self):
        """测试初始化"""
        collector = SystemMetricsCollector()
        reporter = MetricsReporter(collector)
        assert reporter.metrics_collector == collector
        assert reporter.alert_manager is None

    def test_init_with_alert_manager(self):
        """测试带告警管理器的初始化"""
        collector = SystemMetricsCollector()
        alert_manager = AlertManager()
        reporter = MetricsReporter(collector, alert_manager)
        assert reporter.alert_manager == alert_manager

    def test_generate_daily_report_empty(self):
        """测试生成空日报"""
        collector = SystemMetricsCollector()
        reporter = MetricsReporter(collector)

        report = reporter.generate_daily_report()
        assert "暂无数据" in report

    def test_generate_daily_report_with_data(self):
        """测试生成有数据的日报"""
        collector = SystemMetricsCollector()
        # 添加一些历史数据
        collector.collect()

        reporter = MetricsReporter(collector)
        report = reporter.generate_daily_report()

        assert "量化交易系统日报" in report
        assert "数据健康" in report
        assert "内存占用" in report

    def test_generate_daily_report_specific_date(self):
        """测试生成指定日期的日报"""
        collector = SystemMetricsCollector()
        # 添加一些历史数据
        from datetime import datetime, timedelta
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        for i in range(5):
            metrics = SystemMetrics(timestamp=base_time + timedelta(hours=i))
            collector._history.append(metrics)

        reporter = MetricsReporter(collector)
        specific_date = datetime(2024, 1, 15)
        report = reporter.generate_daily_report(specific_date)

        assert "2024-01-15" in report

    def test_generate_daily_report_with_alerts(self):
        """测试生成带告警的日报"""
        collector = SystemMetricsCollector()
        # 添加一些历史数据
        collector.collect()

        alert_manager = AlertManager()

        # 触发一个告警
        metrics = SystemMetrics(data_freshness_minutes=150)
        alert_manager.check_metrics(metrics)

        reporter = MetricsReporter(collector, alert_manager)
        report = reporter.generate_daily_report()

        assert "活跃告警" in report

    def test_generate_weekly_report_empty(self):
        """测试生成空周报"""
        collector = SystemMetricsCollector()
        reporter = MetricsReporter(collector)

        report = reporter.generate_weekly_report()
        assert "暂无数据" in report

    def test_generate_weekly_report_with_data(self):
        """测试生成有数据的周报"""
        collector = SystemMetricsCollector()
        # 添加一些历史数据
        for _ in range(5):
            collector.collect()

        reporter = MetricsReporter(collector)
        report = reporter.generate_weekly_report()

        assert "量化交易系统周报" in report
        assert "汇总统计" in report
        assert "数据健康" in report
        assert "模型性能" in report

    def test_generate_weekly_report_specific_date(self):
        """测试生成指定日期的周报"""
        collector = SystemMetricsCollector()
        # 添加一些历史数据
        from datetime import datetime, timedelta
        base_time = datetime(2024, 1, 10, 10, 0, 0)
        for i in range(10):
            metrics = SystemMetrics(timestamp=base_time + timedelta(days=i))
            collector._history.append(metrics)

        reporter = MetricsReporter(collector)

        end_date = datetime(2024, 1, 15)
        report = reporter.generate_weekly_report(end_date)

        # 周报应该包含前7天的日期
        assert "2024-01-08" in report or "2024-01-15" in report

    def test_generate_json_report(self):
        """测试生成JSON报告"""
        collector = SystemMetricsCollector()
        collector.collect()

        reporter = MetricsReporter(collector)
        report = reporter.generate_json_report()

        assert "generated_at" in report
        assert "summary" in report
        assert "current_metrics" in report

    def test_generate_json_report_with_alerts(self):
        """测试生成带告警的JSON报告"""
        collector = SystemMetricsCollector()
        alert_manager = AlertManager()

        # 触发告警
        metrics = SystemMetrics(data_freshness_minutes=150)
        alert_manager.check_metrics(metrics)

        reporter = MetricsReporter(collector, alert_manager)
        report = reporter.generate_json_report()

        assert "active_alerts" in report
        assert len(report["active_alerts"]) > 0

    def test_save_report(self):
        """测试保存报告"""
        collector = SystemMetricsCollector()
        reporter = MetricsReporter(collector)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_report.md"
            report_content = "# Test Report"

            reporter.save_report(report_content, str(filepath))

            assert filepath.exists()
            assert filepath.read_text() == report_content

    def test_save_json_report(self):
        """测试保存JSON报告"""
        collector = SystemMetricsCollector()
        collector.collect()

        reporter = MetricsReporter(collector)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_report.json"
            reporter.save_json_report(str(filepath))

            assert filepath.exists()
            content = filepath.read_text()
            assert "generated_at" in content


class TestMetricsReporterWithMockData:
    """使用模拟数据的报告测试"""

    def create_mock_collector_with_data(self):
        """创建带模拟数据的采集器"""
        collector = SystemMetricsCollector()

        # 创建一些模拟历史数据
        base_time = datetime.now() - timedelta(days=1)
        for i in range(24):  # 24小时的数据
            metrics = SystemMetrics(
                timestamp=base_time + timedelta(hours=i),
                data_freshness_minutes=30.0 + i,
                data_completeness_pct=99.0 - i * 0.1,
                rolling_ic=0.03 + i * 0.001,
                ic_ir=0.4 + i * 0.01,
                backtest_time_seconds=25.0 + i,
                memory_usage_mb=1024.0 + i * 10,
            )
            collector._history.append(metrics)

        return collector

    def test_daily_report_with_mock_data(self):
        """测试使用模拟数据的日报"""
        collector = self.create_mock_collector_with_data()
        reporter = MetricsReporter(collector)

        yesterday = datetime.now() - timedelta(days=1)
        report = reporter.generate_daily_report(yesterday)

        assert "数据延迟" in report
        assert "数据完整率" in report

    def test_weekly_report_with_mock_data(self):
        """测试使用模拟数据的周报"""
        collector = self.create_mock_collector_with_data()
        reporter = MetricsReporter(collector)

        report = reporter.generate_weekly_report()

        # 验证表格内容
        assert "平均值" in report
        assert "最小值" in report
        assert "最大值" in report

        # 验证数据指标
        assert "数据延迟" in report or "分钟" in report
        assert "滚动IC" in report
