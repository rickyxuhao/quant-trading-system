# t_stock_dailylimitprice

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_dailylimitprice |
| 中文名 | 每日涨跌停价格表 - 来自Tushare limit_list |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 152,872 行 |
| 数据大小 | 35.59 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `close` | DECIMAL(16,4) | YES | - | 收盘价 |
| `pct_chg` | DECIMAL(10,4) | YES | - | 涨跌幅(%) |
| `amp` | DECIMAL(10,4) | YES | - | 振幅(%) |
| `up_limit` | DECIMAL(16,4) | YES | - | 涨停板价 |
| `down_limit` | DECIMAL(16,4) | YES | - | 跌停板价 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | name | close | pct_chg | amp |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20200203 | 平安银行 | 13.9900 | -9.9700 | 4.5700 |
| 000001.SZ | 20200706 | 平安银行 | 15.6800 | 10.0400 | 7.6500 |
| 000001.SZ | 20221129 | 平安银行 | 12.9900 | 9.9900 | 7.2800 |
| 000001.SZ | 20240221 | 平安银行 | 10.8000 | 9.9800 | 10.4888 |
| 000002.SZ | 20160704 | 万  科Ａ | 21.9900 | -9.9900 | 0.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_dailylimitprice` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `close` decimal(16,4) DEFAULT NULL COMMENT '收盘价',
  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
  `amp` decimal(10,4) DEFAULT NULL COMMENT '振幅(%)',
  `up_limit` decimal(16,4) DEFAULT NULL COMMENT '涨停板价',
  `down_limit` decimal(16,4) DEFAULT NULL COMMENT '跌停板价',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每日涨跌停价格表 - 来自Tushare limit_list'
```
