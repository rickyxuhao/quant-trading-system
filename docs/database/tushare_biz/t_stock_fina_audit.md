# t_stock_fina_audit

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_fina_audit |
| 中文名 | 财务审计意见表 - 来自Tushare fina_audit |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 66,075 行 |
| 数据大小 | 19.56 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `end_date` | VARCHAR(8) | NO | - | 报告期 |
| `audit_result` | VARCHAR(200) | YES | - | 审计结果 |
| `audit_fees` | DECIMAL(20,4) | YES | - | 审计总费用（元） |
| `audit_agency` | VARCHAR(200) | YES | - | 会计事务所 |
| `sign_account` | VARCHAR(200) | YES | - | 签字会计师 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code, end_date | - |

## 数据示例

| ts_code | ann_date | end_date | audit_result | audit_fees | audit_agency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | 20050426 | 20041231 | 带强调事项段的无保留意见 | NULL | 深圳鹏城会计师事务所 |
| 000001.SZ | 20050819 | 20050630 | 标准无保留意见 | NULL | 深圳市鹏城会计师事务所有限公司 |
| 000001.SZ | 20060401 | 20051231 | 标准无保留意见 | NULL | 深圳市鹏城会计师事务所有限公司 |
| 000001.SZ | 20060818 | 20060630 | 标准无保留意见 | NULL | 深圳市鹏城会计师事务所 |
| 000001.SZ | 20070322 | 20061231 | 标准无保留意见 | NULL | 深圳市鹏城会计师事务所有限公司 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_fina_audit` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `end_date` varchar(8) NOT NULL COMMENT '报告期',
  `audit_result` varchar(200) DEFAULT NULL COMMENT '审计结果',
  `audit_fees` decimal(20,4) DEFAULT NULL COMMENT '审计总费用（元）',
  `audit_agency` varchar(200) DEFAULT NULL COMMENT '会计事务所',
  `sign_account` varchar(200) DEFAULT NULL COMMENT '签字会计师',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='财务审计意见表 - 来自Tushare fina_audit'
```
