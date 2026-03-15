# t_fund_manager

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_fund_manager |
| 中文名 | 基金经理表 - 来自Tushare fund_manager |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 3,503 行 |
| 数据大小 | 12.56 MB |
| 索引大小 | 528.00 KB |
| 创建时间 | 2026-03-08 13:52:23 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS基金代码 |
| `ann_date` | VARCHAR(8) | YES | - | 公告日期 |
| `name` | VARCHAR(100) | NO | - | 基金经理姓名 |
| `gender` | VARCHAR(10) | YES | - | 性别 |
| `birth_year` | VARCHAR(10) | YES | - | 出生年份 |
| `edu` | VARCHAR(50) | YES | - | 学历 |
| `nationality` | VARCHAR(50) | YES | - | 国籍 |
| `begin_date` | VARCHAR(8) | NO | - | 任职日期 |
| `end_date` | VARCHAR(8) | YES | - | 离职日期 |
| `resume` | TEXT | YES | - | 简历 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |
| `updated_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| idx_fund_manager_begin_date | 普通 | begin_date | - |
| idx_fund_manager_name | 普通 | name | - |
| PRIMARY | 主键 | ts_code, name, begin_date | - |

## 数据示例

| ts_code | ann_date | name | gender | birth_year | edu |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.OF | 20240713 | 万方方 | M | NULL | 硕士 |
| 000001.OF | 20151121 | 倪邈 | M | NULL | 硕士 |
| 000001.OF | 20221029 | 刘文成 | M | NULL | 硕士 |
| 000001.OF | 20241228 | 刘睿聪 | M | NULL | 硕士 |
| 000001.OF | 20130629 | 孙振峰 | M | 1978 | 博士 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_fund_manager` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS基金代码',
  `ann_date` varchar(8) DEFAULT NULL COMMENT '公告日期',
  `name` varchar(100) NOT NULL COMMENT '基金经理姓名',
  `gender` varchar(10) DEFAULT NULL COMMENT '性别',
  `birth_year` varchar(10) DEFAULT NULL COMMENT '出生年份',
  `edu` varchar(50) DEFAULT NULL COMMENT '学历',
  `nationality` varchar(50) DEFAULT NULL COMMENT '国籍',
  `begin_date` varchar(8) NOT NULL COMMENT '任职日期',
  `end_date` varchar(8) DEFAULT NULL COMMENT '离职日期',
  `resume` text COMMENT '简历',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`,`name`,`begin_date`),
  KEY `idx_fund_manager_name` (`name`),
  KEY `idx_fund_manager_begin_date` (`begin_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金经理表 - 来自Tushare fund_manager'
```
