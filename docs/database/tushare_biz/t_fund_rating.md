# t_fund_rating

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_fund_rating |
| 中文名 | 基金评级表 - 来自Tushare fund_rating |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 13:52:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS基金代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `rating_agency` | VARCHAR(50) | NO | - | 评级机构 |
| `rating_date` | VARCHAR(8) | NO | - | 评级日期 |
| `fund_rating` | VARCHAR(20) | YES | - | 基金星级 |
| `manager_rating` | VARCHAR(20) | YES | - | 经理星级 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_fund_rating_agency | 普通 | rating_agency | - |
| idx_fund_rating_date | 普通 | rating_date | - |
| PRIMARY | 主键 | ts_code, rating_agency, rating_date | - |

## 建表语句

```sql
CREATE TABLE `t_fund_rating` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS基金代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `rating_agency` varchar(50) NOT NULL COMMENT '评级机构',
  `rating_date` varchar(8) NOT NULL COMMENT '评级日期',
  `fund_rating` varchar(20) DEFAULT NULL COMMENT '基金星级',
  `manager_rating` varchar(20) DEFAULT NULL COMMENT '经理星级',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`rating_agency`,`rating_date`),
  KEY `idx_fund_rating_agency` (`rating_agency`),
  KEY `idx_fund_rating_date` (`rating_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金评级表 - 来自Tushare fund_rating'
```
