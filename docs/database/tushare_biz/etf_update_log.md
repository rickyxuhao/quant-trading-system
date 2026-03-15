# etf_update_log

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | etf_update_log |
| 中文名 | ETF更新日志表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 09:15:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `table_name` | VARCHAR(50) | NO | - | 表名 |
| `sync_date` | VARCHAR(8) | NO | - | 同步日期 |
| `sync_type` | VARCHAR(20) | YES | - | 同步类型(full/incremental) |
| `start_time` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 开始时间 |
| `end_time` | TIMESTAMP | YES | - | 结束时间 |
| `rows_fetched` | INT | YES | - | 获取记录数 |
| `rows_inserted` | INT | YES | - | 插入记录数 |
| `rows_updated` | INT | YES | - | 更新记录数 |
| `status` | VARCHAR(20) | YES | - | 状态(success/failed) |
| `error_message` | TEXT | YES | - | 错误信息 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_etf_update_log_date | 普通 | sync_date | - |
| idx_etf_update_log_status | 普通 | status | - |
| idx_etf_update_log_table | 普通 | table_name | - |
| PRIMARY | 主键 | id | - |

## 建表语句

```sql
CREATE TABLE `etf_update_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `table_name` varchar(50) NOT NULL COMMENT '表名',
  `sync_date` varchar(8) NOT NULL COMMENT '同步日期',
  `sync_type` varchar(20) DEFAULT NULL COMMENT '同步类型(full/incremental)',
  `start_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
  `end_time` timestamp NULL DEFAULT NULL COMMENT '结束时间',
  `rows_fetched` int DEFAULT NULL COMMENT '获取记录数',
  `rows_inserted` int DEFAULT NULL COMMENT '插入记录数',
  `rows_updated` int DEFAULT NULL COMMENT '更新记录数',
  `status` varchar(20) DEFAULT NULL COMMENT '状态(success/failed)',
  `error_message` text COMMENT '错误信息',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_etf_update_log_table` (`table_name`),
  KEY `idx_etf_update_log_date` (`sync_date`),
  KEY `idx_etf_update_log_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETF更新日志表'
```
