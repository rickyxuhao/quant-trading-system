# t_stock_technical

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_technical |
| 中文名 | 股票技术指标表 - 基于日线行情计算 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 16:27:32 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS股票代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `ma5` | DECIMAL(10,4) | YES | - | 5日均线 |
| `ma10` | DECIMAL(10,4) | YES | - | 10日均线 |
| `ma20` | DECIMAL(10,4) | YES | - | 20日均线 |
| `ma60` | DECIMAL(10,4) | YES | - | 60日均线 |
| `ma120` | DECIMAL(10,4) | YES | - | 120日均线 |
| `ma250` | DECIMAL(10,4) | YES | - | 250日均线(年线) |
| `macd_dif` | DECIMAL(10,4) | YES | - | MACD DIF |
| `macd_dea` | DECIMAL(10,4) | YES | - | MACD DEA |
| `macd_bar` | DECIMAL(10,4) | YES | - | MACD BAR(柱状线) |
| `kdj_k` | DECIMAL(10,4) | YES | - | KDJ K值 |
| `kdj_d` | DECIMAL(10,4) | YES | - | KDJ D值 |
| `kdj_j` | DECIMAL(10,4) | YES | - | KDJ J值 |
| `rsi6` | DECIMAL(10,4) | YES | - | RSI6 |
| `rsi12` | DECIMAL(10,4) | YES | - | RSI12 |
| `rsi24` | DECIMAL(10,4) | YES | - | RSI24 |
| `boll_upper` | DECIMAL(10,4) | YES | - | 布林带上轨 |
| `boll_mid` | DECIMAL(10,4) | YES | - | 布林带中轨 |
| `boll_lower` | DECIMAL(10,4) | YES | - | 布林带下轨 |
| `vol_ma5` | DECIMAL(20,4) | YES | - | 成交量5日均值 |
| `vol_ma10` | DECIMAL(20,4) | YES | - | 成交量10日均值 |
| `vol_ma20` | DECIMAL(20,4) | YES | - | 成交量20日均值 |
| `amplitude` | DECIMAL(10,4) | YES | - | 振幅(%) |
| `volatility_20` | DECIMAL(10,4) | YES | - | 20日波动率 |
| `price_vol_corr` | DECIMAL(10,4) | YES | - | 价量相关系数(10日) |
| `trend_strength` | DECIMAL(10,4) | YES | - | 趋势强度(收盘价与均线偏离度) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_technical_kdj | 普通 | kdj_j | - |
| idx_technical_ma5 | 普通 | ma5 | - |
| idx_technical_macd | 普通 | macd_bar | - |
| idx_technical_rsi | 普通 | rsi6 | - |
| idx_technical_trade_date | 普通 | trade_date | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 建表语句

```sql
CREATE TABLE `t_stock_technical` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS股票代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `ma5` decimal(10,4) DEFAULT NULL COMMENT '5日均线',
  `ma10` decimal(10,4) DEFAULT NULL COMMENT '10日均线',
  `ma20` decimal(10,4) DEFAULT NULL COMMENT '20日均线',
  `ma60` decimal(10,4) DEFAULT NULL COMMENT '60日均线',
  `ma120` decimal(10,4) DEFAULT NULL COMMENT '120日均线',
  `ma250` decimal(10,4) DEFAULT NULL COMMENT '250日均线(年线)',
  `macd_dif` decimal(10,4) DEFAULT NULL COMMENT 'MACD DIF',
  `macd_dea` decimal(10,4) DEFAULT NULL COMMENT 'MACD DEA',
  `macd_bar` decimal(10,4) DEFAULT NULL COMMENT 'MACD BAR(柱状线)',
  `kdj_k` decimal(10,4) DEFAULT NULL COMMENT 'KDJ K值',
  `kdj_d` decimal(10,4) DEFAULT NULL COMMENT 'KDJ D值',
  `kdj_j` decimal(10,4) DEFAULT NULL COMMENT 'KDJ J值',
  `rsi6` decimal(10,4) DEFAULT NULL COMMENT 'RSI6',
  `rsi12` decimal(10,4) DEFAULT NULL COMMENT 'RSI12',
  `rsi24` decimal(10,4) DEFAULT NULL COMMENT 'RSI24',
  `boll_upper` decimal(10,4) DEFAULT NULL COMMENT '布林带上轨',
  `boll_mid` decimal(10,4) DEFAULT NULL COMMENT '布林带中轨',
  `boll_lower` decimal(10,4) DEFAULT NULL COMMENT '布林带下轨',
  `vol_ma5` decimal(20,4) DEFAULT NULL COMMENT '成交量5日均值',
  `vol_ma10` decimal(20,4) DEFAULT NULL COMMENT '成交量10日均值',
  `vol_ma20` decimal(20,4) DEFAULT NULL COMMENT '成交量20日均值',
  `amplitude` decimal(10,4) DEFAULT NULL COMMENT '振幅(%)',
  `volatility_20` decimal(10,4) DEFAULT NULL COMMENT '20日波动率',
  `price_vol_corr` decimal(10,4) DEFAULT NULL COMMENT '价量相关系数(10日)',
  `trend_strength` decimal(10,4) DEFAULT NULL COMMENT '趋势强度(收盘价与均线偏离度)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_technical_trade_date` (`trade_date`),
  KEY `idx_technical_ma5` (`ma5`),
  KEY `idx_technical_macd` (`macd_bar`),
  KEY `idx_technical_kdj` (`kdj_j`),
  KEY `idx_technical_rsi` (`rsi6`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票技术指标表 - 基于日线行情计算'
```
