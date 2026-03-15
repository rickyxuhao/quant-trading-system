# t_index_basic

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_index_basic |
| 中文名 | 指数基本信息表 - 来自Tushare index_basic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 7,885 行 |
| 数据大小 | 1.52 MB |
| 索引大小 | 2.23 MB |
| 创建时间 | 2026-03-08 12:41:35 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS指数代码 |
| `name` | VARCHAR(100) | YES | - | 指数名称 |
| `market` | VARCHAR(20) | YES | - | 市场(SZ/SH) |
| `publisher` | VARCHAR(50) | YES | - | 发布方 |
| `category` | VARCHAR(50) | YES | - | 指数类别 |
| `base_date` | VARCHAR(8) | YES | - | 基期 |
| `base_point` | DECIMAL(10,4) | YES | - | 基点点位 |
| `list_date` | VARCHAR(8) | YES | - | 发布日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_index_basic_category | 普通 | category | - |
| idx_index_basic_market | 普通 | market | - |
| idx_index_basic_name | 普通 | name | - |
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | name | market | publisher | category | base_date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.CJ | 能源(长江) | OTH | 长江证券股份有限公司 | 行业指数 | 20021231 |
| 000001.SH | 上证指数 | SSE | 中证指数有限公司 | 综合指数 | 19901219 |
| 000002.CJ | 原材料(长江) | OTH | 长江证券股份有限公司 | 行业指数 | 20021231 |
| 000002.SH | A股指数 | SSE | 中证指数有限公司 | 规模指数 | 19901219 |
| 000003.CJ | 工业(长江) | OTH | 长江证券股份有限公司 | 行业指数 | 20021231 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_index_basic` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS指数代码',
  `name` varchar(100) DEFAULT NULL COMMENT '指数名称',
  `market` varchar(20) DEFAULT NULL COMMENT '市场(SZ/SH)',
  `publisher` varchar(50) DEFAULT NULL COMMENT '发布方',
  `category` varchar(50) DEFAULT NULL COMMENT '指数类别',
  `base_date` varchar(8) DEFAULT NULL COMMENT '基期',
  `base_point` decimal(10,4) DEFAULT NULL COMMENT '基点点位',
  `list_date` varchar(8) DEFAULT NULL COMMENT '发布日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`),
  KEY `idx_index_basic_name` (`name`),
  KEY `idx_index_basic_market` (`market`),
  KEY `idx_index_basic_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指数基本信息表 - 来自Tushare index_basic'
```
