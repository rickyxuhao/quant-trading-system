# Tushare 数据同步配置指南

本文档介绍如何使用 `scripts/sync/` 目录下的同步脚本进行 Tushare 数据同步。

## 目录

1. [环境配置](#环境配置)
2. [数据库初始化](#数据库初始化)
3. [同步脚本使用](#同步脚本使用)
4. [单表脚本说明](#单表脚本说明)
5. [批量同步示例](#批量同步示例)
6. [开发新同步脚本](#开发新同步脚本)
7. [表配置说明](#表配置说明)
8. [同步策略](#同步策略)
9. [常见问题](#常见问题)
10. [定时任务配置](#定时任务配置)
11. [迁移说明](#迁移说明)

---

## 环境配置

### 1. 环境变量

在 `.env` 文件中配置以下环境变量：

```env
# PostgreSQL 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME_TUSHARE=tushare_biz
DB_USER=postgres
DB_PASSWORD=your_password

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
pip install pandas psycopg2-binary tushare python-dotenv
```

---

## 数据库初始化

### 1. 创建数据库

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE tushare_biz WITH ENCODING 'UTF8';
```

### 2. 执行建表脚本

```bash
# 方式1: 使用 psql
psql -U postgres -d tushare_biz -f database/schema.sql

# 方式2: 在 psql 中执行
\c tushare_biz
\i database/schema.sql
```

### 3. 验证表创建

```sql
-- 查看所有表
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 't_%'
ORDER BY table_name;

-- 查看表结构
\d t_stock_basic
```

---

## 同步脚本使用

### 脚本结构

```
scripts/sync/
├── base_sync.py                    # 公共基础模块
├── sync_t_stock_basic.py           # 股票基础信息
├── sync_t_stock_tradedate.py       # 交易日历
├── sync_t_stock_dailymarketdata.py # 日线行情
├── sync_t_stock_fina_indicator.py  # 财务指标
├── ... (共29个单表同步脚本)
└── tushare_sync.py                 # 原聚合脚本（保留兼容）
```

### 单表脚本基本用法

每个单表脚本都支持相同的命令行参数：

```bash
# 查看帮助
python scripts/sync/sync_t_stock_basic.py --help

# 同步股票基础信息（自动模式）
python scripts/sync/sync_t_stock_basic.py

# 同步股票基础信息（全量模式）
python scripts/sync/sync_t_stock_basic.py --mode full

# 同步日线行情（增量）
python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental

# 同步指定日期范围
python scripts/sync/sync_t_stock_dailymarketdata.py --start-date 20240101 --end-date 20240131

# 指定日志文件
python scripts/sync/sync_t_stock_dailymarketdata.py --log-file logs/daily_$(date +%Y%m%d).log
```

### 通用参数说明

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `--mode` | 同步模式 | full/incremental/auto | auto |
| `--start-date` | 开始日期 (YYYYMMDD) | - | - |
| `--end-date` | 结束日期 (YYYYMMDD) | - | - |
| `--log-file` | 日志文件路径 | - | - |

---

## 单表脚本说明

### 单表脚本列表（29个）

| 脚本名 | 表名 | 同步模式 | 说明 |
|--------|------|----------|------|
| `sync_t_stock_basic.py` | t_stock_basic | full | 股票基础信息 |
| `sync_t_stock_tradedate.py` | t_stock_tradedate | full | 交易日历 |
| `sync_t_stock_name_history.py` | t_stock_name_history | incremental | 股票曾用名 |
| `sync_t_stock_hs_const.py` | t_stock_hs_const | full | 沪深股通成分股 |
| `sync_t_stock_ipo.py` | t_stock_ipo | incremental | IPO新股列表 |
| `sync_t_stock_company.py` | t_stock_company | full | 上市公司基本信息 |
| `sync_t_stock_dailymarketdata.py` | t_stock_dailymarketdata | incremental | 日线行情 |
| `sync_t_stock_adjfactor.py` | t_stock_adjfactor | incremental | 复权因子 |
| `sync_t_stock_daily_basic.py` | t_stock_daily_basic | incremental | 每日指标 |
| `sync_t_stock_st_list.py` | t_stock_st_list | incremental | ST股票列表 |
| `sync_t_stock_dailylimitprice.py` | t_stock_dailylimitprice | incremental | 涨跌停价格 |
| `sync_t_stock_moneyflow.py` | t_stock_moneyflow | incremental | 个股资金流向 |
| `sync_t_stock_moneyflow_market.py` | t_stock_moneyflow_market | incremental | 沪深港通资金流向 |
| `sync_t_stock_income.py` | t_stock_income | incremental | 利润表 |
| `sync_t_stock_balancesheet.py` | t_stock_balancesheet | incremental | 资产负债表 |
| `sync_t_stock_cashflow.py` | t_stock_cashflow | incremental | 现金流量表 |
| `sync_t_stock_fina_indicator.py` | t_stock_fina_indicator | incremental | 财务指标数据 |
| `sync_t_stock_fina_audit.py` | t_stock_fina_audit | incremental | 财务审计意见 |
| `sync_t_stock_fina_mainbz.py` | t_stock_fina_mainbz | incremental | 主营业务构成 |
| `sync_t_stock_forecast.py` | t_stock_forecast | incremental | 业绩预告 |
| `sync_t_stock_express.py` | t_stock_express | incremental | 业绩快报 |
| `sync_t_stock_dividend.py` | t_stock_dividend | incremental | 分红送股 |
| `sync_t_stock_top10_holders.py` | t_stock_top10_holders | incremental | 前十大股东 |
| `sync_t_stock_top10_float_holders.py` | t_stock_top10_float_holders | incremental | 前十大流通股东 |
| `sync_t_stock_holder_number.py` | t_stock_holder_number | incremental | 股东人数 |
| `sync_t_stock_holder_trade.py` | t_stock_holder_trade | incremental | 股东增减持 |
| `sync_t_stock_cgq.py` | t_stock_cgq | incremental | 股权质押 |
| `sync_t_stock_jgcc.py` | t_stock_jgcc | incremental | 机构持股汇总 |
| `sync_t_stock_jgdy.py` | t_stock_jgdy | incremental | 机构调研 |
| `sync_t_stock_gdfx.py` | t_stock_gdfx | incremental | 股权质押明细 |

---

## 批量同步示例

### 使用 Shell 循环批量执行

```bash
#!/bin/bash

# 基础数据表
BASIC_TABLES=(
    "sync_t_stock_basic.py"
    "sync_t_stock_tradedate.py"
    "sync_t_stock_hs_const.py"
    "sync_t_stock_company.py"
)

# 行情数据表
MARKET_TABLES=(
    "sync_t_stock_dailymarketdata.py"
    "sync_t_stock_adjfactor.py"
    "sync_t_stock_daily_basic.py"
    "sync_t_stock_moneyflow.py"
)

# 财务数据表
FINA_TABLES=(
    "sync_t_stock_fina_indicator.py"
    "sync_t_stock_income.py"
    "sync_t_stock_balancesheet.py"
    "sync_t_stock_cashflow.py"
)

# 同步所有基础数据
echo "===== 同步基础数据 ====="
for script in "${BASIC_TABLES[@]}"; do
    echo "执行: $script"
    python "scripts/sync/$script" --mode full
done

# 同步所有行情数据（增量）
echo "===== 同步行情数据 ====="
for script in "${MARKET_TABLES[@]}"; do
    echo "执行: $script"
    python "scripts/sync/$script" --mode incremental
done

# 同步所有财务数据（增量）
echo "===== 同步财务数据 ====="
for script in "${FINA_TABLES[@]}"; do
    echo "执行: $script"
    python "scripts/sync/$script" --mode incremental
done
```

### 并行同步（后台执行）

```bash
# 在后台并行执行多个不相关的同步任务
python scripts/sync/sync_t_stock_basic.py --mode full &
python scripts/sync/sync_t_stock_tradedate.py --mode full &
python scripts/sync/sync_t_stock_hs_const.py --mode full &

# 等待所有后台任务完成
wait
echo "所有同步任务完成"
```

### Python 批量同步脚本示例

```python
#!/usr/bin/env python3
"""批量同步示例"""

import subprocess
import sys
from datetime import datetime

# 定义同步任务
SYNC_TASKS = {
    'basic': [
        'sync_t_stock_basic.py',
        'sync_t_stock_tradedate.py',
        'sync_t_stock_company.py',
    ],
    'market': [
        'sync_t_stock_dailymarketdata.py',
        'sync_t_stock_adjfactor.py',
        'sync_t_stock_daily_basic.py',
    ],
    'fina': [
        'sync_t_stock_fina_indicator.py',
        'sync_t_stock_income.py',
    ]
}

def run_sync(script_name, mode='auto'):
    """执行单个同步脚本"""
    cmd = ['python', f'scripts/sync/{script_name}', '--mode', mode]
    print(f"[INFO] 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] {script_name} 失败:\n{result.stderr}")
        return False
    print(f"[OK] {script_name} 完成")
    return True

def sync_all(category=None, mode='auto'):
    """批量同步"""
    if category and category in SYNC_TASKS:
        tasks = SYNC_TASKS[category]
    else:
        tasks = [s for sublist in SYNC_TASKS.values() for s in sublist]

    failed = []
    for script in tasks:
        if not run_sync(script, mode):
            failed.append(script)

    print(f"\n{'='*60}")
    print(f"同步完成: 成功 {len(tasks)-len(failed)}/{len(tasks)}")
    if failed:
        print(f"失败任务: {failed}")
    return len(failed) == 0

if __name__ == '__main__':
    # 示例: 同步所有基础数据
    sync_all('basic', 'full')
```

---

## 开发新同步脚本

### base_sync.py 模块说明

`base_sync.py` 提供同步任务的基础功能，包含以下主要组件：

| 组件 | 说明 |
|------|------|
| `SyncConfig` | 配置类，从环境变量加载数据库和 API 配置 |
| `DatabaseManager` | 数据库管理器，提供连接池、UPSERT 等操作 |
| `TushareSyncClient` | Tushare 客户端包装，带重试和速率限制 |
| `BaseSyncTask` | 基础同步任务类，子类继承此类实现具体同步逻辑 |
| `create_base_parser()` | 创建标准命令行参数解析器 |
| `init_sync_env()` | 初始化同步环境（配置、数据库、客户端、日志） |

### 继承 BaseSyncTask 创建新脚本

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新表同步脚本模板
表名: t_your_table_name
数据来源: Tushare xxx API
"""

import sys
import os

# 添加当前目录到路径以导入 base_sync
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import BaseSyncTask, create_base_parser, init_sync_env


class YourTableSync(BaseSyncTask):
    """新表同步任务"""

    # 必填配置
    TABLE_NAME = "t_your_table_name"      # 数据库表名
    API_NAME = "tushare_api_name"         # Tushare API 名称
    COLUMNS = [                           # 表列名列表
        'ts_code', 'column1', 'column2', 'column3'
    ]
    UNIQUE_COLUMNS = ['ts_code', 'date']  # 唯一键列名（用于 UPSERT）

    # 可选配置
    UPDATE_COLUMNS = None                 # 冲突时更新的列，None表示更新所有非唯一列
    SYNC_TYPE = "incremental"             # 默认同步类型: full/incremental
    DATE_COLUMN = "trade_date"            # 日期列名（用于增量同步）
    TS_CODE_REQUIRED = False              # 是否需要按股票代码循环获取
    FETCH_PARAMS = {}                     # 额外的 API 查询参数


def main():
    parser = create_base_parser("新表同步 - t_your_table_name")
    args = parser.parse_args()

    # 初始化环境
    config, db, client, logger = init_sync_env(args.log_file)

    # 执行同步
    sync_task = YourTableSync(config, db, client)
    result = sync_task.execute(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # 输出结果
    logger.info("-" * 60)
    if result['status'] == 'success':
        logger.info(f"✅ 同步成功: 获取 {result['rows_fetched']} 条, "
                   f"插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
    else:
        logger.info(f"⚠️ {result.get('reason', '未知状态')}")


if __name__ == "__main__":
    main()
```

### BaseSyncTask 属性说明

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `TABLE_NAME` | str | 是 | 数据库表名 |
| `API_NAME` | str | 是 | Tushare API 名称 |
| `COLUMNS` | List[str] | 是 | 表的所有列名 |
| `UNIQUE_COLUMNS` | List[str] | 是 | 唯一键列名，用于 UPSERT |
| `UPDATE_COLUMNS` | List[str] | 否 | 冲突时更新的列，None表示更新所有非唯一列 |
| `SYNC_TYPE` | str | 否 | 默认同步类型: `full` 或 `incremental` |
| `DATE_COLUMN` | str | 否 | 日期列名，用于增量同步判断 |
| `TS_CODE_REQUIRED` | bool | 否 | 是否按股票代码循环获取（财务数据用） |
| `FETCH_PARAMS` | dict | 否 | 额外的 API 查询参数 |

### 同步类型选择

| 同步类型 | 适用场景 | 示例 |
|----------|----------|------|
| `sync_full` | 一次性获取所有数据 | stock_basic, trade_cal |
| `sync_by_date` | 按交易日逐日获取 | daily, moneyflow |
| `sync_by_stock_code` | 按股票代码逐个获取 | fina_indicator, income |

---

## 表配置说明

### 基础数据表 (6张)

| 配置名 | 表名 | 同步模式 | 说明 |
|--------|------|----------|------|
| `stock_basic` | t_stock_basic | full | 股票基础信息，每日全量 |
| `trade_cal` | t_stock_tradedate | full | 交易日历，每年更新一次 |
| `namechange` | t_stock_name_history | incremental | 股票曾用名 |
| `hs_const` | t_stock_hs_const | full | 沪深股通成分股 |
| `new_share` | t_stock_ipo | incremental | IPO新股列表 |
| `stock_company` | t_stock_company | full | 上市公司基本信息 |

### 行情数据表 (7张)

| 配置名 | 表名 | 同步模式 | 说明 |
|--------|------|----------|------|
| `daily` | t_stock_dailymarketdata | incremental | 日线行情 |
| `adj_factor` | t_stock_adjfactor | incremental | 复权因子 |
| `daily_basic` | t_stock_daily_basic | incremental | 每日指标 |
| `stock_st` | t_stock_st_list | incremental | ST股票列表 |
| `limit_list` | t_stock_dailylimitprice | incremental | 涨跌停价格 |
| `moneyflow` | t_stock_moneyflow | incremental | 个股资金流向 |
| `moneyflow_hsgt` | t_stock_moneyflow_market | incremental | 沪深港通资金流向 |

### 财务数据表 (12张)

| 配置名 | 表名 | 同步模式 | 说明 |
|--------|------|----------|------|
| `income` | t_stock_income | incremental | 利润表-一般工商业 |
| `balancesheet` | t_stock_balancesheet | incremental | 资产负债表-一般工商业 |
| `cashflow` | t_stock_cashflow | incremental | 现金流量表-一般工商业 |
| `fina_indicator` | t_stock_fina_indicator | incremental | 财务指标数据 |
| `fina_audit` | t_stock_fina_audit | incremental | 财务审计意见 |
| `fina_mainbz` | t_stock_fina_mainbz | incremental | 主营业务构成 |
| `forecast` | t_stock_forecast | incremental | 业绩预告 |
| `express` | t_stock_express | incremental | 业绩快报 |
| `dividend` | t_stock_dividend | incremental | 分红送股 |

### 市场行为数据表 (8张)

| 配置名 | 表名 | 同步模式 | 说明 |
|--------|------|----------|------|
| `top10_holders` | t_stock_top10_holders | incremental | 前十大股东 |
| `top10_fh` | t_stock_top10_float_holders | incremental | 前十大流通股东 |
| `stk_holdernumber` | t_stock_holder_number | incremental | 股东人数 |
| `stk_holdertrade` | t_stock_holder_trade | incremental | 股东增减持 |
| `cgq` | t_stock_cgq | incremental | 股权质押 |
| `jgcc` | t_stock_jgcc | incremental | 机构持股汇总 |
| `jgdy` | t_stock_jgdy | incremental | 机构调研 |
| `gdfx` | t_stock_gdfx | incremental | 股权质押明细 |

---

## 同步策略

### 首次同步建议顺序

```bash
# 1. 首先同步基础数据
python scripts/sync/sync_t_stock_basic.py --mode full
python scripts/sync/sync_t_stock_tradedate.py --mode full
python scripts/sync/sync_t_stock_hs_const.py --mode full

# 2. 然后同步历史行情数据（时间较长）
python scripts/sync/sync_t_stock_dailymarketdata.py --mode full
python scripts/sync/sync_t_stock_adjfactor.py --mode full

# 3. 最后同步财务数据
python scripts/sync/sync_t_stock_fina_indicator.py --mode full
```

### 日常增量同步

```bash
# 每日收盘后执行 - 行情数据
python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental
python scripts/sync/sync_t_stock_daily_basic.py --mode incremental

# 每周/每月同步财务数据
python scripts/sync/sync_t_stock_fina_indicator.py --mode incremental
```

---

## 常见问题

### Q1: 同步过程中出现连接超时

**解决方案：**
```bash
# 增加重试次数和延迟
export SYNC_MAX_RETRIES=5
export SYNC_RETRY_DELAY=10
python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental
```

### Q2: 内存不足导致程序崩溃

**解决方案：**
- 减小批处理大小：`export SYNC_BATCH_SIZE=500`
- 对于财务数据，按股票分批同步

### Q3: API 速率限制

**解决方案：**
- 默认 500次/分钟，可通过环境变量调整
- 如需更高频率，请升级 Tushare 会员等级

### Q4: 如何处理重复数据

同步脚本使用 PostgreSQL 的 `ON CONFLICT DO UPDATE` 实现 UPSERT 功能：
- 新数据：直接插入
- 重复数据：根据唯一键自动更新

### Q5: 如何查看同步日志

```bash
# 实时查看日志
tail -f logs/sync_*.log

# 查找错误
grep "ERROR" logs/sync_*.log
```

---

## 定时任务配置

### Crontab 配置示例

```bash
# 编辑 crontab
crontab -e
```

```cron
# 每日 17:00 同步基础数据
0 17 * * * cd /path/to/project && python scripts/sync/sync_t_stock_basic.py --mode full >> logs/cron_basic.log 2>&1

# 每日 18:00 同步行情数据
0 18 * * * cd /path/to/project && python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental >> logs/cron_daily.log 2>&1
python scripts/sync/sync_t_stock_daily_basic.py --mode incremental >> logs/cron_daily_basic.log 2>&1

# 每周日 02:00 同步财务数据
0 2 * * 0 cd /path/to/project && python scripts/sync/sync_t_stock_fina_indicator.py --mode incremental >> logs/cron_fina.log 2>&1

# 每月 1 日 03:00 全量同步财务数据
0 3 1 * * cd /path/to/project && for script in scripts/sync/sync_t_stock_fina_*.py; do python "$script" --mode full; done >> logs/cron_fina_full.log 2>&1
```

### 使用批量脚本定时任务

```bash
# 创建每日同步脚本 ~/daily_sync.sh
#!/bin/bash
cd /path/to/project

# 行情数据
for script in sync_t_stock_daily*.py sync_t_stock_moneyflow*.py; do
    python "scripts/sync/$script" --mode incremental
done

# 日志记录
echo "$(date): 日常同步完成" >> logs/daily_sync.log
```

```cron
# crontab 条目
0 18 * * * /path/to/daily_sync.sh
```

### Systemd Timer (Linux)

创建服务文件 `/etc/systemd/system/tushare-sync.service`：

```ini
[Unit]
Description=Tushare Data Sync
After=network.target

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/project
Environment=PYTHONPATH=/path/to/project
EnvironmentFile=/path/to/project/.env
ExecStart=/path/to/python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental
```

创建定时器文件 `/etc/systemd/system/tushare-sync.timer`：

```ini
[Unit]
Description=Run Tushare Sync daily at 18:00

[Timer]
OnCalendar=*-*-* 18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器：

```bash
sudo systemctl daemon-reload
sudo systemctl enable tushare-sync.timer
sudo systemctl start tushare-sync.timer
```

---

## 迁移说明

### 从旧脚本迁移到新脚本

#### 变更对比

| 旧方式 (tushare_sync.py) | 新方式 (单表脚本) | 说明 |
|-------------------------|------------------|------|
| `--table stock_basic` | `sync_t_stock_basic.py` | 直接执行对应脚本 |
| `--all-basic` | Shell 循环 | 需要自行编写批量脚本 |
| `--all-market` | Shell 循环 | 需要自行编写批量脚本 |
| `--all-fina` | Shell 循环 | 需要自行编写批量脚本 |
| `--all` | Shell 循环 | 需要自行编写批量脚本 |

#### 迁移示例

**旧命令：**
```bash
python scripts/sync/tushare_sync.py --table daily --mode incremental
```

**新命令：**
```bash
python scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental
```

**旧批量命令：**
```bash
python scripts/sync/tushare_sync.py --all-market --mode incremental
```

**新批量方式：**
```bash
# 创建批量执行脚本
for script in sync_t_stock_dailymarketdata.py sync_t_stock_adjfactor.py \
              sync_t_stock_daily_basic.py sync_t_stock_moneyflow.py; do
    echo "执行: $script"
    python "scripts/sync/$script" --mode incremental
done
```

#### 保留的兼容功能

原 `tushare_sync.py` 脚本仍然保留，可以继续使用：

```bash
# 以下命令仍然有效（向后兼容）
python scripts/sync/tushare_sync.py --table stock_basic --mode full
python scripts/sync/tushare_sync.py --list
```

---

## 数据验证

### 基础数据验证

```sql
-- 检查股票数量
SELECT list_status, COUNT(*) FROM t_stock_basic GROUP BY list_status;

-- 检查最新交易日
SELECT MAX(trade_date) FROM t_stock_dailymarketdata;

-- 检查数据完整性
SELECT ts_code, COUNT(*) as days
FROM t_stock_dailymarketdata
WHERE trade_date >= '20240101'
GROUP BY ts_code
ORDER BY days DESC
LIMIT 10;
```

### 财务数据验证

```sql
-- 检查最新报告期
SELECT MAX(end_date) FROM t_stock_fina_indicator;

-- 检查 ROE 分布
SELECT
    CASE
        WHEN roe < 0 THEN '亏损'
        WHEN roe < 10 THEN '0-10%'
        WHEN roe < 20 THEN '10-20%'
        ELSE '>20%'
    END as roe_range,
    COUNT(*) as count
FROM t_stock_fina_indicator
WHERE end_date = (SELECT MAX(end_date) FROM t_stock_fina_indicator)
GROUP BY 1;
```

---

## 性能优化

### 数据库优化

```sql
-- 为常用查询创建额外索引
CREATE INDEX idx_daily_ts_code_date ON t_stock_dailymarketdata(ts_code, trade_date);
CREATE INDEX idx_fina_ts_code_date ON t_stock_fina_indicator(ts_code, end_date);

-- 分析表以优化查询计划
ANALYZE t_stock_dailymarketdata;
ANALYZE t_stock_fina_indicator;
```

### 同步优化

1. **并行同步**：对不相关的表可以并行执行（使用 `&` 和 `wait`）
2. **增量优先**：尽量使用增量同步而非全量
3. **合理批大小**：根据内存调整 `SYNC_BATCH_SIZE`

---

## 故障排查

### 检查数据库连接

```python
import sys
sys.path.insert(0, 'scripts/sync')

from base_sync import DatabaseManager, SyncConfig

config = SyncConfig.from_env()
db = DatabaseManager(config)

# 测试连接
result = db.fetchone("SELECT version()")
print(result)
```

### 检查 API 连接

```python
import sys
sys.path.insert(0, 'scripts/sync')

from base_sync import TushareSyncClient, SyncConfig

config = SyncConfig.from_env()
client = TushareSyncClient(config)

# 测试 API
df = client.query("stock_basic", list_status='L')
print(f"获取 {len(df)} 条股票数据")
```

---

## 附录

### A. 数据库 Schema 版本

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-03-07 | 初始版本，40张表 |
| 1.1.0 | 2026-03-07 | 新增单表同步脚本结构 |

### B. 支持的数据类型映射

| Tushare | PostgreSQL | 说明 |
|---------|------------|------|
| String | VARCHAR(n) | 字符串 |
| Float | DECIMAL(p,s) | 精确小数 |
| Integer | INTEGER/BIGINT | 整数 |
| Date | VARCHAR(8) | 日期 (YYYYMMDD) |

### C. 联系与支持

- Tushare 官网: https://tushare.pro
- API 文档: https://tushare.pro/document/2
