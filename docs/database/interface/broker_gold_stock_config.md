# broker_gold_stock_config

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | broker_gold_stock_config |
| 中文名 | 系统配置表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 8 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 16.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `config_key` | VARCHAR(100) | NO | - | 配置键 |
| `config_value` | TEXT | YES | - | 配置值 |
| `config_type` | VARCHAR(20) | YES | string | 值类型: string, int, float, json |
| `description` | VARCHAR(500) | YES | - | 配置说明 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | id | - |
| uk_config_key | 唯一 | config_key | - |

## 数据示例

| id | config_key | config_value | config_type | description | updated_at |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | analysis.weight.technical | 0.30 | float | 技术分析权重 | 2026-03-10 16:10:28 |
| 2 | analysis.weight.financial | 0.30 | float | 财务分析权重 | 2026-03-10 16:10:28 |
| 3 | analysis.weight.quant | 0.30 | float | 量化因子权重 | 2026-03-10 16:10:28 |
| 4 | analysis.weight.sentiment | 0.10 | float | 市场情绪权重 | 2026-03-10 16:10:28 |
| 5 | anomaly.threshold.price_change | 5.0 | float | 价格异动阈值(%) | 2026-03-10 16:10:28 |

## 建表语句

```sql
CREATE TABLE `broker_gold_stock_config` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `config_key` varchar(100) NOT NULL COMMENT '配置键',
  `config_value` text COMMENT '配置值',
  `config_type` varchar(20) DEFAULT 'string' COMMENT '值类型: string, int, float, json',
  `description` varchar(500) DEFAULT NULL COMMENT '配置说明',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_config_key` (`config_key`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统配置表'
```
