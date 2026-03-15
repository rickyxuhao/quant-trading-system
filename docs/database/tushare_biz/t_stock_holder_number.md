# t_stock_holder_number

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_holder_number |
| 中文名 | 股东人数表 - 来自Tushare stk_holdernumber |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 351,865 行 |
| 数据大小 | 52.64 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 截止日期 |
| `holder_num` | INT | YES | - | 股东户数 |
| `holder_num_change` | INT | YES | - | 股东户数变动 |
| `holder_num_ratio` | DECIMAL(10,4) | YES | - | 股东户数变动比例(%) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | holder_num | holder_num_change | holder_num_ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050426 | 20041231 | 666196 | NULL | NULL |
| 000001.SZ | 20050426 | 20050331 | 658855 | NULL | NULL |
| 000001.SZ | 20050819 | 20050630 | 645701 | NULL | NULL |
| 000001.SZ | 20051029 | 20050930 | 630989 | NULL | NULL |
| 000001.SZ | 20060401 | 20051231 | 621312 | NULL | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_holder_number` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '截止日期',
  `holder_num` int DEFAULT NULL COMMENT '股东户数',
  `holder_num_change` int DEFAULT NULL COMMENT '股东户数变动',
  `holder_num_ratio` decimal(10,4) DEFAULT NULL COMMENT '股东户数变动比例(%)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股东人数表 - 来自Tushare stk_holdernumber'
```
