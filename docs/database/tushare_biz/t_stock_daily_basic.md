# t_stock_daily_basic

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_daily_basic |
| 中文名 | 每日指标表 - 来自Tushare daily_basic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 14,431,161 行 |
| 数据大小 | 2.82 GB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `close` | DECIMAL(16,4) | YES | - | 当日收盘价 |
| `turnover_rate` | DECIMAL(10,4) | YES | - | 换手率(%) |
| `turnover_rate_f` | DECIMAL(10,4) | YES | - | 换手率(自由流通股) |
| `volume_ratio` | DECIMAL(10,4) | YES | - | 量比 |
| `pe` | DECIMAL(16,4) | YES | - | 市盈率(总市值/净利润) |
| `pe_ttm` | DECIMAL(16,4) | YES | - | 市盈率TTM |
| `pb` | DECIMAL(16,4) | YES | - | 市净率(总市值/净资产) |
| `ps` | DECIMAL(16,4) | YES | - | 市销率 |
| `ps_ttm` | DECIMAL(16,4) | YES | - | 市销率TTM |
| `dv_ratio` | DECIMAL(10,4) | YES | - | 股息率(%) |
| `dv_ttm` | DECIMAL(10,4) | YES | - | 股息率TTM(%) |
| `total_share` | DECIMAL(20,4) | YES | - | 总股本(万股) |
| `float_share` | DECIMAL(20,4) | YES | - | 流通股本(万股) |
| `free_share` | DECIMAL(20,4) | YES | - | 自由流通股本(万股) |
| `total_mv` | DECIMAL(20,4) | YES | - | 总市值(万元) |
| `circ_mv` | DECIMAL(20,4) | YES | - | 流通市值(万元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | close | turnover_rate | turnover_rate_f | volume_ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050104 | 6.5200 | 0.1249 | 0.1568 | 0.7300 |
| 000001.SZ | 20050105 | 6.4600 | 0.2286 | 0.2870 | 1.4500 |
| 000001.SZ | 20050106 | 6.5200 | 0.1892 | 0.2375 | 1.0700 |
| 000001.SZ | 20050107 | 6.5100 | 0.1338 | 0.1680 | 0.7200 |
| 000001.SZ | 20050110 | 6.5900 | 0.1868 | 0.2345 | 1.1700 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_daily_basic` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `close` decimal(16,4) DEFAULT NULL COMMENT '当日收盘价',
  `turnover_rate` decimal(10,4) DEFAULT NULL COMMENT '换手率(%)',
  `turnover_rate_f` decimal(10,4) DEFAULT NULL COMMENT '换手率(自由流通股)',
  `volume_ratio` decimal(10,4) DEFAULT NULL COMMENT '量比',
  `pe` decimal(16,4) DEFAULT NULL COMMENT '市盈率(总市值/净利润)',
  `pe_ttm` decimal(16,4) DEFAULT NULL COMMENT '市盈率TTM',
  `pb` decimal(16,4) DEFAULT NULL COMMENT '市净率(总市值/净资产)',
  `ps` decimal(16,4) DEFAULT NULL COMMENT '市销率',
  `ps_ttm` decimal(16,4) DEFAULT NULL COMMENT '市销率TTM',
  `dv_ratio` decimal(10,4) DEFAULT NULL COMMENT '股息率(%)',
  `dv_ttm` decimal(10,4) DEFAULT NULL COMMENT '股息率TTM(%)',
  `total_share` decimal(20,4) DEFAULT NULL COMMENT '总股本(万股)',
  `float_share` decimal(20,4) DEFAULT NULL COMMENT '流通股本(万股)',
  `free_share` decimal(20,4) DEFAULT NULL COMMENT '自由流通股本(万股)',
  `total_mv` decimal(20,4) DEFAULT NULL COMMENT '总市值(万元)',
  `circ_mv` decimal(20,4) DEFAULT NULL COMMENT '流通市值(万元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每日指标表 - 来自Tushare daily_basic'
```
