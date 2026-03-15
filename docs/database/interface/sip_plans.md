# sip_plans

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | sip_plans |
| 中文名 | 定投计划表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-12 13:34:48 |
| 更新时间 | 2026-03-13 10:46:08 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `code` | VARCHAR(20) | NO | - | 基金代码 |
| `name` | VARCHAR(50) | YES | - | 基金名称 |
| `asset_type` | ENUM | YES | - | 资产类型 |
| `cycle` | VARCHAR(20) | NO | - |  |
| `cycle_day` | INT | YES | - | 定投日（周几/每月几号） |
| `fixed_amount` | DECIMAL(12,2) | YES | - | 每期金额 |
| `start_date` | DATE | YES | - | 开始日期 |
| `end_date` | DATE | YES | - | 结束日期（可选） |
| `is_active` | TINYINT | YES | - | 是否进行中 |
| `total_invested` | DECIMAL(15,2) | YES | - | 累计投入 |
| `total_shares` | DECIMAL(12,4) | YES | - | 累计份额 |
| `notes` | TEXT | YES | - | 备注 |
| `created_at` | DATETIME | YES | - | 创建时间 |
| `updated_at` | DATETIME | YES | - | 更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | id | - |

## 数据示例

| id | code | name | asset_type | cycle | cycle_day |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 016665 | 天弘全球高端制造混合(QDII)C | FUND_OE | DAILY | NULL |
| 2 | 008764 | 天弘越南市场股票(QDII)C | FUND_OE | DAILY | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `sip_plans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT '基金代码',
  `name` varchar(50) DEFAULT NULL COMMENT '基金名称',
  `asset_type` enum('STOCK','FUND_ETF','FUND_LOF','FUND_OE','BOND','CASH') DEFAULT NULL COMMENT '资产类型',
  `cycle` varchar(20) NOT NULL,
  `cycle_day` int DEFAULT NULL COMMENT '定投日（周几/每月几号）',
  `fixed_amount` decimal(12,2) DEFAULT NULL COMMENT '每期金额',
  `start_date` date DEFAULT NULL COMMENT '开始日期',
  `end_date` date DEFAULT NULL COMMENT '结束日期（可选）',
  `is_active` tinyint(1) DEFAULT NULL COMMENT '是否进行中',
  `total_invested` decimal(15,2) DEFAULT NULL COMMENT '累计投入',
  `total_shares` decimal(12,4) DEFAULT NULL COMMENT '累计份额',
  `notes` text COMMENT '备注',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_at` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='定投计划表'
```
