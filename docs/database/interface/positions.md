# positions

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | positions |
| 中文名 | 当前持仓表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 21 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 32.00 KB |
| 创建时间 | 2026-03-12 10:32:09 |
| 更新时间 | 2026-03-13 11:32:48 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `code` | VARCHAR(20) | NO | - | 资产代码 |
| `name` | VARCHAR(50) | YES | - | 资产名称 |
| `asset_type` | ENUM | YES | - | 资产类型 |
| `volume` | DECIMAL(12,4) | YES | - | 持仓数量/份额 |
| `cost_price` | DECIMAL(12,4) | YES | - | 加权成本价 |
| `current_price` | DECIMAL(12,4) | YES | - | 当前价格/净值 |
| `market_value` | DECIMAL(15,2) | YES | - | 市值 |
| `sector` | VARCHAR(50) | YES | - | 所属行业 |
| `fund_type` | VARCHAR(20) | YES | - | 基金类型：股票型、债券型、混合型等 |
| `fund_company` | VARCHAR(50) | YES | - | 基金公司 |
| `nav` | DECIMAL(10,4) | YES | - | 最新净值 |
| `entry_date` | DATE | YES | - | 首次买入日期 |
| `updated_at` | DATETIME | YES | - | 更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| ix_positions_code | 普通 | code | - |
| PRIMARY | 主键 | id | - |
| uk_code | 唯一 | code | - |

## 数据示例

| id | code | name | asset_type | volume | cost_price |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 000708.SZ | 中信特钢 | STOCK | 600.0000 | 17.4180 |
| 2 | 002195.SZ | 岩山科技 | STOCK | 1400.0000 | 10.3640 |
| 3 | 002364.SZ | 中恒电气 | STOCK | 400.0000 | 38.1540 |
| 4 | 159870.SZ | 化工ETF嘉实 | FUND_ETF | 5700.0000 | 1.0460 |
| 5 | 159353.SZ | A500ETF嘉实 | FUND_ETF | 14200.0000 | 1.2970 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `positions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT '资产代码',
  `name` varchar(50) DEFAULT NULL COMMENT '资产名称',
  `asset_type` enum('STOCK','FUND_ETF','FUND_LOF','FUND_OE','BOND','CASH') DEFAULT NULL COMMENT '资产类型',
  `volume` decimal(12,4) DEFAULT NULL COMMENT '持仓数量/份额',
  `cost_price` decimal(12,4) DEFAULT NULL COMMENT '加权成本价',
  `current_price` decimal(12,4) DEFAULT NULL COMMENT '当前价格/净值',
  `market_value` decimal(15,2) DEFAULT NULL COMMENT '市值',
  `sector` varchar(50) DEFAULT NULL COMMENT '所属行业',
  `fund_type` varchar(20) DEFAULT NULL COMMENT '基金类型：股票型、债券型、混合型等',
  `fund_company` varchar(50) DEFAULT NULL COMMENT '基金公司',
  `nav` decimal(10,4) DEFAULT NULL COMMENT '最新净值',
  `entry_date` date DEFAULT NULL COMMENT '首次买入日期',
  `updated_at` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `ix_positions_code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='当前持仓表'
```
