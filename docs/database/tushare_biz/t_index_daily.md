# t_index_daily

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_index_daily |
| 中文名 | 指数日线行情表 - 来自Tushare index_daily |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 6,472 行 |
| 数据大小 | 1.52 MB |
| 索引大小 | 432.00 KB |
| 创建时间 | 2026-03-08 12:41:35 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS指数代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日 |
| `open` | DECIMAL(10,4) | YES | - | 开盘点位 |
| `high` | DECIMAL(10,4) | YES | - | 最高点位 |
| `low` | DECIMAL(10,4) | YES | - | 最低点位 |
| `close` | DECIMAL(10,4) | YES | - | 收盘点位 |
| `pre_close` | DECIMAL(10,4) | YES | - | 昨日收盘 |
| `chng` | DECIMAL(10,4) | YES | - | 涨跌点位 |
| `pct_chg` | DECIMAL(10,4) | YES | - | 涨跌幅(%) |
| `vol` | DECIMAL(20,4) | YES | - | 成交量(手) |
| `amount` | DECIMAL(20,4) | YES | - | 成交额(千元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_index_daily_trade_date | 普通 | trade_date | - |
| idx_index_daily_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | open | high | low | close |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SH | 20050104 | 1260.7820 | 1260.7820 | 1238.1790 | 1242.7740 |
| 000001.SH | 20050105 | 1241.6820 | 1258.5800 | 1235.7460 | 1251.9370 |
| 000001.SH | 20050106 | 1252.4930 | 1252.7350 | 1234.2360 | 1239.4300 |
| 000001.SH | 20050107 | 1239.3230 | 1256.3130 | 1235.5080 | 1244.7460 |
| 000001.SH | 20050110 | 1243.5760 | 1252.7230 | 1236.0890 | 1252.4010 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_index_daily` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS指数代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日',
  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘点位',
  `high` decimal(10,4) DEFAULT NULL COMMENT '最高点位',
  `low` decimal(10,4) DEFAULT NULL COMMENT '最低点位',
  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘点位',
  `pre_close` decimal(10,4) DEFAULT NULL COMMENT '昨日收盘',
  `chng` decimal(10,4) DEFAULT NULL COMMENT '涨跌点位',
  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
  `vol` decimal(20,4) DEFAULT NULL COMMENT '成交量(手)',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额(千元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_index_daily_trade_date` (`trade_date`),
  KEY `idx_index_daily_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指数日线行情表 - 来自Tushare index_daily'
```
