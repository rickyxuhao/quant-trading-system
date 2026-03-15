# t_stock_express

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_express |
| 中文名 | 业绩快报表 - 来自Tushare express |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 25,458 行 |
| 数据大小 | 8.52 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `revenue` | DECIMAL(20,4) | YES | - | 营业收入(元) |
| `operate_profit` | DECIMAL(20,4) | YES | - | 营业利润(元) |
| `total_profit` | DECIMAL(20,4) | YES | - | 利润总额(元) |
| `n_income` | DECIMAL(20,4) | YES | - | 净利润(元) |
| `total_assets` | DECIMAL(20,4) | YES | - | 总资产(元) |
| `total_hldr_eqy_exc_min_int` | DECIMAL(20,4) | YES | - |  |
| `diluted_eps` | DECIMAL(20,4) | YES | - | 摊薄每股收益 |
| `dps` | DECIMAL(20,4) | YES | - |  |
| `yoy_sales` | DECIMAL(10,4) | YES | - | 同比增长率:营业收入 |
| `yoy_op` | DECIMAL(10,4) | YES | - |  |
| `yoy_tp` | DECIMAL(10,4) | YES | - |  |
| `yoy_netprofit` | DECIMAL(10,4) | YES | - | 同比增长率:净利润 |
| `growth_assets` | DECIMAL(10,4) | YES | - |  |
| `yoy_equity` | DECIMAL(10,4) | YES | - |  |
| `growth_bps` | DECIMAL(10,4) | YES | - |  |
| `or_last_year` | DECIMAL(20,4) | YES | - |  |
| `op_last_year` | DECIMAL(20,4) | YES | - |  |
| `tp_last_year` | DECIMAL(20,4) | YES | - |  |
| `np_last_year` | DECIMAL(20,4) | YES | - |  |
| `assets_last_year` | DECIMAL(20,4) | YES | - |  |
| `equity_last_year` | DECIMAL(20,4) | YES | - |  |
| `bps_last_year` | DECIMAL(20,4) | YES | - |  |
| `update_flag` | VARCHAR(10) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | revenue | operate_profit | total_profit |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20190104 | 20181231 | 116716000000.0000 | 32305000000.0000 | 32231000000.0000 |
| 000001.SZ | 20200114 | 20191231 | 137958000000.0000 | 36289000000.0000 | 36240000000.0000 |
| 000001.SZ | 20220114 | 20211231 | 169383000000.0000 | 45985000000.0000 | 45879000000.0000 |
| 000001.SZ | 20230117 | 20221231 | 179895000000.0000 | 57475000000.0000 | 57253000000.0000 |
| 000002.SZ | 20080320 | 20071231 | 35526611301.9400 | NULL | 7641605685.3300 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_express` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `revenue` decimal(20,4) DEFAULT NULL COMMENT '营业收入(元)',
  `operate_profit` decimal(20,4) DEFAULT NULL COMMENT '营业利润(元)',
  `total_profit` decimal(20,4) DEFAULT NULL COMMENT '利润总额(元)',
  `n_income` decimal(20,4) DEFAULT NULL COMMENT '净利润(元)',
  `total_assets` decimal(20,4) DEFAULT NULL COMMENT '总资产(元)',
  `total_hldr_eqy_exc_min_int` decimal(20,4) DEFAULT NULL,
  `diluted_eps` decimal(20,4) DEFAULT NULL COMMENT '摊薄每股收益',
  `dps` decimal(20,4) DEFAULT NULL,
  `yoy_sales` decimal(10,4) DEFAULT NULL COMMENT '同比增长率:营业收入',
  `yoy_op` decimal(10,4) DEFAULT NULL,
  `yoy_tp` decimal(10,4) DEFAULT NULL,
  `yoy_netprofit` decimal(10,4) DEFAULT NULL COMMENT '同比增长率:净利润',
  `growth_assets` decimal(10,4) DEFAULT NULL,
  `yoy_equity` decimal(10,4) DEFAULT NULL,
  `growth_bps` decimal(10,4) DEFAULT NULL,
  `or_last_year` decimal(20,4) DEFAULT NULL,
  `op_last_year` decimal(20,4) DEFAULT NULL,
  `tp_last_year` decimal(20,4) DEFAULT NULL,
  `np_last_year` decimal(20,4) DEFAULT NULL,
  `assets_last_year` decimal(20,4) DEFAULT NULL,
  `equity_last_year` decimal(20,4) DEFAULT NULL,
  `bps_last_year` decimal(20,4) DEFAULT NULL,
  `update_flag` varchar(10) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业绩快报表 - 来自Tushare express'
```
