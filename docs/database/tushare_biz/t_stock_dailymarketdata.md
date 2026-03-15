# t_stock_dailymarketdata

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_dailymarketdata |
| 中文名 | 股票日线行情表 - 来自Tushare daily |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 14,531,714 行 |
| 数据大小 | 2.23 GB |
| 索引大小 | 2.28 GB |
| 创建时间 | 2026-03-06 21:07:48 |
| 更新时间 | 2026-03-12 16:30:05 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 YYYYMMDD |
| `open` | DECIMAL(16,4) | YES | - | 开盘价 |
| `high` | DECIMAL(16,4) | YES | - | 最高价 |
| `low` | DECIMAL(16,4) | YES | - | 最低价 |
| `close` | DECIMAL(16,4) | YES | - | 收盘价 |
| `pre_close` | DECIMAL(16,4) | YES | - | 昨收价 |
| `t_change` | DECIMAL(16,4) | YES | - |  |
| `pct_chg` | DECIMAL(10,4) | YES | - | 涨跌幅(%) |
| `vol` | BIGINT | YES | - | 成交量(手) |
| `amount` | DECIMAL(20,4) | YES | - | 成交额(千元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_amount | 普通 | amount | - |
| idx_trade_date | 普通 | trade_date | - |
| idx_vol | 普通 | vol | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | open | high | low | close |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050104 | 6.5900 | 6.5900 | 6.4600 | 6.5200 |
| 000001.SZ | 20050105 | 6.5200 | 6.5500 | 6.3500 | 6.4600 |
| 000001.SZ | 20050106 | 6.5000 | 6.5900 | 6.4500 | 6.5200 |
| 000001.SZ | 20050107 | 6.5800 | 6.6000 | 6.4600 | 6.5100 |
| 000001.SZ | 20050110 | 6.5100 | 6.5900 | 6.3700 | 6.5900 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_dailymarketdata` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
  `open` decimal(16,4) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(16,4) DEFAULT NULL COMMENT '最高价',
  `low` decimal(16,4) DEFAULT NULL COMMENT '最低价',
  `close` decimal(16,4) DEFAULT NULL COMMENT '收盘价',
  `pre_close` decimal(16,4) DEFAULT NULL COMMENT '昨收价',
  `t_change` decimal(16,4) DEFAULT NULL,
  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
  `vol` bigint DEFAULT NULL COMMENT '成交量(手)',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额(千元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_trade_date` (`trade_date`),
  KEY `idx_vol` (`vol`),
  KEY `idx_amount` (`amount`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票日线行情表 - 来自Tushare daily'
```
