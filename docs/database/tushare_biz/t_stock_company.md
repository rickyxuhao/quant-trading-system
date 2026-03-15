# t_stock_company

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | tushare_biz |
| 表名 | t_stock_company |
| 中文名 | 上市公司基本信息表 - 来自Tushare stock_company |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 4,504 行 |
| 数据大小 | 26.55 MB |
| 索引大小 | 0 B |
| 创建时间 | 2026-03-07 12:22:34 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `ts_code` | VARCHAR(20) | NO | - | TS代码 |
| `exchange` | VARCHAR(20) | YES | - | 交易所代码 |
| `chairman` | VARCHAR(100) | YES | - | 董事长 |
| `manager` | VARCHAR(100) | YES | - | 总经理 |
| `secretary` | VARCHAR(100) | YES | - | 董秘 |
| `reg_capital` | DECIMAL(20,4) | YES | - | 注册资本 |
| `setup_date` | VARCHAR(8) | YES | - | 注册日期 |
| `province` | VARCHAR(50) | YES | - | 所在省份 |
| `city` | VARCHAR(50) | YES | - | 所在城市 |
| `introduction` | TEXT | YES | - | 公司介绍 |
| `website` | VARCHAR(200) | YES | - | 公司主页 |
| `email` | VARCHAR(100) | YES | - | 电子邮件 |
| `office` | VARCHAR(200) | YES | - | 办公室 |
| `employees` | INT | YES | - | 员工人数 |
| `main_business` | TEXT | YES | - | 主要业务及产品 |
| `business_scope` | TEXT | YES | - | 经营范围 |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP |  |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| PRIMARY | 主键 | ts_code | - |

## 数据示例

| ts_code | exchange | chairman | manager | secretary | reg_capital |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000001.SZ | SZSE | 谢永林 | 冀光恒 | 周强 | 1940591.8198 |
| 000002.SZ | SZSE | 黄力平 | NULL | 田钧 | 1193070.9471 |
| 000003.SZ | SZSE | 张曙欣 | 张曙欣 | NULL | 40012.0286 |
| 000004.SZ | SZSE | 黄翔 | 阮旭里 | 阮旭里 | 13238.0282 |
| 000005.SZ | SZSE | 丁芃 | 郑列列 | 丁芃 | 105853.6842 |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `t_stock_company` (
  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
  `exchange` varchar(20) DEFAULT NULL COMMENT '交易所代码',
  `chairman` varchar(100) DEFAULT NULL COMMENT '董事长',
  `manager` varchar(100) DEFAULT NULL COMMENT '总经理',
  `secretary` varchar(100) DEFAULT NULL COMMENT '董秘',
  `reg_capital` decimal(20,4) DEFAULT NULL COMMENT '注册资本',
  `setup_date` varchar(8) DEFAULT NULL COMMENT '注册日期',
  `province` varchar(50) DEFAULT NULL COMMENT '所在省份',
  `city` varchar(50) DEFAULT NULL COMMENT '所在城市',
  `introduction` text COMMENT '公司介绍',
  `website` varchar(200) DEFAULT NULL COMMENT '公司主页',
  `email` varchar(100) DEFAULT NULL COMMENT '电子邮件',
  `office` varchar(200) DEFAULT NULL COMMENT '办公室',
  `employees` int DEFAULT NULL COMMENT '员工人数',
  `main_business` text COMMENT '主要业务及产品',
  `business_scope` text COMMENT '经营范围',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='上市公司基本信息表 - 来自Tushare stock_company'
```
