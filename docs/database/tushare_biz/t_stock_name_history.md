# t_stock_name_history

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_name_history |
| 中文名 | 股票曾用名表 - 来自Tushare namechange |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 6,219 行 |
| 数据大小 | 1.48 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 证券名称 |
| `start_date` | VARCHAR(8) | NO | - | 开始日期 |
| `end_date` | VARCHAR(8) | YES | - | 结束日期 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, start_date | - |

## 数据示例

| ts_code | name | start_date | end_date | ann_date | created_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000004.SZ | 国华网安 | 20201201 | 20220505 | 20201201 | 2026-03-07 12:27:43 |
| 000004.SZ | ST国华 | 20220506 | 20230627 | 20220430 | 2026-03-07 12:27:42 |
| 000004.SZ | 国华网安 | 20230628 | NULL | 20230627 | 2026-03-07 12:27:42 |
| 000004.SZ | *ST国华 | 20250430 | NULL | 20250429 | 2026-03-07 12:27:42 |
| 000005.SZ | ST星源 | 20210506 | NULL | 20210430 | 2026-03-07 12:27:42 |

## 建表语句

```sql
CREATE TABLE `t_stock_name_history` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '证券名称',
  `start_date` varchar(8) NOT NULL COMMENT '开始日期',
  `end_date` varchar(8) DEFAULT NULL COMMENT '结束日期',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`start_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票曾用名表 - 来自Tushare namechange'
```
