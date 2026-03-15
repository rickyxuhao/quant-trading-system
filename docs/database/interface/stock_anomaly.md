# stock_anomaly

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | stock_anomaly |
| 中文名 | 股票异动检测记录 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 139 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 48.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |
| 更新时间 | 2026-03-13 08:00:05 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `detect_date` | VARCHAR(8) | YES | - | 检测日期 |
| `anomaly_type` | VARCHAR(50) | YES | - | 异动类型 |
| `severity` | ENUM | YES | medium | 严重程度 |
| `trigger_price` | DECIMAL(16,4) | YES | - | 触发价格 |
| `price_change` | DECIMAL(10,4) | YES | - | 涨跌幅% |
| `volume_ratio` | DECIMAL(10,4) | YES | - | 量比 |
| `news_collected` | TINYINT | YES | 0 | 是否收集新闻 |
| `news_analyzed` | TINYINT | YES | 0 | 是否AI分析 |
| `ai_analysis` | TEXT | YES | - | AI分析结果 |
| `ai_sentiment` | VARCHAR(20) | YES | - | AI情感判断 |
| `recommendation` | VARCHAR(50) | YES | - | 建议动作 |
| `confidence` | DECIMAL(5,4) | YES | - | 置信度 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_anomaly_type | 普通 | anomaly_type | - |
| idx_detect_date | 普通 | detect_date | - |
| idx_ts_code_date | 普通 | ts_code, detect_date | - |
| PRIMARY | 主键 | id | - |

## 数据示例

| id | ts_code | name | detect_date | anomaly_type | severity |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 688702.SH | 盛科通信-U | 20260310 | price_spike | high |
| 2 | 603225.SH | 新凤鸣 | 20260310 | price_spike | medium |
| 3 | 603610.SH | 麒盛科技 | 20260310 | price_spike | medium |
| 4 | 603610.SH | 麒盛科技 | 20260310 | volume_surge | low |
| 5 | 300750.SZ | 宁德时代 | 20260310 | price_spike | medium |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `stock_anomaly` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `detect_date` varchar(8) DEFAULT NULL COMMENT '检测日期',
  `anomaly_type` varchar(50) DEFAULT NULL COMMENT '异动类型',
  `severity` enum('low','medium','high','critical') DEFAULT 'medium' COMMENT '严重程度',
  `trigger_price` decimal(16,4) DEFAULT NULL COMMENT '触发价格',
  `price_change` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅%',
  `volume_ratio` decimal(10,4) DEFAULT NULL COMMENT '量比',
  `news_collected` tinyint DEFAULT '0' COMMENT '是否收集新闻',
  `news_analyzed` tinyint DEFAULT '0' COMMENT '是否AI分析',
  `ai_analysis` text COMMENT 'AI分析结果',
  `ai_sentiment` varchar(20) DEFAULT NULL COMMENT 'AI情感判断',
  `recommendation` varchar(50) DEFAULT NULL COMMENT '建议动作',
  `confidence` decimal(5,4) DEFAULT NULL COMMENT '置信度',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_ts_code_date` (`ts_code`,`detect_date`),
  KEY `idx_anomaly_type` (`anomaly_type`),
  KEY `idx_detect_date` (`detect_date`)
) ENGINE=InnoDB AUTO_INCREMENT=147 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票异动检测记录'
```
