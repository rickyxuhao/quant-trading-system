# morning_report

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | morning_report |
| 中文名 | 晨间投资报告 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 3 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 32.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |
| 更新时间 | 2026-03-13 08:00:10 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `report_date` | VARCHAR(8) | YES | - | 报告日期 |
| `gold_stock_count` | INT | YES | - | 监控金股数量 |
| `anomaly_count` | INT | YES | - | 异动股票数量 |
| `buy_signals` | INT | YES | - | 买入信号数量 |
| `sell_signals` | INT | YES | - | 卖出信号数量 |
| `summary` | TEXT | YES | - | 执行摘要 |
| `highlight_stocks` | JSON | YES | - | 重点股票 |
| `market_outlook` | TEXT | YES | - | 市场展望 |
| `strategy_signals` | JSON | YES | - | 策略信号(预留) |
| `markdown_path` | VARCHAR(500) | YES | - | Markdown文件路径 |
| `pdf_path` | VARCHAR(500) | YES | - | PDF文件路径 |
| `sent_at` | TIMESTAMP | YES | - | 发送时间 |
| `send_status` | VARCHAR(20) | YES | - | 发送状态 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_created_at | 普通 | created_at | - |
| PRIMARY | 主键 | id | - |
| uk_report_date | 唯一 | report_date | - |

## 数据示例

| id | report_date | gold_stock_count | anomaly_count | buy_signals | sell_signals |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 20260310 | 122 | 5 | 31 | 0 |
| 8 | 20260311 | 122 | 4 | 31 | 0 |
| 9 | 20260312 | 122 | 9 | 32 | 0 |
| 10 | 20260313 | 122 | 6 | 28 | 0 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `morning_report` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `report_date` varchar(8) DEFAULT NULL COMMENT '报告日期',
  `gold_stock_count` int DEFAULT NULL COMMENT '监控金股数量',
  `anomaly_count` int DEFAULT NULL COMMENT '异动股票数量',
  `buy_signals` int DEFAULT NULL COMMENT '买入信号数量',
  `sell_signals` int DEFAULT NULL COMMENT '卖出信号数量',
  `summary` text COMMENT '执行摘要',
  `highlight_stocks` json DEFAULT NULL COMMENT '重点股票',
  `market_outlook` text COMMENT '市场展望',
  `strategy_signals` json DEFAULT NULL COMMENT '策略信号(预留)',
  `markdown_path` varchar(500) DEFAULT NULL COMMENT 'Markdown文件路径',
  `pdf_path` varchar(500) DEFAULT NULL COMMENT 'PDF文件路径',
  `sent_at` timestamp NULL DEFAULT NULL COMMENT '发送时间',
  `send_status` varchar(20) DEFAULT NULL COMMENT '发送状态',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_date` (`report_date`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='晨间投资报告'
```
