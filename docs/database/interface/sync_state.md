# sync_state

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | sync_state |
| 中文名 | 数据同步状态 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 6 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 32.00 KB |
| 创建时间 | 2026-03-06 13:51:48 |
| 更新时间 | 2026-03-13 09:00:18 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | BIGINT | NO | - |  |
| `task_name` | VARCHAR(100) | NO | - | 任务名称 |
| `table_name` | VARCHAR(100) | NO | - | 表名 |
| `last_sync_time` | TIMESTAMP | YES | - | 最后同步时间 |
| `last_sync_date` | VARCHAR(8) | YES | - | 最后同步日期YYYYMMDD |
| `last_success_time` | TIMESTAMP | YES | - | 最后成功时间 |
| `last_success_date` | VARCHAR(8) | YES | - | 最后成功日期 |
| `total_rows` | INT | YES | - | 当前表记录数 |
| `consecutive_failures` | INT | YES | 0 | 连续失败次数 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_table_name | 普通 | table_name | - |
| PRIMARY | 主键 | id | - |
| task_name | 唯一 | task_name | - |

## 数据示例

| id | task_name | table_name | last_sync_time | last_sync_date | last_success_time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | stock_basic | t_stock_basic | 2026-03-13 09:00:18 | 20260313 | 2026-03-12 09:00:04 |
| 2 | trade_date | t_tradedate | 2026-03-06 14:21:33 | 20260306 | 2026-03-06 14:21:33 |
| 3 | stock_daily_market_data | t_stock_dailymarketdata | 2026-03-12 16:41:14 | 20260312 | 2026-03-12 16:41:14 |
| 4 | stock_adj_factor | t_stock_adjfactor | 2026-03-06 23:05:28 | 20260306 | 2026-03-06 23:05:28 |
| 5 | stock_st_list | t_stock_st_list | 2026-03-12 16:41:21 | 20260312 | 2026-03-12 16:41:21 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `sync_state` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_name` varchar(100) NOT NULL COMMENT '任务名称',
  `table_name` varchar(100) NOT NULL COMMENT '表名',
  `last_sync_time` timestamp NULL DEFAULT NULL COMMENT '最后同步时间',
  `last_sync_date` varchar(8) DEFAULT NULL COMMENT '最后同步日期YYYYMMDD',
  `last_success_time` timestamp NULL DEFAULT NULL COMMENT '最后成功时间',
  `last_success_date` varchar(8) DEFAULT NULL COMMENT '最后成功日期',
  `total_rows` int DEFAULT NULL COMMENT '当前表记录数',
  `consecutive_failures` int DEFAULT '0' COMMENT '连续失败次数',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `task_name` (`task_name`),
  KEY `idx_table_name` (`table_name`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='数据同步状态'
```
