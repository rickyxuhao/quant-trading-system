# t_fund_nav

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_fund_nav |
| 中文名 | 基金净值表 - 来自Tushare fund_nav |
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
| `nav_date` | VARCHAR(8) | NO | - | 净值日期 |
| `unit_nav` | DECIMAL(10,4) | YES | - | 单位净值 |
| `accum_nav` | DECIMAL(10,4) | YES | - | 累计净值 |
| `accum_div` | DECIMAL(10,4) | YES | - | 累计分红 |
| `net_asset` | DECIMAL(20,4) | YES | - | 资产净值 |
| `total_netasset` | DECIMAL(20,4) | YES | - | 合计资产净值 |
| `adj_nav` | DECIMAL(10,4) | YES | - | 复权单位净值 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_fund_nav_nav_date | 普通 | nav_date | - |
| idx_fund_nav_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | ts_code, nav_date | - |

## 建表语句

```sql
CREATE TABLE `t_fund_nav` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS基金代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `nav_date` varchar(8) NOT NULL COMMENT '净值日期',
  `unit_nav` decimal(10,4) DEFAULT NULL COMMENT '单位净值',
  `accum_nav` decimal(10,4) DEFAULT NULL COMMENT '累计净值',
  `accum_div` decimal(10,4) DEFAULT NULL COMMENT '累计分红',
  `net_asset` decimal(20,4) DEFAULT NULL COMMENT '资产净值',
  `total_netasset` decimal(20,4) DEFAULT NULL COMMENT '合计资产净值',
  `adj_nav` decimal(10,4) DEFAULT NULL COMMENT '复权单位净值',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`nav_date`),
  KEY `idx_fund_nav_nav_date` (`nav_date`),
  KEY `idx_fund_nav_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金净值表 - 来自Tushare fund_nav'
```
