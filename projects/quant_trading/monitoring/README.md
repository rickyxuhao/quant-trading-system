# 监控与告警系统

## 功能概述

提供系统指标采集、告警管理和报告生成功能。

## 模块结构

```
monitoring/
├── __init__.py           # 模块导出
├── metrics.py            # 系统指标采集
├── alerts.py             # 告警管理
└── reporters.py          # 报告生成
```

## 系统指标

| 类别 | 指标 | 正常范围 | 告警阈值 |
|:---|:---|:---|:---|
| **数据健康** | 数据延迟 | < 1小时 | > 2小时 |
| | 数据完整率 | > 99% | < 98% |
| | 同步失败率 | < 1% | > 5% |
| **模型性能** | 滚动IC (20日) | > 0.05 | < 0.02 |
| | IC/IR | > 0.5 | < 0.3 |
| | 预测准确率 | > 52% | < 50% |
| **回测性能** | 单次回测时间 | < 30秒 | > 2分钟 |
| | 内存占用 | < 2GB | > 4GB |
| **可视化** | Dashboard加载 | < 3秒 | > 5秒 |

## 告警规则

内置告警规则：

- `data_delay` - 数据延迟超过2小时
- `data_completeness` - 数据完整率低于98%
- `sync_failure_rate` - 同步失败率超过5%
- `model_degradation` - 模型性能衰减
- `prediction_accuracy` - 预测准确率低于50%
- `backtest_slow` - 回测执行时间过长
- `high_memory_usage` - 内存占用过高
- `dashboard_slow` - Dashboard加载缓慢

## 使用示例

```python
from projects.quant_trading.monitoring import (
    SystemMetricsCollector, AlertManager, AlertLevel
)

# 创建指标采集器
collector = SystemMetricsCollector()

# 采集当前指标
metrics = collector.collect()
print(f"Data freshness: {metrics.data_freshness_minutes} min")

# 创建告警管理器
manager = AlertManager()

# 自定义告警规则
manager.add_rule(
    name="custom_rule",
    condition=lambda m: m.memory_usage_mb > 2048,
    level=AlertLevel.WARNING,
    message="内存使用超过2GB"
)

# 检查指标并触发告警
alerts = manager.check_metrics(metrics)

# 配置邮件通知
manager.configure_email(
    smtp_server="smtp.example.com",
    smtp_port=587,
    username="user@example.com",
    password="password",
    from_addr="alerts@example.com",
    to_addr="admin@example.com",
)
```

## 报告生成

```python
from projects.quant_trading.monitoring import MetricsReporter

reporter = MetricsReporter(collector, manager)

# 生成日报
daily_report = reporter.generate_daily_report()
reporter.save_report(daily_report, "reports/daily.md")

# 生成周报
weekly_report = reporter.generate_weekly_report()
reporter.save_report(weekly_report, "reports/weekly.md")

# 生成JSON报告
reporter.save_json_report("reports/metrics.json")
```
