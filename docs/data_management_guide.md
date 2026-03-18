# 数据管理指南

本文档涵盖 MySQL 数据库中 Tushare 数据的同步、检查和修复完整流程。

## 目录

1. [环境配置](#环境配置)
2. [数据同步](#数据同步)
3. [数据检查](#数据检查)
4. [数据修复](#数据修复)
5. [定时任务配置](#定时任务配置)
6. [常见问题](#常见问题)

---

## 环境配置

### 1. 环境变量

在 `.env` 文件中配置以下环境变量：

```env
# MySQL 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME_TUSHARE=tushare_biz
DB_NAME_INTERFACE=interface

# Tushare API 配置
TUSHARE_TOKEN=your_tushare_token_here

# 同步配置
SYNC_BATCH_SIZE=1000
SYNC_MAX_RETRIES=3
SYNC_RETRY_DELAY=5
TUSHARE_RATE_LIMIT=500
LOG_LEVEL=INFO
```

### 2. 安装依赖

```bash
poetry install
```

### 3. 数据库初始化

```bash
# 初始化数据库结构
poetry run python main.py init-db
```

---

## 数据同步

### 单表同步

```bash
# 同步股票基础信息（全量）
poetry run python main.py sync --task stock_basic

# 同步日线行情（增量）
poetry run python main.py sync --task dailymarketdata

# 同步所有数据
poetry run python main.py sync --all
```

### 可用同步任务

| 任务名 | 表名 | 模式 | 说明 |
|--------|------|------|------|
| stock_basic | t_stock_basic | full | 股票基础信息 |
| tradedate | t_stock_tradedate | full | 交易日历 |
| dailymarketdata | t_stock_dailymarketdata | incremental | 日线行情 |
| dailybasic | t_stock_daily_basic | incremental | 每日指标 |
| adjfactor | t_stock_adjfactor | incremental | 复权因子 |
| moneyflow | t_stock_moneyflow | incremental | 资金流向 |
| fina_indicator | t_stock_fina_indicator | incremental | 财务指标 |

---

## 数据检查

### 快速检查（CLI）

```bash
# 检查数据质量
poetry run python main.py check --table t_stock_basic

# 运行数据完整性检查
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025
```

### 检查数据新鲜度

```python
from core.storage.relational.connection import DatabaseManager
from datetime import datetime

tables = [
    ('tushare_biz', 't_stock_dailymarketdata', 'trade_date', '日线行情'),
    ('tushare_biz', 't_stock_daily_basic', 'trade_date', '估值指标'),
    ('tushare_biz', 't_stock_moneyflow', 'trade_date', '资金流向'),
    ('interface', 't_precomputed_factors', 'trade_date', '预计算因子'),
]

for db, table, col, name in tables:
    result = DatabaseManager.fetchone(db, f'SELECT MAX({col}) as latest FROM {table}')
    latest = result['latest']
    if latest:
        days = (datetime.now() - datetime.strptime(latest, '%Y%m%d')).days
        status = '✓' if days <= 3 else '⚠️' if days <= 7 else '❌'
        print(f'{name}: {latest} ({days}天前) {status}')
```

### 核心检查项

| 数据类型 | 预期覆盖 | 新鲜度标准 | 检查命令 |
|----------|----------|------------|----------|
| 日线行情 | 2010-至今 | 滞后≤3天 | `SELECT MAX(trade_date) FROM t_stock_dailymarketdata` |
| 估值指标 | 2010-至今 | 滞后≤3天 | `SELECT MAX(trade_date) FROM t_stock_daily_basic` |
| 资金流向 | 2010-至今 | 滞后≤3天 | `SELECT MAX(trade_date) FROM t_stock_moneyflow` |
| 预计算因子 | 2010-至今 | 滞后≤3天 | `SELECT MAX(trade_date) FROM t_precomputed_factors` |

---

## 数据修复

### 修复流程

```bash
# 1. 检查当前状态
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025

# 2. 同步最新数据
poetry run python main.py sync --all

# 3. 补齐预计算因子（从2010年开始）
python scripts/populate_factors.py --start 2010-01-01 --end 2025-12-31

# 4. 验证修复结果
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025
```

### 仅补齐最近数据（增量）

```bash
# 补齐最近252个交易日的因子
python scripts/populate_factors.py --recent 252
```

### 强制重新计算

```bash
# 强制重新计算（即使数据已存在）
python scripts/populate_factors.py --years 2010-2025 --force
```

---

## 定时任务配置

### Crontab 配置

```bash
# 编辑 crontab
crontab -e
```

```cron
# 每日 18:00 同步行情数据
0 18 * * * cd /path/to/project && poetry run python main.py sync --all >> logs/cron_daily.log 2>&1

# 每周日 02:00 同步财务数据
0 2 * * 0 cd /path/to/project && poetry run python main.py sync --task fina_indicator >> logs/cron_fina.log 2>&1

# 每周一 03:00 数据完整性检查
0 3 * * 1 cd /path/to/project && python scripts/check_data_integrity.py --start-year 2010 >> logs/cron_check.log 2>&1
```

---

## 常见问题

### Q1: 同步过程中出现连接超时

```bash
# 增加重试次数和延迟
export SYNC_MAX_RETRIES=5
export SYNC_RETRY_DELAY=10
poetry run python main.py sync --task dailymarketdata
```

### Q2: 数据滞后超过3天

```bash
# 1. 检查交易日历是否最新
poetry run python main.py sync --task tradedate

# 2. 重新同步日频数据
poetry run python main.py sync --task dailymarketdata

# 3. 更新预计算因子
python scripts/populate_factors.py --recent 30
```

### Q3: 如何处理重复数据

同步脚本使用 MySQL 的 `ON DUPLICATE KEY UPDATE` 实现 UPSERT 功能：
- 新数据：直接插入
- 重复数据：根据唯一键自动更新

### Q4: 查看同步日志

```bash
# 实时查看日志
tail -f logs/*.log

# 查找错误
grep "ERROR" logs/*.log
```

---

## 数据验证 SQL

```sql
-- 检查股票数量
SELECT list_status, COUNT(*) FROM t_stock_basic GROUP BY list_status;

-- 检查最新交易日
SELECT MAX(trade_date) FROM t_stock_dailymarketdata;

-- 检查预计算因子覆盖
SELECT SUBSTRING(trade_date, 1, 4) as year,
       COUNT(DISTINCT trade_date) as days,
       COUNT(*) as total_rows
FROM t_precomputed_factors
GROUP BY SUBSTRING(trade_date, 1, 4)
ORDER BY year;
```

---

*最后更新: 2026-03-18*
