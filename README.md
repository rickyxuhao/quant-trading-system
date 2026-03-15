# 量化交易系统

基于 Python 的股票量化交易系统，提供数据同步、质量检查、复权计算等基础设施能力。

## 快速开始

```bash
# 安装依赖
poetry install

# 查看 CLI 帮助
poetry run python main.py --help

# 执行数据同步
poetry run python main.py sync --all

# 数据质量检查
poetry run python main.py check --table t_stock_basic
```

## 项目结构

- `core/` - 核心基础设施
  - `data_access/` - 数据访问层（Tushare 等）
  - `data_processing/` - 数据处理（复权计算等）
  - `data_quality/` - 数据质量检查
  - `data_sync/` - 数据同步引擎
  - `storage/` - 存储层
- `projects/` - 各项目策略
- `scripts/` - 工具脚本

## 配置

复制 `.env.example` 为 `.env`，填写以下配置：

```bash
TUSHARE_TOKEN=your_token
DB_PASSWORD=your_password
```
