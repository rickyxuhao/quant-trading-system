# portfolio_snapshots

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | portfolio_snapshots |
| 中文名 | 每日净值快照 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 16.00 KB |
| 创建时间 | 2026-03-12 10:32:09 |
| 更新时间 | 2026-03-13 11:21:55 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `date` | DATE | NO | - | 日期 |
| `total_asset` | DECIMAL(15,2) | YES | - | 总资产 |
| `cash` | DECIMAL(15,2) | YES | - | 现金余额 |
| `market_value` | DECIMAL(15,2) | YES | - | 股票市值 |
| `net_value` | DECIMAL(12,6) | YES | - | 单位净值 |
| `daily_return` | DECIMAL(10,6) | YES | - | 日收益率 |
| `cumulative_return` | DECIMAL(10,6) | YES | - | 累计收益率 |
| `benchmark_return` | DECIMAL(10,6) | YES | - | 基准日收益率 |
| `notes` | TEXT | YES | - | 备注 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| ix_portfolio_snapshots_date | 唯一 | date | - |
| PRIMARY | 主键 | id | - |

## 数据示例

| id | date | total_asset | cash | market_value | net_value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 2026-03-13 | 0.00 | 0.00 | 0.00 | 1.000000 |
| 2 | 2026-03-12 | 86107.00 | 0.00 | 86107.00 | 1.000000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `portfolio_snapshots` (
  `id` int NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL COMMENT '日期',
  `total_asset` decimal(15,2) DEFAULT NULL COMMENT '总资产',
  `cash` decimal(15,2) DEFAULT NULL COMMENT '现金余额',
  `market_value` decimal(15,2) DEFAULT NULL COMMENT '股票市值',
  `net_value` decimal(12,6) DEFAULT NULL COMMENT '单位净值',
  `daily_return` decimal(10,6) DEFAULT NULL COMMENT '日收益率',
  `cumulative_return` decimal(10,6) DEFAULT NULL COMMENT '累计收益率',
  `benchmark_return` decimal(10,6) DEFAULT NULL COMMENT '基准日收益率',
  `notes` text COMMENT '备注',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_portfolio_snapshots_date` (`date`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每日净值快照'
```
