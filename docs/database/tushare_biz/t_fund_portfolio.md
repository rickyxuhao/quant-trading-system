# t_fund_portfolio

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_fund_portfolio |
| 中文名 | 基金持仓表 - 来自Tushare fund_portfolio |
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
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `symbol` | VARCHAR(20) | NO | - | 股票代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `mkv` | DECIMAL(20,4) | YES | - | 持有股票市值(元) |
| `amount` | DECIMAL(20,4) | YES | - | 持有股票数量(股) |
| `stk_mkv_ratio` | DECIMAL(10,4) | YES | - | 占股票市值比 |
| `stk_float_ratio` | DECIMAL(10,4) | YES | - | 占流通股本比例 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_fund_portfolio_end_date | 普通 | end_date | - |
| idx_fund_portfolio_symbol | 普通 | symbol | - |
| PRIMARY | 主键 | ts_code, end_date, symbol | - |

## 建表语句

```sql
CREATE TABLE `t_fund_portfolio` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS基金代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `symbol` varchar(20) NOT NULL COMMENT '股票代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `mkv` decimal(20,4) DEFAULT NULL COMMENT '持有股票市值(元)',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '持有股票数量(股)',
  `stk_mkv_ratio` decimal(10,4) DEFAULT NULL COMMENT '占股票市值比',
  `stk_float_ratio` decimal(10,4) DEFAULT NULL COMMENT '占流通股本比例',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`symbol`),
  KEY `idx_fund_portfolio_end_date` (`end_date`),
  KEY `idx_fund_portfolio_symbol` (`symbol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金持仓表 - 来自Tushare fund_portfolio'
```
