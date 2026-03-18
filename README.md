# 量化交易系统

基于 Python 的沪深股市量化交易系统，涵盖数据基础设施、机器学习预测模型（XGBoost/LSTM）、回测引擎和 Streamlit 可视化界面。

## 快速开始

```bash
# 安装依赖
poetry install

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写 TUSHARE_TOKEN 和数据库密码

# 初始化数据库
poetry run python main.py init-db

# 同步基础数据
poetry run python main.py sync --task stock_basic
poetry run python main.py sync --task tradedate

# 同步日线行情（首次全量）
poetry run python main.py sync --task dailymarketdata --full

# 启动可视化面板
streamlit run projects/quant_trading/visualization/app.py
```

## 系统架构

### 五层架构设计

| 层级 | 核心模块 | 职责 |
|------|----------|------|
| **数据层** | `core/data_sync/`, `core/data_access/tushare/`, `core/storage/` | Tushare API → MySQL（双库：tushare_biz + interface） |
| **策略层** | `projects/quant_trading/strategies/` | 信号生成、机器学习模型（XGBoost/LSTM）、配对交易 |
| **回测层** | `projects/quant_trading/backtest/` | 事件驱动引擎、26项绩效指标、交易成本模拟 |
| **风控层** | `projects/quant_trading/backtest/risk_manager.py` | 止损止盈、回撤控制、持仓限制 |
| **可视化层** | `projects/quant_trading/visualization/` | Streamlit 面板（4页面：绩效、交易、模型诊断、参数优化） |

### 核心功能

- **数据基础设施**：支持股票、ETF、公募基金、指数数据，自动复权处理
- **机器学习预测**：XGBoost 和 LSTM 模型，40+ 预计算因子，滚动窗口训练
- **回测引擎**：事件驱动架构，真实交易成本模拟（A股费率），多策略并行
- **绩效评估**：26项完整指标（夏普比率、最大回撤、Calmar比率等）
- **可视化分析**：交互式 Dashboard，支持参数调优、策略对比、模型诊断
- **监控告警**：8条默认告警规则（数据延迟、模型失效、性能监控）

## 项目结构

```
├── core/                          # 核心基础设施
│   ├── data_access/               # 数据访问层（Tushare）
│   ├── data_processing/           # 数据处理（复权、清洗）
│   ├── data_quality/              # 数据质量检查
│   ├── data_sync/                 # 数据同步引擎
│   └── storage/                   # 存储层（MySQL）
├── projects/                      # 各项目策略
│   ├── quant_trading/             # 主量化交易项目
│   │   ├── backtest/              # 回测引擎
│   │   ├── strategies/            # 策略实现
│   │   ├── monitoring/            # 监控告警
│   │   └── visualization/         # 可视化面板
│   └── broker_gold_stock/         # 券商金股分析
├── scripts/                       # 工具脚本
├── tests/                         # 测试框架（130+ 测试）
├── database/                      # 数据库迁移和优化
└── docs/                          # 文档
```

## 常用命令

### 数据操作

```bash
# 查看 CLI 帮助
poetry run python main.py --help

# 同步所有数据
poetry run python main.py sync --all

# 同步特定任务
poetry run python main.py sync --task stock_basic
poetry run python main.py sync --task dailymarketdata

# 数据质量检查
poetry run python main.py check --table t_stock_basic
```

### 回测

```bash
# 运行最优策略回测
python run_optimal_backtest.py

# 运行配对交易回测
python run_pair_backtest.py

# 运行 ML 策略回测
python run_ml_backtest.py
```

### 可视化

```bash
# 启动 Streamlit 面板
streamlit run projects/quant_trading/visualization/app.py

# 指定端口
streamlit run projects/quant_trading/visualization/app.py --server.port 8502
```

### 测试

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行特定测试文件
python -m pytest tests/unit/test_metrics.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=projects --cov-report=html
```

### 代码质量

```bash
# 格式化代码
black .
isort .

# 类型检查
mypy .
```

## 配置

复制 `.env.example` 为 `.env`，填写以下配置：

```bash
# Tushare API Token
TUSHARE_TOKEN=your_token_here

# MySQL 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME_TUSHARE=tushare_biz
DB_NAME_INTERFACE=interface
```

## 文档导航

- [CLAUDE.md](CLAUDE.md) - 项目开发指南（重要约束、常用命令、架构细节）
- [docs/data_management_guide.md](docs/data_management_guide.md) - 数据管理指南（同步、检查、修复）
- [docs/data_dictionary.md](docs/data_dictionary.md) - 数据表字典
- [架构设计.md](架构设计.md) - 高层架构设计
- [第五阶段及后续.md](第五阶段及后续.md) - 系统集成与持续优化规划

## 代码统计

| 阶段 | 代码行数 | 核心成果 |
|------|----------|----------|
| Phase 1 数据基础设施 | ~8,000 | 数据同步体系、双库架构 |
| Phase 2 策略研究 | ~6,500 | PDF解析、统计套利、ML模型 |
| Phase 3 回测引擎 | ~17,000 | 完整回测框架、绩效评估、风控 |
| Phase 4 可视化 | ~3,000 | Streamlit Dashboard |
| Phase 5 监控测试 | ~6,700 | 测试框架、监控告警、性能优化 |
| **总计** | **~34,500** | - |

## 项目状态

- ✅ Phase 1: 数据基础设施（已完成）
- ✅ Phase 2: 策略研究（已完成）
- ✅ Phase 3: 回测引擎（已完成）
- ✅ Phase 4: 可视化（已完成）
- ✅ Phase 5: 系统集成与测试（已完成）

**注意**：本项目**不包含实盘交易**功能，专注于回测与研究。
