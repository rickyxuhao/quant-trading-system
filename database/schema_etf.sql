-- ETF 数据表结构
-- 用于存储ETF基金的基础信息、行情、份额等数据

-- ========================================================
-- ETF 基本信息表
-- ========================================================
DROP TABLE IF EXISTS etf_basic;
CREATE TABLE etf_basic (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '简称',
    management VARCHAR(100) COMMENT '管理人',
    custodian VARCHAR(100) COMMENT '托管人',
    fund_type VARCHAR(50) COMMENT '投资类型',
    found_date VARCHAR(8) COMMENT '成立日期',
    list_date VARCHAR(8) COMMENT '上市日期',
    issue_amount DECIMAL(20,4) COMMENT '发行份额(亿)',
    investment_style VARCHAR(50) COMMENT '投资风格',
    nv DECIMAL(10,4) COMMENT '单位净值',
    accum_nav DECIMAL(10,4) COMMENT '累计净值',
    update_date VARCHAR(8) COMMENT '更新日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code)
) COMMENT='ETF基本信息表 - 来自Tushare fund_basic';

CREATE INDEX idx_etf_basic_name ON etf_basic(name);
CREATE INDEX idx_etf_basic_management ON etf_basic(management);
CREATE INDEX idx_etf_basic_list_date ON etf_basic(list_date);

-- ========================================================
-- ETF 日线行情表
-- ========================================================
DROP TABLE IF EXISTS etf_daily;
CREATE TABLE etf_daily (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    open DECIMAL(10,4) COMMENT '开盘价',
    high DECIMAL(10,4) COMMENT '最高价',
    low DECIMAL(10,4) COMMENT '最低价',
    close DECIMAL(10,4) COMMENT '收盘价',
    pre_close DECIMAL(10,4) COMMENT '昨收价',
    chng DECIMAL(10,4) COMMENT '涨跌额',
    pct_chg DECIMAL(10,4) COMMENT '涨跌幅(%)',
    vol DECIMAL(20,4) COMMENT '成交量(万手)',
    amount DECIMAL(20,4) COMMENT '成交额(万元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='ETF日线行情表 - 来自Tushare fund_daily';

CREATE INDEX idx_etf_daily_trade_date ON etf_daily(trade_date);
CREATE INDEX idx_etf_daily_ts_code ON etf_daily(ts_code);

-- ========================================================
-- ETF 份额规模表
-- ========================================================
DROP TABLE IF EXISTS etf_share;
CREATE TABLE etf_share (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    share DECIMAL(20,4) COMMENT '基金份额(万份)',
    nav_date VARCHAR(8) COMMENT '净值日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='ETF份额规模表 - 来自Tushare fund_share';

CREATE INDEX idx_etf_share_trade_date ON etf_share(trade_date);
CREATE INDEX idx_etf_share_ts_code ON etf_share(ts_code);

-- ========================================================
-- ETF 复权因子表
-- ========================================================
DROP TABLE IF EXISTS etf_adj_factor;
CREATE TABLE etf_adj_factor (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    adj_factor DECIMAL(20,6) COMMENT '复权因子',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='ETF复权因子表 - 来自Tushare fund_adj';

CREATE INDEX idx_etf_adj_factor_trade_date ON etf_adj_factor(trade_date);
CREATE INDEX idx_etf_adj_factor_ts_code ON etf_adj_factor(ts_code);

-- ========================================================
-- ETF 更新日志表
-- ========================================================
DROP TABLE IF EXISTS etf_update_log;
CREATE TABLE etf_update_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL COMMENT '表名',
    sync_date VARCHAR(8) NOT NULL COMMENT '同步日期',
    sync_type VARCHAR(20) COMMENT '同步类型(full/incremental)',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    end_time TIMESTAMP NULL COMMENT '结束时间',
    rows_fetched INT COMMENT '获取记录数',
    rows_inserted INT COMMENT '插入记录数',
    rows_updated INT COMMENT '更新记录数',
    status VARCHAR(20) COMMENT '状态(success/failed)',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='ETF更新日志表';

CREATE INDEX idx_etf_update_log_table ON etf_update_log(table_name);
CREATE INDEX idx_etf_update_log_date ON etf_update_log(sync_date);
CREATE INDEX idx_etf_update_log_status ON etf_update_log(status);
