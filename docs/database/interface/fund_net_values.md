# fund_net_values

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | fund_net_values |
| 中文名 | 基金净值表 |
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
| `code` | VARCHAR(20) | NO | - | 基金代码 |
| `name` | VARCHAR(50) | YES | - | 基金名称 |
| `date` | DATE | NO | - | 净值日期 |
| `nav` | DECIMAL(10,4) | YES | - | 单位净值 |
| `accumulated_nav` | DECIMAL(10,4) | YES | - | 累计净值 |
| `daily_return` | DECIMAL(8,4) | YES | - | 日涨跌幅 |
| `created_at` | DATETIME | YES | - | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| ix_fund_net_values_code | 普通 | code | - |
| PRIMARY | 主键 | id | - |
| uk_fund_date | 唯一 | code, date | - |

## 建表语句

```sql
CREATE TABLE `fund_net_values` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT '基金代码',
  `name` varchar(50) DEFAULT NULL COMMENT '基金名称',
  `date` date NOT NULL COMMENT '净值日期',
  `nav` decimal(10,4) DEFAULT NULL COMMENT '单位净值',
  `accumulated_nav` decimal(10,4) DEFAULT NULL COMMENT '累计净值',
  `daily_return` decimal(8,4) DEFAULT NULL COMMENT '日涨跌幅',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_fund_date` (`code`,`date`),
  KEY `ix_fund_net_values_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金净值表'
```
