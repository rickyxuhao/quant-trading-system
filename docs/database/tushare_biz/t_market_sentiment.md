# t_market_sentiment

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_market_sentiment |
| 中文名 | 市场情绪指标表 - 基于每日行情统计 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-08 16:27:32 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `rise_count` | INT | YES | - | 上涨家数 |
| `fall_count` | INT | YES | - | 下跌家数 |
| `flat_count` | INT | YES | - | 平盘家数 |
| `rise_fall_ratio` | DECIMAL(10,4) | YES | - | 涨跌家数比 |
| `limit_up_count` | INT | YES | - | 涨停家数 |
| `limit_down_count` | INT | YES | - | 跌停家数 |
| `limit_up_down_ratio` | DECIMAL(10,4) | YES | - | 涨停跌停比 |
| `limit_up_2day` | INT | YES | - | 2连板家数 |
| `limit_up_3day` | INT | YES | - | 3连板家数 |
| `limit_up_4day_plus` | INT | YES | - | 4连板及以上家数 |
| `bomb_rate` | DECIMAL(10,4) | YES | - | 炸板率(%) - 开板涨停占比 |
| `turnover_median` | DECIMAL(10,4) | YES | - | 换手率中位数 |
| `turnover_avg` | DECIMAL(10,4) | YES | - | 换手率平均值 |
| `high_turnover_count` | INT | YES | - | 高换手股票数(换手>20%) |
| `total_amount` | DECIMAL(20,4) | YES | - | 全市场成交额(亿元) |
| `amount_ma5` | DECIMAL(20,4) | YES | - | 成交额5日均值 |
| `amount_ratio` | DECIMAL(10,4) | YES | - | 成交额比例(当日/5日均值) |
| `north_money_in` | DECIMAL(20,4) | YES | - | 北向资金流入(亿元) |
| `north_money_cum` | DECIMAL(20,4) | YES | - | 北向资金累计流入(亿元) |
| `sentiment_score` | DECIMAL(10,4) | YES | - | 情绪分数(-100到+100) |
| `sentiment_level` | VARCHAR(20) | YES | - | 情绪等级(极度恐慌/恐慌/中性/乐观/极度乐观) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_sentiment_date | 普通 | trade_date | - |
| idx_sentiment_score | 普通 | sentiment_score | - |
| PRIMARY | 主键 | trade_date | - |

## 建表语句

```sql
CREATE TABLE `t_market_sentiment` (
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `rise_count` int DEFAULT NULL COMMENT '上涨家数',
  `fall_count` int DEFAULT NULL COMMENT '下跌家数',
  `flat_count` int DEFAULT NULL COMMENT '平盘家数',
  `rise_fall_ratio` decimal(10,4) DEFAULT NULL COMMENT '涨跌家数比',
  `limit_up_count` int DEFAULT NULL COMMENT '涨停家数',
  `limit_down_count` int DEFAULT NULL COMMENT '跌停家数',
  `limit_up_down_ratio` decimal(10,4) DEFAULT NULL COMMENT '涨停跌停比',
  `limit_up_2day` int DEFAULT NULL COMMENT '2连板家数',
  `limit_up_3day` int DEFAULT NULL COMMENT '3连板家数',
  `limit_up_4day_plus` int DEFAULT NULL COMMENT '4连板及以上家数',
  `bomb_rate` decimal(10,4) DEFAULT NULL COMMENT '炸板率(%) - 开板涨停占比',
  `turnover_median` decimal(10,4) DEFAULT NULL COMMENT '换手率中位数',
  `turnover_avg` decimal(10,4) DEFAULT NULL COMMENT '换手率平均值',
  `high_turnover_count` int DEFAULT NULL COMMENT '高换手股票数(换手>20%)',
  `total_amount` decimal(20,4) DEFAULT NULL COMMENT '全市场成交额(亿元)',
  `amount_ma5` decimal(20,4) DEFAULT NULL COMMENT '成交额5日均值',
  `amount_ratio` decimal(10,4) DEFAULT NULL COMMENT '成交额比例(当日/5日均值)',
  `north_money_in` decimal(20,4) DEFAULT NULL COMMENT '北向资金流入(亿元)',
  `north_money_cum` decimal(20,4) DEFAULT NULL COMMENT '北向资金累计流入(亿元)',
  `sentiment_score` decimal(10,4) DEFAULT NULL COMMENT '情绪分数(-100到+100)',
  `sentiment_level` varchar(20) DEFAULT NULL COMMENT '情绪等级(极度恐慌/恐慌/中性/乐观/极度乐观)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`),
  KEY `idx_sentiment_date` (`trade_date`),
  KEY `idx_sentiment_score` (`sentiment_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='市场情绪指标表 - 基于每日行情统计'
```
