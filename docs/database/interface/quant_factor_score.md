# quant_factor_score

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | quant_factor_score |
| 中文名 | 量化因子评分 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 259 行 |
| 数据大小 | 48.00 KB |
| 索引大小 | 48.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |
| 更新时间 | 2026-03-13 08:00:10 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `trade_date` | VARCHAR(8) | YES | - | 交易日 |
| `value_factor` | DECIMAL(10,4) | YES | - | 估值因子得分 |
| `quality_factor` | DECIMAL(10,4) | YES | - | 质量因子得分 |
| `growth_factor` | DECIMAL(10,4) | YES | - | 成长因子得分 |
| `momentum_factor` | DECIMAL(10,4) | YES | - | 动量因子得分 |
| `volatility_factor` | DECIMAL(10,4) | YES | - | 波动率因子得分 |
| `liquidity_factor` | DECIMAL(10,4) | YES | - | 流动性因子得分 |
| `total_score` | DECIMAL(10,4) | YES | - | 综合因子得分 |
| `rank_in_industry` | INT | YES | - | 行业内排名 |
| `rank_in_market` | INT | YES | - | 全市场排名 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_total_score | 普通 | total_score | - |
| idx_trade_date | 普通 | trade_date | - |
| PRIMARY | 主键 | id | - |
| uk_code_date | 唯一 | ts_code, trade_date | - |

## 数据示例

| id | ts_code | name | trade_date | value_factor | quality_factor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 000636.SZ |  | 20260310 | 95.0000 | 100.0000 |
| 2 | 001221.SZ |  | 20260310 | 90.0000 | 100.0000 |
| 3 | 002440.SZ |  | 20260310 | 100.0000 | 100.0000 |
| 4 | 300806.SZ |  | 20260310 | 90.0000 | 100.0000 |
| 5 | 300943.SZ |  | 20260310 | 90.0000 | 100.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `quant_factor_score` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `trade_date` varchar(8) DEFAULT NULL COMMENT '交易日',
  `value_factor` decimal(10,4) DEFAULT NULL COMMENT '估值因子得分',
  `quality_factor` decimal(10,4) DEFAULT NULL COMMENT '质量因子得分',
  `growth_factor` decimal(10,4) DEFAULT NULL COMMENT '成长因子得分',
  `momentum_factor` decimal(10,4) DEFAULT NULL COMMENT '动量因子得分',
  `volatility_factor` decimal(10,4) DEFAULT NULL COMMENT '波动率因子得分',
  `liquidity_factor` decimal(10,4) DEFAULT NULL COMMENT '流动性因子得分',
  `total_score` decimal(10,4) DEFAULT NULL COMMENT '综合因子得分',
  `rank_in_industry` int DEFAULT NULL COMMENT '行业内排名',
  `rank_in_market` int DEFAULT NULL COMMENT '全市场排名',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code_date` (`ts_code`,`trade_date`),
  KEY `idx_trade_date` (`trade_date`),
  KEY `idx_total_score` (`total_score`)
) ENGINE=InnoDB AUTO_INCREMENT=1290 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='量化因子评分'
```
