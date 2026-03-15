# t_stock_top10_holders

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_top10_holders |
| 中文名 | 前十大股东表 - 来自Tushare top10_holders |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `holder_name` | VARCHAR(200) | YES | - | 股东名称 |
| `hold_amount` | DECIMAL(20,4) | YES | - | 持有数量（股） |
| `hold_ratio` | DECIMAL(10,4) | YES | - | 持有比例(%) |
| `hold_change` | DECIMAL(20,4) | YES | - | 变动数量 |
| `holder_rank` | INT | NO | - | 股东排名 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date, holder_rank | - |

## 建表语句

```sql
CREATE TABLE `t_stock_top10_holders` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `holder_name` varchar(200) DEFAULT NULL COMMENT '股东名称',
  `hold_amount` decimal(20,4) DEFAULT NULL COMMENT '持有数量（股）',
  `hold_ratio` decimal(10,4) DEFAULT NULL COMMENT '持有比例(%)',
  `hold_change` decimal(20,4) DEFAULT NULL COMMENT '变动数量',
  `holder_rank` int NOT NULL COMMENT '股东排名',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`holder_rank`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='前十大股东表 - 来自Tushare top10_holders'
```
