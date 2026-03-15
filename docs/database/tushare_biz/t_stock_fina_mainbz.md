# t_stock_fina_mainbz

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_fina_mainbz |
| 中文名 | 主营业务构成表 - 来自Tushare fina_mainbz |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 1,019,370 行 |
| 数据大小 | 148.98 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `bz_item` | VARCHAR(200) | NO | - | 主营业务项目 |
| `bz_sales` | DECIMAL(20,4) | YES | - | 主营业务收入（元） |
| `bz_profit` | DECIMAL(20,4) | YES | - | 主营业务利润（元） |
| `bz_cost` | DECIMAL(20,4) | YES | - | 主营业务成本（元） |
| `curr_type` | VARCHAR(10) | YES | - |  |
| `update_flag` | VARCHAR(10) | YES | - |  |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date, bz_item | - |

## 数据示例

| ts_code | end_date | bz_item | bz_sales | bz_profit | bz_cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20230630 | 东区 | 13437000000.0000 | 9864000000.0000 | 3573000000.0000 |
| 000001.SZ | 20230630 | 利息收入:发放贷款及垫款:公司贷款业务(产品) | 22802000000.0000 | NULL | NULL |
| 000001.SZ | 20230630 | 利息收入:发放贷款及垫款:票据贴现业务(产品) | 2228000000.0000 | NULL | NULL |
| 000001.SZ | 20230630 | 利息收入:存放中央银行款项(产品) | 1915000000.0000 | NULL | NULL |
| 000001.SZ | 20230630 | 利息收入:存放同业、拆放同业及买入返售金融资产(产品) | 4104000000.0000 | NULL | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_fina_mainbz` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `bz_item` varchar(200) NOT NULL COMMENT '主营业务项目',
  `bz_sales` decimal(20,4) DEFAULT NULL COMMENT '主营业务收入（元）',
  `bz_profit` decimal(20,4) DEFAULT NULL COMMENT '主营业务利润（元）',
  `bz_cost` decimal(20,4) DEFAULT NULL COMMENT '主营业务成本（元）',
  `curr_type` varchar(10) DEFAULT NULL,
  `update_flag` varchar(10) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`,`bz_item`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='主营业务构成表 - 来自Tushare fina_mainbz'
```
