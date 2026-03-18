-- 指数数据表结构
-- 用于存储A股指数的基础信息、行情、成分股等数据

-- ========================================================
-- 指数基本信息表
-- ========================================================
DROP TABLE IF EXISTS t_index_basic;
CREATE TABLE t_index_basic (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS指数代码',
    name VARCHAR(100) COMMENT '指数名称',
    market VARCHAR(20) COMMENT '市场(SZ/SH)',
    publisher VARCHAR(50) COMMENT '发布方',
    category VARCHAR(50) COMMENT '指数类别',
    base_date VARCHAR(8) COMMENT '基期',
    base_point DECIMAL(10,4) COMMENT '基点点位',
    list_date VARCHAR(8) COMMENT '发布日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code)
) COMMENT='指数基本信息表 - 来自Tushare index_basic';

CREATE INDEX idx_index_basic_name ON t_index_basic(name);
CREATE INDEX idx_index_basic_market ON t_index_basic(market);
CREATE INDEX idx_index_basic_category ON t_index_basic(category);

-- ========================================================
-- 指数日线行情表
-- ========================================================
DROP TABLE IF EXISTS t_index_daily;
CREATE TABLE t_index_daily (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS指数代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日',
    open DECIMAL(10,4) COMMENT '开盘点位',
    high DECIMAL(10,4) COMMENT '最高点位',
    low DECIMAL(10,4) COMMENT '最低点位',
    close DECIMAL(10,4) COMMENT '收盘点位',
    pre_close DECIMAL(10,4) COMMENT '昨日收盘',
    chng DECIMAL(10,4) COMMENT '涨跌点位',
    pct_chg DECIMAL(10,4) COMMENT '涨跌幅(%)',
    vol DECIMAL(20,4) COMMENT '成交量(手)',
    amount DECIMAL(20,4) COMMENT '成交额(千元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='指数日线行情表 - 来自Tushare index_daily';

CREATE INDEX idx_index_daily_trade_date ON t_index_daily(trade_date);
CREATE INDEX idx_index_daily_ts_code ON t_index_daily(ts_code);

-- ========================================================
-- 指数成分和权重表
-- ========================================================
DROP TABLE IF EXISTS t_index_weight;
CREATE TABLE t_index_weight (
    index_code VARCHAR(20) NOT NULL COMMENT '指数代码',
    con_code VARCHAR(20) NOT NULL COMMENT '成分股票代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    weight DECIMAL(10,4) COMMENT '权重(%)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, con_code, trade_date)
) COMMENT='指数成分和权重表 - 来自Tushare index_weight';

CREATE INDEX idx_index_weight_trade_date ON t_index_weight(trade_date);
CREATE INDEX idx_index_weight_con_code ON t_index_weight(con_code);

-- ========================================================
-- 大盘指数每日指标表
-- ========================================================
DROP TABLE IF EXISTS t_index_indicator;
CREATE TABLE t_index_indicator (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS指数代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日',
    total_mv DECIMAL(20,4) COMMENT '当日总市值(元)',
    float_mv DECIMAL(20,4) COMMENT '当日流通市值(元)',
    total_share DECIMAL(20,4) COMMENT '当日总股本(股)',
    float_share DECIMAL(20,4) COMMENT '当日流通股本(股)',
    free_share DECIMAL(20,4) COMMENT '当日自由流通股本(股)',
    turnover_rate DECIMAL(10,4) COMMENT '换手率(%)',
    turnover_rate_f DECIMAL(10,4) COMMENT '换手率(自由流通)(%)',
    pe DECIMAL(10,4) COMMENT '市盈率',
    pe_ttm DECIMAL(10,4) COMMENT '市盈率TTM',
    pb DECIMAL(10,4) COMMENT '市净率',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='大盘指数每日指标表 - 来自Tushare index_dailybasic';

CREATE INDEX idx_index_indicator_trade_date ON t_index_indicator(trade_date);
CREATE INDEX idx_index_indicator_ts_code ON t_index_indicator(ts_code);

-- ========================================================
-- 申万行业指数日行情表
-- ========================================================
DROP TABLE IF EXISTS t_sw_daily;
CREATE TABLE t_sw_daily (
    ts_code VARCHAR(20) NOT NULL COMMENT '行业代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    name VARCHAR(100) COMMENT '行业名称',
    open DECIMAL(10,4) COMMENT '开盘指数',
    low DECIMAL(10,4) COMMENT '最低指数',
    high DECIMAL(10,4) COMMENT '最高指数',
    close DECIMAL(10,4) COMMENT '收盘指数',
    chng DECIMAL(10,4) COMMENT '涨跌点位',
    pct_chg DECIMAL(10,4) COMMENT '涨跌幅(%)',
    vol DECIMAL(20,4) COMMENT '成交量(手)',
    amount DECIMAL(20,4) COMMENT '成交额(千元)',
    pe DECIMAL(10,4) COMMENT '市盈率',
    pb DECIMAL(10,4) COMMENT '市净率',
    float_mv DECIMAL(20,4) COMMENT '流通市值(元)',
    total_mv DECIMAL(20,4) COMMENT '总市值(元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='申万行业指数日行情表 - 来自Tushare sw_daily';

CREATE INDEX idx_sw_daily_trade_date ON t_sw_daily(trade_date);
CREATE INDEX idx_sw_daily_ts_code ON t_sw_daily(ts_code);

-- ========================================================-- 申万行业分类表-- ========================================================DROP TABLE IF EXISTS t_sw_classify;
CREATE TABLE t_sw_classify (
    ts_code VARCHAR(20) NOT NULL COMMENT '行业代码',
    name VARCHAR(100) COMMENT '行业名称',
    industry_type VARCHAR(20) COMMENT '行业类型(1/2/3级)',
    parent_code VARCHAR(20) COMMENT '上级行业代码',
    level INT COMMENT '级别(1=一级,2=二级,3=三级)',    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code)
) COMMENT='申万行业分类表 - 来自Tushare index_classify';

CREATE INDEX idx_sw_classify_level ON t_sw_classify(level);
CREATE INDEX idx_sw_classify_parent ON t_sw_classify(parent_code);

-- ========================================================-- 申万行业成分股表-- ========================================================DROP TABLE IF EXISTS t_sw_member;
CREATE TABLE t_sw_member (
    index_code VARCHAR(20) NOT NULL COMMENT '行业代码',
    index_name VARCHAR(100) COMMENT '行业名称',
    con_code VARCHAR(20) NOT NULL COMMENT '成分股票代码',
    con_name VARCHAR(100) COMMENT '成分股票名称',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    level VARCHAR(20) COMMENT '行业级别(L1/L2/L3)',
    in_date VARCHAR(8) COMMENT '纳入日期',
    out_date VARCHAR(8) COMMENT '剔除日期',
    is_new INT DEFAULT 1 COMMENT '是否最新(1=是,0=否)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, con_code, trade_date)
) COMMENT='申万行业成分股表 - 来自Tushare index_member_all';

CREATE INDEX idx_sw_member_code ON t_sw_member(index_code);
CREATE INDEX idx_sw_member_con ON t_sw_member(con_code);
CREATE INDEX idx_sw_member_date ON t_sw_member(trade_date);
CREATE INDEX idx_sw_member_is_new ON t_sw_member(is_new);
