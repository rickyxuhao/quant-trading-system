# t_stock_fina_indicator

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_fina_indicator |
| 中文名 | 财务指标数据表 - 来自Tushare fina_indicator |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 164,909 行 |
| 数据大小 | 93.77 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `roe` | DECIMAL(10,4) | YES | - | 净资产收益率(%) |
| `roe_diluted` | DECIMAL(10,4) | YES | - | 摊薄净资产收益率(%) |
| `roe_avg` | DECIMAL(10,4) | YES | - |  |
| `roa` | DECIMAL(10,4) | YES | - | 总资产报酬率(%) |
| `roa_yearly` | DECIMAL(10,4) | YES | - |  |
| `sales_margin` | DECIMAL(10,4) | YES | - | 销售净利率(%) |
| `net_profit_margin` | DECIMAL(10,4) | YES | - |  |
| `gross_profit_margin` | DECIMAL(10,4) | YES | - | 销售毛利率(%) |
| `sales_to_admin_ratio` | DECIMAL(10,4) | YES | - |  |
| `sales_to_sale_ratio` | DECIMAL(10,4) | YES | - |  |
| `asset_turnover` | DECIMAL(10,4) | YES | - | 总资产周转率 |
| `ca_turnover` | DECIMAL(10,4) | YES | - |  |
| `fa_turnover` | DECIMAL(10,4) | YES | - |  |
| `current_ratio` | DECIMAL(10,4) | YES | - | 流动比率 |
| `quick_ratio` | DECIMAL(10,4) | YES | - | 速动比率 |
| `cash_ratio` | DECIMAL(10,4) | YES | - |  |
| `inv_days` | DECIMAL(10,4) | YES | - |  |
| `ar_days` | DECIMAL(10,4) | YES | - |  |
| `debt_to_assets` | DECIMAL(10,4) | YES | - | 资产负债率(%) |
| `assets_to_eqt` | DECIMAL(10,4) | YES | - |  |
| `debt_to_eqt` | DECIMAL(10,4) | YES | - |  |
| `netdebt_to_eqt` | DECIMAL(10,4) | YES | - |  |
| `ocf_to_shortdebt` | DECIMAL(10,4) | YES | - |  |
| `ocf_to_debt` | DECIMAL(10,4) | YES | - |  |
| `ocf_to_interest` | DECIMAL(10,4) | YES | - |  |
| `profit_to_op` | DECIMAL(10,4) | YES | - |  |
| `basic_eps_yoy` | DECIMAL(10,4) | YES | - |  |
| `dt_eps_yoy` | DECIMAL(10,4) | YES | - |  |
| `cfps_yoy` | DECIMAL(10,4) | YES | - |  |
| `op_yoy` | DECIMAL(10,4) | YES | - |  |
| `ebt_yoy` | DECIMAL(10,4) | YES | - |  |
| `netprofit_yoy` | DECIMAL(10,4) | YES | - | 归属母公司股东的净利润同比增长率(%) |
| `dt_netprofit_yoy` | DECIMAL(10,4) | YES | - |  |
| `roe_yoy` | DECIMAL(10,4) | YES | - |  |
| `bps_yoy` | DECIMAL(10,4) | YES | - |  |
| `assets_yoy` | DECIMAL(10,4) | YES | - |  |
| `eqt_yoy` | DECIMAL(10,4) | YES | - |  |
| `tr_yoy` | DECIMAL(10,4) | YES | - |  |
| `or_yoy` | DECIMAL(10,4) | YES | - |  |
| `q_sales_yoy` | DECIMAL(10,4) | YES | - |  |
| `q_op_qoq` | DECIMAL(10,4) | YES | - |  |
| `equity_yoy` | DECIMAL(10,4) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | roe | roe_diluted | roe_avg |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20120816 | 20120630 | 8.8308 | NULL | NULL |
| 000001.SZ | 20121026 | 20120930 | 13.2071 | NULL | NULL |
| 000001.SZ | 20130308 | 20121231 | 16.9537 | NULL | NULL |
| 000001.SZ | 20130424 | 20130331 | 4.1358 | NULL | NULL |
| 000001.SZ | 20130823 | 20130630 | 8.5414 | NULL | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_fina_indicator` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `roe` decimal(10,4) DEFAULT NULL COMMENT '净资产收益率(%)',
  `roe_diluted` decimal(10,4) DEFAULT NULL COMMENT '摊薄净资产收益率(%)',
  `roe_avg` decimal(10,4) DEFAULT NULL,
  `roa` decimal(10,4) DEFAULT NULL COMMENT '总资产报酬率(%)',
  `roa_yearly` decimal(10,4) DEFAULT NULL,
  `sales_margin` decimal(10,4) DEFAULT NULL COMMENT '销售净利率(%)',
  `net_profit_margin` decimal(10,4) DEFAULT NULL,
  `gross_profit_margin` decimal(10,4) DEFAULT NULL COMMENT '销售毛利率(%)',
  `sales_to_admin_ratio` decimal(10,4) DEFAULT NULL,
  `sales_to_sale_ratio` decimal(10,4) DEFAULT NULL,
  `asset_turnover` decimal(10,4) DEFAULT NULL COMMENT '总资产周转率',
  `ca_turnover` decimal(10,4) DEFAULT NULL,
  `fa_turnover` decimal(10,4) DEFAULT NULL,
  `current_ratio` decimal(10,4) DEFAULT NULL COMMENT '流动比率',
  `quick_ratio` decimal(10,4) DEFAULT NULL COMMENT '速动比率',
  `cash_ratio` decimal(10,4) DEFAULT NULL,
  `inv_days` decimal(10,4) DEFAULT NULL,
  `ar_days` decimal(10,4) DEFAULT NULL,
  `debt_to_assets` decimal(10,4) DEFAULT NULL COMMENT '资产负债率(%)',
  `assets_to_eqt` decimal(10,4) DEFAULT NULL,
  `debt_to_eqt` decimal(10,4) DEFAULT NULL,
  `netdebt_to_eqt` decimal(10,4) DEFAULT NULL,
  `ocf_to_shortdebt` decimal(10,4) DEFAULT NULL,
  `ocf_to_debt` decimal(10,4) DEFAULT NULL,
  `ocf_to_interest` decimal(10,4) DEFAULT NULL,
  `profit_to_op` decimal(10,4) DEFAULT NULL,
  `basic_eps_yoy` decimal(10,4) DEFAULT NULL,
  `dt_eps_yoy` decimal(10,4) DEFAULT NULL,
  `cfps_yoy` decimal(10,4) DEFAULT NULL,
  `op_yoy` decimal(10,4) DEFAULT NULL,
  `ebt_yoy` decimal(10,4) DEFAULT NULL,
  `netprofit_yoy` decimal(10,4) DEFAULT NULL COMMENT '归属母公司股东的净利润同比增长率(%)',
  `dt_netprofit_yoy` decimal(10,4) DEFAULT NULL,
  `roe_yoy` decimal(10,4) DEFAULT NULL,
  `bps_yoy` decimal(10,4) DEFAULT NULL,
  `assets_yoy` decimal(10,4) DEFAULT NULL,
  `eqt_yoy` decimal(10,4) DEFAULT NULL,
  `tr_yoy` decimal(10,4) DEFAULT NULL,
  `or_yoy` decimal(10,4) DEFAULT NULL,
  `q_sales_yoy` decimal(10,4) DEFAULT NULL,
  `q_op_qoq` decimal(10,4) DEFAULT NULL,
  `equity_yoy` decimal(10,4) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='财务指标数据表 - 来自Tushare fina_indicator'
```
