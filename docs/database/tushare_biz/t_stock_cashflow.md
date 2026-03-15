# t_stock_cashflow

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_cashflow |
| 中文名 | 现金流量表 - 一般工商业 - 来自Tushare cashflow |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 256,995 行 |
| 数据大小 | 136.98 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `f_ann_date` | VARCHAR(8) | NO | - | 实际公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `comp_type` | VARCHAR(10) | YES | - |  |
| `c_cash_equ_end_period` | DECIMAL(20,4) | YES | - | 期末现金及现金等价物余额 |
| `n_cashflow_act` | DECIMAL(20,4) | YES | - | 经营活动产生的现金流量净额 |
| `c_recp_sell_goods` | DECIMAL(20,4) | YES | - | 销售商品、提供劳务收到的现金 |
| `n_depos_incr_fi` | DECIMAL(20,4) | YES | - |  |
| `n_incr_loans_cb` | DECIMAL(20,4) | YES | - |  |
| `n_inc_borr_oth_fi` | DECIMAL(20,4) | YES | - |  |
| `prem_fr_orig_contr` | DECIMAL(20,4) | YES | - |  |
| `n_incr_insured_dep` | DECIMAL(20,4) | YES | - |  |
| `n_reinsur_prem` | DECIMAL(20,4) | YES | - |  |
| `n_incr_disp_tfa` | DECIMAL(20,4) | YES | - |  |
| `ifc_cash_incr` | DECIMAL(20,4) | YES | - |  |
| `n_incr_disp_faas` | DECIMAL(20,4) | YES | - |  |
| `n_incr_loans_oth_bank` | DECIMAL(20,4) | YES | - |  |
| `n_cap_incr_repur` | DECIMAL(20,4) | YES | - |  |
| `c_fr_oth_operate_a` | DECIMAL(20,4) | YES | - |  |
| `c_inf_fr_operate_a` | DECIMAL(20,4) | YES | - |  |
| `c_paid_goods_s` | DECIMAL(20,4) | YES | - | 购买商品、接受劳务支付的现金 |
| `c_paid_to_for_empl` | DECIMAL(20,4) | YES | - |  |
| `c_paid_for_taxes` | DECIMAL(20,4) | YES | - |  |
| `n_incr_clt_loan_adv` | DECIMAL(20,4) | YES | - |  |
| `n_incr_dep_cbob` | DECIMAL(20,4) | YES | - |  |
| `c_pay_claims_orig_inco` | DECIMAL(20,4) | YES | - |  |
| `pay_handling_chrg` | DECIMAL(20,4) | YES | - |  |
| `pay_comm_insur_plcy` | DECIMAL(20,4) | YES | - |  |
| `oth_cash_pay_oper_act` | DECIMAL(20,4) | YES | - |  |
| `st_cash_out_act` | DECIMAL(20,4) | YES | - |  |
| `n_cashflow_inv_act` | DECIMAL(20,4) | YES | - | 投资活动产生的现金流量净额 |
| `c_recp_disp_withdrwl_invest` | DECIMAL(20,4) | YES | - |  |
| `c_recp_return_invest` | DECIMAL(20,4) | YES | - |  |
| `n_recp_disp_fiolta` | DECIMAL(20,4) | YES | - |  |
| `n_recp_disp_sobu` | DECIMAL(20,4) | YES | - |  |
| `stot_inflows_inv_act` | DECIMAL(20,4) | YES | - |  |
| `c_pay_acq_const_fiolta` | DECIMAL(20,4) | YES | - |  |
| `c_paid_invest` | DECIMAL(20,4) | YES | - |  |
| `n_disp_subs_oth_biz` | DECIMAL(20,4) | YES | - |  |
| `oth_pay_ral_inv_act` | DECIMAL(20,4) | YES | - |  |
| `n_incr_pledge_loan` | DECIMAL(20,4) | YES | - |  |
| `stot_out_inv_act` | DECIMAL(20,4) | YES | - |  |
| `n_recp_borrow_oth` | DECIMAL(20,4) | YES | - |  |
| `n_recp_borr_from_cb` | DECIMAL(20,4) | YES | - |  |
| `proc_issue_bonds` | DECIMAL(20,4) | YES | - |  |
| `oth_cash_recp_ral_fnc_act` | DECIMAL(20,4) | YES | - |  |
| `stot_cash_inflow_fnc_act` | DECIMAL(20,4) | YES | - |  |
| `free_cashflow` | DECIMAL(20,4) | YES | - | 企业自由现金流量 |
| `c_prepay_amt_borr` | DECIMAL(20,4) | YES | - |  |
| `c_pay_dist_dcpint_profits` | DECIMAL(20,4) | YES | - |  |
| `c_pay_debts` | DECIMAL(20,4) | YES | - |  |
| `stot_cashout_fnc_act` | DECIMAL(20,4) | YES | - |  |
| `n_incr_cash_equ` | DECIMAL(20,4) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date, f_ann_date | - |

## 数据示例

| ts_code | ann_date | f_ann_date | end_date | comp_type | c_cash_equ_end_period |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20070322 | 20060401 | 20051231 | 2 | 19447900111.0000 |
| 000001.SZ | 20060426 | 20060426 | 20060331 | 2 | NULL |
| 000001.SZ | 20060818 | 20060818 | 20060630 | 2 | NULL |
| 000001.SZ | 20061026 | 20061026 | 20060930 | 2 | NULL |
| 000001.SZ | 20070322 | 20070322 | 20061231 | 2 | 18007515178.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_cashflow` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `f_ann_date` varchar(8) NOT NULL COMMENT '实际公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `comp_type` varchar(10) DEFAULT NULL,
  `c_cash_equ_end_period` decimal(20,4) DEFAULT NULL COMMENT '期末现金及现金等价物余额',
  `n_cashflow_act` decimal(20,4) DEFAULT NULL COMMENT '经营活动产生的现金流量净额',
  `c_recp_sell_goods` decimal(20,4) DEFAULT NULL COMMENT '销售商品、提供劳务收到的现金',
  `n_depos_incr_fi` decimal(20,4) DEFAULT NULL,
  `n_incr_loans_cb` decimal(20,4) DEFAULT NULL,
  `n_inc_borr_oth_fi` decimal(20,4) DEFAULT NULL,
  `prem_fr_orig_contr` decimal(20,4) DEFAULT NULL,
  `n_incr_insured_dep` decimal(20,4) DEFAULT NULL,
  `n_reinsur_prem` decimal(20,4) DEFAULT NULL,
  `n_incr_disp_tfa` decimal(20,4) DEFAULT NULL,
  `ifc_cash_incr` decimal(20,4) DEFAULT NULL,
  `n_incr_disp_faas` decimal(20,4) DEFAULT NULL,
  `n_incr_loans_oth_bank` decimal(20,4) DEFAULT NULL,
  `n_cap_incr_repur` decimal(20,4) DEFAULT NULL,
  `c_fr_oth_operate_a` decimal(20,4) DEFAULT NULL,
  `c_inf_fr_operate_a` decimal(20,4) DEFAULT NULL,
  `c_paid_goods_s` decimal(20,4) DEFAULT NULL COMMENT '购买商品、接受劳务支付的现金',
  `c_paid_to_for_empl` decimal(20,4) DEFAULT NULL,
  `c_paid_for_taxes` decimal(20,4) DEFAULT NULL,
  `n_incr_clt_loan_adv` decimal(20,4) DEFAULT NULL,
  `n_incr_dep_cbob` decimal(20,4) DEFAULT NULL,
  `c_pay_claims_orig_inco` decimal(20,4) DEFAULT NULL,
  `pay_handling_chrg` decimal(20,4) DEFAULT NULL,
  `pay_comm_insur_plcy` decimal(20,4) DEFAULT NULL,
  `oth_cash_pay_oper_act` decimal(20,4) DEFAULT NULL,
  `st_cash_out_act` decimal(20,4) DEFAULT NULL,
  `n_cashflow_inv_act` decimal(20,4) DEFAULT NULL COMMENT '投资活动产生的现金流量净额',
  `c_recp_disp_withdrwl_invest` decimal(20,4) DEFAULT NULL,
  `c_recp_return_invest` decimal(20,4) DEFAULT NULL,
  `n_recp_disp_fiolta` decimal(20,4) DEFAULT NULL,
  `n_recp_disp_sobu` decimal(20,4) DEFAULT NULL,
  `stot_inflows_inv_act` decimal(20,4) DEFAULT NULL,
  `c_pay_acq_const_fiolta` decimal(20,4) DEFAULT NULL,
  `c_paid_invest` decimal(20,4) DEFAULT NULL,
  `n_disp_subs_oth_biz` decimal(20,4) DEFAULT NULL,
  `oth_pay_ral_inv_act` decimal(20,4) DEFAULT NULL,
  `n_incr_pledge_loan` decimal(20,4) DEFAULT NULL,
  `stot_out_inv_act` decimal(20,4) DEFAULT NULL,
  `n_recp_borrow_oth` decimal(20,4) DEFAULT NULL,
  `n_recp_borr_from_cb` decimal(20,4) DEFAULT NULL,
  `proc_issue_bonds` decimal(20,4) DEFAULT NULL,
  `oth_cash_recp_ral_fnc_act` decimal(20,4) DEFAULT NULL,
  `stot_cash_inflow_fnc_act` decimal(20,4) DEFAULT NULL,
  `free_cashflow` decimal(20,4) DEFAULT NULL COMMENT '企业自由现金流量',
  `c_prepay_amt_borr` decimal(20,4) DEFAULT NULL,
  `c_pay_dist_dcpint_profits` decimal(20,4) DEFAULT NULL,
  `c_pay_debts` decimal(20,4) DEFAULT NULL,
  `stot_cashout_fnc_act` decimal(20,4) DEFAULT NULL,
  `n_incr_cash_equ` decimal(20,4) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`f_ann_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='现金流量表 - 一般工商业 - 来自Tushare cashflow'
```
