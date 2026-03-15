# sip_transactions

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | sip_transactions |
| 中文名 | 定投执行记录表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 16.00 KB |
| 创建时间 | 2026-03-12 10:32:09 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `plan_id` | INT | NO | - | 计划ID |
| `execute_date` | DATE | NO | - | 执行日期 |
| `nav` | DECIMAL(10,4) | YES | - | 当日净值 |
| `shares` | DECIMAL(12,4) | YES | - | 获得份额 |
| `amount` | DECIMAL(12,2) | YES | - | 投入金额 |
| `fee` | DECIMAL(10,2) | YES | - | 申购费 |
| `is_auto` | TINYINT | YES | - | 是否自动执行 |
| `status` | VARCHAR(20) | YES | - | 执行状态 |
| `created_at` | DATETIME | YES | - | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_plan_date | 普通 | plan_id, execute_date | - |
| PRIMARY | 主键 | id | - |

## 建表语句

```sql
CREATE TABLE `sip_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `plan_id` int NOT NULL COMMENT '计划ID',
  `execute_date` date NOT NULL COMMENT '执行日期',
  `nav` decimal(10,4) DEFAULT NULL COMMENT '当日净值',
  `shares` decimal(12,4) DEFAULT NULL COMMENT '获得份额',
  `amount` decimal(12,2) DEFAULT NULL COMMENT '投入金额',
  `fee` decimal(10,2) DEFAULT NULL COMMENT '申购费',
  `is_auto` tinyint(1) DEFAULT NULL COMMENT '是否自动执行',
  `status` varchar(20) DEFAULT NULL COMMENT '执行状态',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_plan_date` (`plan_id`,`execute_date`),
  CONSTRAINT `sip_transactions_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `sip_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='定投执行记录表'
```
