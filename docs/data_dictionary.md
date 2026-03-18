# Tushare 数据表字典

_记录 tushare_biz 数据库中所有表的用途、字段和对应的 Tushare API 接口_

---

## 股票基础数据

### t_stock_basic - 股票基础信息
| 项目 | 内容 |
|------|------|
| **用途** | A股股票基础信息，包括上市状态、行业分类等 |
| **Tushare接口** | `stock_basic` |
| **更新频率** | 每周一全量更新 |
| **主键** | `ts_code` |
| **关键字段** | ts_code, symbol, name, area, industry, market, list_date, list_status |

### t_stock_company - 上市公司基本信息
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司详细资料，包括注册地址、主营业务等 |
| **Tushare接口** | `stock_company` |
| **更新频率** | 每周更新 |
| **主键** | `ts_code` |
| **关键字段** | ts_code, exchange, chairman, manager, reg_capital, setup_date, province, city, introduction, main_business, business_scope |

### t_stock_name_history - 股票曾用名
| 项目 | 内容 |
|------|------|
| **用途** | 记录股票名称变更历史 |
| **Tushare接口** | `namechange` |
| **更新频率** | 每周更新 |
| **主键** | `ts_code, name, start_date` |
| **关键字段** | ts_code, name, start_date, end_date, ann_date, change_reason |

### t_stock_ipo - IPO新股列表
| 项目 | 内容 |
|------|------|
| **用途** | 新股IPO信息 |
| **Tushare接口** | `new_share` |
| **更新频率** | 每周更新 |
| **主键** | `ts_code` |
| **关键字段** | ts_code, sub_code, name, ipo_date, issue_date, amount, market_amount, price, pe, limit_amount, funds, ballot |

### t_stock_hs_const - 沪深股通成分股
| 项目 | 内容 |
|------|------|
| **用途** | 沪深港通标的列表 |
| **Tushare接口** | `hs_const` |
| **更新频率** | 每周更新 |
| **主键** | `ts_code` |
| **关键字段** | ts_code, hs_type, in_date, out_date, is_new |

---

## 行情数据

### t_stock_dailymarketdata - 股票日线行情
| 项目 | 内容 |
|------|------|
| **用途** | A股日线行情数据（开高低收、成交量等） |
| **Tushare接口** | `daily` |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount |
| **数据范围** | 2005年至今 |

### t_stock_daily_basic - 每日指标
| 项目 | 内容 |
|------|------|
| **用途** | 每日估值指标（PE、PB、换手率等） |
| **Tushare接口** | `daily_basic` |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, close, turnover_rate, turnover_rate_f, volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share, free_share, total_mv, circ_mv |
| **数据范围** | 2001年至今 |

### t_stock_adjfactor - 复权因子
| 项目 | 内容 |
|------|------|
| **用途** | 股票价格复权因子，用于计算复权价格 |
| **Tushare接口** | `adj_factor` |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, adj_factor |

### t_stock_dailylimitprice - 每日涨跌停价格
| 项目 | 内容 |
|------|------|
| **用途** | 每日涨跌停股票列表及价格信息 |
| **Tushare接口** | `limit_list_d` (原limit_list已停用) |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, name, close, pct_chg, amp, up_limit, down_limit |
| **特殊说明** | 2023-06-22前使用limit_list接口，之后改用limit_list_d |

### t_stock_moneyflow - 个股资金流向
| 项目 | 内容 |
|------|------|
| **用途** | 个股资金流向数据（大单、中单、小单等） |
| **Tushare接口** | `moneyflow` |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, buy_sm_vol, buy_sm_amount, sell_sm_vol, sell_sm_amount, buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount, buy_lg_vol, buy_lg_amount, sell_lg_vol, sell_lg_amount, buy_elg_vol, buy_elg_amount, sell_elg_vol, sell_elg_amount, net_mf_vol, net_mf_amount, trade_count |

### t_stock_moneyflow_market - 沪深港通资金流向
| 项目 | 内容 |
|------|------|
| **用途** | 沪深港通资金流向汇总 |
| **Tushare接口** | `moneyflow_hsgt` |
| **更新频率** | 每日盘后增量更新 |
| **主键** | `trade_date` |
| **关键字段** | trade_date, ggt_ss, ggt_sz, hgt_total, sgt_total, north_money, south_money |

### t_stock_tradedate - 交易日历
| 项目 | 内容 |
|------|------|
| **用途** | A股交易日历 |
| **Tushare接口** | `trade_cal` |
| **更新频率** | 一次性全量 |
| **主键** | `exchange, cal_date` |
| **关键字段** | exchange, cal_date, is_open, pretrade_date |

---

## 财务数据

### t_stock_balancesheet - 资产负债表
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司资产负债表数据 |
| **Tushare接口** | `balancesheet` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date, f_ann_date` |
| **关键字段** | ts_code, ann_date, f_ann_date, end_date, comp_type, total_assets, total_cur_assets, total_nca, total_liab, total_cur_liab, total_ncl, total_equity, total_hldr_eqy_exc_min_int, total_hldr_eqy_inc_min_int, total_liab_hldr_eqy |
| **数据范围** | 1990年至今 |

### t_stock_income - 利润表
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司利润表数据 |
| **Tushare接口** | `income` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date, f_ann_date` |
| **关键字段** | ts_code, ann_date, f_ann_date, end_date, comp_type, total_revenue, revenue, total_cogs, operate_exp, operate_profit, total_profit, n_income, n_income_attr_p, basic_eps, diluted_eps |
| **数据范围** | 1990年至今 |

### t_stock_cashflow - 现金流量表
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司现金流量表数据 |
| **Tushare接口** | `cashflow` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date, f_ann_date` |
| **关键字段** | ts_code, ann_date, f_ann_date, end_date, comp_type, n_cashflow_act, n_cashflow_inv_act, n_cashflow_fnc_act, free_cashflow, c_cash_equ_end_period |
| **数据范围** | 1990年至今 |

### t_stock_fina_indicator - 财务指标数据
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司财务分析指标 |
| **Tushare接口** | `fina_indicator` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, end_date, roe, roa, gross_profit_margin, net_profit_margin, debt_to_assets, current_ratio, quick_ratio, basic_eps_yoy, bps_yoy, cfps, sales_margin |

### t_stock_fina_audit - 财务审计意见
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司年度财务审计意见 |
| **Tushare接口** | `fina_audit` |
| **更新频率** | 年报发布时增量更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, end_date, audit_result, audit_fees, audit_agency, audit_sign |

### t_stock_fina_mainbz - 主营业务构成
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司主营业务分产品/分地区收入 |
| **Tushare接口** | `fina_mainbz` |
| **更新频率** | 年报发布时增量更新 |
| **主键** | `ts_code, end_date, bz_item, bz_code` |
| **关键字段** | ts_code, ann_date, end_date, bz_item, bz_code, bz_sales, bz_profit, bz_cost, curr_type |

### t_stock_express - 业绩快报
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司业绩快报数据 |
| **Tushare接口** | `express` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, end_date, revenue, operate_profit, total_profit, n_income, total_assets, total_hldr_eqy_exc_min_int, diluted_eps, dps, yoy_sales, yoy_op, yoy_tp, yoy_net |

### t_stock_forecast - 业绩预告
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司业绩预告数据 |
| **Tushare接口** | `forecast` |
| **更新频率** | 季报发布前更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, end_date, type, p_change_min, p_change_max, net_profit_min, net_profit_max, last_parent_net, first_ann_date, summary, change_reason |

---

## 股东数据

### t_stock_dividend - 分红送股
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司分红送股方案 |
| **Tushare接口** | `dividend` |
| **更新频率** | 分红公告时增量更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, div_proc, stk_div, stk_bo_rate, stk_co_rate, cash_div, cash_div_tax, record_date, ex_date, pay_date, div_listdate, imp_ann_date, base_date, base_share |

### t_stock_holder_number - 股东人数
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司股东户数变动 |
| **Tushare接口** | `stk_holdernumber` |
| **更新频率** | 季报发布时增量更新 |
| **主键** | `ts_code, end_date` |
| **关键字段** | ts_code, ann_date, end_date, holder_num, holder_num_change, holder_num_ratio |

### t_stock_holder_trade - 股东增减持
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司股东增减持记录 |
| **Tushare接口** | `stk_holdertrade` |
| **更新频率** | 公告时增量更新 |
| **主键** | `ts_code, ann_date, holder_name, holder_type` |
| **关键字段** | ts_code, ann_date, holder_name, holder_type, in_de, change_vol, change_ratio, after_share, after_ratio, avg_price, total_share, begin_date, close_date |

### t_stock_st_list - ST股票列表
| 项目 | 内容 |
|------|------|
| **用途** | 沪深ST股票列表及变动历史 |
| **Tushare接口** | `stock_st` |
| **更新频率** | 每日更新 |
| **主键** | `ts_code, trade_date` |
| **关键字段** | ts_code, trade_date, name |

### t_stock_top10_holders - 前十大股东
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司前十大股东持股情况 |
| **Tushare接口** | `top10_holders` |
| **更新频率** | 按需同步 |
| **主键** | `ts_code, end_date, holder_name` |
| **关键字段** | ts_code, ann_date, end_date, holder_name, hold_amount, hold_ratio, hold_change, holder_type |
| **特殊说明** | 当前为空表，历史数据使用频率低，需要时同步 |

### t_stock_top10_float_holders - 前十大流通股东
| 项目 | 内容 |
|------|------|
| **用途** | 上市公司前十大流通股东持股情况 |
| **Tushare接口** | `top10_floatholders` |
| **更新频率** | 按需同步 |
| **主键** | `ts_code, end_date, holder_name` |
| **关键字段** | ts_code, ann_date, end_date, holder_name, hold_amount, hold_ratio, hold_float_ratio, hold_change, holder_type |
| **特殊说明** | 当前为空表，历史数据使用频率低，需要时同步 |

---

## 已删除的表

以下表已从数据库中删除：

| 表名 | 删除原因 |
|------|---------|
| t_stock_balancesheet_bank | 无专门接口，数据在balancesheet表中 |
| t_stock_balancesheet_insurance | 无专门接口，数据在balancesheet表中 |
| t_stock_balancesheet_securities | 无专门接口，数据在balancesheet表中 |
| t_stock_cashflow_bank | 无专门接口，数据在cashflow表中 |
| t_stock_cashflow_insurance | 无专门接口，数据在cashflow表中 |
| t_stock_cashflow_securities | 无专门接口，数据在cashflow表中 |
| t_stock_income_bank | 无专门接口，数据在income表中 |
| t_stock_income_insurance | 无专门接口，数据在income表中 |
| t_stock_income_securities | 无专门接口，数据在income表中 |
| t_stock_cgq | API需高级权限，暂不可用 |
| t_stock_gdfx | API需高级权限，暂不可用 |
| t_stock_jgcc | API需高级权限，暂不可用 |
| t_stock_jgdy | API需高级权限，暂不可用 |

---

## 同步脚本说明

所有同步脚本位于 `scripts/sync/` 目录，命名格式：`sync_t_{表名}.py`

### 通用参数
```bash
python3 scripts/sync/sync_t_{表名}.py \
  --mode [full|incremental] \
  --start-date YYYYMMDD \
  --end-date YYYYMMDD \
  --log-file logs/{表名}_{日期}.log
```

### 示例
```bash
# 全量同步某表
python3 scripts/sync/sync_t_stock_basic.py --mode full

# 增量同步日线行情
python3 scripts/sync/sync_t_stock_dailymarketdata.py --mode incremental

# 指定日期范围同步
python3 scripts/sync/sync_t_stock_daily_basic.py \
  --mode full --start-date 20240101 --end-date 20260306
```

---

## 数据质量监控

所有同步任务完成后会自动执行数据质量检查，包括：
- 字段非空检查
- 唯一性检查
- 日期格式检查
- 枚举值检查
- 数值范围检查
- 外键引用检查

检查结果记录在 `logs/` 目录和数据库的 `sync_log` 表中。

---

## 附录：表设计清单

> 用户积分：8000分（可访问大部分接口，部分VIP接口需5000积分以上）

### 基础数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_stock_basic | stock_basic | full | 股票基础信息 |
| t_stock_tradedate | trade_cal | full | 交易日历 |
| t_stock_name_history | namechange | incremental | 股票曾用名 |
| t_stock_hs_const | hs_const | full | 沪深股通成分股 |
| t_stock_ipo | new_share | incremental | IPO新股列表 |
| t_stock_company | stock_company | full | 上市公司基本信息 |

### 行情数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_stock_dailymarketdata | daily | incremental | 日线行情（未复权） |
| t_stock_adjfactor | adj_factor | incremental | 复权因子 |
| t_stock_daily_basic | daily_basic | incremental | 每日指标（PE/PB/换手率） |
| t_stock_st_list | stock_st | incremental | ST股票列表 |
| t_stock_dailylimitprice | limit_list | incremental | 每日涨跌停价格 |
| t_stock_moneyflow | moneyflow | incremental | 个股资金流向 |
| t_stock_moneyflow_market | moneyflow_hsgt | incremental | 沪深港通资金流向 |

### 财务数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_stock_income | income | incremental | 利润表 |
| t_stock_balancesheet | balancesheet | incremental | 资产负债表 |
| t_stock_cashflow | cashflow | incremental | 现金流量表 |
| t_stock_fina_indicator | fina_indicator | incremental | 财务指标数据（ROE/周转率等） |
| t_stock_fina_audit | fina_audit | incremental | 财务审计意见 |
| t_stock_fina_mainbz | fina_mainbz | incremental | 主营业务构成 |
| t_stock_forecast | forecast | incremental | 业绩预告 |
| t_stock_express | express | incremental | 业绩快报 |
| t_stock_dividend | dividend | incremental | 分红送股 |

### 股东数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_stock_holder_number | stk_holdernumber | incremental | 股东人数 |
| t_stock_holder_trade | stk_holdertrade | incremental | 股东增减持 |
| t_stock_top10_holders | top10_holders | incremental | 前十大股东（按需同步） |
| t_stock_top10_float_holders | top10_fh | incremental | 前十大流通股东（按需同步） |

### 基金数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_fund_basic | fund_basic | full | 公募基金基础信息 |
| t_fund_nav | fund_nav | incremental | 基金净值（按需同步） |
| t_fund_share | fund_share | incremental | 基金份额（按需同步） |
| t_fund_portfolio | fund_portfolio | incremental | 基金持仓（按需同步） |

### 指数数据表

| 表名 | 对应接口 | 同步模式 | 备注 |
|------|----------|----------|------|
| t_index_basic | index_basic | full | 指数基础信息 |
| t_index_daily | index_daily | incremental | 指数日线行情 |
| t_index_weight | index_weight | incremental | 指数成分权重 |

### Interface 库表

| 表名 | 用途 | 更新频率 |
|------|------|----------|
| t_precomputed_factors | 预计算因子（40+因子） | 每日 |
| quant_factor_score | 因子得分 | 每日 |
| sync_log | 同步日志 | 每次同步 |
| sync_state | 同步状态 | 每次同步 |

---

## 附录：空表状态

### 保留的空表（按需同步）

| 表名 | 用途 | 状态 | 备注 |
|------|------|------|------|
| t_stock_top10_holders | 前十大股东 | 空表 | 历史数据使用频率低，按需同步 |
| t_stock_top10_float_holders | 前十大流通股东 | 空表 | 历史数据使用频率低，按需同步 |
| t_fund_nav | 基金净值 | 空表 | 需逐个基金查询，按需同步 |
| t_fund_share | 基金份额 | 空表 | 需逐个基金查询，按需同步 |
| t_fund_portfolio | 基金持仓 | 空表 | 可按基金代码同步，按需获取 |

### 已删除的表

以下表已从数据库中删除：
- t_stock_balancesheet_bank / insurance / securities → 数据在 balancesheet 表中
- t_stock_cashflow_bank / insurance / securities → 数据在 cashflow 表中
- t_stock_income_bank / insurance / securities → 数据在 income 表中
- t_stock_cgq, t_stock_gdfx, t_stock_jgcc, t_stock_jgdy → API需高级权限

---

*最后更新: 2026-03-18*
