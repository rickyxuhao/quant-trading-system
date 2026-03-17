-- 因子预计算 SQL 优化
-- 使用 MySQL 8.0+ 窗口函数批量计算所有因子
-- 目标：单次查询返回所有因子，替代 Python 逐股循环

-- ============================================================
-- 1. 收益与波动率计算 CTE
-- ============================================================
-- 使用 LAG() 窗口函数计算多周期收益
-- 使用 STDDEV() OVER 计算滚动波动率

WITH price_returns AS (
    SELECT
        ts_code,
        trade_date,
        close,
        -- 5日收益
        LAG(close, 5) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_5d_ago,
        -- 20日收益
        LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_20d_ago,
        -- 60日收益
        LAG(close, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_60d_ago,
        -- 20日波动率（年化）
        STDDEV(pct_chg) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) * SQRT(252) as volatility_20d,
        -- 60日波动率（年化）
        STDDEV(pct_chg) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 59 PRECEDING
        ) * SQRT(252) as volatility_60d,
        -- 20日平均成交量
        AVG(vol) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) as avg_vol_20d,
        -- 5日平均成交量
        AVG(vol) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 4 PRECEDING
        ) as avg_vol_5d,
        vol as current_vol
    FROM t_stock_dailymarketdata
    WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 120 DAY) AND %s
)
SELECT
    ts_code,
    trade_date,
    (close / NULLIF(close_20d_ago, 0) - 1) as return_20d,
    (close / NULLIF(close_60d_ago, 0) - 1) as return_60d,
    volatility_20d,
    volatility_60d,
    avg_vol_5d / NULLIF(avg_vol_20d, 0) as volume_ratio,
    avg_vol_20d as turnover_20d
FROM price_returns
WHERE trade_date = %s;


-- ============================================================
-- 2. 资金流向聚合 CTE
-- ============================================================

WITH moneyflow_agg AS (
    SELECT
        ts_code,
        trade_date,
        net_mf_amount,
        -- 当日主力净流入占比（简化版）
        net_mf_amount / NULLIF(amount * 10000, 0) as main_net_inflow_ratio,
        -- 5日净流入
        SUM(net_mf_amount) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 4 PRECEDING
        ) as net_inflow_5d,
        -- 20日净流入
        SUM(net_mf_amount) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) as net_inflow_20d,
        -- 大单净流入（简化版：使用主力净流入作为代理）
        net_mf_amount as large_order_net_amount
    FROM t_stock_moneyflow
    WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 30 DAY) AND %s
)
SELECT
    ts_code,
    trade_date,
    main_net_inflow_ratio,
    net_inflow_5d,
    net_inflow_20d,
    large_order_net_amount
FROM moneyflow_agg
WHERE trade_date = %s;


-- ============================================================
-- 3. 横截面 Z-Score 计算（单日期批量）
-- ============================================================

WITH factor_stats AS (
    SELECT
        trade_date,
        AVG(pe_ttm) as pe_mean,
        STDDEV(pe_ttm) as pe_std,
        AVG(pb) as pb_mean,
        STDDEV(pb) as pb_std,
        AVG(ps_ttm) as ps_mean,
        STDDEV(ps_ttm) as ps_std,
        AVG(total_mv) as mv_mean,
        STDDEV(total_mv) as mv_std
    FROM t_stock_daily_basic
    WHERE trade_date = %s
    GROUP BY trade_date
),
processed_factors AS (
    SELECT
        d.ts_code,
        d.trade_date,
        d.pe_ttm,
        d.pb,
        d.ps_ttm,
        d.pcf_ncf_ttm as pcf,
        d.dv_ttm as dividend_yield,
        d.total_mv,
        d.circ_mv,
        LN(d.total_mv) as log_mv,
        -- Z-Score 计算
        (d.pe_ttm - s.pe_mean) / NULLIF(s.pe_std, 0) as pe_ttm_zscore,
        (d.pb - s.pb_mean) / NULLIF(s.pb_std, 0) as pb_zscore,
        (d.ps_ttm - s.ps_mean) / NULLIF(s.ps_std, 0) as ps_ttm_zscore,
        (d.total_mv - s.mv_mean) / NULLIF(s.mv_std, 0) as mv_zscore
    FROM t_stock_daily_basic d
    JOIN factor_stats s ON d.trade_date = s.trade_date
    WHERE d.trade_date = %s
)
SELECT * FROM processed_factors;


-- ============================================================
-- 4. 统一因子查询（单次查询所有因子）
-- ============================================================
-- 这是主查询，整合所有因子计算

WITH
-- 4.1 价格与收益数据
price_data AS (
    SELECT
        ts_code,
        trade_date,
        close,
        vol,
        amount,
        pct_chg,
        LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_20d_ago,
        LAG(close, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_60d_ago,
        STDDEV(pct_chg) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) * SQRT(252) as volatility_20d,
        STDDEV(pct_chg) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 59 PRECEDING
        ) * SQRT(252) as volatility_60d,
        AVG(vol) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) as avg_vol_20d,
        AVG(vol) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 4 PRECEDING
        ) as avg_vol_5d
    FROM t_stock_dailymarketdata
    WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 120 DAY) AND %s
),
price_today AS (
    SELECT
        ts_code,
        trade_date,
        (close / NULLIF(close_20d_ago, 0) - 1) as return_20d,
        (close / NULLIF(close_60d_ago, 0) - 1) as return_60d,
        volatility_20d,
        volatility_60d,
        avg_vol_5d / NULLIF(avg_vol_20d, 0) as volume_ratio,
        avg_vol_20d as turnover_20d
    FROM price_data
    WHERE trade_date = %s
),

-- 4.2 资金流向数据
moneyflow_data AS (
    SELECT
        ts_code,
        trade_date,
        net_mf_amount,
        buy_elg_amount - sell_elg_amount as large_order_net_amount,
        SUM(net_mf_amount) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 4 PRECEDING
        ) as net_inflow_5d,
        SUM(net_mf_amount) OVER (
            PARTITION BY ts_code
            ORDER BY trade_date
            ROWS 19 PRECEDING
        ) as net_inflow_20d
    FROM t_stock_moneyflow
    WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 30 DAY) AND %s
),
moneyflow_today AS (
    SELECT
        ts_code,
        trade_date,
        net_mf_amount as main_net_inflow,
        large_order_net_amount,
        net_inflow_5d,
        net_inflow_20d,
        CASE WHEN amount > 0 THEN net_mf_amount / (amount * 10000) ELSE 0 END as main_net_inflow_ratio
    FROM moneyflow_data
    WHERE trade_date = %s
),

-- 4.3 估值与基本面数据
valuation_data AS (
    SELECT
        ts_code,
        trade_date,
        pe_ttm,
        pb,
        ps_ttm,
        pcf_ncf_ttm as pcf,
        dv_ttm as dividend_yield,
        total_mv * 10000 as total_mv,
        circ_mv * 10000 as circ_mv,
        LN(total_mv) as log_mv
    FROM t_stock_daily_basic
    WHERE trade_date = %s
),

-- 4.4 横截面统计（用于Z-score计算）
cross_sectional_stats AS (
    SELECT
        AVG(pe_ttm) as pe_mean,
        STDDEV(pe_ttm) as pe_std,
        AVG(pb) as pb_mean,
        STDDEV(pb) as pb_std,
        AVG(ps_ttm) as ps_mean,
        STDDEV(ps_ttm) as ps_std,
        AVG(total_mv) as mv_mean,
        STDDEV(total_mv) as mv_std,
        AVG(return_20d) as ret20_mean,
        STDDEV(return_20d) as ret20_std,
        AVG(volatility_20d) as vol20_mean,
        STDDEV(volatility_20d) as vol20_std
    FROM valuation_data v
    LEFT JOIN price_today p ON v.ts_code = p.ts_code
),

-- 4.5 行业分类数据
industry_data AS (
    SELECT
        d.ts_code,
        b.industry
    FROM (
        SELECT DISTINCT ts_code FROM valuation_data
    ) d
    LEFT JOIN t_stock_basic b ON d.ts_code = b.ts_code
),

-- 4.6 行业收益统计
industry_returns AS (
    SELECT
        i.industry,
        AVG(p.return_20d) as sector_return_20d,
        AVG(p.return_60d) as sector_return_60d,
        COUNT(*) as sector_stock_count
    FROM price_today p
    JOIN industry_data i ON p.ts_code = i.ts_code
    WHERE i.industry IS NOT NULL
    GROUP BY i.industry
)

-- 4.7 最终因子整合
SELECT
    v.ts_code,
    %s as trade_date,

    -- 估值因子 (8个)
    v.pe_ttm,
    v.pb,
    v.ps_ttm,
    v.pcf,
    v.dividend_yield,
    v.total_mv,
    v.circ_mv,
    v.log_mv,

    -- 收益特征 (6个)
    p.return_20d,
    p.return_60d,
    p.volatility_20d,
    p.volatility_60d,
    p.volume_ratio,
    p.turnover_20d,

    -- 资金流向 (6个)
    COALESCE(m.large_order_net_amount / NULLIF(v.amount * 10000, 0), 0) as large_order_net_ratio,
    COALESCE(m.main_net_inflow, 0) as main_net_inflow,
    COALESCE(m.net_inflow_5d, 0) as net_inflow_5d,
    COALESCE(m.net_inflow_20d, 0) as net_inflow_20d,

    -- 横截面Z-score (7个)
    (v.pe_ttm - cs.pe_mean) / NULLIF(cs.pe_std, 0) as pe_ttm_zscore,
    (v.pb - cs.pb_mean) / NULLIF(cs.pb_std, 0) as pb_zscore,
    (v.ps_ttm - cs.ps_mean) / NULLIF(cs.ps_std, 0) as ps_ttm_zscore,
    (p.return_20d - cs.ret20_mean) / NULLIF(cs.ret20_std, 0) as return_20d_zscore,
    (p.volatility_20d - cs.vol20_mean) / NULLIF(cs.vol20_std, 0) as volatility_20d_zscore,

    -- 行业相对 (4个)
    p.return_20d - COALESCE(ir.sector_return_20d, 0) as sector_alpha_20d,
    p.return_60d - COALESCE(ir.sector_return_60d, 0) as sector_alpha_60d,
    CASE
        WHEN ir.sector_return_20d IS NOT NULL THEN
            PERCENT_RANK() OVER (
                PARTITION BY i.industry
                ORDER BY p.return_20d
            )
        ELSE NULL
    END as sector_rank_20d,

    -- 市场相对 (4个)
    p.return_20d - COALESCE((SELECT AVG(return_20d) FROM price_today), 0) as market_alpha_20d,
    p.return_60d - COALESCE((SELECT AVG(return_60d) FROM price_today), 0) as market_alpha_60d

FROM valuation_data v
LEFT JOIN price_today p ON v.ts_code = p.ts_code
LEFT JOIN moneyflow_today m ON v.ts_code = m.ts_code
LEFT JOIN industry_data i ON v.ts_code = i.ts_code
LEFT JOIN industry_returns ir ON i.industry = ir.industry
CROSS JOIN cross_sectional_stats cs
WHERE v.ts_code IN ({stock_placeholders})
ORDER BY v.ts_code;


-- ============================================================
-- 5. 存储过程：批量预计算单日因子
-- ============================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS sp_calculate_factors_for_date(
    IN p_trade_date VARCHAR(8)
)
BEGIN
    -- 计算起始日期
    SET @start_date = DATE_SUB(STR_TO_DATE(p_trade_date, '%Y%m%d'), INTERVAL 120 DAY);
    SET @end_date = STR_TO_DATE(p_trade_date, '%Y%m%d');

    -- 删除已存在的数据
    DELETE FROM t_precomputed_factors WHERE trade_date = p_trade_date;

    -- 插入新计算的因子
    INSERT INTO t_precomputed_factors (
        trade_date, ts_code,
        pe_ttm, pb, ps_ttm, pcf, dividend_yield, total_mv, circ_mv, log_mv,
        return_20d, return_60d, volatility_20d, volatility_60d, volume_ratio, turnover_20d,
        net_inflow_5d, net_inflow_20d,
        pe_ttm_zscore, pb_zscore
    )
    WITH price_data AS (
        SELECT
            ts_code,
            trade_date,
            close,
            vol,
            pct_chg,
            LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_20d_ago,
            LAG(close, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) as close_60d_ago,
            STDDEV(pct_chg) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING
            ) * SQRT(252) as volatility_20d,
            STDDEV(pct_chg) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 59 PRECEDING
            ) * SQRT(252) as volatility_60d,
            AVG(vol) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING
            ) as avg_vol_20d,
            AVG(vol) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 4 PRECEDING
            ) as avg_vol_5d
        FROM t_stock_dailymarketdata
        WHERE trade_date BETWEEN @start_date AND @end_date
    ),
    moneyflow_agg AS (
        SELECT
            ts_code,
            trade_date,
            SUM(net_mf_amount) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 4 PRECEDING
            ) as net_inflow_5d,
            SUM(net_mf_amount) OVER (
                PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING
            ) as net_inflow_20d
        FROM t_stock_moneyflow
        WHERE trade_date BETWEEN DATE_SUB(@end_date, INTERVAL 30 DAY) AND @end_date
    ),
    factor_stats AS (
        SELECT
            AVG(pe_ttm) as pe_mean,
            STDDEV(pe_ttm) as pe_std,
            AVG(pb) as pb_mean,
            STDDEV(pb) as pb_std
        FROM t_stock_daily_basic
        WHERE trade_date = p_trade_date
    )
    SELECT
        p_trade_date,
        p.ts_code,
        v.pe_ttm,
        v.pb,
        v.ps_ttm,
        v.pcf_ncf_ttm,
        v.dv_ttm,
        v.total_mv * 10000,
        v.circ_mv * 10000,
        LN(v.total_mv),
        (p.close / NULLIF(p.close_20d_ago, 0) - 1),
        (p.close / NULLIF(p.close_60d_ago, 0) - 1),
        p.volatility_20d,
        p.volatility_60d,
        p.avg_vol_5d / NULLIF(p.avg_vol_20d, 0),
        p.avg_vol_20d,
        m.net_inflow_5d,
        m.net_inflow_20d,
        (v.pe_ttm - fs.pe_mean) / NULLIF(fs.pe_std, 0),
        (v.pb - fs.pb_mean) / NULLIF(fs.pb_std, 0)
    FROM price_data p
    JOIN t_stock_daily_basic v ON p.ts_code = v.ts_code AND v.trade_date = p_trade_date
    LEFT JOIN moneyflow_agg m ON p.ts_code = m.ts_code AND m.trade_date = p_trade_date
    CROSS JOIN factor_stats fs
    WHERE p.trade_date = p_trade_date;

END //

DELIMITER ;


-- ============================================================
-- 6. 性能优化索引
-- ============================================================

-- 为窗口函数查询添加必要的索引
CREATE INDEX IF NOT EXISTS idx_daily_market_ts_date ON t_stock_dailymarketdata(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_moneyflow_ts_date ON t_stock_moneyflow(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_basic_date ON t_stock_daily_basic(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_basic_ts_date ON t_stock_daily_basic(ts_code, trade_date);
