# t_stock_dividend

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_dividend |
| 中文名 | 分红送股表 - 来自Tushare dividend |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 88,062 行 |
| 数据大小 | 11.53 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `end_date` | VARCHAR(8) | NO | - | 分红年度 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `div_proc` | VARCHAR(50) | YES | - | 实施进度 |
| `stk_div` | DECIMAL(10,4) | YES | - | 每股送转 |
| `stk_bo_rate` | DECIMAL(10,4) | YES | - |  |
| `stk_co_rate` | DECIMAL(10,4) | YES | - |  |
| `cash_div` | DECIMAL(10,4) | YES | - | 每股分红（税后） |
| `cash_div_tax` | DECIMAL(10,4) | YES | - | 每股分红（税前） |
| `record_date` | VARCHAR(8) | YES | - | 股权登记日 |
| `ex_date` | VARCHAR(8) | YES | - | 除权除息日 |
| `pay_date` | VARCHAR(8) | YES | - | 派息日 |
| `div_listdate` | VARCHAR(8) | YES | - | 红股上市日 |
| `imp_ann_date` | VARCHAR(8) | YES | - |  |
| `base_date` | VARCHAR(8) | YES | - |  |
| `base_share` | DECIMAL(20,4) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | end_date | ann_date | div_proc | stk_div | stk_bo_rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20070615 | 20070524 | 实施 | 0.1000 | 0.1000 |
| 000001.SZ | 20080630 | 20080926 | 实施 | 0.3000 | 0.3000 |
| 000001.SZ | 20120630 | 20120816 | 实施 | 0.0000 | NULL |
| 000001.SZ | 20121231 | 20130308 | 实施 | 0.6000 | 0.6000 |
| 000001.SZ | 20131231 | 20140307 | 实施 | 0.2000 | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_dividend` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `end_date` varchar(8) NOT NULL COMMENT '分红年度',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `div_proc` varchar(50) DEFAULT NULL COMMENT '实施进度',
  `stk_div` decimal(10,4) DEFAULT NULL COMMENT '每股送转',
  `stk_bo_rate` decimal(10,4) DEFAULT NULL,
  `stk_co_rate` decimal(10,4) DEFAULT NULL,
  `cash_div` decimal(10,4) DEFAULT NULL COMMENT '每股分红（税后）',
  `cash_div_tax` decimal(10,4) DEFAULT NULL COMMENT '每股分红（税前）',
  `record_date` varchar(8) DEFAULT NULL COMMENT '股权登记日',
  `ex_date` varchar(8) DEFAULT NULL COMMENT '除权除息日',
  `pay_date` varchar(8) DEFAULT NULL COMMENT '派息日',
  `div_listdate` varchar(8) DEFAULT NULL COMMENT '红股上市日',
  `imp_ann_date` varchar(8) DEFAULT NULL,
  `base_date` varchar(8) DEFAULT NULL,
  `base_share` decimal(20,4) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='分红送股表 - 来自Tushare dividend'
```
