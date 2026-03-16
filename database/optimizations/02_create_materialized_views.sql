-- 物化视图优化脚本
-- 预计算常用查询结果以提高性能

-- 月度收益物化视图
DROP TABLE IF EXISTS mv_monthly_returns;
CREATE TABLE mv_monthly_returns AS
SELECT
    ts_code,
    DATE_FORMAT(trade_date, '%Y-%m') as month,
    close,
    LAG(close) OVER (PARTITION BY ts_code ORDER BY trade_date) as prev_close
FROM t_stock_dailymarketdata;

-- 添加索引
CREATE INDEX idx_monthly_returns ON mv_monthly_returns(ts_code, month);

-- 年度统计物化视图
DROP TABLE IF EXISTS mv_yearly_stats;
CREATE TABLE mv_yearly_stats AS
SELECT
    ts_code,
    YEAR(trade_date) as year,
    AVG(close) as avg_close,
    MAX(close) as max_close,
    MIN(close) as min_close,
    AVG(vol) as avg_volume,
    STDDEV(pct_chg) as volatility
FROM t_stock_dailymarketdata
GROUP BY ts_code, YEAR(trade_date);

-- 添加索引
CREATE INDEX idx_yearly_stats ON mv_yearly_stats(ts_code, year);

-- 每日市场概况物化视图
DROP TABLE IF EXISTS mv_daily_market_summary;
CREATE TABLE mv_daily_market_summary AS
SELECT
    trade_date,
    COUNT(DISTINCT ts_code) as stock_count,
    AVG(pct_chg) as avg_change,
    SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
    SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
    SUM(amount) as total_amount
FROM t_stock_dailymarketdata
GROUP BY trade_date;

-- 添加索引
CREATE INDEX idx_daily_summary ON mv_daily_market_summary(trade_date);
