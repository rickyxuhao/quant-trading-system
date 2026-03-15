# etf_basic

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | etf_basic |
| 中文名 | ETF基本信息表 - 来自Tushare fund_basic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 2,446 行 |
| 数据大小 | 496.00 KB |
| 索引大小 | 416.00 KB |
| 创建时间 | 2026-03-08 09:15:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `name` | VARCHAR(100) | YES | - | 简称 |
| `management` | VARCHAR(100) | YES | - | 管理人 |
| `custodian` | VARCHAR(100) | YES | - | 托管人 |
| `fund_type` | VARCHAR(50) | YES | - | 投资类型 |
| `found_date` | VARCHAR(8) | YES | - | 成立日期 |
| `list_date` | VARCHAR(8) | YES | - | 上市日期 |
| `issue_amount` | DECIMAL(20,4) | YES | - | 发行份额(亿) |
| `investment_style` | VARCHAR(50) | YES | - | 投资风格 |
| `nv` | DECIMAL(10,4) | YES | - | 单位净值 |
| `accum_nav` | DECIMAL(10,4) | YES | - | 累计净值 |
| `update_date` | VARCHAR(8) | YES | - | 更新日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_etf_basic_list_date | 普通 | list_date | - |
| idx_etf_basic_management | 普通 | management | - |
| idx_etf_basic_name | 普通 | name | - |
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | name | management | custodian | fund_type | found_date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 150001.SZ | 瑞福进取(退市) | 国投瑞银基金 | 中国工商银行 | 股票型 | 20120717 |
| 1500011.SZ | 瑞福进取(退市) | 国投瑞银基金 | 中国工商银行 | 股票型 | 20070717 |
| 150002.SZ | 大成优选(退市) | 大成基金 | 中国银行 | 股票型 | 20070801 |
| 150003.SZ | 建信优势(退市) | 建信基金 | 交通银行 | 股票型 | 20080319 |
| 150006.SZ | 同庆A(退市) | 长盛基金 | 中国建设银行 | 股票型 | 20090512 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `etf_basic` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `name` varchar(100) DEFAULT NULL COMMENT '简称',
  `management` varchar(100) DEFAULT NULL COMMENT '管理人',
  `custodian` varchar(100) DEFAULT NULL COMMENT '托管人',
  `fund_type` varchar(50) DEFAULT NULL COMMENT '投资类型',
  `found_date` varchar(8) DEFAULT NULL COMMENT '成立日期',
  `list_date` varchar(8) DEFAULT NULL COMMENT '上市日期',
  `issue_amount` decimal(20,4) DEFAULT NULL COMMENT '发行份额(亿)',
  `investment_style` varchar(50) DEFAULT NULL COMMENT '投资风格',
  `nv` decimal(10,4) DEFAULT NULL COMMENT '单位净值',
  `accum_nav` decimal(10,4) DEFAULT NULL COMMENT '累计净值',
  `update_date` varchar(8) DEFAULT NULL COMMENT '更新日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`),
  KEY `idx_etf_basic_name` (`name`),
  KEY `idx_etf_basic_management` (`management`),
  KEY `idx_etf_basic_list_date` (`list_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETF基本信息表 - 来自Tushare fund_basic'
```
