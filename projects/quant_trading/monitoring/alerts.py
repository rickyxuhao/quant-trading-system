"""
告警管理模块

提供告警规则配置、告警触发和通知功能。
"""
import json
import smtplib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum, auto
from collections import deque
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .metrics import SystemMetrics

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """告警渠道"""
    LOG = "log"
    EMAIL = "email"
    CONSOLE = "console"
    DASHBOARD = "dashboard"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """告警数据类

    Attributes:
        name: 告警规则名称
        level: 告警级别
        message: 告警消息
        timestamp: 触发时间
        metrics: 触发时的指标值
        details: 额外详情
        acknowledged: 是否已确认
        resolved: 是否已解决
    """
    name: str
    level: AlertLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: Optional[SystemMetrics] = None
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "details": self.details,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }

    def acknowledge(self):
        """确认告警"""
        self.acknowledged = True
        logger.info(f"Alert acknowledged: {self.name}")

    def resolve(self):
        """标记为已解决"""
        self.resolved = True
        logger.info(f"Alert resolved: {self.name}")


# 告警规则类型
AlertCondition = Callable[[SystemMetrics], bool]


@dataclass
class AlertRule:
    """告警规则

    Attributes:
        name: 规则名称
        condition: 触发条件函数
        level: 告警级别
        message: 告警消息模板
        channels: 通知渠道
        cooldown_minutes: 冷却时间（分钟）
    """
    name: str
    condition: AlertCondition
    level: AlertLevel
    message: str
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])
    cooldown_minutes: int = 60
    _last_triggered: Optional[datetime] = field(default=None, repr=False)

    def should_trigger(self, metrics: SystemMetrics) -> bool:
        """检查是否应该触发"""
        # 检查冷却时间
        if self._last_triggered is not None:
            elapsed = (datetime.now() - self._last_triggered).total_seconds() / 60
            if elapsed < self.cooldown_minutes:
                return False

        # 检查条件
        try:
            if self.condition(metrics):
                self._last_triggered = datetime.now()
                return True
        except Exception as e:
            logger.error(f"Error evaluating alert rule {self.name}: {e}")

        return False


class AlertManager:
    """告警管理器

    管理告警规则、触发告警和发送通知。

    Example:
        >>> manager = AlertManager()
        >>> manager.add_rule(
        ...     name="data_delay",
        ...     condition=lambda m: m.data_freshness_minutes > 120,
        ...     level=AlertLevel.CRITICAL,
        ...     message="数据同步延迟超过2小时"
        ... )
        >>> alerts = manager.check_metrics(metrics)
    """

    # 默认告警规则
    DEFAULT_RULES: Dict[str, Dict[str, Any]] = {
        "data_delay": {
            "condition": lambda m: m.data_freshness_minutes > 120,
            "level": AlertLevel.CRITICAL,
            "message": "数据同步延迟超过2小时",
            "channels": [AlertChannel.LOG, AlertChannel.DASHBOARD],
            "cooldown_minutes": 30,
        },
        "data_completeness": {
            "condition": lambda m: m.data_completeness_pct < 98,
            "level": AlertLevel.WARNING,
            "message": "数据完整率低于98%",
            "channels": [AlertChannel.LOG],
            "cooldown_minutes": 60,
        },
        "sync_failure_rate": {
            "condition": lambda m: m.sync_failure_rate_pct > 5,
            "level": AlertLevel.CRITICAL,
            "message": "数据同步失败率超过5%",
            "channels": [AlertChannel.LOG, AlertChannel.DASHBOARD],
            "cooldown_minutes": 30,
        },
        "model_degradation": {
            "condition": lambda m: m.rolling_ic < 0.02 or m.ic_ir < 0.3,
            "level": AlertLevel.WARNING,
            "message": "模型性能衰减，建议检查",
            "channels": [AlertChannel.LOG, AlertChannel.DASHBOARD],
            "cooldown_minutes": 240,  # 4小时冷却
        },
        "prediction_accuracy": {
            "condition": lambda m: m.prediction_accuracy_pct < 50,
            "level": AlertLevel.WARNING,
            "message": "预测准确率低于50%",
            "channels": [AlertChannel.LOG],
            "cooldown_minutes": 60,
        },
        "backtest_slow": {
            "condition": lambda m: m.backtest_time_seconds > 120,
            "level": AlertLevel.WARNING,
            "message": "回测执行时间超过2分钟",
            "channels": [AlertChannel.LOG],
            "cooldown_minutes": 30,
        },
        "high_memory_usage": {
            "condition": lambda m: m.memory_usage_mb > 4096,
            "level": AlertLevel.WARNING,
            "message": "内存占用超过4GB",
            "channels": [AlertChannel.LOG],
            "cooldown_minutes": 30,
        },
        "dashboard_slow": {
            "condition": lambda m: m.dashboard_load_time_ms > 5000,
            "level": AlertLevel.WARNING,
            "message": "Dashboard加载时间超过5秒",
            "channels": [AlertChannel.LOG],
            "cooldown_minutes": 30,
        },
    }

    def __init__(self, max_alert_history: int = 1000):
        """初始化告警管理器

        Args:
            max_alert_history: 最大告警历史记录数
        """
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: deque = deque(maxlen=max_alert_history)
        self._email_config: Optional[Dict[str, str]] = None
        self._webhook_url: Optional[str] = None

        # 注册默认规则
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认告警规则"""
        for name, config in self.DEFAULT_RULES.items():
            self.add_rule(
                name=name,
                condition=config["condition"],
                level=config["level"],
                message=config["message"],
                channels=config.get("channels", [AlertChannel.LOG]),
                cooldown_minutes=config.get("cooldown_minutes", 60),
            )

    def add_rule(
        self,
        name: str,
        condition: AlertCondition,
        level: AlertLevel,
        message: str,
        channels: Optional[List[AlertChannel]] = None,
        cooldown_minutes: int = 60,
    ):
        """添加告警规则

        Args:
            name: 规则名称
            condition: 触发条件函数
            level: 告警级别
            message: 告警消息
            channels: 通知渠道
            cooldown_minutes: 冷却时间
        """
        if channels is None:
            channels = [AlertChannel.LOG]

        self._rules[name] = AlertRule(
            name=name,
            condition=condition,
            level=level,
            message=message,
            channels=channels,
            cooldown_minutes=cooldown_minutes,
        )

        logger.debug(f"Alert rule added: {name}")

    def remove_rule(self, name: str):
        """移除告警规则"""
        if name in self._rules:
            del self._rules[name]
            logger.debug(f"Alert rule removed: {name}")

    def check_metrics(self, metrics: SystemMetrics) -> List[Alert]:
        """检查指标并触发告警

        Args:
            metrics: 系统指标

        Returns:
            触发的告警列表
        """
        triggered_alerts = []

        for rule_name, rule in self._rules.items():
            if rule.should_trigger(metrics):
                alert = Alert(
                    name=rule_name,
                    level=rule.level,
                    message=rule.message,
                    metrics=metrics,
                )

                self._alerts.append(alert)
                triggered_alerts.append(alert)

                # 发送通知
                self._send_alert(alert, rule.channels)

                logger.warning(f"Alert triggered: {rule_name} - {rule.message}")

        return triggered_alerts

    def _send_alert(self, alert: Alert, channels: List[AlertChannel]):
        """发送告警通知

        Args:
            alert: 告警对象
            channels: 通知渠道列表
        """
        for channel in channels:
            try:
                if channel == AlertChannel.LOG:
                    self._send_to_log(alert)
                elif channel == AlertChannel.CONSOLE:
                    self._send_to_console(alert)
                elif channel == AlertChannel.EMAIL:
                    self._send_email(alert)
                elif channel == AlertChannel.DASHBOARD:
                    self._send_to_dashboard(alert)
                elif channel == AlertChannel.WEBHOOK:
                    self._send_webhook(alert)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel.value}: {e}")

    def _send_to_log(self, alert: Alert):
        """记录到日志"""
        log_msg = f"[{alert.level.value.upper()}] {alert.name}: {alert.message}"

        if alert.level == AlertLevel.CRITICAL:
            logger.critical(log_msg)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def _send_to_console(self, alert: Alert):
        """输出到控制台"""
        print(f"\n[ALERT] {alert.level.value.upper()}: {alert.message}")
        print(f"  Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    def _send_email(self, alert: Alert):
        """发送邮件"""
        if self._email_config is None:
            logger.debug("Email not configured, skipping email alert")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self._email_config["from"]
            msg["To"] = self._email_config["to"]
            msg["Subject"] = f"[{alert.level.value.upper()}] 量化交易系统告警: {alert.name}"

            body = f"""
告警名称: {alert.name}
告警级别: {alert.level.value}
告警消息: {alert.message}
触发时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

详细信息:
{json.dumps(alert.metrics.to_dict() if alert.metrics else {}, indent=2, ensure_ascii=False)}
            """

            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(
                self._email_config["smtp_server"],
                int(self._email_config.get("smtp_port", 587)),
            ) as server:
                if self._email_config.get("use_tls", "true").lower() == "true":
                    server.starttls()
                server.login(
                    self._email_config["username"],
                    self._email_config["password"],
                )
                server.send_message(msg)

            logger.info(f"Alert email sent: {alert.name}")

        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    def _send_to_dashboard(self, alert: Alert):
        """发送到Dashboard（保存到内存供查询）"""
        # Dashboard可以通过get_active_alerts获取活跃告警
        pass

    def _send_webhook(self, alert: Alert):
        """发送到Webhook"""
        if self._webhook_url is None:
            return

        try:
            import requests

            payload = {
                "alert_name": alert.name,
                "level": alert.level.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "metrics": alert.metrics.to_dict() if alert.metrics else None,
            }

            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

            logger.info(f"Alert webhook sent: {alert.name}")

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")

    def configure_email(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addr: str,
        use_tls: bool = True,
    ):
        """配置邮件通知

        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口
            username: 用户名
            password: 密码
            from_addr: 发件人
            to_addr: 收件人
            use_tls: 是否使用TLS
        """
        self._email_config = {
            "smtp_server": smtp_server,
            "smtp_port": str(smtp_port),
            "username": username,
            "password": password,
            "from": from_addr,
            "to": to_addr,
            "use_tls": str(use_tls).lower(),
        }
        logger.info(f"Email configured: {from_addr} -> {to_addr}")

    def configure_webhook(self, url: str):
        """配置Webhook通知

        Args:
            url: Webhook URL
        """
        self._webhook_url = url
        logger.info(f"Webhook configured: {url}")

    def get_active_alerts(
        self,
        level: Optional[AlertLevel] = None,
        include_resolved: bool = False,
    ) -> List[Alert]:
        """获取活跃告警

        Args:
            level: 过滤指定级别
            include_resolved: 是否包含已解决的告警

        Returns:
            告警列表
        """
        alerts = list(self._alerts)

        if not include_resolved:
            alerts = [a for a in alerts if not a.resolved]

        if level is not None:
            alerts = [a for a in alerts if a.level == level]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_history(self, n: Optional[int] = None) -> List[Alert]:
        """获取告警历史

        Args:
            n: 最近n条

        Returns:
            告警列表
        """
        alerts = list(self._alerts)
        if n is not None:
            alerts = alerts[-n:]
        return alerts

    def acknowledge_alert(self, alert_name: str):
        """确认告警"""
        for alert in self._alerts:
            if alert.name == alert_name and not alert.acknowledged:
                alert.acknowledge()

    def resolve_alert(self, alert_name: str):
        """解决告警"""
        for alert in self._alerts:
            if alert.name == alert_name and not alert.resolved:
                alert.resolve()

    def clear_history(self):
        """清空告警历史"""
        self._alerts.clear()
        logger.info("Alert history cleared")

    def get_rules(self) -> Dict[str, AlertRule]:
        """获取所有规则"""
        return self._rules.copy()

    def enable_rule(self, name: str):
        """启用规则"""
        # 规则默认启用，可以通过重新添加来实现
        pass

    def disable_rule(self, name: str):
        """禁用规则"""
        if name in self._rules:
            del self._rules[name]
            logger.info(f"Rule disabled: {name}")
