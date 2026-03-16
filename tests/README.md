# Phase 5 测试框架文档

## 目录结构

```
tests/
├── conftest.py                    # pytest配置与共享fixtures
├── pytest.ini                     # pytest配置文件
├── fixtures/                      # 测试数据
├── unit/                          # 单元测试
│   ├── test_data_manager.py       # 数据管理器测试
│   ├── test_portfolio.py          # 投资组合测试
│   ├── test_metrics.py            # 绩效计算测试
│   ├── test_risk_manager.py       # 风控管理器测试
│   └── test_strategy.py           # 策略基类测试
├── integration/                   # 集成测试
│   ├── test_backtest_flow.py      # 回测流程测试
│   └── test_ml_pipeline.py        # ML流程测试
└── e2e/                          # 端到端测试
    ├── test_full_workflow.py      # 完整工作流测试
    └── test_extreme_scenarios.py  # 极端场景测试
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 运行端到端测试
pytest -m e2e

# 排除慢速测试
pytest -m "not slow"

# 生成覆盖率报告
pytest --cov=projects --cov-report=html
```

## 测试覆盖率

| 模块 | 测试文件 | 覆盖范围 |
|:---|:---|:---|
| DataManager | test_data_manager.py | 缓存、数据获取、完整性检查 |
| Portfolio | test_portfolio.py | 订单、持仓、交易成本、调仓 |
| Metrics | test_metrics.py | 收益/风险/风险调整/交易指标 |
| RiskManager | test_risk_manager.py | 止损、回撤、持仓限制 |
| Strategy | test_strategy.py | 信号生成、权重分配 |
| BacktestEngine | test_backtest_flow.py | 完整回测流程 |
| ML Pipeline | test_ml_pipeline.py | 特征工程、模型训练预测 |

## Fixtures

`conftest.py` 提供了以下共享fixtures:

- `sample_start_date/end_date` - 样本日期
- `sample_trade_dates` - 252个样本交易日
- `sample_stock_codes` - 样本股票代码列表
- `sample_price_data` - 样本价格DataFrame
- `sample_backtest_config` - 样本回测配置
- `sample_portfolio` - 样本投资组合
- `sample_nav_history` - 样本净值历史
- `mock_strategy` - 模拟策略
- `mock_data_manager` - 模拟数据管理器
