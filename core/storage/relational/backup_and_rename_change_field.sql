-- ============================================
-- 备份并重命名 t_stock_dailymarketdata 表的 change 字段
-- 原因: change 是 MySQL 保留关键字，导致 SQL 查询报错
-- 目标: 将 `change` 重命名为 `change_amount`
-- ============================================

-- 1. 备份原表数据（重要！）
-- 创建备份表，包含所有数据
CREATE TABLE IF NOT EXISTS t_stock_dailymarketdata_backup_$(date +%Y%m%d) AS
SELECT * FROM t_stock_dailymarketdata;

-- 或者使用 mysqldump 命令行备份（推荐）:
-- mysqldump -u username -p tushare_biz t_stock_dailymarketdata > t_stock_dailymarketdata_backup_$(date +%Y%m%d).sql

-- 2. 执行字段重命名
-- MySQL 8.0+ 使用 RENAME COLUMN 语法
ALTER TABLE t_stock_dailymarketdata
    RENAME COLUMN `change` TO `change_amount`;

-- 对于 MySQL 5.7，使用 CHANGE COLUMN 语法:
-- ALTER TABLE t_stock_dailymarketdata
--     CHANGE COLUMN `change` `change_amount` DECIMAL(16,4) COMMENT '涨跌额';

-- 3. 验证修改结果
DESCRIBE t_stock_dailymarketdata;

-- 4. 检查数据是否正常
SELECT COUNT(*) as total_rows FROM t_stock_dailymarketdata;
SELECT ts_code, trade_date, change_amount, pct_chg
FROM t_stock_dailymarketdata
LIMIT 5;
