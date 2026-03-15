# gold_stock_performance

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | gold_stock_performance |
| 中文名 | 金股表现追踪 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 48.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `month` | VARCHAR(6) | NO | - | 推荐月份 |
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `recommend_date` | VARCHAR(8) | YES | - | 推荐日期 |
| `end_date` | VARCHAR(8) | YES | - | 统计截止日期 |
| `recommend_price` | DECIMAL(16,4) | YES | - | 推荐日收盘价 |
| `current_price` | DECIMAL(16,4) | YES | - | 当前价格 |
| `max_price` | DECIMAL(16,4) | YES | - | 月内最高价 |
| `min_price` | DECIMAL(16,4) | YES | - | 月内最低价 |
| `total_return` | DECIMAL(10,4) | YES | - | 累计收益率% |
| `excess_return` | DECIMAL(10,4) | YES | - | 超额收益%(相对沪深300) |
| `max_drawdown` | DECIMAL(10,4) | YES | - | 最大回撤% |
| `avg_volume` | DECIMAL(20,4) | YES | - | 日均成交额(万元) |
| `volatility` | DECIMAL(10,4) | YES | - | 波动率 |
| `technical_score` | INT | YES | - | 技术评分(0-100) |
| `technical_signals` | JSON | YES | - | 技术信号详情 |
| `ext_data` | JSON | YES | - | 扩展数据字段(预留) |
| `status` | ENUM | YES | watching | 状态 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_status | 普通 | status | - |
| idx_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | id | - |
| uk_month_code | 唯一 | month, ts_code | - |

## 建表语句

```sql
CREATE TABLE `gold_stock_performance` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `month` varchar(6) NOT NULL COMMENT '推荐月份',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `recommend_date` varchar(8) DEFAULT NULL COMMENT '推荐日期',
  `end_date` varchar(8) DEFAULT NULL COMMENT '统计截止日期',
  `recommend_price` decimal(16,4) DEFAULT NULL COMMENT '推荐日收盘价',
  `current_price` decimal(16,4) DEFAULT NULL COMMENT '当前价格',
  `max_price` decimal(16,4) DEFAULT NULL COMMENT '月内最高价',
  `min_price` decimal(16,4) DEFAULT NULL COMMENT '月内最低价',
  `total_return` decimal(10,4) DEFAULT NULL COMMENT '累计收益率%',
  `excess_return` decimal(10,4) DEFAULT NULL COMMENT '超额收益%(相对沪深300)',
  `max_drawdown` decimal(10,4) DEFAULT NULL COMMENT '最大回撤%',
  `avg_volume` decimal(20,4) DEFAULT NULL COMMENT '日均成交额(万元)',
  `volatility` decimal(10,4) DEFAULT NULL COMMENT '波动率',
  `technical_score` int DEFAULT NULL COMMENT '技术评分(0-100)',
  `technical_signals` json DEFAULT NULL COMMENT '技术信号详情',
  `ext_data` json DEFAULT NULL COMMENT '扩展数据字段(预留)',
  `status` enum('holding','closed','watching') DEFAULT 'watching' COMMENT '状态',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_month_code` (`month`,`ts_code`),
  KEY `idx_status` (`status`),
  KEY `idx_ts_code` (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='金股表现追踪'
```
