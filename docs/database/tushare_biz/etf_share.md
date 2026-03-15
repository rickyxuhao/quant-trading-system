# etf_share

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | etf_share |
| 中文名 | ETF份额规模表 - 来自Tushare fund_share |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 1,964,431 行 |
| 数据大小 | 133.86 MB |
| 索引大小 | 169.41 MB |
| 创建时间 | 2026-03-08 09:15:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `share` | DECIMAL(20,4) | YES | - | 基金份额(万份) |
| `nav_date` | VARCHAR(8) | YES | - | 净值日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_etf_share_trade_date | 普通 | trade_date | - |
| idx_etf_share_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | share | nav_date | created_at | updated_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.OF | 20100331 | NULL | NULL | 2026-03-08 10:00:01 | 2026-03-08 10:00:01 |
| 000001.OF | 20100630 | NULL | NULL | 2026-03-08 10:00:11 | 2026-03-08 10:00:11 |
| 000001.OF | 20100930 | NULL | NULL | 2026-03-08 10:00:21 | 2026-03-08 10:00:21 |
| 000001.OF | 20101231 | NULL | NULL | 2026-03-08 10:00:31 | 2026-03-08 10:00:31 |
| 000001.OF | 20110331 | NULL | NULL | 2026-03-08 10:00:41 | 2026-03-08 10:00:41 |

## 建表语句

```sql
CREATE TABLE `etf_share` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `share` decimal(20,4) DEFAULT NULL COMMENT '基金份额(万份)',
  `nav_date` varchar(8) DEFAULT NULL COMMENT '净值日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_etf_share_trade_date` (`trade_date`),
  KEY `idx_etf_share_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETF份额规模表 - 来自Tushare fund_share'
```
