-- 预计算因子表
-- 用于存储每日批量计算的横截面因子，支持快速回测
-- 存储估算: 4500只股票 × 250天 × 40因子 × 4字节 ≈ 180MB/年

CREATE TABLE IF NOT EXISTS t_precomputed_factors (
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期YYYYMMDD',
    ts_code VARCHAR(16) NOT NULL COMMENT '股票代码',

    -- 估值因子 (8个)
    pe_ttm FLOAT COMMENT '市盈率TTM',
    pb FLOAT COMMENT '市净率',
    ps_ttm FLOAT COMMENT '市销率TTM',
    pcf FLOAT COMMENT '市现率',
    dividend_yield FLOAT COMMENT '股息率',
    total_mv FLOAT COMMENT '总市值(元)',
    circ_mv FLOAT COMMENT '流通市值(元)',
    log_mv FLOAT COMMENT '对数市值',

    -- 盈利能力因子 (5个)
    roe FLOAT COMMENT '净资产收益率',
    roa FLOAT COMMENT '总资产收益率',
    gross_margin FLOAT COMMENT '毛利率',
    net_margin FLOAT COMMENT '净利率',
    operating_margin FLOAT COMMENT '营业利润率',

    -- 成长因子 (4个)
    revenue_yoy FLOAT COMMENT '营收同比增长率',
    profit_yoy FLOAT COMMENT '净利润同比增长率',
    roe_yoy FLOAT COMMENT 'ROE同比增长率',
    asset_growth FLOAT COMMENT '总资产同比增长率',

    -- 资金流向因子 (6个)
    large_order_net_ratio FLOAT COMMENT '大单净流入占比',
    main_net_inflow FLOAT COMMENT '主力净流入(元)',
    retail_net_inflow FLOAT COMMENT '散户净流入(元)',
    net_inflow_5d FLOAT COMMENT '5日净流入(元)',
    net_inflow_20d FLOAT COMMENT '20日净流入(元)',

    -- 收益特征 (6个)
    return_20d FLOAT COMMENT '20日收益率',
    return_60d FLOAT COMMENT '60日收益率',
    volatility_20d FLOAT COMMENT '20日波动率(年化)',
    volatility_60d FLOAT COMMENT '60日波动率(年化)',
    volume_ratio FLOAT COMMENT '成交量比率',
    turnover_20d FLOAT COMMENT '20日平均换手率',

    -- 行业相对 (4个)
    sector_alpha_20d FLOAT COMMENT '20日行业超额收益',
    sector_alpha_60d FLOAT COMMENT '60日行业超额收益',
    sector_rank_20d FLOAT COMMENT '20日行业内排名',
    sector_rank_60d FLOAT COMMENT '60日行业内排名',

    -- 市场相对 (4个)
    market_alpha_20d FLOAT COMMENT '20日市场超额收益',
    market_alpha_60d FLOAT COMMENT '60日市场超额收益',
    rs_20d_market FLOAT COMMENT '20日相对强弱',
    rs_60d_market FLOAT COMMENT '60日相对强弱',

    -- 横截面Z-score (7个核心因子的Z-score)
    pe_ttm_zscore FLOAT COMMENT 'PE Z-score(横截面)',
    pb_zscore FLOAT COMMENT 'PB Z-score(横截面)',
    roe_zscore FLOAT COMMENT 'ROE Z-score(横截面)',
    profit_yoy_zscore FLOAT COMMENT 'Profit Growth Z-score(横截面)',
    return_20d_zscore FLOAT COMMENT 'Return 20d Z-score(横截面)',
    volatility_20d_zscore FLOAT COMMENT 'Volatility Z-score(横截面)',
    market_alpha_20d_zscore FLOAT COMMENT 'Alpha Z-score(横截面)',

    -- 元数据
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (trade_date, ts_code),
    KEY idx_trade_date (trade_date),
    KEY idx_ts_code (ts_code),
    KEY idx_pe_zscore (trade_date, pe_ttm_zscore),
    KEY idx_roe_zscore (trade_date, roe_zscore),
    KEY idx_return_zscore (trade_date, return_20d_zscore)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预计算因子表';

-- 使用说明
-- 1. 数据填充: 运行 projects/quant_trading/strategies/ml_prediction/precomputed_factors.py
--    - 单日预计算: FactorPrecomputer.precompute_for_date(date)
--    - 批量预计算: FactorPrecomputer.batch_precompute(start_date, end_date)
--
-- 2. 查询示例:
--    -- 获取某日所有股票的因子
--    SELECT * FROM t_precomputed_factors WHERE trade_date = '20240115';
--
--    -- 获取特定股票的时序因子
--    SELECT * FROM t_precomputed_factors WHERE ts_code = '000001.SZ' ORDER BY trade_date;
--
--    -- 获取某日PE最低的股票
--    SELECT ts_code, pe_ttm FROM t_precomputed_factors
--    WHERE trade_date = '20240115' ORDER BY pe_ttm ASC LIMIT 50;
--
--    -- 获取某日在特定因子上的高分股票
--    SELECT ts_code, roe_zscore FROM t_precomputed_factors
--    WHERE trade_date = '20240115' ORDER BY roe_zscore DESC LIMIT 50;

-- 索引优化说明
-- idx_trade_date: 支持按日期快速查询
-- idx_ts_code: 支持按股票代码查询
-- idx_pe_zscore: 支持基于PE的选股
-- idx_roe_zscore: 支持基于ROE的选股
-- idx_return_zscore: 支持基于收益的选股
