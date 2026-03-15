# etf_adj_factor

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | etf_adj_factor |
| 中文名 | ETF复权因子表 - 来自Tushare fund_adj |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2,967,204 行 |
| 数据大小 | 251.00 MB |
| 索引大小 | 207.44 MB |
| 创建时间 | 2026-03-08 09:15:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `adj_factor` | DECIMAL(20,6) | YES | - | 复权因子 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_etf_adj_factor_trade_date | 普通 | trade_date | - |
| idx_etf_adj_factor_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | adj_factor | created_at | updated_at |
| :--- | :--- | :--- | :--- | :--- |
| 150001-1.SZ | 20100104 | 1.178000 | 2026-03-08 09:59:51 | 2026-03-08 09:59:51 |
| 150001-1.SZ | 20100105 | 1.178000 | 2026-03-08 09:59:51 | 2026-03-08 09:59:51 |
| 150001-1.SZ | 20100106 | 1.178000 | 2026-03-08 09:59:51 | 2026-03-08 09:59:51 |
| 150001-1.SZ | 20100107 | 1.178000 | 2026-03-08 09:59:51 | 2026-03-08 09:59:51 |
| 150001-1.SZ | 20100108 | 1.178000 | 2026-03-08 09:59:52 | 2026-03-08 09:59:52 |

## 建表语句

```sql
CREATE TABLE `etf_adj_factor` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `adj_factor` decimal(20,6) DEFAULT NULL COMMENT '复权因子',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_etf_adj_factor_trade_date` (`trade_date`),
  KEY `idx_etf_adj_factor_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETF复权因子表 - 来自Tushare fund_adj'
```
