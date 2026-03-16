-- 查询优化示例
-- 使用批量查询代替循环查询

-- 示例1: 批量获取多只股票数据（高效）
-- 替代: 多次执行 SELECT * FROM t_stock_dailymarketdata WHERE ts_code = ?
-- 使用: IN 子句批量查询

-- 示例2: 获取股票列表的最近N天数据
WITH RECURSIVE date_range AS (
    SELECT MAX(trade_date) as max_date
    FROM t_stock_dailymarketdata
)
SELECT
    d.ts_code,
    d.trade_date,
    d.close,
    d.vol
FROM t_stock_dailymarketdata d
JOIN date_range r ON d.trade_date BETWEEN DATE_SUB(r.max_date, INTERVAL 20 DAY) AND r.max_date
WHERE d.ts_code IN ('000001.SZ', '000002.SZ', '600000.SH')
ORDER BY d.ts_code, d.trade_date;

-- 示例3: 获取移动平均线
SELECT
    ts_code,
    trade_date,
    close,
    AVG(close) OVER (
        PARTITION BY ts_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) as ma20
FROM t_stock_dailymarketdata
WHERE ts_code = '000001.SZ'
ORDER BY trade_date;

-- 示例4: 获取涨跌停股票
SELECT
    ts_code,
    trade_date,
    pct_chg,
    CASE
        WHEN pct_chg >= 9.9 THEN 'limit_up'
        WHEN pct_chg <= -9.9 THEN 'limit_down'
        ELSE 'normal'
    END as price_status
FROM t_stock_dailymarketdata
WHERE ABS(pct_chg) >= 9.9
ORDER BY trade_date DESC, pct_chg DESC
LIMIT 100;

-- 示例5: 获取行业资金流向
SELECT
    b.industry,
    d.trade_date,
    SUM(d.amount) as total_amount,
    AVG(d.pct_chg) as avg_change
FROM t_stock_dailymarketdata d
JOIN t_stock_basic b ON d.ts_code = b.ts_code
WHERE d.trade_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY b.industry, d.trade_date
ORDER BY d.trade_date DESC, total_amount DESC;
