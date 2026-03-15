# news_sentiment

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | news_sentiment |
| 中文名 | 新闻舆情数据 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 32.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `news_date` | VARCHAR(8) | YES | - | 新闻日期 |
| `title` | VARCHAR(500) | YES | - | 标题 |
| `content` | TEXT | YES | - | 内容 |
| `source` | VARCHAR(100) | YES | - | 来源 |
| `url` | VARCHAR(500) | YES | - | 链接 |
| `sentiment_score` | DECIMAL(5,4) | YES | - | 情感得分(-1到1) |
| `sentiment_label` | VARCHAR(20) | YES | - | 情感标签 |
| `ai_summary` | TEXT | YES | - | AI摘要 |
| `key_points` | JSON | YES | - | 关键要点 |
| `impact_assessment` | VARCHAR(50) | YES | - | 影响评估 |
| `relevance_score` | DECIMAL(5,4) | YES | - | 相关度得分 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_news_date | 普通 | news_date | - |
| idx_ts_code_date | 普通 | ts_code, news_date | - |
| PRIMARY | 主键 | id | - |

## 建表语句

```sql
CREATE TABLE `news_sentiment` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `news_date` varchar(8) DEFAULT NULL COMMENT '新闻日期',
  `title` varchar(500) DEFAULT NULL COMMENT '标题',
  `content` text COMMENT '内容',
  `source` varchar(100) DEFAULT NULL COMMENT '来源',
  `url` varchar(500) DEFAULT NULL COMMENT '链接',
  `sentiment_score` decimal(5,4) DEFAULT NULL COMMENT '情感得分(-1到1)',
  `sentiment_label` varchar(20) DEFAULT NULL COMMENT '情感标签',
  `ai_summary` text COMMENT 'AI摘要',
  `key_points` json DEFAULT NULL COMMENT '关键要点',
  `impact_assessment` varchar(50) DEFAULT NULL COMMENT '影响评估',
  `relevance_score` decimal(5,4) DEFAULT NULL COMMENT '相关度得分',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_ts_code_date` (`ts_code`,`news_date`),
  KEY `idx_news_date` (`news_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='新闻舆情数据'
```
