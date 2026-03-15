# t_stock_moneyflow

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_moneyflow |
| 中文名 | 个股资金流向表 - 来自Tushare moneyflow |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 13,162,705 行 |
| 数据大小 | 2.86 GB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `buy_sm_vol` | BIGINT | YES | - | 小单买入量(手) |
| `buy_sm_amount` | DECIMAL(20,4) | YES | - | 小单买入金额(万元) |
| `sell_sm_vol` | BIGINT | YES | - | 小单卖出量(手) |
| `sell_sm_amount` | DECIMAL(20,4) | YES | - | 小单卖出金额(万元) |
| `buy_md_vol` | BIGINT | YES | - | 中单买入量(手) |
| `buy_md_amount` | DECIMAL(20,4) | YES | - | 中单买入金额(万元) |
| `sell_md_vol` | BIGINT | YES | - | 中单卖出量(手) |
| `sell_md_amount` | DECIMAL(20,4) | YES | - | 中单卖出金额(万元) |
| `buy_lg_vol` | BIGINT | YES | - | 大单买入量(手) |
| `buy_lg_amount` | DECIMAL(20,4) | YES | - | 大单买入金额(万元) |
| `sell_lg_vol` | BIGINT | YES | - | 大单卖出量(手) |
| `sell_lg_amount` | DECIMAL(20,4) | YES | - | 大单卖出金额(万元) |
| `buy_elg_vol` | BIGINT | YES | - | 特大单买入量(手) |
| `buy_elg_amount` | DECIMAL(20,4) | YES | - | 特大单买入金额(万元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | trade_date | buy_sm_vol | buy_sm_amount | sell_sm_vol | sell_sm_amount |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20100105 | 128295 | 29814.7200 | 73093 | 17011.0200 |
| 000001.SZ | 20100106 | 106034 | 24285.3900 | 34725 | 7965.8400 |
| 000001.SZ | 20100107 | 90880 | 20566.1100 | 31746 | 7195.4700 |
| 000001.SZ | 20100108 | 64138 | 14455.6000 | 21515 | 4855.2600 |
| 000001.SZ | 20100111 | 98102 | 22318.3700 | 44191 | 10104.4100 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_moneyflow` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `buy_sm_vol` bigint DEFAULT NULL COMMENT '小单买入量(手)',
  `buy_sm_amount` decimal(20,4) DEFAULT NULL COMMENT '小单买入金额(万元)',
  `sell_sm_vol` bigint DEFAULT NULL COMMENT '小单卖出量(手)',
  `sell_sm_amount` decimal(20,4) DEFAULT NULL COMMENT '小单卖出金额(万元)',
  `buy_md_vol` bigint DEFAULT NULL COMMENT '中单买入量(手)',
  `buy_md_amount` decimal(20,4) DEFAULT NULL COMMENT '中单买入金额(万元)',
  `sell_md_vol` bigint DEFAULT NULL COMMENT '中单卖出量(手)',
  `sell_md_amount` decimal(20,4) DEFAULT NULL COMMENT '中单卖出金额(万元)',
  `buy_lg_vol` bigint DEFAULT NULL COMMENT '大单买入量(手)',
  `buy_lg_amount` decimal(20,4) DEFAULT NULL COMMENT '大单买入金额(万元)',
  `sell_lg_vol` bigint DEFAULT NULL COMMENT '大单卖出量(手)',
  `sell_lg_amount` decimal(20,4) DEFAULT NULL COMMENT '大单卖出金额(万元)',
  `buy_elg_vol` bigint DEFAULT NULL COMMENT '特大单买入量(手)',
  `buy_elg_amount` decimal(20,4) DEFAULT NULL COMMENT '特大单买入金额(万元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='个股资金流向表 - 来自Tushare moneyflow'
```
