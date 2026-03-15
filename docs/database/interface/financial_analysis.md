# financial_analysis

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | financial_analysis |
| 中文名 | 财务指标分析 |
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
| `report_date` | VARCHAR(8) | YES | - | 报告期 |
| `pe_ttm` | DECIMAL(16,4) | YES | - | PE TTM |
| `pb` | DECIMAL(16,4) | YES | - | PB |
| `ps_ttm` | DECIMAL(16,4) | YES | - | PS TTM |
| `peg` | DECIMAL(16,4) | YES | - | PEG |
| `roe` | DECIMAL(10,4) | YES | - | ROE% |
| `roa` | DECIMAL(10,4) | YES | - | ROA% |
| `gross_margin` | DECIMAL(10,4) | YES | - | 毛利率% |
| `net_margin` | DECIMAL(10,4) | YES | - | 净利率% |
| `revenue_growth` | DECIMAL(10,4) | YES | - | 营收增长率% |
| `profit_growth` | DECIMAL(10,4) | YES | - | 净利润增长率% |
| `debt_ratio` | DECIMAL(10,4) | YES | - | 资产负债率% |
| `current_ratio` | DECIMAL(10,4) | YES | - | 流动比率 |
| `financial_score` | INT | YES | - | 财务评分(0-100) |
| `quality_tag` | VARCHAR(50) | YES | - | 质量标签(优/良/中/差) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_report_date | 普通 | report_date | - |
| PRIMARY | 主键 | id | - |
| uk_code_date | 唯一 | ts_code, report_date | - |

## 建表语句

```sql
CREATE TABLE `financial_analysis` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `report_date` varchar(8) DEFAULT NULL COMMENT '报告期',
  `pe_ttm` decimal(16,4) DEFAULT NULL COMMENT 'PE TTM',
  `pb` decimal(16,4) DEFAULT NULL COMMENT 'PB',
  `ps_ttm` decimal(16,4) DEFAULT NULL COMMENT 'PS TTM',
  `peg` decimal(16,4) DEFAULT NULL COMMENT 'PEG',
  `roe` decimal(10,4) DEFAULT NULL COMMENT 'ROE%',
  `roa` decimal(10,4) DEFAULT NULL COMMENT 'ROA%',
  `gross_margin` decimal(10,4) DEFAULT NULL COMMENT '毛利率%',
  `net_margin` decimal(10,4) DEFAULT NULL COMMENT '净利率%',
  `revenue_growth` decimal(10,4) DEFAULT NULL COMMENT '营收增长率%',
  `profit_growth` decimal(10,4) DEFAULT NULL COMMENT '净利润增长率%',
  `debt_ratio` decimal(10,4) DEFAULT NULL COMMENT '资产负债率%',
  `current_ratio` decimal(10,4) DEFAULT NULL COMMENT '流动比率',
  `financial_score` int DEFAULT NULL COMMENT '财务评分(0-100)',
  `quality_tag` varchar(50) DEFAULT NULL COMMENT '质量标签(优/良/中/差)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code_date` (`ts_code`,`report_date`),
  KEY `idx_report_date` (`report_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='财务指标分析'
```
