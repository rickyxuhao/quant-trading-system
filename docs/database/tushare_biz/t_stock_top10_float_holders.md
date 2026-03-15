# t_stock_top10_float_holders

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_top10_float_holders |
| 中文名 | 前十大流通股东表 - 来自Tushare top10_fh |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 16,579 行 |
| 数据大小 | 4.42 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 08:57:03 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `holder_name` | VARCHAR(200) | YES | - | 股东名称 |
| `hold_amount` | DECIMAL(20,4) | YES | - | 持有数量（股） |
| `hold_ratio` | DECIMAL(10,4) | YES | - | 持有比例(%) |
| `hold_float_ratio` | DECIMAL(10,4) | YES | - |  |
| `hold_change` | DECIMAL(20,4) | YES | - | 变动数量 |
| `holder_type` | VARCHAR(100) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | holder_name | hold_amount | hold_ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20160421 | 20160331 | 中国平安保险(集团)股份有限公司-集团本级-自有资金 | 53109300.0000 | 0.3712 |
| 000001.SZ | 20160812 | 20160630 | 中国平安保险(集团)股份有限公司-集团本级-自有资金 | 63731160.0000 | 0.3712 |
| 000001.SZ | 20161021 | 20160930 | 中国平安保险(集团)股份有限公司-集团本级-自有资金 | 66599906.0000 | 0.3879 |
| 000001.SZ | 20170317 | 20161231 | 中国平安保险(集团)股份有限公司-集团本级-自有资金 | 63731160.0000 | 0.3712 |
| 000001.SZ | 20170422 | 20170331 | 中国平安保险(集团)股份有限公司-集团本级-自有资金 | 63731160.0000 | 0.3712 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_top10_float_holders` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `holder_name` varchar(200) DEFAULT NULL COMMENT '股东名称',
  `hold_amount` decimal(20,4) DEFAULT NULL COMMENT '持有数量（股）',
  `hold_ratio` decimal(10,4) DEFAULT NULL COMMENT '持有比例(%)',
  `hold_float_ratio` decimal(10,4) DEFAULT NULL,
  `hold_change` decimal(20,4) DEFAULT NULL COMMENT '变动数量',
  `holder_type` varchar(100) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='前十大流通股东表 - 来自Tushare top10_fh'
```
