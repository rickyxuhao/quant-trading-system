# t_stock_income

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_income |
| 中文名 | 利润表 - 一般工商业 - 来自Tushare income |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 217,350 行 |
| 数据大小 | 124.97 MB |
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
| `basic_eps` | DECIMAL(20,4) | YES | - | 基本每股收益 |
| `diluted_eps` | DECIMAL(20,4) | YES | - | 稀释每股收益 |
| `total_revenue` | DECIMAL(20,4) | YES | - | 营业总收入 |
| `revenue` | DECIMAL(20,4) | YES | - | 营业收入 |
| `int_income` | DECIMAL(20,4) | YES | - |  |
| `prem_earned` | DECIMAL(20,4) | YES | - |  |
| `comm_income` | DECIMAL(20,4) | YES | - |  |
| `n_commis_income` | DECIMAL(20,4) | YES | - |  |
| `n_oth_income` | DECIMAL(20,4) | YES | - |  |
| `n_oth_b_income` | DECIMAL(20,4) | YES | - |  |
| `prem_income` | DECIMAL(20,4) | YES | - |  |
| `out_prem` | DECIMAL(20,4) | YES | - |  |
| `une_prem_reser` | DECIMAL(20,4) | YES | - |  |
| `reins_income` | DECIMAL(20,4) | YES | - |  |
| `n_sec_tb_income` | DECIMAL(20,4) | YES | - |  |
| `n_sec_uw_income` | DECIMAL(20,4) | YES | - |  |
| `n_asset_mg_income` | DECIMAL(20,4) | YES | - |  |
| `oth_b_income` | DECIMAL(20,4) | YES | - |  |
| `fv_value_chg_gain` | DECIMAL(20,4) | YES | - |  |
| `invest_income` | DECIMAL(20,4) | YES | - |  |
| `a_j_income` | DECIMAL(20,4) | YES | - |  |
| `assets_dispos_income` | DECIMAL(20,4) | YES | - |  |
| `total_cogs` | DECIMAL(20,4) | YES | - |  |
| `operate_exp` | DECIMAL(20,4) | YES | - |  |
| `int_exp` | DECIMAL(20,4) | YES | - |  |
| `comm_exp` | DECIMAL(20,4) | YES | - |  |
| `prem_refund` | DECIMAL(20,4) | YES | - |  |
| `compens_payout` | DECIMAL(20,4) | YES | - |  |
| `reser_insur_liab` | DECIMAL(20,4) | YES | - |  |
| `policy_div_payt` | DECIMAL(20,4) | YES | - |  |
| `reinsur_exp` | DECIMAL(20,4) | YES | - |  |
| `operate_taxes` | DECIMAL(20,4) | YES | - |  |
| `sale_exp` | DECIMAL(20,4) | YES | - |  |
| `admin_exp` | DECIMAL(20,4) | YES | - |  |
| `finan_exp` | DECIMAL(20,4) | YES | - |  |
| `assets_impair_loss` | DECIMAL(20,4) | YES | - |  |
| `credit_impair_loss` | DECIMAL(20,4) | YES | - |  |
| `oth_loss` | DECIMAL(20,4) | YES | - |  |
| `net_exp_other_business` | DECIMAL(20,4) | YES | - |  |
| `operate_profit` | DECIMAL(20,4) | YES | - | 营业利润 |
| `noperate_income` | DECIMAL(20,4) | YES | - |  |
| `noperate_exp` | DECIMAL(20,4) | YES | - |  |
| `nca_disploss` | DECIMAL(20,4) | YES | - |  |
| `total_profit` | DECIMAL(20,4) | YES | - | 利润总额 |
| `income_tax` | DECIMAL(20,4) | YES | - | 所得税费用 |
| `n_income` | DECIMAL(20,4) | YES | - | 净利润 |
| `n_income_attr_p` | DECIMAL(20,4) | YES | - |  |
| `minority_gain` | DECIMAL(20,4) | YES | - |  |
| `oth_compr_income` | DECIMAL(20,4) | YES | - |  |
| `t_compr_income` | DECIMAL(20,4) | YES | - |  |
| `compr_inc_attr_p` | DECIMAL(20,4) | YES | - |  |
| `compr_inc_attr_m_s` | DECIMAL(20,4) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date, f_ann_date | - |

## 数据示例

| ts_code | ann_date | f_ann_date | end_date | comp_type | basic_eps |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050426 | 20050426 | 20041231 | 2 | NULL |
| 000001.SZ | 20050426 | 20050426 | 20050331 | 2 | NULL |
| 000001.SZ | 20050819 | 20060705 | 20050630 | 2 | NULL |
| 000001.SZ | 20051029 | 20051029 | 20050930 | 2 | NULL |
| 000001.SZ | 20070322 | 20060401 | 20051231 | 2 | 0.1600 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_income` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `f_ann_date` varchar(8) NOT NULL COMMENT '实际公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `comp_type` varchar(10) DEFAULT NULL,
  `basic_eps` decimal(20,4) DEFAULT NULL COMMENT '基本每股收益',
  `diluted_eps` decimal(20,4) DEFAULT NULL COMMENT '稀释每股收益',
  `total_revenue` decimal(20,4) DEFAULT NULL COMMENT '营业总收入',
  `revenue` decimal(20,4) DEFAULT NULL COMMENT '营业收入',
  `int_income` decimal(20,4) DEFAULT NULL,
  `prem_earned` decimal(20,4) DEFAULT NULL,
  `comm_income` decimal(20,4) DEFAULT NULL,
  `n_commis_income` decimal(20,4) DEFAULT NULL,
  `n_oth_income` decimal(20,4) DEFAULT NULL,
  `n_oth_b_income` decimal(20,4) DEFAULT NULL,
  `prem_income` decimal(20,4) DEFAULT NULL,
  `out_prem` decimal(20,4) DEFAULT NULL,
  `une_prem_reser` decimal(20,4) DEFAULT NULL,
  `reins_income` decimal(20,4) DEFAULT NULL,
  `n_sec_tb_income` decimal(20,4) DEFAULT NULL,
  `n_sec_uw_income` decimal(20,4) DEFAULT NULL,
  `n_asset_mg_income` decimal(20,4) DEFAULT NULL,
  `oth_b_income` decimal(20,4) DEFAULT NULL,
  `fv_value_chg_gain` decimal(20,4) DEFAULT NULL,
  `invest_income` decimal(20,4) DEFAULT NULL,
  `a_j_income` decimal(20,4) DEFAULT NULL,
  `assets_dispos_income` decimal(20,4) DEFAULT NULL,
  `total_cogs` decimal(20,4) DEFAULT NULL,
  `operate_exp` decimal(20,4) DEFAULT NULL,
  `int_exp` decimal(20,4) DEFAULT NULL,
  `comm_exp` decimal(20,4) DEFAULT NULL,
  `prem_refund` decimal(20,4) DEFAULT NULL,
  `compens_payout` decimal(20,4) DEFAULT NULL,
  `reser_insur_liab` decimal(20,4) DEFAULT NULL,
  `policy_div_payt` decimal(20,4) DEFAULT NULL,
  `reinsur_exp` decimal(20,4) DEFAULT NULL,
  `operate_taxes` decimal(20,4) DEFAULT NULL,
  `sale_exp` decimal(20,4) DEFAULT NULL,
  `admin_exp` decimal(20,4) DEFAULT NULL,
  `finan_exp` decimal(20,4) DEFAULT NULL,
  `assets_impair_loss` decimal(20,4) DEFAULT NULL,
  `credit_impair_loss` decimal(20,4) DEFAULT NULL,
  `oth_loss` decimal(20,4) DEFAULT NULL,
  `net_exp_other_business` decimal(20,4) DEFAULT NULL,
  `operate_profit` decimal(20,4) DEFAULT NULL COMMENT '营业利润',
  `noperate_income` decimal(20,4) DEFAULT NULL,
  `noperate_exp` decimal(20,4) DEFAULT NULL,
  `nca_disploss` decimal(20,4) DEFAULT NULL,
  `total_profit` decimal(20,4) DEFAULT NULL COMMENT '利润总额',
  `income_tax` decimal(20,4) DEFAULT NULL COMMENT '所得税费用',
  `n_income` decimal(20,4) DEFAULT NULL COMMENT '净利润',
  `n_income_attr_p` decimal(20,4) DEFAULT NULL,
  `minority_gain` decimal(20,4) DEFAULT NULL,
  `oth_compr_income` decimal(20,4) DEFAULT NULL,
  `t_compr_income` decimal(20,4) DEFAULT NULL,
  `compr_inc_attr_p` decimal(20,4) DEFAULT NULL,
  `compr_inc_attr_m_s` decimal(20,4) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`f_ann_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='利润表 - 一般工商业 - 来自Tushare income'
```
