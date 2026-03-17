"""
系统指标采集模块

采集数据健康、模型性能、回测性能等系统指标。
"""

import psutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import deque
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """系统指标数据类

    Attributes:
        timestamp: 采集时间戳

        # 数据健康指标
        data_freshness_minutes: 数据延迟（分钟）
        data_completeness_pct: 数据完整率（%）
        sync_failure_rate_pct: 同步失败率（%）

        # 模型性能指标
        rolling_ic: 滚动IC（20日）
        ic_ir: IC/IR比率
        prediction_accuracy_pct: 预测准确率（%）

        # 回测性能指标
        backtest_time_seconds: 单次回测时间（秒）
        memory_usage_mb: 内存占用（MB）
        cache_hit_rate_pct: 缓存命中率（%）

        # 可视化指标
        dashboard_load_time_ms: Dashboard加载时间（毫秒）
    """

    timestamp: datetime = field(default_factory=datetime.now)

    # 数据健康
    data_freshness_minutes: float = 0.0
    data_completeness_pct: float = 100.0
    sync_failure_rate_pct: float = 0.0

    # 模型性能
    rolling_ic: float = 0.0
    ic_ir: float = 0.0
    prediction_accuracy_pct: float = 0.0

    # 回测性能
    backtest_time_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cache_hit_rate_pct: float = 0.0

    # 可视化
    dashboard_load_time_ms: float = 0.0

    # 扩展指标
    extra_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "data_freshness_minutes": self.data_freshness_minutes,
            "data_completeness_pct": self.data_completeness_pct,
            "sync_failure_rate_pct": self.sync_failure_rate_pct,
            "rolling_ic": self.rolling_ic,
            "ic_ir": self.ic_ir,
            "prediction_accuracy_pct": self.prediction_accuracy_pct,
            "backtest_time_seconds": self.backtest_time_seconds,
            "memory_usage_mb": self.memory_usage_mb,
            "cache_hit_rate_pct": self.cache_hit_rate_pct,
            "dashboard_load_time_ms": self.dashboard_load_time_ms,
            **self.extra_metrics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemMetrics":
        """从字典创建"""
        extra = {k: v for k, v in data.items() if k not in cls.__dataclass_fields__}

        metrics = cls(
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            data_freshness_minutes=data.get("data_freshness_minutes", 0.0),
            data_completeness_pct=data.get("data_completeness_pct", 100.0),
            sync_failure_rate_pct=data.get("sync_failure_rate_pct", 0.0),
            rolling_ic=data.get("rolling_ic", 0.0),
            ic_ir=data.get("ic_ir", 0.0),
            prediction_accuracy_pct=data.get("prediction_accuracy_pct", 0.0),
            backtest_time_seconds=data.get("backtest_time_seconds", 0.0),
            memory_usage_mb=data.get("memory_usage_mb", 0.0),
            cache_hit_rate_pct=data.get("cache_hit_rate_pct", 0.0),
            dashboard_load_time_ms=data.get("dashboard_load_time_ms", 0.0),
            extra_metrics=extra,
        )
        return metrics


class SystemMetricsCollector:
    """系统指标采集器

    负责采集系统各项性能指标。

    Example:
        >>> collector = SystemMetricsCollector()
        >>> metrics = collector.collect()
        >>> print(f"Data freshness: {metrics.data_freshness_minutes} min")
    """

    def __init__(self, max_history: int = 1000):
        """初始化采集器

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._backtest_times: deque = deque(maxlen=100)
        self._cache_stats = {"hits": 0, "misses": 0}
        self._dashboard_load_times: deque = deque(maxlen=100)

    def collect(self) -> SystemMetrics:
        """采集当前系统指标

        Returns:
            SystemMetrics 包含所有当前指标
        """
        metrics = SystemMetrics()

        # 采集数据健康指标
        metrics = self._collect_data_health(metrics)

        # 采集模型性能指标
        metrics = self._collect_model_performance(metrics)

        # 采集回测性能指标
        metrics = self._collect_backtest_performance(metrics)

        # 采集系统资源
        metrics = self._collect_system_resources(metrics)

        # 保存到历史
        self._history.append(metrics)

        logger.debug(f"Metrics collected: {metrics.to_dict()}")
        return metrics

    def _collect_data_health(self, metrics: SystemMetrics) -> SystemMetrics:
        """采集数据健康指标"""
        try:
            # 这里应该连接到实际的数据同步模块
            # 现在使用模拟值
            metrics.data_freshness_minutes = self._get_data_freshness()
            metrics.data_completeness_pct = self._get_data_completeness()
            metrics.sync_failure_rate_pct = self._get_sync_failure_rate()
        except Exception as e:
            logger.warning(f"Failed to collect data health metrics: {e}")

        return metrics

    def _collect_model_performance(self, metrics: SystemMetrics) -> SystemMetrics:
        """采集模型性能指标"""
        try:
            # 从模型评估模块获取
            metrics.rolling_ic = self._get_rolling_ic()
            metrics.ic_ir = self._get_ic_ir()
            metrics.prediction_accuracy_pct = self._get_prediction_accuracy()
        except Exception as e:
            logger.warning(f"Failed to collect model performance metrics: {e}")

        return metrics

    def _collect_backtest_performance(self, metrics: SystemMetrics) -> SystemMetrics:
        """采集回测性能指标"""
        # 平均回测时间
        if self._backtest_times:
            metrics.backtest_time_seconds = np.mean(list(self._backtest_times))

        # 缓存命中率
        total_cache_ops = self._cache_stats["hits"] + self._cache_stats["misses"]
        if total_cache_ops > 0:
            metrics.cache_hit_rate_pct = self._cache_stats["hits"] / total_cache_ops * 100

        # Dashboard加载时间
        if self._dashboard_load_times:
            metrics.dashboard_load_time_ms = np.mean(list(self._dashboard_load_times))

        return metrics

    def _collect_system_resources(self, metrics: SystemMetrics) -> SystemMetrics:
        """采集系统资源指标"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
        except Exception as e:
            logger.warning(f"Failed to collect system resources: {e}")

        return metrics

    # 模拟方法（实际应该连接到相应模块）
    def _get_data_freshness(self) -> float:
        """获取数据延迟（分钟）"""
        # TODO: 从数据同步模块获取实际延迟
        return 0.0

    def _get_data_completeness(self) -> float:
        """获取数据完整率"""
        # TODO: 从数据完整性检查获取
        return 99.5

    def _get_sync_failure_rate(self) -> float:
        """获取同步失败率"""
        # TODO: 从同步日志统计
        return 0.0

    def _get_rolling_ic(self) -> float:
        """获取滚动IC"""
        # TODO: 从模型评估模块获取
        return 0.05

    def _get_ic_ir(self) -> float:
        """获取IC/IR"""
        # TODO: 从模型评估模块获取
        return 0.5

    def _get_prediction_accuracy(self) -> float:
        """获取预测准确率"""
        # TODO: 从模型评估模块获取
        return 55.0

    def record_backtest_time(self, duration_seconds: float):
        """记录回测时间

        Args:
            duration_seconds: 回测耗时（秒）
        """
        self._backtest_times.append(duration_seconds)
        logger.debug(f"Backtest time recorded: {duration_seconds:.2f}s")

    def record_cache_hit(self):
        """记录缓存命中"""
        self._cache_stats["hits"] += 1

    def record_cache_miss(self):
        """记录缓存未命中"""
        self._cache_stats["misses"] += 1

    def record_dashboard_load_time(self, duration_ms: float):
        """记录Dashboard加载时间

        Args:
            duration_ms: 加载时间（毫秒）
        """
        self._dashboard_load_times.append(duration_ms)

    def get_history(self, n: Optional[int] = None) -> List[SystemMetrics]:
        """获取历史指标

        Args:
            n: 获取最近n条，None表示全部

        Returns:
            SystemMetrics列表
        """
        history_list = list(self._history)
        if n is not None:
            return history_list[-n:]
        return history_list

    def get_history_df(self, n: Optional[int] = None) -> pd.DataFrame:
        """获取历史指标DataFrame

        Args:
            n: 获取最近n条

        Returns:
            指标DataFrame
        """
        history = self.get_history(n)
        if not history:
            return pd.DataFrame()

        data = [m.to_dict() for m in history]
        return pd.DataFrame(data)

    def clear_history(self):
        """清空历史记录"""
        self._history.clear()
        self._backtest_times.clear()
        self._cache_stats = {"hits": 0, "misses": 0}
        self._dashboard_load_times.clear()
        logger.info("Metrics history cleared")

    def get_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        if not self._history:
            return {}

        history_df = self.get_history_df()

        summary = {
            "records_count": len(history_df),
            "time_range": {
                "start": history_df["timestamp"].iloc[0] if len(history_df) > 0 else None,
                "end": history_df["timestamp"].iloc[-1] if len(history_df) > 0 else None,
            },
            "avg_backtest_time": history_df["backtest_time_seconds"].mean(),
            "avg_memory_usage": history_df["memory_usage_mb"].mean(),
            "avg_cache_hit_rate": history_df["cache_hit_rate_pct"].mean(),
            "avg_data_freshness": history_df["data_freshness_minutes"].mean(),
        }

        return summary
