# fund_info

## 表信息

| 属性 | 值 |
|:---|:---|
| 数据库 | interface |
| 表名 | fund_info |
| 中文名 | 基金基本信息表 |
| 存储引擎 | InnoDB |
| 字符集 | utf8mb4_0900_ai_ci |
| 数据量 | 9 行 |
| 数据大小 | 16.00 KB |
| 索引大小 | 16.00 KB |
| 创建时间 | 2026-03-12 10:32:09 |
| 更新时间 | 2026-03-12 11:35:17 |

## 字段列表

| 字段名 | 类型 | 是否可空 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| `id` | INT | NO | - |  |
| `code` | VARCHAR(20) | NO | - | 基金代码 |
| `name` | VARCHAR(100) | YES | - | 基金名称 |
| `fund_type` | VARCHAR(20) | YES | - | 基金类型：股票型/债券型/混合型/指数型 |
| `company` | VARCHAR(50) | YES | - | 基金公司 |
| `setup_date` | DATE | YES | - | 成立日期 |
| `management_fee` | DECIMAL(6,4) | YES | - | 管理费率 |
| `custodian_fee` | DECIMAL(6,4) | YES | - | 托管费率 |
| `purchase_fee` | DECIMAL(6,4) | YES | - | 申购费率 |
| `redemption_fee` | DECIMAL(6,4) | YES | - | 赎回费率 |
| `redemption_fee_structure` | TEXT | YES | - | 赎回费率结构JSON |
| `updated_at` | DATETIME | YES | - | 更新时间 |
| `created_at` | DATETIME | YES | - | 创建时间 |

## 索引

| 索引名 | 类型 | 字段 | 说明 |
|:---|:---|:---|:---|
| code | 唯一 | code | - |
| PRIMARY | 主键 | id | - |

## 数据示例

| id | code | name | fund_type | company | setup_date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 001122 | 鹏华弘利灵活配置混合A | 混合型 | 鹏华基金 | NULL |
| 2 | 008764 | 天弘越南市场股票(QDII)C | QDII | 天弘基金 | NULL |
| 3 | 016665 | 天弘全球高端制造混合(QDII)C | QDII | 天弘基金 | NULL |
| 4 | 013345 | 嘉实中证稀有金属主题ETF联接A | 指数型 | 嘉实基金 | NULL |
| 5 | 013172 | 华夏恒生科技ETF联接(QDII)A | QDII | 华夏基金 | NULL |

> 注：仅显示前 6 列，完整字段见上方「字段列表」。

## 建表语句

```sql
CREATE TABLE `fund_info` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT '基金代码',
  `name` varchar(100) DEFAULT NULL COMMENT '基金名称',
  `fund_type` varchar(20) DEFAULT NULL COMMENT '基金类型：股票型/债券型/混合型/指数型',
  `company` varchar(50) DEFAULT NULL COMMENT '基金公司',
  `setup_date` date DEFAULT NULL COMMENT '成立日期',
  `management_fee` decimal(6,4) DEFAULT NULL COMMENT '管理费率',
  `custodian_fee` decimal(6,4) DEFAULT NULL COMMENT '托管费率',
  `purchase_fee` decimal(6,4) DEFAULT NULL COMMENT '申购费率',
  `redemption_fee` decimal(6,4) DEFAULT NULL COMMENT '赎回费率',
  `redemption_fee_structure` text COMMENT '赎回费率结构JSON',
  `updated_at` datetime DEFAULT NULL COMMENT '更新时间',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='基金基本信息表'
```
