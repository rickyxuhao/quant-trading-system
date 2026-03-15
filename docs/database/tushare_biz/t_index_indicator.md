# t_index_indicator

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_index_indicator |
| 中文名 | 大盘指数每日指标表 - 来自Tushare index_dailybasic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 56,043 行 |
| 数据大小 | 8.52 MB |
| 索引大小 | 5.03 MB |
| 创建时间 | 2026-03-08 12:41:35 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS指数代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日 |
| `total_mv` | DECIMAL(20,4) | YES | - | 当日总市值(元) |
| `float_mv` | DECIMAL(20,4) | YES | - | 当日流通市值(元) |
| `total_share` | DECIMAL(20,4) | YES | - | 当日总股本(股) |
| `float_share` | DECIMAL(20,4) | YES | - | 当日流通股本(股) |
| `free_share` | DECIMAL(20,4) | YES | - | 当日自由流通股本(股) |
| `turnover_rate` | DECIMAL(10,4) | YES | - | 换手率(%) |
| `turnover_rate_f` | DECIMAL(10,4) | YES | - | 换手率(自由流通)(%) |
| `pe` | DECIMAL(10,4) | YES | - | 市盈率 |
| `pe_ttm` | DECIMAL(10,4) | YES | - | 市盈率TTM |
| `pb` | DECIMAL(10,4) | YES | - | 市净率 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_index_indicator_trade_date | 普通 | trade_date | - |
| idx_index_indicator_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | total_mv | float_mv | total_share | float_share |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SH | 20050104 | 2778648940501.0000 | 700571878598.0000 | 509585541152.0000 | 128523439786.0000 |
| 000001.SH | 20050105 | 2796570049861.0000 | 708913076004.0000 | 509593415749.0000 | 128531314383.0000 |
| 000001.SH | 20050106 | 2768656405153.0000 | 703535918671.0000 | 509697182792.0000 | 128635081426.0000 |
| 000001.SH | 20050107 | 2780700363655.0000 | 705473594629.0000 | 509697182792.0000 | 128635081426.0000 |
| 000001.SH | 20050110 | 2795547199334.0000 | 711684206675.0000 | 509410543352.0000 | 128530366426.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_index_indicator` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS指数代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日',
  `total_mv` decimal(20,4) DEFAULT NULL COMMENT '当日总市值(元)',
  `float_mv` decimal(20,4) DEFAULT NULL COMMENT '当日流通市值(元)',
  `total_share` decimal(20,4) DEFAULT NULL COMMENT '当日总股本(股)',
  `float_share` decimal(20,4) DEFAULT NULL COMMENT '当日流通股本(股)',
  `free_share` decimal(20,4) DEFAULT NULL COMMENT '当日自由流通股本(股)',
  `turnover_rate` decimal(10,4) DEFAULT NULL COMMENT '换手率(%)',
  `turnover_rate_f` decimal(10,4) DEFAULT NULL COMMENT '换手率(自由流通)(%)',
  `pe` decimal(10,4) DEFAULT NULL COMMENT '市盈率',
  `pe_ttm` decimal(10,4) DEFAULT NULL COMMENT '市盈率TTM',
  `pb` decimal(10,4) DEFAULT NULL COMMENT '市净率',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_index_indicator_trade_date` (`trade_date`),
  KEY `idx_index_indicator_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='大盘指数每日指标表 - 来自Tushare index_dailybasic'
```
