"""
指标报告模块

提供系统指标的报表生成功能。
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

import pandas as pd
import numpy as np

from .metrics import SystemMetricsCollector, SystemMetrics
from .alerts import AlertManager

logger = logging.getLogger(__name__)


class MetricsReporter:
    """指标报告生成器

    生成系统指标的各种报表。

    Example:
        >>> reporter = MetricsReporter(collector, alert_manager)
        >>> reporter.generate_daily_report()
        >>> reporter.save_report("reports/2023-01-01.md")
    """

    def __init__(
        self,
        metrics_collector: SystemMetricsCollector,
        alert_manager: Optional[AlertManager] = None,
    ):
        """初始化报告生成器

        Args:
            metrics_collector: 指标采集器
            alert_manager: 告警管理器（可选）
        """
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager

    def generate_daily_report(self, date: Optional[datetime] = None) -> str:
        """生成日报

        Args:
            date: 报告日期，默认今天

        Returns:
            Markdown格式的报告
        """
        if date is None:
            date = datetime.now()

        # 获取当天的指标
        history = self.metrics_collector.get_history_df()

        if history.empty:
            return "# 日报\n\n暂无数据"

        # 过滤当天数据
        history["timestamp"] = pd.to_datetime(history["timestamp"])
        day_data = history[history["timestamp"].dt.date == date.date()]

        if day_data.empty:
            return f"# 日报 - {date.strftime('%Y-%m-%d')}\n\n当天暂无数据"

        # 生成报告
        lines = [
            f"# 量化交易系统日报 - {date.strftime('%Y-%m-%d')}",
            "",
            "## 数据健康",
            f"- 数据延迟: {day_data['data_freshness_minutes'].mean():.1f} 分钟",
            f"- 数据完整率: {day_data['data_completeness_pct'].mean():.2f}%",
            f"- 同步失败率: {day_data['sync_failure_rate_pct'].mean():.2f}%",
            "",
            "## 模型性能",
            f"- 滚动IC: {day_data['rolling_ic'].mean():.4f}",
            f"- IC/IR: {day_data['ic_ir'].mean():.4f}",
            f"- 预测准确率: {day_data['prediction_accuracy_pct'].mean():.2f}%",
            "",
            "## 系统性能",
            f"- 平均回测时间: {day_data['backtest_time_seconds'].mean():.2f} 秒",
            f"- 平均内存占用: {day_data['memory_usage_mb'].mean():.1f} MB",
            f"- 平均缓存命中率: {day_data['cache_hit_rate_pct'].mean():.1f}%",
            f"- 平均Dashboard加载时间: {day_data['dashboard_load_time_ms'].mean():.0f} ms",
            "",
        ]

        # 添加告警信息
        if self.alert_manager:
            active_alerts = self.alert_manager.get_active_alerts()
            if active_alerts:
                lines.extend([
                    "## 活跃告警",
                    "",
                ])
                for alert in active_alerts[:10]:  # 最多显示10条
                    status = "✓" if alert.acknowledged else "✗"
                    lines.append(
                        f"- {status} [{alert.level.value.upper()}] {alert.name}: {alert.message}"
                    )
                lines.append("")

        return "\n".join(lines)

    def generate_weekly_report(self, end_date: Optional[datetime] = None) -> str:
        """生成周报

        Args:
            end_date: 报告结束日期，默认今天

        Returns:
            Markdown格式的报告
        """
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=7)

        history = self.metrics_collector.get_history_df()

        if history.empty:
            return "# 周报\n\n暂无数据"

        history["timestamp"] = pd.to_datetime(history["timestamp"])
        week_data = history[
            (history["timestamp"] >= start_date) &
            (history["timestamp"] <= end_date)
        ]

        if week_data.empty:
            return f"# 周报 - {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}\n\n本周暂无数据"

        lines = [
            f"# 量化交易系统周报",
            f"",
            f"**周期**: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
            f"",
            "## 汇总统计",
            f"",
            "### 数据健康",
            f"| 指标 | 平均值 | 最小值 | 最大值 |",
            f"|------|--------|--------|--------|",
            f"| 数据延迟(分钟) | {week_data['data_freshness_minutes'].mean():.1f} | {week_data['data_freshness_minutes'].min():.1f} | {week_data['data_freshness_minutes'].max():.1f} |",
            f"| 数据完整率(%) | {week_data['data_completeness_pct'].mean():.2f} | {week_data['data_completeness_pct'].min():.2f} | {week_data['data_completeness_pct'].max():.2f} |",
            f"",
            "### 模型性能",
            f"| 指标 | 平均值 | 最小值 | 最大值 |",
            f"|------|--------|--------|--------|",
            f"| 滚动IC | {week_data['rolling_ic'].mean():.4f} | {week_data['rolling_ic'].min():.4f} | {week_data['rolling_ic'].max():.4f} |",
            f"| IC/IR | {week_data['ic_ir'].mean():.4f} | {week_data['ic_ir'].min():.4f} | {week_data['ic_ir'].max():.4f} |",
            f"| 预测准确率(%) | {week_data['prediction_accuracy_pct'].mean():.2f} | {week_data['prediction_accuracy_pct'].min():.2f} | {week_data['prediction_accuracy_pct'].max():.2f} |",
            f"",
            "### 系统性能",
            f"| 指标 | 平均值 | 最小值 | 最大值 |",
            f"|------|--------|--------|--------|",
            f"| 回测时间(秒) | {week_data['backtest_time_seconds'].mean():.2f} | {week_data['backtest_time_seconds'].min():.2f} | {week_data['backtest_time_seconds'].max():.2f} |",
            f"| 内存占用(MB) | {week_data['memory_usage_mb'].mean():.1f} | {week_data['memory_usage_mb'].min():.1f} | {week_data['memory_usage_mb'].max():.1f} |",
            f"",
        ]

        return "\n".join(lines)

    def generate_json_report(self) -> Dict[str, Any]:
        """生成JSON格式的报告

        Returns:
            报告数据字典
        """
        summary = self.metrics_collector.get_summary()

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "current_metrics": self.metrics_collector.collect().to_dict(),
        }

        if self.alert_manager:
            report["active_alerts"] = [
                alert.to_dict()
                for alert in self.alert_manager.get_active_alerts()
            ]

        return report

    def save_report(self, report: str, filepath: str):
        """保存报告到文件

        Args:
            report: 报告内容
            filepath: 文件路径
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Report saved: {filepath}")

    def save_json_report(self, filepath: str):
        """保存JSON报告

        Args:
            filepath: 文件路径
        """
        report = self.generate_json_report()

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report saved: {filepath}")
