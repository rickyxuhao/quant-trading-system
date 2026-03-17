"""
监控告警模块单元测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from projects.quant_trading.monitoring.alerts import (
    AlertLevel,
    AlertChannel,
    Alert,
    AlertRule,
    AlertManager,
    AlertCondition,
)
from projects.quant_trading.monitoring.metrics import SystemMetrics


class TestAlertLevel:
    """测试告警级别枚举"""

    def test_alert_level_values(self):
        """测试告警级别值"""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"


class TestAlertChannel:
    """测试告警渠道枚举"""

    def test_alert_channel_values(self):
        """测试告警渠道值"""
        assert AlertChannel.LOG.value == "log"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.CONSOLE.value == "console"
        assert AlertChannel.DASHBOARD.value == "dashboard"
        assert AlertChannel.WEBHOOK.value == "webhook"


class TestAlert:
    """测试告警数据类"""

    def test_alert_creation(self):
        """测试告警创建"""
        alert = Alert(
            name="test_alert",
            level=AlertLevel.WARNING,
            message="Test message",
        )
        assert alert.name == "test_alert"
        assert alert.level == AlertLevel.WARNING
        assert alert.message == "Test message"
        assert alert.acknowledged is False
        assert alert.resolved is False
        assert isinstance(alert.timestamp, datetime)

    def test_alert_with_metrics(self):
        """测试带指标的告警"""
        metrics = SystemMetrics(data_freshness_minutes=150)
        alert = Alert(
            name="data_delay",
            level=AlertLevel.CRITICAL,
            message="Data delay detected",
            metrics=metrics,
        )
        assert alert.metrics == metrics

    def test_alert_to_dict(self):
        """测试告警转字典"""
        alert = Alert(
            name="test_alert",
            level=AlertLevel.WARNING,
            message="Test message",
            details={"key": "value"},
        )
        data = alert.to_dict()
        assert data["name"] == "test_alert"
        assert data["level"] == "warning"
        assert data["message"] == "Test message"
        assert data["details"] == {"key": "value"}
        assert "timestamp" in data

    def test_alert_to_dict_with_metrics(self):
        """测试带指标的告警转字典"""
        metrics = SystemMetrics(memory_usage_mb=1024)
        alert = Alert(
            name="test_alert",
            level=AlertLevel.INFO,
            message="Test",
            metrics=metrics,
        )
        data = alert.to_dict()
        assert data["metrics"] is not None
        assert data["metrics"]["memory_usage_mb"] == 1024

    def test_alert_acknowledge(self):
        """测试告警确认"""
        alert = Alert(
            name="test_alert",
            level=AlertLevel.WARNING,
            message="Test",
        )
        alert.acknowledge()
        assert alert.acknowledged is True

    def test_alert_resolve(self):
        """测试告警解决"""
        alert = Alert(
            name="test_alert",
            level=AlertLevel.WARNING,
            message="Test",
        )
        alert.resolve()
        assert alert.resolved is True


class TestAlertRule:
    """测试告警规则"""

    def test_alert_rule_creation(self):
        """测试告警规则创建"""
        condition: AlertCondition = lambda m: m.data_freshness_minutes > 120
        rule = AlertRule(
            name="data_delay",
            condition=condition,
            level=AlertLevel.CRITICAL,
            message="Data delay > 2 hours",
        )
        assert rule.name == "data_delay"
        assert rule.level == AlertLevel.CRITICAL
        assert rule.message == "Data delay > 2 hours"
        assert rule.cooldown_minutes == 60  # 默认值

    def test_alert_rule_should_trigger(self):
        """测试告警规则触发"""
        condition: AlertCondition = lambda m: m.data_freshness_minutes > 120
        rule = AlertRule(
            name="data_delay",
            condition=condition,
            level=AlertLevel.CRITICAL,
            message="Data delay",
        )
        # 应该触发
        metrics_high = SystemMetrics(data_freshness_minutes=150)
        assert rule.should_trigger(metrics_high) is True

        # 不应该触发
        metrics_low = SystemMetrics(data_freshness_minutes=60)
        assert rule.should_trigger(metrics_low) is False

    def test_alert_rule_cooldown(self):
        """测试告警规则冷却时间"""
        condition: AlertCondition = lambda m: True
        rule = AlertRule(
            name="always_trigger",
            condition=condition,
            level=AlertLevel.WARNING,
            message="Always",
            cooldown_minutes=5,
        )
        metrics = SystemMetrics()

        # 第一次触发
        assert rule.should_trigger(metrics) is True

        # 冷却期内不应触发
        assert rule.should_trigger(metrics) is False

    def test_alert_rule_exception_handling(self):
        """测试告警规则异常处理"""
        def bad_condition(m):
            raise ValueError("Test error")

        rule = AlertRule(
            name="bad_rule",
            condition=bad_condition,
            level=AlertLevel.WARNING,
            message="Bad",
        )
        metrics = SystemMetrics()
        # 应该返回False而不是抛出异常
        assert rule.should_trigger(metrics) is False


class TestAlertManager:
    """测试告警管理器"""

    def test_alert_manager_init(self):
        """测试告警管理器初始化"""
        manager = AlertManager()
        assert len(manager.get_rules()) == 8  # 8个默认规则

    def test_add_rule(self):
        """测试添加规则"""
        manager = AlertManager()
        condition: AlertCondition = lambda m: m.memory_usage_mb > 1000

        manager.add_rule(
            name="high_memory",
            condition=condition,
            level=AlertLevel.WARNING,
            message="Memory usage > 1GB",
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            cooldown_minutes=30,
        )

        rules = manager.get_rules()
        assert "high_memory" in rules
        assert rules["high_memory"].level == AlertLevel.WARNING

    def test_remove_rule(self):
        """测试移除规则"""
        manager = AlertManager()
        assert "data_delay" in manager.get_rules()

        manager.remove_rule("data_delay")
        assert "data_delay" not in manager.get_rules()

    def test_check_metrics_triggers_alert(self):
        """测试检查指标触发告警"""
        manager = AlertManager()
        # 使用会触发 data_delay 告警的指标 (延迟>120分钟)
        metrics = SystemMetrics(data_freshness_minutes=150)

        alerts = manager.check_metrics(metrics)

        # 应该触发 data_delay 告警
        assert len(alerts) >= 1
        assert any(a.name == "data_delay" for a in alerts)

    def test_check_metrics_no_trigger(self):
        """测试检查指标不触发告警"""
        manager = AlertManager()
        # 使用正常指标
        metrics = SystemMetrics(
            data_freshness_minutes=30,
            data_completeness_pct=99.5,
            rolling_ic=0.06,
            ic_ir=0.6,
            prediction_accuracy_pct=55,
            backtest_time_seconds=30,
            memory_usage_mb=1024,
            dashboard_load_time_ms=1000,
        )

        alerts = manager.check_metrics(metrics)
        # 所有指标正常，不应该触发任何告警
        assert len(alerts) == 0

    def test_check_metrics_multiple_alerts(self):
        """测试检查指标触发多个告警"""
        manager = AlertManager()
        # 多个异常指标
        metrics = SystemMetrics(
            data_freshness_minutes=150,  # 触发 data_delay
            data_completeness_pct=95,     # 触发 data_completeness
            rolling_ic=0.01,              # 触发 model_degradation
            prediction_accuracy_pct=48,   # 触发 prediction_accuracy
        )

        alerts = manager.check_metrics(metrics)
        assert len(alerts) >= 3

    def test_get_active_alerts(self):
        """测试获取活跃告警"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        # 触发告警
        manager.check_metrics(metrics)
        active_alerts = manager.get_active_alerts()

        assert len(active_alerts) >= 1

    def test_get_active_alerts_by_level(self):
        """测试按级别获取活跃告警"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        manager.check_metrics(metrics)
        critical_alerts = manager.get_active_alerts(level=AlertLevel.CRITICAL)

        # data_delay 是 CRITICAL 级别
        assert all(a.level == AlertLevel.CRITICAL for a in critical_alerts)

    def test_get_active_alerts_include_resolved(self):
        """测试包含已解决告警"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        alerts = manager.check_metrics(metrics)
        # 解决告警
        for alert in alerts:
            alert.resolve()

        # 不包含已解决的
        active_only = manager.get_active_alerts(include_resolved=False)
        assert len(active_only) == 0

        # 包含已解决的
        with_resolved = manager.get_active_alerts(include_resolved=True)
        assert len(with_resolved) >= 1

    def test_acknowledge_alert(self):
        """测试确认告警"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        manager.check_metrics(metrics)
        manager.acknowledge_alert("data_delay")

        alerts = manager.get_active_alerts()
        data_delay_alert = next((a for a in alerts if a.name == "data_delay"), None)
        if data_delay_alert:
            assert data_delay_alert.acknowledged is True

    def test_resolve_alert(self):
        """测试解决告警"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        manager.check_metrics(metrics)
        manager.resolve_alert("data_delay")

        active_alerts = manager.get_active_alerts()
        assert not any(a.name == "data_delay" for a in active_alerts)

    def test_clear_history(self):
        """测试清空历史"""
        manager = AlertManager()
        metrics = SystemMetrics(data_freshness_minutes=150)

        manager.check_metrics(metrics)
        assert len(manager.get_alert_history()) >= 1

        manager.clear_history()
        assert len(manager.get_alert_history()) == 0

    def test_disable_rule(self):
        """测试禁用规则"""
        manager = AlertManager()
        assert "data_delay" in manager.get_rules()

        manager.disable_rule("data_delay")
        assert "data_delay" not in manager.get_rules()

    def test_configure_email(self):
        """测试配置邮件"""
        manager = AlertManager()
        manager.configure_email(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            username="test@example.com",
            password="password",
            from_addr="test@example.com",
            to_addr="admin@example.com",
        )
        # 配置成功不会抛出异常
        assert True

    def test_configure_webhook(self):
        """测试配置Webhook"""
        manager = AlertManager()
        manager.configure_webhook("https://hooks.example.com/alerts")
        assert True


class TestAlertManagerChannels:
    """测试告警通知渠道"""

    def test_send_to_log(self):
        """测试发送到日志"""
        manager = AlertManager()
        alert = Alert(
            name="test",
            level=AlertLevel.WARNING,
            message="Test message",
        )
        # 不应该抛出异常
        manager._send_to_log(alert)

    def test_send_to_console(self):
        """测试发送到控制台"""
        manager = AlertManager()
        alert = Alert(
            name="test",
            level=AlertLevel.INFO,
            message="Test message",
        )
        # 不应该抛出异常
        manager._send_to_console(alert)

    @patch("smtplib.SMTP")
    def test_send_email(self, mock_smtp):
        """测试发送邮件"""
        manager = AlertManager()
        manager.configure_email(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            username="test@example.com",
            password="password",
            from_addr="test@example.com",
            to_addr="admin@example.com",
        )

        alert = Alert(
            name="test",
            level=AlertLevel.CRITICAL,
            message="Critical alert",
        )

        manager._send_email(alert)
        mock_smtp.assert_called_once()

    def test_send_email_not_configured(self):
        """测试未配置邮件时发送"""
        manager = AlertManager()  # 未配置邮件
        alert = Alert(
            name="test",
            level=AlertLevel.WARNING,
            message="Test",
        )
        # 不应该抛出异常
        manager._send_email(alert)

    @patch("requests.post")
    def test_send_webhook(self, mock_post):
        """测试发送Webhook"""
        manager = AlertManager()
        manager.configure_webhook("https://hooks.example.com/alerts")

        alert = Alert(
            name="test",
            level=AlertLevel.WARNING,
            message="Test alert",
        )

        manager._send_webhook(alert)
        mock_post.assert_called_once()

    def test_send_webhook_not_configured(self):
        """测试未配置Webhook时发送"""
        manager = AlertManager()
        alert = Alert(
            name="test",
            level=AlertLevel.WARNING,
            message="Test",
        )
        # 不应该抛出异常
        manager._send_webhook(alert)


class TestDefaultRules:
    """测试默认告警规则"""

    def test_default_rules_count(self):
        """测试默认规则数量"""
        manager = AlertManager()
        rules = manager.get_rules()
        assert len(rules) == 8

    def test_data_delay_rule(self):
        """测试数据延迟规则"""
        manager = AlertManager()
        rules = manager.get_rules()

        assert "data_delay" in rules
        rule = rules["data_delay"]
        assert rule.level == AlertLevel.CRITICAL
        assert rule.cooldown_minutes == 30

        # 测试触发条件
        metrics_trigger = SystemMetrics(data_freshness_minutes=150)
        metrics_normal = SystemMetrics(data_freshness_minutes=60)

        assert rule.should_trigger(metrics_trigger) is True
        assert rule.should_trigger(metrics_normal) is False

    def test_data_completeness_rule(self):
        """测试数据完整率规则"""
        manager = AlertManager()
        rule = manager.get_rules()["data_completeness"]

        assert rule.level == AlertLevel.WARNING

        metrics_trigger = SystemMetrics(data_completeness_pct=95)
        metrics_normal = SystemMetrics(data_completeness_pct=99)

        assert rule.should_trigger(metrics_trigger) is True
        assert rule.should_trigger(metrics_normal) is False

    def test_model_degradation_rule(self):
        """测试模型性能衰减规则"""
        manager = AlertManager()
        rule = manager.get_rules()["model_degradation"]

        assert rule.level == AlertLevel.WARNING

        # IC < 0.02 触发
        metrics_low_ic = SystemMetrics(rolling_ic=0.01, ic_ir=0.5)
        metrics_normal = SystemMetrics(rolling_ic=0.05, ic_ir=0.5)

        assert rule.should_trigger(metrics_low_ic) is True
        assert rule.should_trigger(metrics_normal) is False

    def test_backtest_slow_rule(self):
        """测试回测慢规则"""
        manager = AlertManager()
        rule = manager.get_rules()["backtest_slow"]

        assert rule.level == AlertLevel.WARNING

        metrics_trigger = SystemMetrics(backtest_time_seconds=150)
        metrics_normal = SystemMetrics(backtest_time_seconds=30)

        assert rule.should_trigger(metrics_trigger) is True
        assert rule.should_trigger(metrics_normal) is False

    def test_high_memory_usage_rule(self):
        """测试高内存使用规则"""
        manager = AlertManager()
        rule = manager.get_rules()["high_memory_usage"]

        assert rule.level == AlertLevel.WARNING

        metrics_trigger = SystemMetrics(memory_usage_mb=5000)
        metrics_normal = SystemMetrics(memory_usage_mb=1024)

        assert rule.should_trigger(metrics_trigger) is True
        assert rule.should_trigger(metrics_normal) is False
