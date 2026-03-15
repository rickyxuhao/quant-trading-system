# broker_gold_stock

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | broker_gold_stock |
| 中文名 | 券商月度金股推荐 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 572 行 |
| 数据大小 | 80.00 KB |
| 索引大小 | 96.00 KB |
| 创建时间 | 2026-03-10 16:10:28 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - | 自增ID |
| `month` | VARCHAR(6) | NO | - | 月份 YYYYMM |
| `broker_name` | VARCHAR(100) | YES | - | 券商名称 |
| `ts_code` | VARCHAR(20) | NO | - | TS股票代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `industry` | VARCHAR(100) | YES | - | 所属行业 |
| `analyst` | VARCHAR(100) | YES | - | 分析师 |
| `logic` | TEXT | YES | - | 推荐逻辑 |
| `target_price` | DECIMAL(16,4) | YES | - | 目标价 |
| `previous_perf` | DECIMAL(10,4) | YES | - | 上月涨跌幅% |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_industry | 普通 | industry | - |
| idx_month | 普通 | month | - |
| idx_ts_code | 普通 | ts_code | - |
| PRIMARY | 主键 | id | - |
| uk_month_broker_stock | 唯一 | month, broker_name, ts_code | - |

## 数据示例

| id | month | broker_name | ts_code | name | industry |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 202603 | 东北证券 | 000636.SZ | 风华高科 |  |
| 2 | 202603 | 东北证券 | 001221.SZ | 悍高集团 |  |
| 3 | 202603 | 东北证券 | 002440.SZ | 闰土股份 |  |
| 4 | 202603 | 东北证券 | 300806.SZ | 斯迪克 |  |
| 5 | 202603 | 东北证券 | 300943.SZ | 春晖智控 |  |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `broker_gold_stock` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `month` varchar(6) NOT NULL COMMENT '月份 YYYYMM',
  `broker_name` varchar(100) DEFAULT NULL COMMENT '券商名称',
  `ts_code` varchar(20) NOT NULL COMMENT 'TS股票代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `industry` varchar(100) DEFAULT NULL COMMENT '所属行业',
  `analyst` varchar(100) DEFAULT NULL COMMENT '分析师',
  `logic` text COMMENT '推荐逻辑',
  `target_price` decimal(16,4) DEFAULT NULL COMMENT '目标价',
  `previous_perf` decimal(10,4) DEFAULT NULL COMMENT '上月涨跌幅%',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_month_broker_stock` (`month`,`broker_name`,`ts_code`),
  KEY `idx_month` (`month`),
  KEY `idx_ts_code` (`ts_code`),
  KEY `idx_industry` (`industry`)
) ENGINE=InnoDB AUTO_INCREMENT=573 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='券商月度金股推荐'
```
