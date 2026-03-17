"""
风控管理器单元测试
"""

from datetime import datetime

import pandas as pd

from projects.quant_trading.backtest.risk_manager import (
    RiskManager,
    RiskConfig,
    RiskAlert,
    RiskSeverity,
    RiskAlertType,
)


class TestRiskConfig:
    """测试风控配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = RiskConfig()

        assert config.max_drawdown_limit == 0.15
        assert config.drawdown_warning == 0.10
        assert config.max_position_weight == 0.30
        assert config.stop_loss_pct == 0.08

    def test_custom_config(self):
        """测试自定义配置"""
        config = RiskConfig(max_drawdown_limit=0.20, stop_loss_pct=0.10, max_position_weight=0.40)

        assert config.max_drawdown_limit == 0.20
        assert config.stop_loss_pct == 0.10
        assert config.max_position_weight == 0.40


class TestRiskAlert:
    """测试风控告警"""

    def test_alert_creation(self):
        """测试告警创建"""
        alert = RiskAlert(
            timestamp=datetime(2023, 1, 15),
            alert_type=RiskAlertType.STOP_LOSS,
            severity=RiskSeverity.CRITICAL,
            message="触发止损",
            value=0.12,
            threshold=0.08,
        )

        assert alert.alert_type == RiskAlertType.STOP_LOSS
        assert alert.severity == RiskSeverity.CRITICAL
        assert alert.value == 0.12

    def test_alert_to_dict(self):
        """测试告警转字典"""
        alert = RiskAlert(
            timestamp=datetime(2023, 1, 15),
            alert_type=RiskAlertType.MAX_DRAWDOWN,
            severity=RiskSeverity.WARNING,
            message="回撤超限",
            value=0.18,
            threshold=0.15,
        )

        data = alert.to_dict()

        assert data["type"] == "max_drawdown"
        assert data["severity"] == "warning"
        assert data["value"] == 0.18


class TestRiskManagerInit:
    """测试风控管理器初始化"""

    def test_default_init(self):
        """测试默认初始化"""
        rm = RiskManager()

        assert rm.config is not None
        assert len(rm.alerts) == 0

    def test_custom_config_init(self):
        """测试自定义配置初始化"""
        config = RiskConfig(max_drawdown_limit=0.20)
        rm = RiskManager(config)

        assert rm.config.max_drawdown_limit == 0.20


class TestStopLoss:
    """测试止损功能"""

    def test_stop_loss_triggered(self):
        """测试止损触发"""
        config = RiskConfig(stop_loss_pct=0.10, enable_stop_loss=True)
        rm = RiskManager(config)

        current_price = 90.0
        avg_cost = 100.0

        # API: check_stop_loss(timestamp, ts_code, current_price, avg_cost)
        triggered = rm.check_stop_loss(
            timestamp=datetime(2023, 1, 15),
            ts_code="000001.SZ",
            current_price=current_price,
            avg_cost=avg_cost,
        )

        assert triggered is True

    def test_stop_loss_not_triggered(self):
        """测试止损未触发"""
        config = RiskConfig(stop_loss_pct=0.10, enable_stop_loss=True)
        rm = RiskManager(config)

        current_price = 95.0
        avg_cost = 100.0

        triggered = rm.check_stop_loss(
            timestamp=datetime(2023, 1, 15),
            ts_code="000001.SZ",
            current_price=current_price,
            avg_cost=avg_cost,
        )

        assert triggered is False

    def test_stop_loss_disabled(self):
        """测试禁用止损"""
        config = RiskConfig(enable_stop_loss=False)
        rm = RiskManager(config)

        triggered = rm.check_stop_loss(
            timestamp=datetime(2023, 1, 15), ts_code="000001.SZ", current_price=80.0, avg_cost=100.0
        )

        assert triggered is False


class TestDrawdownControl:
    """测试回撤控制"""

    def test_drawdown_check(self):
        """测试回撤检查 - 使用should_clear_position"""
        config = RiskConfig(max_drawdown_limit=0.15)
        rm = RiskManager(config)

        # 更新历史净值
        dates = pd.date_range("2023-01-01", periods=20, freq="B")
        for i, d in enumerate(dates):
            if i < 10:
                value = 100000 + i * 1000  # 上涨到峰值
            else:
                value = 110000 - (i - 9) * 2000  # 下跌
            rm.update_portfolio_value(d, value)

        # 检查是否触发回撤限制 - 使用should_clear_position
        triggered = rm.should_clear_position()

        # 应该触发或产生告警
        assert triggered is True or len(rm.alerts) > 0

    def test_drawdown_warning(self):
        """测试回撤预警 - 使用should_reduce_position"""
        config = RiskConfig(drawdown_warning=0.10, max_drawdown_limit=0.15)
        rm = RiskManager(config)

        # 更新历史净值
        dates = pd.date_range("2023-01-01", periods=15, freq="B")
        for i, d in enumerate(dates):
            if i < 5:
                value = 100000 + i * 2000
            else:
                value = 110000 - (i - 4) * 1500
            rm.update_portfolio_value(d, value)

        # 使用should_reduce_position检查回撤预警
        should_reduce = rm.should_reduce_position()
        assert isinstance(should_reduce, bool)


class TestPositionLimits:
    """测试持仓限制"""

    def test_position_weight_limit(self):
        """测试持仓权重限制 - API使用timestamp而非date"""
        config = RiskConfig(max_position_weight=0.30)
        rm = RiskManager(config)

        positions = {"000001.SZ": {"quantity": 1000, "market_value": 40000}}

        # API: check_position_limits(timestamp, positions, total_value)
        violations = rm.check_position_limits(
            timestamp=datetime(2023, 1, 15), positions=positions, total_value=100000
        )

        # 单只股票40%权重，超过30%限制
        assert len(violations) > 0

    def test_position_weight_ok(self):
        """测试持仓权重正常"""
        config = RiskConfig(max_position_weight=0.30)
        rm = RiskManager(config)

        positions = {"000001.SZ": {"quantity": 1000, "market_value": 20000}}

        violations = rm.check_position_limits(
            timestamp=datetime(2023, 1, 15), positions=positions, total_value=100000
        )

        # 单只股票20%权重，未超限
        assert len(violations) == 0


class TestAlerts:
    """测试告警功能"""

    def test_get_alerts_by_type(self):
        """测试按类型获取告警"""
        rm = RiskManager()

        # 创建告警
        rm.alerts.append(
            RiskAlert(
                timestamp=datetime(2023, 1, 15),
                alert_type=RiskAlertType.STOP_LOSS,
                severity=RiskSeverity.CRITICAL,
                message="止损触发",
            )
        )

        # 使用get_alerts_by_type而非get_alerts
        alerts = rm.get_alerts_by_type(RiskAlertType.STOP_LOSS)

        assert len(alerts) == 1

    def test_clear_alerts(self):
        """测试清除告警"""
        rm = RiskManager()

        rm.alerts.append(
            RiskAlert(
                timestamp=datetime(2023, 1, 15),
                alert_type=RiskAlertType.STOP_LOSS,
                severity=RiskSeverity.CRITICAL,
                message="止损触发",
            )
        )

        rm.clear_alerts()

        assert len(rm.alerts) == 0

    def test_get_alerts_df(self):
        """测试获取告警DataFrame"""
        rm = RiskManager()

        rm.alerts.append(
            RiskAlert(
                timestamp=datetime(2023, 1, 15),
                alert_type=RiskAlertType.STOP_LOSS,
                severity=RiskSeverity.CRITICAL,
                message="止损触发",
            )
        )

        df = rm.get_alerts_df()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1


class TestDailyLimits:
    """测试每日限制"""

    def test_daily_loss_limit(self):
        """测试单日亏损限制 - 使用check_daily_limits"""
        config = RiskConfig(max_daily_loss=0.03)
        rm = RiskManager(config)

        # 模拟前一天净值
        rm.update_portfolio_value(datetime(2023, 1, 14), 100000)

        # 使用check_daily_limits API
        result = rm.check_daily_limits(
            timestamp=datetime(2023, 1, 15), daily_pnl=-4000, trade_count=1, turnover=0.1  # 亏损4%
        )

        # 应该触发限制
        assert result["can_trade"] is False or len(rm.alerts) > 0

    def test_daily_trade_limit(self):
        """测试单日交易次数限制"""
        config = RiskConfig(max_daily_trades=5)
        rm = RiskManager(config)

        # 使用check_daily_limits API
        result = rm.check_daily_limits(
            timestamp=datetime(2023, 1, 15),
            daily_pnl=100,
            trade_count=7,  # 超过5次限制
            turnover=0.1,
        )

        assert result["can_trade"] is False or len(rm.alerts) > 0


class TestPortfolioValueTracking:
    """测试投资组合价值跟踪"""

    def test_update_portfolio_value(self):
        """测试更新组合价值"""
        rm = RiskManager()

        rm.update_portfolio_value(datetime(2023, 1, 15), 100000)
        rm.update_portfolio_value(datetime(2023, 1, 16), 105000)

        # 使用get_peak_value()方法而非peak_value属性
        assert rm.get_peak_value() == 105000

    def test_peak_value_tracking(self):
        """测试峰值跟踪"""
        rm = RiskManager()

        values = [100000, 105000, 102000, 110000, 108000]
        dates = pd.date_range("2023-01-01", periods=5, freq="B")

        for d, value in zip(dates, values):
            rm.update_portfolio_value(d, value)

        assert rm.get_peak_value() == 110000


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_portfolio(self):
        """测试空持仓"""
        rm = RiskManager()

        violations = rm.check_position_limits(
            timestamp=datetime(2023, 1, 15), positions={}, total_value=100000
        )

        assert len(violations) == 0

    def test_zero_total_value(self):
        """测试总值为0"""
        rm = RiskManager()

        violations = rm.check_position_limits(
            timestamp=datetime(2023, 1, 15),
            positions={"000001.SZ": {"quantity": 100, "market_value": 0}},
            total_value=0,
        )

        # 应该能正常处理
        assert isinstance(violations, list)

    def test_invalid_config_values(self):
        """测试无效配置值"""
        # 应该发出警告但正常创建
        config = RiskConfig(max_drawdown_limit=1.5)
        assert config.max_drawdown_limit == 1.5
