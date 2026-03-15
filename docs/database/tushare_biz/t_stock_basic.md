# t_stock_basic

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_basic |
| 中文名 | 股票基础信息表 - 来自Tushare stock_basic |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 6,005 行 |
| 数据大小 | 2.44 MB |
| 索引大小 | 1.45 MB |
| 创建时间 | 2026-03-06 13:24:29 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `symbol` | VARCHAR(20) | YES | - | 股票代码 |
| `name` | VARCHAR(100) | YES | - | 股票名称 |
| `area` | VARCHAR(50) | YES | - | 地域 |
| `industry` | VARCHAR(100) | YES | - | 所属行业 |
| `fullname` | VARCHAR(200) | YES | - | 股票全称 |
| `enname` | VARCHAR(200) | YES | - | 英文全称 |
| `cnspell` | VARCHAR(100) | YES | - | 拼音缩写 |
| `market` | VARCHAR(20) | YES | - | 市场类型（主板/创业板/科创板/CDR） |
| `exchange` | VARCHAR(20) | YES | - | 交易所代码 |
| `curr_type` | VARCHAR(20) | YES | - | 交易货币 |
| `list_status` | VARCHAR(10) | YES | - | 上市状态 L上市 D退市 G过会未交易 P暂停上市 |
| `list_date` | VARCHAR(8) | YES | - | 上市日期 YYYYMMDD |
| `delist_date` | VARCHAR(8) | YES | - | 退市日期 YYYYMMDD |
| `is_hs` | VARCHAR(10) | YES | - | 是否沪深港通标的 N否 H沪股通 S深股通 |
| `act_name` | VARCHAR(100) | YES | - | 实控人名称 |
| `act_ent_type` | VARCHAR(50) | YES | - | 实控人企业性质 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | 记录更新时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_area | 普通 | area | - |
| idx_industry | 普通 | industry | - |
| idx_list_date | 普通 | list_date | - |
| idx_list_status | 普通 | list_status | - |
| idx_market | 普通 | market | - |
| idx_symbol | 普通 | symbol | - |
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | symbol | name | area | industry | fullname |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 000001 | 平安银行 | 深圳 | 银行 | 平安银行股份有限公司 |
| 000002.SZ | 000002 | 万科Ａ | 深圳 | 全国地产 | 万科企业股份有限公司 |
| 000003.SZ | 000003 | PT金田A(退) | NULL | NULL | 金田实业(集团)股份有限公司 |
| 000004.SZ | 000004 | *ST国华 | 深圳 | 软件服务 | 深圳国华网安科技股份有限公司 |
| 000005.SZ | 000005 | ST星源(退) | NULL | NULL | 深圳世纪星源股份有限公司 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_basic` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `symbol` varchar(20) DEFAULT NULL COMMENT '股票代码',
  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `area` varchar(50) DEFAULT NULL COMMENT '地域',
  `industry` varchar(100) DEFAULT NULL COMMENT '所属行业',
  `fullname` varchar(200) DEFAULT NULL COMMENT '股票全称',
  `enname` varchar(200) DEFAULT NULL COMMENT '英文全称',
  `cnspell` varchar(100) DEFAULT NULL COMMENT '拼音缩写',
  `market` varchar(20) DEFAULT NULL COMMENT '市场类型（主板/创业板/科创板/CDR）',
  `exchange` varchar(20) DEFAULT NULL COMMENT '交易所代码',
  `curr_type` varchar(20) DEFAULT NULL COMMENT '交易货币',
  `list_status` varchar(10) DEFAULT NULL COMMENT '上市状态 L上市 D退市 G过会未交易 P暂停上市',
  `list_date` varchar(8) DEFAULT NULL COMMENT '上市日期 YYYYMMDD',
  `delist_date` varchar(8) DEFAULT NULL COMMENT '退市日期 YYYYMMDD',
  `is_hs` varchar(10) DEFAULT NULL COMMENT '是否沪深港通标的 N否 H沪股通 S深股通',
  `act_name` varchar(100) DEFAULT NULL COMMENT '实控人名称',
  `act_ent_type` varchar(50) DEFAULT NULL COMMENT '实控人企业性质',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`ts_code`),
  KEY `idx_symbol` (`symbol`),
  KEY `idx_industry` (`industry`),
  KEY `idx_market` (`market`),
  KEY `idx_list_status` (`list_status`),
  KEY `idx_list_date` (`list_date`),
  KEY `idx_area` (`area`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票基础信息表 - 来自Tushare stock_basic'
```
