# t_stock_st_list

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_st_list |
| 中文名 | ST股票列表表 - 来自Tushare stock_st |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 347,723 行 |
| 数据大小 | 52.66 MB |
| 索引大小 | 48.67 MB |
| 创建时间 | 2026-03-06 15:05:23 |
| 更新时间 | 2026-03-12 16:41:15 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | 股票代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 YYYYMMDD |
| `type` | VARCHAR(20) | YES | - | 类型 |
| `type_name` | VARCHAR(50) | YES | - | 类型名称 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_trade_date | 普通 | trade_date | - |
| idx_ts_code | 普通 | ts_code | - |
| idx_type | 普通 | type | - |
| PRIMARY | 主键 | ts_code, trade_date | - |

## 数据示例

| ts_code | name | trade_date | type | type_name | created_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000004.SZ | ST国华 | 20220506 | ST | 风险警示板 | 2026-03-06 15:22:56 |
| 000004.SZ | ST国华 | 20220509 | ST | 风险警示板 | 2026-03-06 15:22:56 |
| 000004.SZ | ST国华 | 20220510 | ST | 风险警示板 | 2026-03-06 15:22:56 |
| 000004.SZ | ST国华 | 20220511 | ST | 风险警示板 | 2026-03-06 15:22:56 |
| 000004.SZ | ST国华 | 20220512 | ST | 风险警示板 | 2026-03-06 15:22:56 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_st_list` (
  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
  `type` varchar(20) DEFAULT NULL COMMENT '类型',
  `type_name` varchar(50) DEFAULT NULL COMMENT '类型名称',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `idx_ts_code` (`ts_code`),
  KEY `idx_trade_date` (`trade_date`),
  KEY `idx_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ST股票列表表 - 来自Tushare stock_st'
```
