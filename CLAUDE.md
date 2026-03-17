# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供该代码库的操作指导。

## 项目概述

基于 Python 的沪深股市量化交易系统，五阶段实现（约 34,500 行代码），涵盖数据基础设施、机器学习预测模型（XGBoost/LSTM）、回测引擎和 Streamlit 可视化界面。

**重要约束**：本项目**不包含实盘交易**功能（用户明确拒绝），专注于回测与研究。

## 常用命令

### 测试
```bash
# 运行所有单元测试（130+ 测试用例）
python -m pytest tests/unit/ -v

# 运行特定测试文件
python -m pytest tests/unit/test_metrics.py -v

# 运行单个测试
python -m pytest tests/unit/test_metrics.py::TestReturnMetrics::test_total_return_calculation -v

# 按标记运行测试
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m "not slow"
```

### 数据操作（CLI）
```bash
# 从 Tushare 同步所有数据
poetry run python main.py sync --all

# 同步特定任务
poetry run python main.py sync --task stock_basic

# 数据质量检查
poetry run python main.py check --table t_stock_basic

# 初始化数据库结构
poetry run python main.py init-db
```

### 可视化
```bash
# 启动 Streamlit 面板
streamlit run projects/quant_trading/visualization/app.py
```

### 代码质量
```bash
# 格式化代码
black .
isort .

# 类型检查
mypy .
```

## 高层架构

### 五层架构设计

| 层级 | 核心模块 | 职责 |
|------|----------|------|
| **数据层** | `core/data_sync/`, `core/data_access/tushare/`, `core/storage/` | Tushare API → MySQL（双库：tushare_biz + interface） |
| **策略层** | `projects/quant_trading/strategies/`, `projects/quant_trading/backtest/strategy.py` | 信号生成、机器学习模型（XGBoost/LSTM）、配对交易 |
| **回测层** | `projects/quant_trading/backtest/engine.py`, `portfolio.py`, `metrics.py` | 事件驱动引擎、26项绩效指标、交易成本模拟 |
| **风控层** | `projects/quant_trading/backtest/risk_manager.py` | 止损止盈、回撤控制、持仓限制 |
| **可视化层** | `projects/quant_trading/visualization/` | Streamlit 面板（4页面：绩效、交易、模型诊断、参数优化） |

### 关键实现细节

**DatabaseManager** (`core/storage/relational/connection.py`):
- 单例连接池模式
- 两个数据库：`tushare_biz`（原始数据）、`interface`（加工数据）
- 始终通过 `fetchall()`, `fetchone()`, `execute()` 使用参数化查询

**DataManager** (`projects/quant_trading/backtest/data_manager.py`):
- 股票数据 LRU 缓存（默认 128 条）
- 日期处理：使用 `pd.Timestamp` 支持 normalize()，避免直接使用 datetime
- 主要方法：`get_stock_data()`, `get_batch_stock_data()`, `get_trade_dates()`

**绩效计算** (`projects/quant_trading/backtest/metrics.py`):
- 计算至少需要 2 个日收益率（建议提供 30+ 天的 NAV 历史）
- 返回包含 26 项指标的 `PerformanceMetrics` 数据类
- 关键方法：`calculate()`, `calculate_rolling_metrics()`

**交易成本** (`projects/quant_trading/backtest/transaction_cost.py`):
- 股票：印花税 0.1%（仅卖出）、佣金 0.025%（最低 5元）、过户费 0.002%
- ETF：仅佣金，无印花税
- 滑点：可配置（默认 0.02%）

### 支持的资产类别

| 资产 | 数据源 | 特殊处理 |
|------|--------|----------|
| A股股票 | Tushare | 前复权、ST标记、涨跌停 |
| ETF | Tushare | 无印花税、佣金较低 |
| 公募基金 | Tushare | 净值披露延迟 |
| 指数 | Tushare | 沪深300（000300.SH）作为基准 |

### 关键文件位置

- **入口文件**：`main.py`（数据操作 CLI）
- **回测脚本**：`run_optimal_backtest.py`, `run_pair_backtest.py`, `run_ml_backtest.py`
- **数据库 DDL**：`database/migrations/`
- **优化 SQL**：`database/optimizations/`
- **测试数据**：`tests/fixtures/`

### 环境配置

`.env` 中必需配置（从 `.env.example` 复制）：
```bash
TUSHARE_TOKEN=your_tushare_token
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME_TUSHARE=tushare_biz
DB_NAME_INTERFACE=interface
```

### 测试规范

- 浮点数比较使用 `pytest.approx()`
- 数据库调用使用 `@patch("projects.quant_trading.backtest.data_manager.DatabaseManager")` 进行模拟
- 测试中日期使用 `pd.Timestamp`（而非 `datetime`）以确保 `.normalize()` 正常工作
- 随机数据设置 `np.random.seed(42)` 以保证可重复性

### 常见陷阱

1. **日期归一化**：代码库使用 `pd.Timestamp(d).normalize()` 实现 datetime 与 pd.Timestamp 的跨类型兼容。测试中始终使用此模式。

2. **指标计算数据不足**：绩效计算器至少需要 2 个日收益率。仅提供 2 个 NAV 点的测试将返回全零结果。

3. **平仓后持仓**：平仓时实现会从 `portfolio.positions` 字典中移除持仓（而非设置 quantity=0）。测试应先检查 `if ts_code in portfolio.positions`。

4. **得分权重分配器**：使用 max_weight 上限后进行重新归一化。预期权重可能与简单得分比例不同。
