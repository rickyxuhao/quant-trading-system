# t_stock_hs_const

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_hs_const |
| 中文名 | 沪深股通成分股表 - 来自Tushare hs_const |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 823 行 |
| 数据大小 | 80.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `hs_type` | VARCHAR(10) | NO | - | 沪深港通类型 SH沪股通 SZ深股通 |
| `in_date` | VARCHAR(8) | YES | - | 纳入日期 |
| `out_date` | VARCHAR(8) | YES | - | 剔除日期 |
| `is_new` | INT | YES | - | 是否最新 1是 0否 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, hs_type | - |

## 数据示例

| ts_code | hs_type | in_date | out_date | is_new | created_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000016.SZ | SZ | 20180102 | NULL | 1 | 2026-03-07 12:31:00 |
| 000019.SZ | SZ | 20190617 | NULL | 1 | 2026-03-07 12:31:00 |
| 000025.SZ | SZ | 20170703 | NULL | 1 | 2026-03-07 12:31:00 |
| 000040.SZ | SZ | 20180102 | NULL | 1 | 2026-03-07 12:31:00 |
| 000049.SZ | SZ | 20190617 | NULL | 1 | 2026-03-07 12:31:00 |

## 建表语句

```sql
CREATE TABLE `t_stock_hs_const` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `hs_type` varchar(10) NOT NULL COMMENT '沪深港通类型 SH沪股通 SZ深股通',
  `in_date` varchar(8) DEFAULT NULL COMMENT '纳入日期',
  `out_date` varchar(8) DEFAULT NULL COMMENT '剔除日期',
  `is_new` int DEFAULT NULL COMMENT '是否最新 1是 0否',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`hs_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='沪深股通成分股表 - 来自Tushare hs_const'
```
