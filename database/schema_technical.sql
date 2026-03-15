-- 技术指标数据表结构
-- 用于存储股票的技术指标计算结果

-- ========================================================
-- 股票技术指标表
-- ========================================================
DROP TABLE IF EXISTS t_stock_technical;
CREATE TABLE t_stock_technical (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS股票代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    
    -- 均线指标
    ma5 DECIMAL(10,4) COMMENT '5日均线',
    ma10 DECIMAL(10,4) COMMENT '10日均线',
    ma20 DECIMAL(10,4) COMMENT '20日均线',
    ma60 DECIMAL(10,4) COMMENT '60日均线',
    ma120 DECIMAL(10,4) COMMENT '120日均线',
    ma250 DECIMAL(10,4) COMMENT '250日均线(年线)',
    
    -- MACD指标
    macd_dif DECIMAL(10,4) COMMENT 'MACD DIF',
    macd_dea DECIMAL(10,4) COMMENT 'MACD DEA',
    macd_bar DECIMAL(10,4) COMMENT 'MACD BAR(柱状线)',
    
    -- KDJ指标
    kdj_k DECIMAL(10,4) COMMENT 'KDJ K值',
    kdj_d DECIMAL(10,4) COMMENT 'KDJ D值',
    kdj_j DECIMAL(10,4) COMMENT 'KDJ J值',
    
    -- RSI指标
    rsi6 DECIMAL(10,4) COMMENT 'RSI6',
    rsi12 DECIMAL(10,4) COMMENT 'RSI12',
    rsi24 DECIMAL(10,4) COMMENT 'RSI24',
    
    -- 布林带
    boll_upper DECIMAL(10,4) COMMENT '布林带上轨',
    boll_mid DECIMAL(10,4) COMMENT '布林带中轨',
    boll_lower DECIMAL(10,4) COMMENT '布林带下轨',
    
    -- 成交量均线
    vol_ma5 DECIMAL(20,4) COMMENT '成交量5日均值',
    vol_ma10 DECIMAL(20,4) COMMENT '成交量10日均值',
    vol_ma20 DECIMAL(20,4) COMMENT '成交量20日均值',
    
    -- 振幅和波动率
    amplitude DECIMAL(10,4) COMMENT '振幅(%)',
    volatility_20 DECIMAL(10,4) COMMENT '20日波动率',
    
    -- 价量关系指标
    price_vol_corr DECIMAL(10,4) COMMENT '价量相关系数(10日)',
    
    -- 趋势强度
    trend_strength DECIMAL(10,4) COMMENT '趋势强度(收盘价与均线偏离度)',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='股票技术指标表 - 基于日线行情计算';

CREATE INDEX idx_technical_trade_date ON t_stock_technical(trade_date);
CREATE INDEX idx_technical_ma5 ON t_stock_technical(ma5);
CREATE INDEX idx_technical_macd ON t_stock_technical(macd_bar);
CREATE INDEX idx_technical_kdj ON t_stock_technical(kdj_j);
CREATE INDEX idx_technical_rsi ON t_stock_technical(rsi6);

-- ========================================================
-- 市场情绪指标表
-- ========================================================
DROP TABLE IF EXISTS t_market_sentiment;
CREATE TABLE t_market_sentiment (
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    
    -- 涨跌统计
    rise_count INT COMMENT '上涨家数',
    fall_count INT COMMENT '下跌家数',
    flat_count INT COMMENT '平盘家数',
    rise_fall_ratio DECIMAL(10,4) COMMENT '涨跌家数比',
    
    -- 涨停跌停统计
    limit_up_count INT COMMENT '涨停家数',
    limit_down_count INT COMMENT '跌停家数',
    limit_up_down_ratio DECIMAL(10,4) COMMENT '涨停跌停比',
    
    -- 连板统计
    limit_up_2day INT COMMENT '2连板家数',
    limit_up_3day INT COMMENT '3连板家数',
    limit_up_4day_plus INT COMMENT '4连板及以上家数',
    
    -- 炸板率
    bomb_rate DECIMAL(10,4) COMMENT '炸板率(%) - 开板涨停占比',
    
    -- 换手率统计
    turnover_median DECIMAL(10,4) COMMENT '换手率中位数',
    turnover_avg DECIMAL(10,4) COMMENT '换手率平均值',
    high_turnover_count INT COMMENT '高换手股票数(换手>20%)',
    
    -- 成交量能
    total_amount DECIMAL(20,4) COMMENT '全市场成交额(亿元)',
    amount_ma5 DECIMAL(20,4) COMMENT '成交额5日均值',
    amount_ratio DECIMAL(10,4) COMMENT '成交额比例(当日/5日均值)',
    
    -- 北向资金
    north_money_in DECIMAL(20,4) COMMENT '北向资金流入(亿元)',
    north_money_cum DECIMAL(20,4) COMMENT '北向资金累计流入(亿元)',
    
    -- 市场情绪综合指标
    sentiment_score DECIMAL(10,4) COMMENT '情绪分数(-100到+100)',
    sentiment_level VARCHAR(20) COMMENT '情绪等级(极度恐慌/恐慌/中性/乐观/极度乐观)',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date)
) COMMENT='市场情绪指标表 - 基于每日行情统计';

CREATE INDEX idx_sentiment_date ON t_market_sentiment(trade_date);
CREATE INDEX idx_sentiment_score ON t_market_sentiment(sentiment_score);

-- ========================================================
-- 申万行业轮动指标表
-- ========================================================
DROP TABLE IF EXISTS t_sw_industry_rotation;
CREATE TABLE t_sw_industry_rotation (
    industry_code VARCHAR(20) NOT NULL COMMENT '行业代码',
    industry_name VARCHAR(100) COMMENT '行业名称',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    
    -- 涨跌幅排名
    change_pct DECIMAL(10,4) COMMENT '当日涨跌幅',
    rank_1day INT COMMENT '1日涨幅排名',
    rank_5day INT COMMENT '5日涨幅排名',
    rank_10day INT COMMENT '10日涨幅排名',
    rank_20day INT COMMENT '20日涨幅排名',
    
    -- 相对强弱
    rs_vs_index DECIMAL(10,4) COMMENT '相对大盘强弱(行业涨幅-大盘涨幅)',
    rs_5day DECIMAL(10,4) COMMENT '5日相对强弱',
    rs_10day DECIMAL(10,4) COMMENT '10日相对强弱',
    rs_20day DECIMAL(10,4) COMMENT '20日相对强弱',
    
    -- 成交量占比
    amount DECIMAL(20,4) COMMENT '行业成交额',
    amount_ratio DECIMAL(10,4) COMMENT '成交额占比(行业/全市场)',
    amount_ratio_change DECIMAL(10,4) COMMENT '成交额占比变化(较5日前)',
    
    -- 估值指标
    pe DECIMAL(10,4) COMMENT '市盈率',
    pb DECIMAL(10,4) COMMENT '市净率',
    pe_percentile DECIMAL(10,4) COMMENT 'PE历史分位(近2年)',
    pb_percentile DECIMAL(10,4) COMMENT 'PB历史分位(近2年)',
    
    -- 趋势评分
    trend_score DECIMAL(10,4) COMMENT '趋势评分(综合涨幅+量能+估值)',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (industry_code, trade_date)
) COMMENT='申万行业轮动指标表 - 基于sw_daily计算';

CREATE INDEX idx_sw_rotation_date ON t_sw_industry_rotation(trade_date);
CREATE INDEX idx_sw_rotation_rank ON t_sw_industry_rotation(rank_5day);
CREATE INDEX idx_sw_rotation_score ON t_sw_industry_rotation(trend_score);
