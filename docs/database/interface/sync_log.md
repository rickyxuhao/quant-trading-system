# sync_log

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | sync_log |
| 中文名 | 数据同步日志 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 40 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 64.00 KB |
| 创建时间 | 2026-03-06 13:51:48 |
| 更新时间 | 2026-03-13 09:00:18 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | BIGINT | NO | - |  |
| `task_name` | VARCHAR(100) | NO | - | 任务名称 |
| `table_name` | VARCHAR(100) | NO | - | 表名 |
| `sync_type` | VARCHAR(20) | YES | - | 同步类型：full/incremental |
| `start_time` | TIMESTAMP | NO | - | 开始时间 |
| `end_time` | TIMESTAMP | YES | - | 结束时间 |
| `duration_seconds` | INT | YES | - | 耗时秒数 |
| `status` | VARCHAR(20) | YES | - | 状态：success/failed/running |
| `rows_affected` | INT | YES | - | 影响行数 |
| `rows_inserted` | INT | YES | - | 插入行数 |
| `rows_updated` | INT | YES | - | 更新行数 |
| `error_message` | TEXT | YES | - | 错误信息 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_start_time | 普通 | start_time | - |
| idx_status | 普通 | status | - |
| idx_table_name | 普通 | table_name | - |
| idx_task_name | 普通 | task_name | - |
| PRIMARY | 主键 | id | - |

## 数据示例

| id | task_name | table_name | sync_type | start_time | end_time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | stock_basic | t_stock_basic | full | 2026-03-06 13:51:55 | 2026-03-06 13:51:56 |
| 2 | stock_basic | t_stock_basic | full | 2026-03-06 14:06:03 | 2026-03-06 14:06:04 |
| 3 | trade_date | t_tradedate | full | 2026-03-06 14:21:32 | 2026-03-06 14:21:33 |
| 4 | stock_daily_market_data | t_stock_dailymarketdata | incremental | 2026-03-06 15:43:17 | 2026-03-06 16:09:40 |
| 5 | stock_daily_market_data | t_stock_dailymarketdata | incremental | 2026-03-06 16:51:10 | 2026-03-06 17:09:23 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `sync_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_name` varchar(100) NOT NULL COMMENT '任务名称',
  `table_name` varchar(100) NOT NULL COMMENT '表名',
  `sync_type` varchar(20) DEFAULT NULL COMMENT '同步类型：full/incremental',
  `start_time` timestamp NOT NULL COMMENT '开始时间',
  `end_time` timestamp NULL DEFAULT NULL COMMENT '结束时间',
  `duration_seconds` int DEFAULT NULL COMMENT '耗时秒数',
  `status` varchar(20) DEFAULT NULL COMMENT '状态：success/failed/running',
  `rows_affected` int DEFAULT NULL COMMENT '影响行数',
  `rows_inserted` int DEFAULT NULL COMMENT '插入行数',
  `rows_updated` int DEFAULT NULL COMMENT '更新行数',
  `error_message` text COMMENT '错误信息',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_name` (`task_name`),
  KEY `idx_table_name` (`table_name`),
  KEY `idx_start_time` (`start_time`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='数据同步日志'
```
