# t_stock_tradedate

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_tradedate |
| 中文名 | 交易日历表 - 来自Tushare trade_cal |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 9,027 行 |
| 数据大小 | 1.52 MB |
| 索引大小 | 3.47 MB |
| 创建时间 | 2026-03-06 14:20:08 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `exchange` | VARCHAR(20) | NO | - | 交易所 SSE/SZSE |
| `cal_date` | VARCHAR(8) | NO | - | 日历日期 YYYYMMDD |
| `is_open` | TINYINT | YES | - | 是否交易日 0否 1是 |
| `pretrade_date` | VARCHAR(8) | YES | - | 上一个交易日 YYYYMMDD |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_cal_date | 普通 | cal_date | - |
| idx_is_open | 普通 | is_open | - |
| idx_pretrade_date | 普通 | pretrade_date | - |
| PRIMARY | 主键 | exchange, cal_date | - |

## 数据示例

| exchange | cal_date | is_open | pretrade_date | created_at | updated_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SSE | 20010101 | 0 | 20001229 | 2026-03-06 14:40:03 | 2026-03-06 14:40:03 |
| SSE | 20010102 | 1 | 20001229 | 2026-03-06 14:40:03 | 2026-03-06 14:40:03 |
| SSE | 20010103 | 1 | 20010102 | 2026-03-06 14:40:03 | 2026-03-06 14:40:03 |
| SSE | 20010104 | 1 | 20010103 | 2026-03-06 14:40:03 | 2026-03-06 14:40:03 |
| SSE | 20010105 | 1 | 20010104 | 2026-03-06 14:40:03 | 2026-03-06 14:40:03 |

## 建表语句

```sql
CREATE TABLE `t_stock_tradedate` (
  `exchange` varchar(20) NOT NULL COMMENT '交易所 SSE/SZSE',
  `cal_date` varchar(8) NOT NULL COMMENT '日历日期 YYYYMMDD',
  `is_open` tinyint(1) DEFAULT NULL COMMENT '是否交易日 0否 1是',
  `pretrade_date` varchar(8) DEFAULT NULL COMMENT '上一个交易日 YYYYMMDD',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`exchange`,`cal_date`),
  KEY `idx_cal_date` (`cal_date`),
  KEY `idx_is_open` (`is_open`),
  KEY `idx_pretrade_date` (`pretrade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='交易日历表 - 来自Tushare trade_cal'
```
