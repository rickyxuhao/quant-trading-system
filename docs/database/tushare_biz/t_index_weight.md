# t_index_weight

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_index_weight |
| 中文名 | 指数成分和权重表 - 来自Tushare index_weight |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 552,944 行 |
| 数据大小 | 59.70 MB |
| 索引大小 | 72.25 MB |
| 创建时间 | 2026-03-08 12:41:35 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `index_code` | VARCHAR(20) | NO | - | 指数代码 |
| `con_code` | VARCHAR(20) | NO | - | 成分股票代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `weight` | DECIMAL(10,4) | YES | - | 权重(%) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_index_weight_con_code | 普通 | con_code | - |
| idx_index_weight_trade_date | 普通 | trade_date | - |
| PRIMARY | 主键 | index_code, con_code, trade_date | - |

## 数据示例

| index_code | con_code | trade_date | weight | created_at | updated_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000010.SH | 600000.SH | 20080102 | 4.6800 | 2026-03-08 13:20:05 | 2026-03-08 13:20:05 |
| 000010.SH | 600000.SH | 20080103 | 4.4200 | 2026-03-08 13:20:07 | 2026-03-08 13:20:07 |
| 000010.SH | 600000.SH | 20080104 | 4.5500 | 2026-03-08 13:20:09 | 2026-03-08 13:20:09 |
| 000010.SH | 600000.SH | 20080107 | 4.7400 | 2026-03-08 13:20:11 | 2026-03-08 13:20:11 |
| 000010.SH | 600000.SH | 20080108 | 4.7900 | 2026-03-08 13:20:13 | 2026-03-08 13:20:13 |

## 建表语句

```sql
CREATE TABLE `t_index_weight` (
  `index_code` varchar(20) NOT NULL COMMENT '指数代码',
  `con_code` varchar(20) NOT NULL COMMENT '成分股票代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `weight` decimal(10,4) DEFAULT NULL COMMENT '权重(%)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`index_code`,`con_code`,`trade_date`),
  KEY `idx_index_weight_trade_date` (`trade_date`),
  KEY `idx_index_weight_con_code` (`con_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指数成分和权重表 - 来自Tushare index_weight'
```
