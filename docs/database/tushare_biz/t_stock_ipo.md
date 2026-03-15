# t_stock_ipo

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_ipo |
| 中文名 | IPO新股列表 - 来自Tushare new_share |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 1,986 行 |
| 数据大小 | 432.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `sub_code` | VARCHAR(20) | YES | - | 申购代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `ipo_date` | VARCHAR(8) | YES | - | 上网发行日期 |
| `issue_date` | VARCHAR(8) | YES | - | 上市日期 |
| `amount` | DECIMAL(20,4) | YES | - | 发行总量（万股） |
| `market_amount` | DECIMAL(20,4) | YES | - | 上网发行数量（万股） |
| `price` | DECIMAL(16,4) | YES | - | 发行价格 |
| `pe` | DECIMAL(16,4) | YES | - | 市盈率 |
| `limit_amount` | DECIMAL(16,4) | YES | - | 个人申购上限（万股） |
| `funds` | DECIMAL(20,4) | YES | - | 募集资金总额（亿元） |
| `ballot` | DECIMAL(10,4) | YES | - | 中签率(%) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | sub_code | name | ipo_date | issue_date | amount |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 001201.SZ | 001201 | 东瑞股份 | 20210414 | 20210428 | 3167.0000 |
| 001202.SZ | 001202 | 炬申股份 | 20210419 | 20210429 | 3224.0000 |
| 001203.SZ | 001203 | 大中矿业 | 20210420 | 20210510 | 21894.0000 |
| 001205.SZ | 001205 | 盛航股份 | 20210428 | 20210513 | 3007.0000 |
| 001206.SZ | 001206 | 依依股份 | 20210506 | 20210518 | 2358.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_ipo` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `sub_code` varchar(20) DEFAULT NULL COMMENT '申购代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `ipo_date` varchar(8) DEFAULT NULL COMMENT '上网发行日期',
  `issue_date` varchar(8) DEFAULT NULL COMMENT '上市日期',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '发行总量（万股）',
  `market_amount` decimal(20,4) DEFAULT NULL COMMENT '上网发行数量（万股）',
  `price` decimal(16,4) DEFAULT NULL COMMENT '发行价格',
  `pe` decimal(16,4) DEFAULT NULL COMMENT '市盈率',
  `limit_amount` decimal(16,4) DEFAULT NULL COMMENT '个人申购上限（万股）',
  `funds` decimal(20,4) DEFAULT NULL COMMENT '募集资金总额（亿元）',
  `ballot` decimal(10,4) DEFAULT NULL COMMENT '中签率(%)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='IPO新股列表 - 来自Tushare new_share'
```
