-- 公募基金数据表结构
-- 用于存储公募基金的基础信息、净值、持仓、份额等数据

-- ========================================================
-- 公募基金基本信息表
-- ========================================================
DROP TABLE IF EXISTS t_fund_basic;
CREATE TABLE t_fund_basic (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    name VARCHAR(100) COMMENT '基金名称',
    management VARCHAR(100) COMMENT '管理人',
    custodian VARCHAR(100) COMMENT '托管人',
    fund_type VARCHAR(50) COMMENT '投资类型',
    found_date VARCHAR(8) COMMENT '成立日期',
    list_date VARCHAR(8) COMMENT '上市日期',
    issue_date VARCHAR(8) COMMENT '发行日期',
    issue_amount DECIMAL(20,4) COMMENT '发行份额(亿)',
    invest_type VARCHAR(50) COMMENT '投资风格',
    type VARCHAR(50) COMMENT '基金类型(开放式/封闭式)',
    status VARCHAR(20) COMMENT '存续状态',
    redemp_date VARCHAR(8) COMMENT '赎回开放日',
    purc_startdate VARCHAR(8) COMMENT '申购起始日',
    redemp_startdate VARCHAR(8) COMMENT '赎回起始日',
    market VARCHAR(20) COMMENT '上市市场',
    update_date VARCHAR(8) COMMENT '更新日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code)
) COMMENT='公募基金基本信息表 - 来自Tushare fund_basic';

CREATE INDEX idx_fund_basic_name ON t_fund_basic(name);
CREATE INDEX idx_fund_basic_management ON t_fund_basic(management);
CREATE INDEX idx_fund_basic_fund_type ON t_fund_basic(fund_type);
CREATE INDEX idx_fund_basic_status ON t_fund_basic(status);

-- ========================================================
-- 基金净值表
-- ========================================================
DROP TABLE IF EXISTS t_fund_nav;
CREATE TABLE t_fund_nav (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    nav_date VARCHAR(8) NOT NULL COMMENT '净值日期',
    unit_nav DECIMAL(10,4) COMMENT '单位净值',
    accum_nav DECIMAL(10,4) COMMENT '累计净值',
    accum_div DECIMAL(10,4) COMMENT '累计分红',
    net_asset DECIMAL(20,4) COMMENT '资产净值',
    total_netasset DECIMAL(20,4) COMMENT '合计资产净值',
    adj_nav DECIMAL(10,4) COMMENT '复权单位净值',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, nav_date)
) COMMENT='基金净值表 - 来自Tushare fund_nav';

CREATE INDEX idx_fund_nav_nav_date ON t_fund_nav(nav_date);
CREATE INDEX idx_fund_nav_ts_code ON t_fund_nav(ts_code);

-- ========================================================
-- 基金持仓表
-- ========================================================
DROP TABLE IF EXISTS t_fund_portfolio;
CREATE TABLE t_fund_portfolio (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    symbol VARCHAR(20) NOT NULL COMMENT '股票代码',
    name VARCHAR(100) COMMENT '股票名称',
    mkv DECIMAL(20,4) COMMENT '持有股票市值(元)',
    amount DECIMAL(20,4) COMMENT '持有股票数量(股)',
    stk_mkv_ratio DECIMAL(10,4) COMMENT '占股票市值比',
    stk_float_ratio DECIMAL(10,4) COMMENT '占流通股本比例',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, symbol)
) COMMENT='基金持仓表 - 来自Tushare fund_portfolio';

CREATE INDEX idx_fund_portfolio_end_date ON t_fund_portfolio(end_date);
CREATE INDEX idx_fund_portfolio_symbol ON t_fund_portfolio(symbol);

-- ========================================================
-- 基金份额表
-- ========================================================
DROP TABLE IF EXISTS t_fund_share;
CREATE TABLE t_fund_share (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    fd_share DECIMAL(20,4) COMMENT '基金份额(万份)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='基金份额表 - 来自Tushare fund_share';

CREATE INDEX idx_fund_share_trade_date ON t_fund_share(trade_date);
CREATE INDEX idx_fund_share_ts_code ON t_fund_share(ts_code);

-- ========================================================
-- 基金经理表
-- ========================================================
DROP TABLE IF EXISTS t_fund_manager;
CREATE TABLE t_fund_manager (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    name VARCHAR(100) NOT NULL COMMENT '基金经理姓名',
    gender VARCHAR(10) COMMENT '性别',
    birth_year VARCHAR(10) COMMENT '出生年份',
    edu VARCHAR(50) COMMENT '学历',
    nationality VARCHAR(50) COMMENT '国籍',
    begin_date VARCHAR(8) NOT NULL COMMENT '任职日期',
    end_date VARCHAR(8) COMMENT '离职日期',
    resume TEXT COMMENT '简历',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, name, begin_date)
) COMMENT='基金经理表 - 来自Tushare fund_manager';

CREATE INDEX idx_fund_manager_name ON t_fund_manager(name);
CREATE INDEX idx_fund_manager_begin_date ON t_fund_manager(begin_date);

-- ========================================================
-- 基金评级表
-- ========================================================
DROP TABLE IF EXISTS t_fund_rating;
CREATE TABLE t_fund_rating (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS基金代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    rating_agency VARCHAR(50) NOT NULL COMMENT '评级机构',
    rating_date VARCHAR(8) NOT NULL COMMENT '评级日期',
    fund_rating VARCHAR(20) COMMENT '基金星级',
    manager_rating VARCHAR(20) COMMENT '经理星级',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, rating_agency, rating_date)
) COMMENT='基金评级表 - 来自Tushare fund_rating';

CREATE INDEX idx_fund_rating_agency ON t_fund_rating(rating_agency);
CREATE INDEX idx_fund_rating_date ON t_fund_rating(rating_date);
