# position_history

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | position_history |
| 中文名 | 历史持仓记录 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 5 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 48.00 KB |
| 创建时间 | 2026-03-12 10:32:09 |
| 更新时间 | 2026-03-13 11:21:08 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `date` | DATE | NO | - | 日期 |
| `code` | VARCHAR(20) | NO | - | 股票代码 |
| `name` | VARCHAR(50) | YES | - | 股票名称 |
| `volume` | INT | YES | - | 持股数量 |
| `cost_price` | DECIMAL(12,4) | YES | - | 成本价 |
| `close_price` | DECIMAL(12,4) | YES | - | 当日收盘价 |
| `market_value` | DECIMAL(15,2) | YES | - | 市值 |
| `pnl` | DECIMAL(15,2) | YES | - | 累计盈亏 |
| `pnl_pct` | DECIMAL(10,6) | YES | - | 盈亏比例 |
| `weight` | DECIMAL(8,6) | YES | - | 权重 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_date | 普通 | date | - |
| ix_position_history_date | 普通 | date | - |
| PRIMARY | 主键 | id | - |
| uk_date_code | 唯一 | date, code | - |

## 数据示例

| id | date | code | name | volume | cost_price |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 2026-03-12 | 000708.SZ | 中信特钢 | 600 | 17.4180 |
| 2 | 2026-03-12 | 002195.SZ | 岩山科技 | 1400 | 10.3640 |
| 3 | 2026-03-12 | 002364.SZ | 中恒电气 | 400 | 38.1540 |
| 4 | 2026-03-12 | 300750.SZ | 宁德时代 | 100 | 394.2310 |
| 5 | 2026-03-12 | 300970.SZ | 华绿生物 | 300 | 25.5770 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `position_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL COMMENT '日期',
  `code` varchar(20) NOT NULL COMMENT '股票代码',
  `name` varchar(50) DEFAULT NULL COMMENT '股票名称',
  `volume` int DEFAULT NULL COMMENT '持股数量',
  `cost_price` decimal(12,4) DEFAULT NULL COMMENT '成本价',
  `close_price` decimal(12,4) DEFAULT NULL COMMENT '当日收盘价',
  `market_value` decimal(15,2) DEFAULT NULL COMMENT '市值',
  `pnl` decimal(15,2) DEFAULT NULL COMMENT '累计盈亏',
  `pnl_pct` decimal(10,6) DEFAULT NULL COMMENT '盈亏比例',
  `weight` decimal(8,6) DEFAULT NULL COMMENT '权重',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_date_code` (`date`,`code`),
  KEY `idx_date` (`date`),
  KEY `ix_position_history_date` (`date`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='历史持仓记录'
```
