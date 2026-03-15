# t_stock_holder_trade

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_holder_trade |
| 中文名 | 股东增减持表 - 来自Tushare stk_holdertrade |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 96,670 行 |
| 数据大小 | 25.59 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | NO | - | 公告日期 |
| `holder_name` | VARCHAR(200) | NO | - | 股东名称 |
| `holder_type` | VARCHAR(50) | YES | - | 股东类型 |
| `in_de` | VARCHAR(10) | YES | - | 增减持方向 |
| `change_vol` | DECIMAL(20,4) | YES | - | 变动数量 |
| `change_ratio` | DECIMAL(10,4) | YES | - | 变动占总股本比例(%) |
| `after_share` | DECIMAL(20,4) | YES | - | 变动后持股数量 |
| `after_ratio` | DECIMAL(10,4) | YES | - | 变动后持股比例(%) |
| `avg_price` | DECIMAL(16,4) | YES | - | 平均交易价格 |
| `total_share` | DECIMAL(20,4) | YES | - | 持股总数 |
| `begin_date` | VARCHAR(8) | YES | - | 增减持开始日期 |
| `close_date` | VARCHAR(8) | YES | - | 增减持结束日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, ann_date, holder_name | - |

## 数据示例

| ts_code | ann_date | holder_name | holder_type | in_de | change_vol |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20071204 | 宝钢集团有限公司 | C | IN | 250000.0000 |
| 000001.SZ | 20090616 | 中国平安人寿保险股份有限公司 | C | IN | 1536545.0000 |
| 000001.SZ | 20090616 | 中国平安保险(集团)股份有限公司 | C | IN | 137200.0000 |
| 000001.SZ | 20090616 | 中国平安健康保险股份有限公司 | C | DE | 71500.0000 |
| 000001.SZ | 20100915 | 邱伟 | P | DE | 12700.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_holder_trade` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) NOT NULL COMMENT '公告日期',
  `holder_name` varchar(200) NOT NULL COMMENT '股东名称',
  `holder_type` varchar(50) DEFAULT NULL COMMENT '股东类型',
  `in_de` varchar(10) DEFAULT NULL COMMENT '增减持方向',
  `change_vol` decimal(20,4) DEFAULT NULL COMMENT '变动数量',
  `change_ratio` decimal(10,4) DEFAULT NULL COMMENT '变动占总股本比例(%)',
  `after_share` decimal(20,4) DEFAULT NULL COMMENT '变动后持股数量',
  `after_ratio` decimal(10,4) DEFAULT NULL COMMENT '变动后持股比例(%)',
  `avg_price` decimal(16,4) DEFAULT NULL COMMENT '平均交易价格',
  `total_share` decimal(20,4) DEFAULT NULL COMMENT '持股总数',
  `begin_date` varchar(8) DEFAULT NULL COMMENT '增减持开始日期',
  `close_date` varchar(8) DEFAULT NULL COMMENT '增减持结束日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`ann_date`,`holder_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股东增减持表 - 来自Tushare stk_holdertrade'
```
