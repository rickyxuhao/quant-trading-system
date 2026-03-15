# t_stock_adjfactor

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_adjfactor |
| 中文名 | 复权因子表 - 来自Tushare adj_factor |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 12,858,788 行 |
| 数据大小 | 1.08 GB |
| 索引大小 | 709.00 MB |
| 创建时间 | 2026-03-06 15:50:54 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 YYYYMMDD |
| `adj_factor` | DECIMAL(16,6) | YES | - | 复权因子 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_trade_date | 普通 | trade_date | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | adj_factor | created_at | updated_at |
| :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050104 | 25.015000 | 2026-03-06 22:38:15 | 2026-03-06 22:38:15 |
| 000001.SZ | 20050105 | 25.015000 | 2026-03-06 22:38:15 | 2026-03-06 22:38:15 |
| 000001.SZ | 20050106 | 25.015000 | 2026-03-06 22:38:15 | 2026-03-06 22:38:15 |
| 000001.SZ | 20050107 | 25.015000 | 2026-03-06 22:38:15 | 2026-03-06 22:38:15 |
| 000001.SZ | 20050110 | 25.015000 | 2026-03-06 22:38:15 | 2026-03-06 22:38:15 |

## 建表语句

```sql
CREATE TABLE `t_stock_adjfactor` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
  `adj_factor` decimal(16,6) DEFAULT NULL COMMENT '复权因子',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='复权因子表 - 来自Tushare adj_factor'
```
