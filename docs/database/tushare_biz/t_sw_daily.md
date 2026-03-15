# t_sw_daily

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_sw_daily |
| 中文名 | 申万行业指数日行情表 - 来自Tushare sw_daily |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 1,953,463 行 |
| 数据大小 | 325.00 MB |
| 索引大小 | 142.34 MB |
| 创建时间 | 2026-03-08 12:41:35 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | 行业代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `name` | VARCHAR(100) | YES | - | 行业名称 |
| `open` | DECIMAL(10,4) | YES | - | 开盘指数 |
| `low` | DECIMAL(10,4) | YES | - | 最低指数 |
| `high` | DECIMAL(10,4) | YES | - | 最高指数 |
| `close` | DECIMAL(10,4) | YES | - | 收盘指数 |
| `chng` | DECIMAL(10,4) | YES | - | 涨跌点位 |
| `pct_chg` | DECIMAL(10,4) | YES | - | 涨跌幅(%) |
| `vol` | DECIMAL(20,4) | YES | - | 成交量(手) |
| `amount` | DECIMAL(20,4) | YES | - | 成交额(千元) |
| `pe` | DECIMAL(10,4) | YES | - | 市盈率 |
| `pb` | DECIMAL(10,4) | YES | - | 市净率 |
| `float_mv` | DECIMAL(20,4) | YES | - | 流通市值(元) |
| `total_mv` | DECIMAL(20,4) | YES | - | 总市值(元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_sw_daily_trade_date | 普通 | trade_date | - |
| idx_sw_daily_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | name | open | low | high |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 801001.SI | 20120801 | 申万50 | 1665.6800 | 1665.6800 | 1687.7000 |
| 801001.SI | 20120802 | 申万50 | 1676.8100 | 1658.0000 | 1679.4200 |
| 801001.SI | 20120803 | 申万50 | 1668.2700 | 1657.2600 | 1672.2500 |
| 801001.SI | 20120806 | 申万50 | 1670.0900 | 1669.4600 | 1694.7500 |
| 801001.SI | 20120807 | 申万50 | 1691.1700 | 1686.6100 | 1694.6300 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_sw_daily` (
  `ts_code` varchar(20) NOT NULL COMMENT '行业代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `name` varchar(100) DEFAULT NULL COMMENT '行业名称',
  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘指数',
  `low` decimal(10,4) DEFAULT NULL COMMENT '最低指数',
  `high` decimal(10,4) DEFAULT NULL COMMENT '最高指数',
  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘指数',
  `chng` decimal(10,4) DEFAULT NULL COMMENT '涨跌点位',
  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
  `vol` decimal(20,4) DEFAULT NULL COMMENT '成交量(手)',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额(千元)',
  `pe` decimal(10,4) DEFAULT NULL COMMENT '市盈率',
  `pb` decimal(10,4) DEFAULT NULL COMMENT '市净率',
  `float_mv` decimal(20,4) DEFAULT NULL COMMENT '流通市值(元)',
  `total_mv` decimal(20,4) DEFAULT NULL COMMENT '总市值(元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_sw_daily_trade_date` (`trade_date`),
  KEY `idx_sw_daily_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='申万行业指数日行情表 - 来自Tushare sw_daily'
```
