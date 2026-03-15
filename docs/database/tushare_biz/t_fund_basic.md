# t_fund_basic

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_fund_basic |
| 中文名 | 公募基金基本信息表 - 来自Tushare fund_basic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 15,321 行 |
| 数据大小 | 5.52 MB |
| 索引大小 | 4.98 MB |
| 创建时间 | 2026-03-08 13:52:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS基金代码 |
| `name` | VARCHAR(100) | YES | - | 基金名称 |
| `management` | VARCHAR(100) | YES | - | 管理人 |
| `custodian` | VARCHAR(100) | YES | - | 托管人 |
| `fund_type` | VARCHAR(50) | YES | - | 投资类型 |
| `found_date` | VARCHAR(8) | YES | - | 成立日期 |
| `list_date` | VARCHAR(8) | YES | - | 上市日期 |
| `issue_date` | VARCHAR(8) | YES | - | 发行日期 |
| `issue_amount` | DECIMAL(20,4) | YES | - | 发行份额(亿) |
| `invest_type` | VARCHAR(50) | YES | - | 投资风格 |
| `type` | VARCHAR(50) | YES | - | 基金类型(开放式/封闭式) |
| `status` | VARCHAR(20) | YES | - | 存续状态 |
| `redemp_date` | VARCHAR(8) | YES | - | 赎回开放日 |
| `purc_startdate` | VARCHAR(8) | YES | - | 申购起始日 |
| `redemp_startdate` | VARCHAR(8) | YES | - | 赎回起始日 |
| `market` | VARCHAR(20) | YES | - | 上市市场 |
| `update_date` | VARCHAR(8) | YES | - | 更新日期 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_fund_basic_fund_type | 普通 | fund_type | - |
| idx_fund_basic_management | 普通 | management | - |
| idx_fund_basic_name | 普通 | name | - |
| idx_fund_basic_status | 普通 | status | - |
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | name | management | custodian | fund_type | found_date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000459.OF | 英大领先回报B | 英大基金 | 广发银行 | 混合型 | 20250103 |
| 001025.OF | 银华惠增利C | 银华基金 | 中国农业银行 | 货币市场型 | 20240111 |
| 001296.OF | 长城悦享增利A | 长城基金 | 中国银行 | 债券型 | 20211123 |
| 002176.OF | 华商双翼C | 华商基金 | 中国建设银行 | 混合型 | 20230616 |
| 002504.OF | 鹏华永达中短债6个月定开A | 鹏华基金 | 中国工商银行 | 债券型 | 20230815 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_fund_basic` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS基金代码',
  `name` varchar(100) DEFAULT NULL COMMENT '基金名称',
  `management` varchar(100) DEFAULT NULL COMMENT '管理人',
  `custodian` varchar(100) DEFAULT NULL COMMENT '托管人',
  `fund_type` varchar(50) DEFAULT NULL COMMENT '投资类型',
  `found_date` varchar(8) DEFAULT NULL COMMENT '成立日期',
  `list_date` varchar(8) DEFAULT NULL COMMENT '上市日期',
  `issue_date` varchar(8) DEFAULT NULL COMMENT '发行日期',
  `issue_amount` decimal(20,4) DEFAULT NULL COMMENT '发行份额(亿)',
  `invest_type` varchar(50) DEFAULT NULL COMMENT '投资风格',
  `type` varchar(50) DEFAULT NULL COMMENT '基金类型(开放式/封闭式)',
  `status` varchar(20) DEFAULT NULL COMMENT '存续状态',
  `redemp_date` varchar(8) DEFAULT NULL COMMENT '赎回开放日',
  `purc_startdate` varchar(8) DEFAULT NULL COMMENT '申购起始日',
  `redemp_startdate` varchar(8) DEFAULT NULL COMMENT '赎回起始日',
  `market` varchar(20) DEFAULT NULL COMMENT '上市市场',
  `update_date` varchar(8) DEFAULT NULL COMMENT '更新日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`),
  KEY `idx_fund_basic_name` (`name`),
  KEY `idx_fund_basic_management` (`management`),
  KEY `idx_fund_basic_fund_type` (`fund_type`),
  KEY `idx_fund_basic_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='公募基金基本信息表 - 来自Tushare fund_basic'
```
