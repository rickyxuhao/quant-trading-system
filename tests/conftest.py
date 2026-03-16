"""
pytest配置与共享fixtures
"""
import os
import sys
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Generator
from unittest.mock import Mock, MagicMock

import pytest
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from projects.quant_trading.backtest.strategy import BaseStrategy, Signal, SignalType
from projects.quant_trading.backtest.engine import BacktestConfig, BacktestEngine
from projects.quant_trading.backtest.portfolio import Portfolio, TransactionCost, Order, OrderSide
from projects.quant_trading.backtest.metrics import MetricsCalculator, PerformanceMetrics
from projects.quant_trading.backtest.risk_manager import RiskManager, RiskConfig


# ============================================================================
# pytest配置
# ============================================================================

def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """测试数据目录"""
    return Path(__file__).parent / "fixtures"


# ============================================================================
# 日期Fixtures
# ============================================================================

@pytest.fixture
def sample_start_date() -> datetime:
    """样本开始日期"""
    return datetime(2023, 1, 1)


@pytest.fixture
def sample_end_date() -> datetime:
    """样本结束日期"""
    return datetime(2023, 12, 31)


@pytest.fixture
def sample_trade_dates() -> List[datetime]:
    """样本交易日列表（约252个交易日）"""
    start = datetime(2023, 1, 3)  # 第一个交易日
    dates = []
    current = start
    while current.year == 2023:
        # 跳过周末
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates[:252]  # 返回252个交易日


# ============================================================================
# 股票数据Fixtures
# ============================================================================

@pytest.fixture
def sample_stock_codes() -> List[str]:
    """样本股票代码列表"""
    return [
        "000001.SZ",  # 平安银行
        "000002.SZ",  # 万科A
        "600000.SH",  # 浦发银行
        "600519.SH",  # 贵州茅台
        "000858.SZ",  # 五粮液
    ]


@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """样本价格数据DataFrame"""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:252]
    np.random.seed(42)

    # 生成随机价格数据（带趋势）
    base_price = 100.0
    prices = []
    for i in range(len(dates)):
        change = np.random.normal(0.0005, 0.02)
        base_price *= (1 + change)
        prices.append({
            "trade_date": dates[i].strftime("%Y%m%d"),
            "open": base_price * (1 + np.random.normal(0, 0.005)),
            "high": base_price * (1 + abs(np.random.normal(0, 0.01))),
            "low": base_price * (1 - abs(np.random.normal(0, 0.01))),
            "close": base_price,
            "pre_close": base_price / (1 + change),
            "vol": np.random.randint(100000, 1000000),
            "amount": np.random.randint(10000000, 100000000),
            "pct_chg": change * 100,
        })

    df = pd.DataFrame(prices)
    df["ts_code"] = "000001.SZ"
    return df


@pytest.fixture
def sample_stock_data_dict(sample_stock_codes) -> Dict[str, pd.DataFrame]:
    """多只股票样本数据字典"""
    data = {}
    np.random.seed(42)

    for ts_code in sample_stock_codes:
        dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:252]
        base_price = np.random.uniform(10, 200)
        prices = []

        for i in range(len(dates)):
            change = np.random.normal(0.0003, 0.015)
            base_price *= (1 + change)
            prices.append({
                "open": base_price * (1 + np.random.normal(0, 0.005)),
                "high": base_price * (1 + abs(np.random.normal(0, 0.01))),
                "low": base_price * (1 - abs(np.random.normal(0, 0.01))),
                "close": base_price,
                "pre_close": base_price / (1 + change),
                "vol": np.random.randint(100000, 1000000),
                "amount": np.random.randint(10000000, 100000000),
            })

        df = pd.DataFrame(prices, index=dates)
        df.index.name = "trade_date"
        data[ts_code] = df

    return data


# ============================================================================
# 回测相关Fixtures
# ============================================================================

@pytest.fixture
def sample_backtest_config(sample_start_date, sample_end_date) -> BacktestConfig:
    """样本回测配置"""
    return BacktestConfig(
        start_date=sample_start_date,
        end_date=sample_end_date,
        initial_cash=100000.0,
        max_positions=10,
        min_positions=3,
        rebalance_freq="weekly",
        commission_rate=0.00015,
        slippage_rate=0.0002,
        benchmark="000300.SH",
        enable_risk_control=True,
    )


@pytest.fixture
def sample_portfolio() -> Portfolio:
    """样本投资组合"""
    return Portfolio(
        initial_cash=100000.0,
        commission_rate=0.00015,
        slip_rate=0.0002
    )


@pytest.fixture
def sample_transaction_cost() -> TransactionCost:
    """样本交易成本计算器"""
    return TransactionCost(
        commission_rate=0.00015,
        min_commission=5.0,
        slip_rate=0.0002,
        stamp_tax_rate=0.001,
        transfer_fee_rate=0.00002
    )


@pytest.fixture
def sample_risk_config() -> RiskConfig:
    """样本风控配置"""
    return RiskConfig(
        max_position_pct=0.3,
        max_drawdown_limit=0.2,
        stop_loss_pct=0.1,
        position_limit=10
    )


@pytest.fixture
def sample_risk_manager(sample_risk_config) -> RiskManager:
    """样本风控管理器"""
    return RiskManager(sample_risk_config)


# ============================================================================
# 策略Fixtures
# ============================================================================

class MockStrategy(BaseStrategy):
    """测试用模拟策略"""

    def __init__(self, name: str = "MockStrategy", signals_to_return: List[str] = None):
        super().__init__(name)
        self.signals_to_return = signals_to_return or []
        self.call_count = 0

    def generate_signals(self, data, current_date, available_stocks):
        self.call_count += 1
        signals = []
        for ts_code in self.signals_to_return[:5]:  # 最多返回5只
            if ts_code in available_stocks:
                signals.append(Signal(
                    ts_code=ts_code,
                    signal_type=SignalType.BUY,
                    weight=0.2,
                    reason="Mock strategy signal"
                ))
        return signals


@pytest.fixture
def mock_strategy() -> MockStrategy:
    """模拟策略"""
    return MockStrategy(
        name="TestMockStrategy",
        signals_to_return=["000001.SZ", "000002.SZ", "600000.SH"]
    )


# ============================================================================
# Mock DataManager Fixtures
# ============================================================================

@pytest.fixture
def mock_data_manager() -> MagicMock:
    """模拟数据管理器"""
    mock = MagicMock()

    # 配置默认返回值
    mock.get_trade_dates.return_value = [
        (datetime(2023, 1, 3) + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(0, 365, 1)
        if (datetime(2023, 1, 3) + timedelta(days=i)).weekday() < 5
    ][:252]

    mock.get_all_stocks.return_value = [
        "000001.SZ", "000002.SZ", "600000.SH", "600519.SH", "000858.SZ"
    ]

    mock.get_stock_data.return_value = pd.DataFrame({
        "open": [100.0, 101.0, 102.0],
        "high": [102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0],
        "close": [101.0, 102.0, 103.0],
        "vol": [100000, 110000, 120000],
    }, index=pd.date_range("2023-01-01", periods=3))

    return mock


# ============================================================================
# 绩效指标Fixtures
# ============================================================================

@pytest.fixture
def sample_nav_history() -> List[tuple]:
    """样本净值历史"""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:252]
    nav = 1.0
    history = []
    for date in dates:
        ret = np.random.normal(0.0005, 0.015)
        nav *= (1 + ret)
        history.append((date, nav))
    return history


@pytest.fixture
def sample_benchmark_nav() -> List[tuple]:
    """样本基准净值历史"""
    np.random.seed(43)
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")[:252]
    nav = 1.0
    history = []
    for date in dates:
        ret = np.random.normal(0.0003, 0.012)
        nav *= (1 + ret)
        history.append((date, nav))
    return history


@pytest.fixture
def sample_trades_df() -> pd.DataFrame:
    """样本交易记录DataFrame"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
        "side": ["buy", "sell", "buy", "sell"],
        "quantity": [100, 100, 200, 200],
        "price": [100.0, 105.0, 50.0, 52.0],
        "amount": [10000.0, 10500.0, 10000.0, 10400.0],
        "commission": [5.0, 5.0, 5.0, 5.0],
        "trade_date": pd.date_range("2023-01-01", periods=4),
    })


@pytest.fixture
def metrics_calculator() -> MetricsCalculator:
    """绩效指标计算器"""
    return MetricsCalculator(risk_free_rate=0.03, trading_days_per_year=252)


# ============================================================================
# 临时文件Fixtures
# ============================================================================

@pytest.fixture
def temp_output_dir(tmp_path) -> Path:
    """临时输出目录"""
    output_dir = tmp_path / "backtest_output"
    output_dir.mkdir()
    return output_dir


# ============================================================================
# 数据库Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_db_connection() -> Generator[MagicMock, None, None]:
    """模拟数据库连接"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # 模拟查询结果
    mock_cursor.fetchall.return_value = [
        {"ts_code": "000001.SZ", "name": "平安银行", "industry": "银行"},
        {"ts_code": "000002.SZ", "name": "万科A", "industry": "房地产"},
    ]
    mock_cursor.fetchone.return_value = {
        "ts_code": "000001.SZ", "name": "平安银行", "industry": "银行"
    }

    yield mock_conn


# ============================================================================
# 极端场景Fixtures
# ============================================================================

@pytest.fixture
def limit_up_scenario_data() -> pd.DataFrame:
    """连续涨停场景数据"""
    dates = pd.date_range("2023-01-01", periods=10, freq="B")
    base_price = 100.0
    data = []

    for i, date in enumerate(dates):
        # 涨停 +10%
        close = base_price * (1.10 ** (i + 1))
        data.append({
            "trade_date": date.strftime("%Y%m%d"),
            "open": close * 0.99,  # 涨停开盘
            "high": close,
            "low": close * 0.99,
            "close": close,
            "pre_close": close / 1.10,
            "pct_chg": 10.0,
            "vol": 1000,  # 成交量极低（涨停无法买入）
        })

    return pd.DataFrame(data)


@pytest.fixture
def gap_data_scenario() -> pd.DataFrame:
    """数据缺失场景"""
    dates = pd.date_range("2023-01-01", periods=20, freq="B")
    # 删除部分日期模拟数据缺失
    missing_dates = [dates[5], dates[6], dates[15]]
    valid_dates = [d for d in dates if d not in missing_dates]

    np.random.seed(42)
    data = []
    base_price = 100.0

    for date in valid_dates:
        change = np.random.normal(0, 0.02)
        base_price *= (1 + change)
        data.append({
            "trade_date": date.strftime("%Y%m%d"),
            "open": base_price * 0.99,
            "high": base_price * 1.01,
            "low": base_price * 0.98,
            "close": base_price,
            "pre_close": base_price / (1 + change),
            "vol": 100000,
        })

    return pd.DataFrame(data)


# ============================================================================
# 环境变量Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def setup_test_env():
    """自动设置测试环境"""
    # 保存原始环境变量
    original_env = dict(os.environ)

    # 设置测试环境变量
    os.environ["TEST_MODE"] = "1"
    os.environ["LOG_LEVEL"] = "DEBUG"

    yield

    # 恢复原始环境变量
    os.environ.clear()
    os.environ.update(original_env)
