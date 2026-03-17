# Check Data - 数据完整性检查与补齐

检查 MySQL 数据库中所有表的数据日期覆盖情况，识别缺失数据，并自动补齐。

## 使用方式

```bash
# 检查所有表的数据完整性
/check-data

# 检查并自动补齐缺失数据
/check-data --fix

# 只检查特定年份范围
/check-data --start-year 2010 --end-year 2025

# 只检查特定表
/check-data --table t_precomputed_factors

# 检查数据更新及时性（是否滞后超过3天）
/check-data --check-freshness
```

## 实现步骤

### 1. 运行数据完整性检查脚本

```bash
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025
```

### 2. 检查预计算因子状态

```python
from core.storage.relational.connection import DatabaseManager

results = DatabaseManager.fetchall('interface',
    '''SELECT SUBSTRING(trade_date, 1, 4) as year,
              COUNT(DISTINCT trade_date) as days,
              COUNT(*) as total_rows
       FROM t_precomputed_factors
       GROUP BY SUBSTRING(trade_date, 1, 4)
       ORDER BY year''')

for r in results:
    print(f"Year {r['year']}: {r['days']} days, {r['total_rows']:,} rows")
```

### 3. 补齐预计算因子数据（覆盖 2010 年至今）

**要求**：预计算因子应覆盖 2010 年以来的全部历史数据，而不仅限于 2019 年后。

```bash
# 批量预计算 2010-2025 年全部历史数据
python scripts/populate_factors.py --start 2010-01-01 --end 2025-12-31

# 或使用年份参数
python scripts/populate_factors.py --years 2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025

# 仅处理最近的数据（增量更新）
python scripts/populate_factors.py --recent 252

# 强制重新计算（即使数据已存在）
python scripts/populate_factors.py --years 2010-2025 --force
```

### 4. 同步最新行情数据到最新日期

**要求**：所有日频数据应更新到最近交易日（滞后不超过 3 天）。

```bash
# 同步日线数据
poetry run python main.py sync --task dailymarketdata

# 同步估值数据
poetry run python main.py sync --task dailybasic

# 同步资金流向
poetry run python main.py sync --task moneyflow

# 同步复权因子
poetry run python main.py sync --task adjfactor

# 同步所有数据
poetry run python main.py sync --all
```

### 5. 检查数据更新及时性

```python
from core.storage.relational.connection import DatabaseManager
from datetime import datetime

# 检查各日频表的最新日期
tables = [
    ('t_stock_dailymarketdata', 'trade_date', '日线行情'),
    ('t_stock_daily_basic', 'trade_date', '估值指标'),
    ('t_stock_moneyflow', 'trade_date', '资金流向'),
    ('t_stock_adjfactor', 'trade_date', '复权因子'),
]

for table, date_col, desc in tables:
    result = DatabaseManager.fetchone('tushare_biz',
        f'SELECT MAX({date_col}) as latest FROM {table}')
    latest = result['latest']
    if latest:
        latest_date = datetime.strptime(latest, '%Y%m%d')
        today = datetime.now()
        days_diff = (today - latest_date).days
        status = '✓' if days_diff <= 3 else '⚠️' if days_diff <= 7 else '❌'
        print(f'{desc}: {latest} ({days_diff}天前) {status}')
```

## 数据检查项

### 核心数据表

| 表名 | 日期字段 | 预期覆盖 | 检查方式 |
|------|----------|----------|----------|
| t_stock_dailymarketdata | trade_date | 2010-至今 | 每年约242个交易日，滞后≤3天 |
| t_stock_daily_basic | trade_date | 2010-至今 | PE/PB覆盖>95%，滞后≤3天 |
| t_stock_moneyflow | trade_date | 2010-至今 | 股票数逐年增长，滞后≤3天 |
| t_stock_adjfactor | trade_date | 2010-至今 | 滞后≤3天 |
| t_stock_fina_indicator | end_date | 2010Q1-至今 | 每季度4000+股票 |
| t_precomputed_factors | trade_date | **2010-至今** | 与交易日历同步 |

### 关键指标

1. **日线数据**: 每年约242个交易日，覆盖所有上市股票，**滞后≤3天**
2. **估值数据**: PE/PB/MV 覆盖率 > 95%，**滞后≤3天**
3. **财务数据**: ROE 覆盖率 > 99%
4. **资金流向**: 与日线数据同步，**滞后≤3天**
5. **预计算因子**: **2010-至今**，包含40+因子

## 数据新鲜度检查

### 检查标准

| 数据类型 | 最大允许滞后 | 检查命令 |
|----------|-------------|----------|
| 日线行情 | 3天 | `SELECT MAX(trade_date) FROM t_stock_dailymarketdata` |
| 估值指标 | 3天 | `SELECT MAX(trade_date) FROM t_stock_daily_basic` |
| 资金流向 | 3天 | `SELECT MAX(trade_date) FROM t_stock_moneyflow` |
| 复权因子 | 3天 | `SELECT MAX(trade_date) FROM t_stock_adjfactor` |
| 预计算因子 | 3天 | `SELECT MAX(trade_date) FROM t_precomputed_factors` |

### 更新不及时处理

如果发现数据滞后超过3天：

```bash
# 1. 检查交易日历是否最新
python -c "from core.storage.relational.connection import DatabaseManager; print(DatabaseManager.fetchone('tushare_biz', 'SELECT MAX(cal_date) FROM t_stock_tradedate'))"

# 2. 同步交易日历
poetry run python main.py sync --task tradecal

# 3. 重新同步日频数据
poetry run python main.py sync --task dailymarketdata --start-date $(date -d '7 days ago' +%Y%m%d)

# 4. 更新预计算因子
python scripts/populate_factors.py --recent 30
```

## 常见缺失原因

1. **数据源限制**: Tushare 免费版/付费版权限
2. **同步任务失败**: 检查 sync 任务日志
3. **新上市股票**: 自然缺失历史数据
4. **停牌/退市**: 股票停牌或退市
5. **预计算因子**: 后台任务未完成或范围设置错误（应从2010开始）

## 完整修复流程

```bash
# 1. 检查当前状态（所有表）
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025

# 2. 检查数据新鲜度
python -c "
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
        print(f'{name}: {latest} ({days}天前)')
"

# 3. 同步最新数据到最近交易日
poetry run python main.py sync --all

# 4. 补齐预计算因子（从2010年开始）
python scripts/populate_factors.py --start 2010-01-01 --end 2025-12-31

# 5. 验证修复结果
python scripts/check_data_integrity.py --start-year 2010 --end-year 2025
```

## 报告输出

检查完成后生成报告 `data_integrity_report.txt`，包含：
- 日线数据覆盖情况（2010-至今）
- 估值数据完整性
- 财务数据覆盖情况
- 资金流向数据状态
- **数据更新及时性评估**
- 股票池统计信息
- ST股票记录统计

## 注意事项

1. **预计算因子时间范围**: 必须从 2010-01-01 开始计算，而不只是 2019 年
2. **数据更新频率**: 日频数据应每日同步，最长不超过 3 天滞后
3. **节假日处理**: A股市场节假日休市，数据自然缺失属于正常情况
4. **新股票处理**: 新上市股票历史数据缺失是正常的
