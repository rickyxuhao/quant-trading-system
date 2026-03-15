# t_stock_moneyflow_market

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_moneyflow_market |
| 中文名 | 沪深港通资金流向表 - 来自Tushare moneyflow_hsgt |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2,454 行 |
| 数据大小 | 256.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `trade_date` | VARCHAR(8) | NO | - | 交易日期 |
| `ggt_ss` | DECIMAL(20,4) | YES | - | 港股通(上海)(亿元) |
| `ggt_sz` | DECIMAL(20,4) | YES | - | 港股通(深圳)(亿元) |
| `hgt` | DECIMAL(20,4) | YES | - | 沪股通(亿元) |
| `sgt` | DECIMAL(20,4) | YES | - | 深股通(亿元) |
| `north_money` | DECIMAL(20,4) | YES | - | 北向资金(亿元) |
| `south_money` | DECIMAL(20,4) | YES | - | 南向资金(亿元) |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | trade_date | - |

## 数据示例

| trade_date | ggt_ss | ggt_sz | hgt | sgt | north_money |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 20141117 | 1768.0000 | NULL | 13000.0000 | NULL | 13000.0000 |
| 20141118 | 800.0000 | NULL | 4845.0000 | NULL | 4845.0000 |
| 20141119 | 253.0000 | NULL | 2612.0000 | NULL | 2612.0000 |
| 20141120 | 196.0000 | NULL | 2276.0000 | NULL | 2276.0000 |
| 20141121 | 186.0000 | NULL | 2341.0000 | NULL | 2341.0000 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_moneyflow_market` (
  `trade_date` varchar(8) NOT NULL COMMENT '交易日期',
  `ggt_ss` decimal(20,4) DEFAULT NULL COMMENT '港股通(上海)(亿元)',
  `ggt_sz` decimal(20,4) DEFAULT NULL COMMENT '港股通(深圳)(亿元)',
  `hgt` decimal(20,4) DEFAULT NULL COMMENT '沪股通(亿元)',
  `sgt` decimal(20,4) DEFAULT NULL COMMENT '深股通(亿元)',
  `north_money` decimal(20,4) DEFAULT NULL COMMENT '北向资金(亿元)',
  `south_money` decimal(20,4) DEFAULT NULL COMMENT '南向资金(亿元)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='沪深港通资金流向表 - 来自Tushare moneyflow_hsgt'
```
