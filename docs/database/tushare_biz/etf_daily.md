# etf_daily

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | etf_daily |
| 中文名 | ETF日线行情表 - 来自Tushare fund_daily |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2,721,215 行 |
| 数据大小 | 364.00 MB |
| 索引大小 | 209.47 MB |
| 创建时间 | 2026-03-08 09:16:09 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `open` | DECIMAL(10,4) | YES | - | 开盘价 |
| `high` | DECIMAL(10,4) | YES | - | 最高价 |
| `low` | DECIMAL(10,4) | YES | - | 最低价 |
| `close` | DECIMAL(10,4) | YES | - | 收盘价 |
| `pre_close` | DECIMAL(10,4) | YES | - | 昨收价 |
| `chng` | DECIMAL(10,4) | YES | - | 涨跌额 |
| `pct_chg` | DECIMAL(10,4) | YES | - | 涨跌幅(%) |
| `vol` | DECIMAL(20,4) | YES | - | 成交量(万手) |
| `amount` | DECIMAL(20,4) | YES | - | 成交额(万元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_etf_daily_trade_date | 普通 | trade_date | - |
| idx_etf_daily_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | open | high | low | close |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 150001.SZ | 20100104 | 0.9500 | 0.9530 | 0.9300 | 0.9300 |
| 150001.SZ | 20100105 | 0.9310 | 0.9510 | 0.9110 | 0.9420 |
| 150001.SZ | 20100106 | 0.9380 | 0.9480 | 0.9240 | 0.9250 |
| 150001.SZ | 20100107 | 0.9220 | 0.9260 | 0.9030 | 0.9100 |
| 150001.SZ | 20100108 | 0.9050 | 0.9210 | 0.8880 | 0.9200 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `etf_daily` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(10,4) DEFAULT NULL COMMENT '最高价',
  `low` decimal(10,4) DEFAULT NULL COMMENT '最低价',
  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘价',
  `pre_close` decimal(10,4) DEFAULT NULL COMMENT '昨收价',
  `chng` decimal(10,4) DEFAULT NULL COMMENT '涨跌额',
  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
  `vol` decimal(20,4) DEFAULT NULL COMMENT '成交量(万手)',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额(万元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_etf_daily_trade_date` (`trade_date`),
  KEY `idx_etf_daily_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETF日线行情表 - 来自Tushare fund_daily'
```
