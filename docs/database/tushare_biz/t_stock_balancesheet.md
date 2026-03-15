# t_stock_balancesheet

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_balancesheet |
| 中文名 | 资产负债表 - 一般工商业 - 来自Tushare balancesheet |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 221,163 行 |
| 数据大小 | 190.97 MB |
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
| `total_share` | DECIMAL(20,4) | YES | - |  |
| `cap_rese` | DECIMAL(20,4) | YES | - |  |
| `undistr_porfit` | DECIMAL(20,4) | YES | - |  |
| `surplus_rese` | DECIMAL(20,4) | YES | - |  |
| `special_rese` | DECIMAL(20,4) | YES | - |  |
| `money_cap` | DECIMAL(20,4) | YES | - |  |
| `trad_asset` | DECIMAL(20,4) | YES | - |  |
| `notes_receiv` | DECIMAL(20,4) | YES | - |  |
| `accounts_receiv` | DECIMAL(20,4) | YES | - |  |
| `oth_receiv` | DECIMAL(20,4) | YES | - |  |
| `prepayment` | DECIMAL(20,4) | YES | - |  |
| `div_receiv` | DECIMAL(20,4) | YES | - |  |
| `int_receiv` | DECIMAL(20,4) | YES | - |  |
| `inventories` | DECIMAL(20,4) | YES | - |  |
| `amor_exp` | DECIMAL(20,4) | YES | - |  |
| `nca_within_1y` | DECIMAL(20,4) | YES | - |  |
| `sett_rsrv` | DECIMAL(20,4) | YES | - |  |
| `loanto_oth_bank_fi` | DECIMAL(20,4) | YES | - |  |
| `premium_receiv` | DECIMAL(20,4) | YES | - |  |
| `reinsur_receiv` | DECIMAL(20,4) | YES | - |  |
| `reinsur_res_receiv` | DECIMAL(20,4) | YES | - |  |
| `pur_resale_fa` | DECIMAL(20,4) | YES | - |  |
| `oth_cur_assets` | DECIMAL(20,4) | YES | - |  |
| `total_cur_assets` | DECIMAL(20,4) | YES | - | 流动资产合计 |
| `fa_avail_for_sale` | DECIMAL(20,4) | YES | - |  |
| `htm_invest` | DECIMAL(20,4) | YES | - |  |
| `lt_eqt_invest` | DECIMAL(20,4) | YES | - |  |
| `invest_real_estate` | DECIMAL(20,4) | YES | - |  |
| `time_deposits` | DECIMAL(20,4) | YES | - |  |
| `oth_assets` | DECIMAL(20,4) | YES | - |  |
| `lt_rec` | DECIMAL(20,4) | YES | - |  |
| `fix_assets` | DECIMAL(20,4) | YES | - |  |
| `cip` | DECIMAL(20,4) | YES | - |  |
| `const_materials` | DECIMAL(20,4) | YES | - |  |
| `fixed_assets_disp` | DECIMAL(20,4) | YES | - |  |
| `produc_bio_assets` | DECIMAL(20,4) | YES | - |  |
| `oil_and_gas_assets` | DECIMAL(20,4) | YES | - |  |
| `intan_assets` | DECIMAL(20,4) | YES | - |  |
| `r_and_d` | DECIMAL(20,4) | YES | - |  |
| `goodwill` | DECIMAL(20,4) | YES | - |  |
| `lt_amor_exp` | DECIMAL(20,4) | YES | - |  |
| `defer_tax_assets` | DECIMAL(20,4) | YES | - |  |
| `decr_in_disbur` | DECIMAL(20,4) | YES | - |  |
| `oth_nca` | DECIMAL(20,4) | YES | - |  |
| `total_nca` | DECIMAL(20,4) | YES | - | 非流动资产合计 |
| `cash_reser_cb` | DECIMAL(20,4) | YES | - |  |
| `depos_in_oth_bfi` | DECIMAL(20,4) | YES | - |  |
| `prec_metals` | DECIMAL(20,4) | YES | - |  |
| `deriv_assets` | DECIMAL(20,4) | YES | - |  |
| `total_assets` | DECIMAL(20,4) | YES | - | 资产总计 |
| `c_borr_from_oth_fi` | DECIMAL(20,4) | YES | - |  |
| `notes_payable` | DECIMAL(20,4) | YES | - |  |
| `acct_payable` | DECIMAL(20,4) | YES | - |  |
| `adv_receipts` | DECIMAL(20,4) | YES | - |  |
| `sold_for_repur_fa` | DECIMAL(20,4) | YES | - |  |
| `comm_payable` | DECIMAL(20,4) | YES | - |  |
| `payroll_payable` | DECIMAL(20,4) | YES | - |  |
| `taxes_payable` | DECIMAL(20,4) | YES | - |  |
| `int_payable` | DECIMAL(20,4) | YES | - |  |
| `div_payable` | DECIMAL(20,4) | YES | - |  |
| `oth_payable` | DECIMAL(20,4) | YES | - |  |
| `acc_exp` | DECIMAL(20,4) | YES | - |  |
| `deferred_inc` | DECIMAL(20,4) | YES | - |  |
| `st_bonds_payable` | DECIMAL(20,4) | YES | - |  |
| `payable_to_reinsurer` | DECIMAL(20,4) | YES | - |  |
| `rsrv_insur_cont` | DECIMAL(20,4) | YES | - |  |
| `acting_trading_sec` | DECIMAL(20,4) | YES | - |  |
| `acting_uw_sec` | DECIMAL(20,4) | YES | - |  |
| `non_cur_liab_due_1y` | DECIMAL(20,4) | YES | - |  |
| `oth_cur_liab` | DECIMAL(20,4) | YES | - |  |
| `total_cur_liab` | DECIMAL(20,4) | YES | - | 流动负债合计 |
| `bonds_payable` | DECIMAL(20,4) | YES | - |  |
| `lt_payable` | DECIMAL(20,4) | YES | - |  |
| `specific_payables` | DECIMAL(20,4) | YES | - |  |
| `estimated_liab` | DECIMAL(20,4) | YES | - |  |
| `defer_tax_liab` | DECIMAL(20,4) | YES | - |  |
| `defer_inc_non_cur_liab` | DECIMAL(20,4) | YES | - |  |
| `oth_ncl` | DECIMAL(20,4) | YES | - |  |
| `total_ncl` | DECIMAL(20,4) | YES | - | 非流动负债合计 |
| `depos_oth_bfi` | DECIMAL(20,4) | YES | - |  |
| `deriv_liab` | DECIMAL(20,4) | YES | - |  |
| `depos_fr_non_bank` | DECIMAL(20,4) | YES | - |  |
| `loan_oth_bank` | DECIMAL(20,4) | YES | - |  |
| `trading_fl` | DECIMAL(20,4) | YES | - |  |
| `notes_payable_1` | DECIMAL(20,4) | YES | - |  |
| `int_payable_1` | DECIMAL(20,4) | YES | - |  |
| `div_payable_1` | DECIMAL(20,4) | YES | - |  |
| `oth_payable_1` | DECIMAL(20,4) | YES | - |  |
| `acc_exp_1` | DECIMAL(20,4) | YES | - |  |
| `total_liab` | DECIMAL(20,4) | YES | - | 负债合计 |
| `rec_dep_invests` | DECIMAL(20,4) | YES | - |  |
| `total_equity` | DECIMAL(20,4) | YES | - | 所有者权益合计 |
| `minority_int` | DECIMAL(20,4) | YES | - |  |
| `total_hldr_eqy_exc_min_int` | DECIMAL(20,4) | YES | - | 归属于母公司所有者权益合计 |
| `total_hldr_eqy_inc_min_int` | DECIMAL(20,4) | YES | - |  |
| `total_liab_hldr_eqy` | DECIMAL(20,4) | YES | - |  |
| `lt_payroll_payable` | DECIMAL(20,4) | YES | - |  |
| `oth_comp_income` | DECIMAL(20,4) | YES | - |  |
| `oth_eqt_tools` | DECIMAL(20,4) | YES | - |  |
| `oth_eqt_tools_p_shr` | DECIMAL(20,4) | YES | - |  |
| `lending_funds` | DECIMAL(20,4) | YES | - |  |
| `acc_receivable` | DECIMAL(20,4) | YES | - |  |
| `st_fin_payable` | DECIMAL(20,4) | YES | - |  |
| `payables` | DECIMAL(20,4) | YES | - |  |
| `hfs_assets` | DECIMAL(20,4) | YES | - |  |
| `hfs_sales` | DECIMAL(20,4) | YES | - |  |
| `update_flag` | VARCHAR(10) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date, f_ann_date | - |

## 数据示例

| ts_code | ann_date | f_ann_date | end_date | comp_type | total_share |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20090424 | 20090424 | 20090331 | 2 | 3105434000.0000 |
| 000001.SZ | 20090821 | 20090821 | 20090630 | 2 | 3105434000.0000 |
| 000001.SZ | 20091029 | 20091029 | 20090930 | 2 | 3105434000.0000 |
| 000001.SZ | 20100312 | 20100312 | 20091231 | 2 | 3105434000.0000 |
| 000001.SZ | 20100429 | 20100429 | 20100331 | 2 | 3105434000.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_balancesheet` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `f_ann_date` varchar(8) NOT NULL COMMENT '实际公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `comp_type` varchar(10) DEFAULT NULL,
  `total_share` decimal(20,4) DEFAULT NULL,
  `cap_rese` decimal(20,4) DEFAULT NULL,
  `undistr_porfit` decimal(20,4) DEFAULT NULL,
  `surplus_rese` decimal(20,4) DEFAULT NULL,
  `special_rese` decimal(20,4) DEFAULT NULL,
  `money_cap` decimal(20,4) DEFAULT NULL,
  `trad_asset` decimal(20,4) DEFAULT NULL,
  `notes_receiv` decimal(20,4) DEFAULT NULL,
  `accounts_receiv` decimal(20,4) DEFAULT NULL,
  `oth_receiv` decimal(20,4) DEFAULT NULL,
  `prepayment` decimal(20,4) DEFAULT NULL,
  `div_receiv` decimal(20,4) DEFAULT NULL,
  `int_receiv` decimal(20,4) DEFAULT NULL,
  `inventories` decimal(20,4) DEFAULT NULL,
  `amor_exp` decimal(20,4) DEFAULT NULL,
  `nca_within_1y` decimal(20,4) DEFAULT NULL,
  `sett_rsrv` decimal(20,4) DEFAULT NULL,
  `loanto_oth_bank_fi` decimal(20,4) DEFAULT NULL,
  `premium_receiv` decimal(20,4) DEFAULT NULL,
  `reinsur_receiv` decimal(20,4) DEFAULT NULL,
  `reinsur_res_receiv` decimal(20,4) DEFAULT NULL,
  `pur_resale_fa` decimal(20,4) DEFAULT NULL,
  `oth_cur_assets` decimal(20,4) DEFAULT NULL,
  `total_cur_assets` decimal(20,4) DEFAULT NULL COMMENT '流动资产合计',
  `fa_avail_for_sale` decimal(20,4) DEFAULT NULL,
  `htm_invest` decimal(20,4) DEFAULT NULL,
  `lt_eqt_invest` decimal(20,4) DEFAULT NULL,
  `invest_real_estate` decimal(20,4) DEFAULT NULL,
  `time_deposits` decimal(20,4) DEFAULT NULL,
  `oth_assets` decimal(20,4) DEFAULT NULL,
  `lt_rec` decimal(20,4) DEFAULT NULL,
  `fix_assets` decimal(20,4) DEFAULT NULL,
  `cip` decimal(20,4) DEFAULT NULL,
  `const_materials` decimal(20,4) DEFAULT NULL,
  `fixed_assets_disp` decimal(20,4) DEFAULT NULL,
  `produc_bio_assets` decimal(20,4) DEFAULT NULL,
  `oil_and_gas_assets` decimal(20,4) DEFAULT NULL,
  `intan_assets` decimal(20,4) DEFAULT NULL,
  `r_and_d` decimal(20,4) DEFAULT NULL,
  `goodwill` decimal(20,4) DEFAULT NULL,
  `lt_amor_exp` decimal(20,4) DEFAULT NULL,
  `defer_tax_assets` decimal(20,4) DEFAULT NULL,
  `decr_in_disbur` decimal(20,4) DEFAULT NULL,
  `oth_nca` decimal(20,4) DEFAULT NULL,
  `total_nca` decimal(20,4) DEFAULT NULL COMMENT '非流动资产合计',
  `cash_reser_cb` decimal(20,4) DEFAULT NULL,
  `depos_in_oth_bfi` decimal(20,4) DEFAULT NULL,
  `prec_metals` decimal(20,4) DEFAULT NULL,
  `deriv_assets` decimal(20,4) DEFAULT NULL,
  `total_assets` decimal(20,4) DEFAULT NULL COMMENT '资产总计',
  `c_borr_from_oth_fi` decimal(20,4) DEFAULT NULL,
  `notes_payable` decimal(20,4) DEFAULT NULL,
  `acct_payable` decimal(20,4) DEFAULT NULL,
  `adv_receipts` decimal(20,4) DEFAULT NULL,
  `sold_for_repur_fa` decimal(20,4) DEFAULT NULL,
  `comm_payable` decimal(20,4) DEFAULT NULL,
  `payroll_payable` decimal(20,4) DEFAULT NULL,
  `taxes_payable` decimal(20,4) DEFAULT NULL,
  `int_payable` decimal(20,4) DEFAULT NULL,
  `div_payable` decimal(20,4) DEFAULT NULL,
  `oth_payable` decimal(20,4) DEFAULT NULL,
  `acc_exp` decimal(20,4) DEFAULT NULL,
  `deferred_inc` decimal(20,4) DEFAULT NULL,
  `st_bonds_payable` decimal(20,4) DEFAULT NULL,
  `payable_to_reinsurer` decimal(20,4) DEFAULT NULL,
  `rsrv_insur_cont` decimal(20,4) DEFAULT NULL,
  `acting_trading_sec` decimal(20,4) DEFAULT NULL,
  `acting_uw_sec` decimal(20,4) DEFAULT NULL,
  `non_cur_liab_due_1y` decimal(20,4) DEFAULT NULL,
  `oth_cur_liab` decimal(20,4) DEFAULT NULL,
  `total_cur_liab` decimal(20,4) DEFAULT NULL COMMENT '流动负债合计',
  `bonds_payable` decimal(20,4) DEFAULT NULL,
  `lt_payable` decimal(20,4) DEFAULT NULL,
  `specific_payables` decimal(20,4) DEFAULT NULL,
  `estimated_liab` decimal(20,4) DEFAULT NULL,
  `defer_tax_liab` decimal(20,4) DEFAULT NULL,
  `defer_inc_non_cur_liab` decimal(20,4) DEFAULT NULL,
  `oth_ncl` decimal(20,4) DEFAULT NULL,
  `total_ncl` decimal(20,4) DEFAULT NULL COMMENT '非流动负债合计',
  `depos_oth_bfi` decimal(20,4) DEFAULT NULL,
  `deriv_liab` decimal(20,4) DEFAULT NULL,
  `depos_fr_non_bank` decimal(20,4) DEFAULT NULL,
  `loan_oth_bank` decimal(20,4) DEFAULT NULL,
  `trading_fl` decimal(20,4) DEFAULT NULL,
  `notes_payable_1` decimal(20,4) DEFAULT NULL,
  `int_payable_1` decimal(20,4) DEFAULT NULL,
  `div_payable_1` decimal(20,4) DEFAULT NULL,
  `oth_payable_1` decimal(20,4) DEFAULT NULL,
  `acc_exp_1` decimal(20,4) DEFAULT NULL,
  `total_liab` decimal(20,4) DEFAULT NULL COMMENT '负债合计',
  `rec_dep_invests` decimal(20,4) DEFAULT NULL,
  `total_equity` decimal(20,4) DEFAULT NULL COMMENT '所有者权益合计',
  `minority_int` decimal(20,4) DEFAULT NULL,
  `total_hldr_eqy_exc_min_int` decimal(20,4) DEFAULT NULL COMMENT '归属于母公司所有者权益合计',
  `total_hldr_eqy_inc_min_int` decimal(20,4) DEFAULT NULL,
  `total_liab_hldr_eqy` decimal(20,4) DEFAULT NULL,
  `lt_payroll_payable` decimal(20,4) DEFAULT NULL,
  `oth_comp_income` decimal(20,4) DEFAULT NULL,
  `oth_eqt_tools` decimal(20,4) DEFAULT NULL,
  `oth_eqt_tools_p_shr` decimal(20,4) DEFAULT NULL,
  `lending_funds` decimal(20,4) DEFAULT NULL,
  `acc_receivable` decimal(20,4) DEFAULT NULL,
  `st_fin_payable` decimal(20,4) DEFAULT NULL,
  `payables` decimal(20,4) DEFAULT NULL,
  `hfs_assets` decimal(20,4) DEFAULT NULL,
  `hfs_sales` decimal(20,4) DEFAULT NULL,
  `update_flag` varchar(10) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`f_ann_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='资产负债表 - 一般工商业 - 来自Tushare balancesheet'
```
