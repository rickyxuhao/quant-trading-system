# transactions

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | transactions |
| 中文名 | 交易记录表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 0 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-12 10:32:09 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `trade_date` | DATE | NO | - | 交易日期 |
| `code` | VARCHAR(20) | NO | - | 资产代码 |
| `name` | VARCHAR(50) | YES | - | 资产名称 |
| `asset_type` | ENUM | YES | - | 资产类型 |
| `trade_type` | ENUM | NO | - | 交易类型 |
| `volume` | DECIMAL(12,4) | NO | - | 交易数量/份额 |
| `price` | DECIMAL(12,4) | NO | - | 成交价格 |
| `amount` | DECIMAL(15,2) | YES | - | 成交金额 |
| `commission` | DECIMAL(10,2) | YES | - | 佣金 |
| `stamp_tax` | DECIMAL(10,2) | YES | - | 印花税 |
| `transfer_fee` | DECIMAL(10,2) | YES | - | 过户费 |
| `other_fee` | DECIMAL(10,2) | YES | - | 其他费用 |
| `fee` | DECIMAL(10,2) | YES | - | 总手续费 |
| `strategy` | VARCHAR(50) | YES | - | 策略名称 |
| `notes` | TEXT | YES | - | 备注 |
| `created_at` | DATETIME | YES | - | 记录创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_code_date | 普通 | code, trade_date | - |
| ix_transactions_trade_date | 普通 | trade_date | - |
| PRIMARY | 主键 | id | - |

## 建表语句

```sql
CREATE TABLE `transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL COMMENT '交易日期',
  `code` varchar(20) NOT NULL COMMENT '资产代码',
  `name` varchar(50) DEFAULT NULL COMMENT '资产名称',
  `asset_type` enum('STOCK','FUND_ETF','FUND_LOF','FUND_OE','BOND','CASH') DEFAULT NULL COMMENT '资产类型',
  `trade_type` enum('BUY','SELL') NOT NULL COMMENT '交易类型',
  `volume` decimal(12,4) NOT NULL COMMENT '交易数量/份额',
  `price` decimal(12,4) NOT NULL COMMENT '成交价格',
  `amount` decimal(15,2) DEFAULT NULL COMMENT '成交金额',
  `commission` decimal(10,2) DEFAULT NULL COMMENT '佣金',
  `stamp_tax` decimal(10,2) DEFAULT NULL COMMENT '印花税',
  `transfer_fee` decimal(10,2) DEFAULT NULL COMMENT '过户费',
  `other_fee` decimal(10,2) DEFAULT NULL COMMENT '其他费用',
  `fee` decimal(10,2) DEFAULT NULL COMMENT '总手续费',
  `strategy` varchar(50) DEFAULT NULL COMMENT '策略名称',
  `notes` text COMMENT '备注',
  `created_at` datetime DEFAULT NULL COMMENT '记录创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_transactions_trade_date` (`trade_date`),
  KEY `idx_code_date` (`code`,`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='交易记录表'
```
