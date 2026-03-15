# t_sw_industry_rotation

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_sw_industry_rotation |
| 中文名 | 申万行业轮动指标表 - 基于sw_daily计算 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 16:27:32 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `industry_code` | VARCHAR(20) | NO | - | 行业代码 |
| `industry_name` | VARCHAR(100) | YES | - | 行业名称 |
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `change_pct` | DECIMAL(10,4) | YES | - | 当日涨跌幅 |
| `rank_1day` | INT | YES | - | 1日涨幅排名 |
| `rank_5day` | INT | YES | - | 5日涨幅排名 |
| `rank_10day` | INT | YES | - | 10日涨幅排名 |
| `rank_20day` | INT | YES | - | 20日涨幅排名 |
| `rs_vs_index` | DECIMAL(10,4) | YES | - | 相对大盘强弱(行业涨幅-大盘涨幅) |
| `rs_5day` | DECIMAL(10,4) | YES | - | 5日相对强弱 |
| `rs_10day` | DECIMAL(10,4) | YES | - | 10日相对强弱 |
| `rs_20day` | DECIMAL(10,4) | YES | - | 20日相对强弱 |
| `amount` | DECIMAL(20,4) | YES | - | 行业成交额 |
| `amount_ratio` | DECIMAL(10,4) | YES | - | 成交额占比(行业/全市场) |
| `amount_ratio_change` | DECIMAL(10,4) | YES | - | 成交额占比变化(较5日前) |
| `pe` | DECIMAL(10,4) | YES | - | 市盈率 |
| `pb` | DECIMAL(10,4) | YES | - | 市净率 |
| `pe_percentile` | DECIMAL(10,4) | YES | - | PE历史分位(近2年) |
| `pb_percentile` | DECIMAL(10,4) | YES | - | PB历史分位(近2年) |
| `trend_score` | DECIMAL(10,4) | YES | - | 趋势评分(综合涨幅+量能+估值) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_sw_rotation_date | 普通 | trade_date | - |
| idx_sw_rotation_rank | 普通 | rank_5day | - |
| idx_sw_rotation_score | 普通 | trend_score | - |
| PRIMARY | 主键 | industry_code, trade_date | - |

## 建表语句

```sql
CREATE TABLE `t_sw_industry_rotation` (
  `industry_code` varchar(20) NOT NULL COMMENT '行业代码',
  `industry_name` varchar(100) DEFAULT NULL COMMENT '行业名称',
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `change_pct` decimal(10,4) DEFAULT NULL COMMENT '当日涨跌幅',
  `rank_1day` int DEFAULT NULL COMMENT '1日涨幅排名',
  `rank_5day` int DEFAULT NULL COMMENT '5日涨幅排名',
  `rank_10day` int DEFAULT NULL COMMENT '10日涨幅排名',
  `rank_20day` int DEFAULT NULL COMMENT '20日涨幅排名',
  `rs_vs_index` decimal(10,4) DEFAULT NULL COMMENT '相对大盘强弱(行业涨幅-大盘涨幅)',
  `rs_5day` decimal(10,4) DEFAULT NULL COMMENT '5日相对强弱',
  `rs_10day` decimal(10,4) DEFAULT NULL COMMENT '10日相对强弱',
  `rs_20day` decimal(10,4) DEFAULT NULL COMMENT '20日相对强弱',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '行业成交额',
  `amount_ratio` decimal(10,4) DEFAULT NULL COMMENT '成交额占比(行业/全市场)',
  `amount_ratio_change` decimal(10,4) DEFAULT NULL COMMENT '成交额占比变化(较5日前)',
  `pe` decimal(10,4) DEFAULT NULL COMMENT '市盈率',
  `pb` decimal(10,4) DEFAULT NULL COMMENT '市净率',
  `pe_percentile` decimal(10,4) DEFAULT NULL COMMENT 'PE历史分位(近2年)',
  `pb_percentile` decimal(10,4) DEFAULT NULL COMMENT 'PB历史分位(近2年)',
  `trend_score` decimal(10,4) DEFAULT NULL COMMENT '趋势评分(综合涨幅+量能+估值)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`industry_code`,`trade_date`),
  KEY `idx_sw_rotation_date` (`trade_date`),
  KEY `idx_sw_rotation_rank` (`rank_5day`),
  KEY `idx_sw_rotation_score` (`trend_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='申万行业轮动指标表 - 基于sw_daily计算'
```
