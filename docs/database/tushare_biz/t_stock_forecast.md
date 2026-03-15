# t_stock_forecast

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_forecast |
| 中文名 | 业绩预告表 - 来自Tushare forecast |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 109,643 行 |
| 数据大小 | 80.53 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `type` | VARCHAR(50) | YES | - | 业绩预告类型 |
| `p_change_min` | DECIMAL(10,4) | YES | - | 预告净利润变动幅度下限(%) |
| `p_change_max` | DECIMAL(10,4) | YES | - | 预告净利润变动幅度上限(%) |
| `net_profit_min` | DECIMAL(20,4) | YES | - | 预告净利润下限（万元） |
| `net_profit_max` | DECIMAL(20,4) | YES | - | 预告净利润上限（万元） |
| `last_parent_net` | DECIMAL(20,4) | YES | - | 上年同期归属母公司净利润（万元） |
| `first_ann_date` | VARCHAR(8) | YES | - | 首次公告日 |
| `summary` | TEXT | YES | - | 业绩预告摘要 |
| `change_reason` | TEXT | YES | - | 业绩变动原因 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | type | p_change_min | p_change_max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20060705 | 20060630 | 预增 | 150.0000 | 200.0000 |
| 000001.SZ | 20061013 | 20060930 | 预增 | 150.0000 | 200.0000 |
| 000001.SZ | 20070126 | 20061231 | 预增 | 300.0000 | 350.0000 |
| 000001.SZ | 20070717 | 20070630 | 预增 | 125.0000 | 145.0000 |
| 000001.SZ | 20071015 | 20070930 | 预增 | 100.0000 | 120.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_forecast` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `type` varchar(50) DEFAULT NULL COMMENT '业绩预告类型',
  `p_change_min` decimal(10,4) DEFAULT NULL COMMENT '预告净利润变动幅度下限(%)',
  `p_change_max` decimal(10,4) DEFAULT NULL COMMENT '预告净利润变动幅度上限(%)',
  `net_profit_min` decimal(20,4) DEFAULT NULL COMMENT '预告净利润下限（万元）',
  `net_profit_max` decimal(20,4) DEFAULT NULL COMMENT '预告净利润上限（万元）',
  `last_parent_net` decimal(20,4) DEFAULT NULL COMMENT '上年同期归属母公司净利润（万元）',
  `first_ann_date` varchar(8) DEFAULT NULL COMMENT '首次公告日',
  `summary` text COMMENT '业绩预告摘要',
  `change_reason` text COMMENT '业绩变动原因',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业绩预告表 - 来自Tushare forecast'
```
