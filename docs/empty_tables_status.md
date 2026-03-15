# 空表状态说明

## 保留的空表 (按需同步)

### 股票相关
| 表名 | 用途 | 状态 | 备注 |
|------|------|------|------|
| t_stock_top10_holders | 前十大股东 | 空表 | 历史数据使用频率低，按需同步 |
| t_stock_top10_float_holders | 前十大流通股东 | 空表 | 历史数据使用频率低，按需同步 |

### 基金相关 (API限制/数据量大)
| 表名 | 用途 | 状态 | 备注 |
|------|------|------|------|
| t_fund_nav | 基金净值 | 空表 | 需逐个基金查询，按需同步 |
| t_fund_share | 基金份额 | 空表 | 需逐个基金查询，按需同步 |
| t_fund_portfolio | 基金持仓 | 空表 | 可按基金代码同步，按需获取 |
| t_fund_rating | 基金评级 | 空表 | API需特定权限 |

### 指数相关 (正在同步中)
| 表名 | 用途 | 状态 | 备注 |
|------|------|------|------|
| t_index_daily | 指数日线行情 | 同步中 | 20个核心指数，2005-2026 |
| t_index_weight | 指数成分权重 | 同步中 | 9个核心指数，2005-2026 |

---

## 按需同步命令

### 基金数据
```bash
cd "/Users/xuhaoricky/ClawProject/trading project"

# 同步指定基金的净值 (替换 FUND_CODE)
python3 scripts/sync/sync_t_fund_nav.py \
  --mode full --start-date 20240101 --end-date 20260306 \
  --log-file logs/fund_nav_custom.log

# 同步指定基金的持仓
python3 scripts/sync/sync_t_fund_portfolio.py \
  --mode full \
  --log-file logs/fund_portfolio_custom.log
```

### 指数日线行情
```bash
# 同步20个核心指数日线数据
python3 scripts/sync/sync_t_index_daily.py \
  --mode full --start-date 20050101 --end-date 20260306 \
  --log-file logs/index_daily_full.log
```

### 指数成分权重
```bash
# 同步9个核心指数成分权重
python3 scripts/sync/sync_t_index_weight.py \
  --mode full --start-date 20050101 --end-date 20260306 \
  --log-file logs/index_weight_full.log
```

### 股东数据
```bash
# 前十大股东
python3 scripts/sync/sync_t_stock_top10_holders.py \
  --mode full --start-date 20240101 --end-date 20260306 \
  --log-file logs/top10_holders_recent.log

# 前十大流通股东
python3 scripts/sync/sync_t_stock_top10_float_holders.py \
  --mode full --start-date 20240101 --end-date 20260306 \
  --log-file logs/top10_float_holders_recent.log
```

---

## 已删除的表 (13张)

### 1. 无数据源的银行/保险/证券细分表 (9张)
- t_stock_balancesheet_bank / insurance / securities
- t_stock_cashflow_bank / insurance / securities
- t_stock_income_bank / insurance / securities

### 2. API 不可用或需求低频表 (4张)
- t_stock_cgq - 股权质押 (API 需高级权限)
- t_stock_gdfx - 股权质押明细 (API 需高级权限)
- t_stock_jgcc - 机构持股汇总 (API 需高级权限)
- t_stock_jgdy - 机构调研 (API 需高级权限)

---
*最后更新: 2026-03-08*
