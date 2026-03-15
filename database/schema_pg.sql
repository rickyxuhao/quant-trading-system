-- ========================================================
-- Tushare 数据表结构 - PostgreSQL 版本
-- 来源: Tushare Pro API
-- 数据库: tushare_biz
-- 表数量: 40张
-- 生成日期: 2026-03-07
-- ========================================================

-- 设置字符集和时区
SET client_encoding = 'UTF8';

-- ========================================================
-- 一、基础数据表 (6张)
-- ========================================================

-- 1. 股票基础信息表
DROP TABLE IF EXISTS t_stock_basic CASCADE;
CREATE TABLE t_stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    area VARCHAR(50),
    industry VARCHAR(100),
    fullname VARCHAR(200),
    enname VARCHAR(200),
    cnspell VARCHAR(100),
    market VARCHAR(20),
    exchange VARCHAR(20),
    curr_type VARCHAR(20),
    list_status VARCHAR(10),
    list_date VARCHAR(8),
    delist_date VARCHAR(8),
    is_hs VARCHAR(10),
    act_name VARCHAR(100),
    act_ent_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_basic_symbol ON t_stock_basic(symbol);
CREATE INDEX idx_stock_basic_industry ON t_stock_basic(industry);
CREATE INDEX idx_stock_basic_market ON t_stock_basic(market);
CREATE INDEX idx_stock_basic_list_status ON t_stock_basic(list_status);
CREATE INDEX idx_stock_basic_list_date ON t_stock_basic(list_date);
CREATE INDEX idx_stock_basic_area ON t_stock_basic(area);

COMMENT ON TABLE t_stock_basic IS '股票基础信息表 - 来自Tushare stock_basic';
COMMENT ON COLUMN t_stock_basic.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_basic.symbol IS '股票代码';
COMMENT ON COLUMN t_stock_basic.name IS '股票名称';
COMMENT ON COLUMN t_stock_basic.area IS '地域';
COMMENT ON COLUMN t_stock_basic.industry IS '所属行业';
COMMENT ON COLUMN t_stock_basic.fullname IS '股票全称';
COMMENT ON COLUMN t_stock_basic.enname IS '英文全称';
COMMENT ON COLUMN t_stock_basic.cnspell IS '拼音缩写';
COMMENT ON COLUMN t_stock_basic.market IS '市场类型（主板/创业板/科创板/CDR）';
COMMENT ON COLUMN t_stock_basic.exchange IS '交易所代码';
COMMENT ON COLUMN t_stock_basic.curr_type IS '交易货币';
COMMENT ON COLUMN t_stock_basic.list_status IS '上市状态 L上市 D退市 G过会未交易 P暂停上市';
COMMENT ON COLUMN t_stock_basic.list_date IS '上市日期 YYYYMMDD';
COMMENT ON COLUMN t_stock_basic.delist_date IS '退市日期 YYYYMMDD';
COMMENT ON COLUMN t_stock_basic.is_hs IS '是否沪深港通标的 N否 H沪股通 S深股通';
COMMENT ON COLUMN t_stock_basic.act_name IS '实控人名称';
COMMENT ON COLUMN t_stock_basic.act_ent_type IS '实控人企业性质';

-- 2. 交易日历表
DROP TABLE IF EXISTS t_stock_tradedate CASCADE;
CREATE TABLE t_stock_tradedate (
    exchange VARCHAR(20) NOT NULL,
    cal_date VARCHAR(8) NOT NULL,
    is_open INTEGER,
    pretrade_date VARCHAR(8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exchange, cal_date)
);

CREATE INDEX idx_tradedate_date ON t_stock_tradedate(cal_date);
CREATE INDEX idx_tradedate_is_open ON t_stock_tradedate(is_open);

COMMENT ON TABLE t_stock_tradedate IS '交易日历表 - 来自Tushare trade_cal';
COMMENT ON COLUMN t_stock_tradedate.exchange IS '交易所 SSE/SZSE';
COMMENT ON COLUMN t_stock_tradedate.cal_date IS '日历日期 YYYYMMDD';
COMMENT ON COLUMN t_stock_tradedate.is_open IS '是否交易 0休市 1交易';
COMMENT ON COLUMN t_stock_tradedate.pretrade_date IS '上一个交易日';

-- 3. 股票曾用名表
DROP TABLE IF EXISTS t_stock_name_history CASCADE;
CREATE TABLE t_stock_name_history (
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    start_date VARCHAR(8),
    end_date VARCHAR(8),
    ann_date VARCHAR(8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, start_date)
);

CREATE INDEX idx_name_history_ts_code ON t_stock_name_history(ts_code);
CREATE INDEX idx_name_history_start_date ON t_stock_name_history(start_date);

COMMENT ON TABLE t_stock_name_history IS '股票曾用名表 - 来自Tushare namechange';
COMMENT ON COLUMN t_stock_name_history.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_name_history.name IS '证券名称';
COMMENT ON COLUMN t_stock_name_history.start_date IS '开始日期';
COMMENT ON COLUMN t_stock_name_history.end_date IS '结束日期';
COMMENT ON COLUMN t_stock_name_history.ann_date IS '公告日期';

-- 4. 沪深股通成分股表
DROP TABLE IF EXISTS t_stock_hs_const CASCADE;
CREATE TABLE t_stock_hs_const (
    ts_code VARCHAR(20) NOT NULL,
    hs_type VARCHAR(10) NOT NULL,
    in_date VARCHAR(8),
    out_date VARCHAR(8),
    is_new INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, hs_type)
);

CREATE INDEX idx_hs_const_ts_code ON t_stock_hs_const(ts_code);
CREATE INDEX idx_hs_const_type ON t_stock_hs_const(hs_type);

COMMENT ON TABLE t_stock_hs_const IS '沪深股通成分股表 - 来自Tushare hs_const';
COMMENT ON COLUMN t_stock_hs_const.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_hs_const.hs_type IS '沪深港通类型 SH沪股通 SZ深股通';
COMMENT ON COLUMN t_stock_hs_const.in_date IS '纳入日期';
COMMENT ON COLUMN t_stock_hs_const.out_date IS '剔除日期';
COMMENT ON COLUMN t_stock_hs_const.is_new IS '是否最新 1是 0否';

-- 5. IPO新股列表
DROP TABLE IF EXISTS t_stock_ipo CASCADE;
CREATE TABLE t_stock_ipo (
    ts_code VARCHAR(20) PRIMARY KEY,
    sub_code VARCHAR(20),
    name VARCHAR(100),
    ipo_date VARCHAR(8),
    issue_date VARCHAR(8),
    amount DECIMAL(20,4),
    market_amount DECIMAL(20,4),
    price DECIMAL(16,4),
    pe DECIMAL(16,4),
    limit_amount DECIMAL(16,4),
    funds DECIMAL(20,4),
    ballot DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ipo_ipo_date ON t_stock_ipo(ipo_date);
CREATE INDEX idx_ipo_issue_date ON t_stock_ipo(issue_date);

COMMENT ON TABLE t_stock_ipo IS 'IPO新股列表 - 来自Tushare new_share';
COMMENT ON COLUMN t_stock_ipo.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_ipo.sub_code IS '申购代码';
COMMENT ON COLUMN t_stock_ipo.name IS '股票名称';
COMMENT ON COLUMN t_stock_ipo.ipo_date IS '上网发行日期';
COMMENT ON COLUMN t_stock_ipo.issue_date IS '上市日期';
COMMENT ON COLUMN t_stock_ipo.amount IS '发行总量（万股）';
COMMENT ON COLUMN t_stock_ipo.market_amount IS '上网发行数量（万股）';
COMMENT ON COLUMN t_stock_ipo.price IS '发行价格';
COMMENT ON COLUMN t_stock_ipo.pe IS '市盈率';
COMMENT ON COLUMN t_stock_ipo.limit_amount IS '个人申购上限（万股）';
COMMENT ON COLUMN t_stock_ipo.funds IS '募集资金总额（亿元）';
COMMENT ON COLUMN t_stock_ipo.ballot IS '中签率(%)';

-- 6. 上市公司基本信息表
DROP TABLE IF EXISTS t_stock_company CASCADE;
CREATE TABLE t_stock_company (
    ts_code VARCHAR(20) PRIMARY KEY,
    exchange VARCHAR(20),
    chairman VARCHAR(100),
    manager VARCHAR(100),
    secretary VARCHAR(100),
    reg_capital DECIMAL(20,4),
    setup_date VARCHAR(8),
    province VARCHAR(50),
    city VARCHAR(50),
    introduction TEXT,
    website VARCHAR(200),
    email VARCHAR(100),
    office VARCHAR(200),
    employees INTEGER,
    main_business TEXT,
    business_scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_company_exchange ON t_stock_company(exchange);
CREATE INDEX idx_company_province ON t_stock_company(province);
CREATE INDEX idx_company_city ON t_stock_company(city);

COMMENT ON TABLE t_stock_company IS '上市公司基本信息表 - 来自Tushare stock_company';
COMMENT ON COLUMN t_stock_company.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_company.exchange IS '交易所代码';
COMMENT ON COLUMN t_stock_company.chairman IS '董事长';
COMMENT ON COLUMN t_stock_company.manager IS '总经理';
COMMENT ON COLUMN t_stock_company.secretary IS '董秘';
COMMENT ON COLUMN t_stock_company.reg_capital IS '注册资本';
COMMENT ON COLUMN t_stock_company.setup_date IS '注册日期';
COMMENT ON COLUMN t_stock_company.province IS '所在省份';
COMMENT ON COLUMN t_stock_company.city IS '所在城市';
COMMENT ON COLUMN t_stock_company.introduction IS '公司介绍';
COMMENT ON COLUMN t_stock_company.website IS '公司主页';
COMMENT ON COLUMN t_stock_company.email IS '电子邮件';
COMMENT ON COLUMN t_stock_company.office IS '办公室';
COMMENT ON COLUMN t_stock_company.employees IS '员工人数';
COMMENT ON COLUMN t_stock_company.main_business IS '主要业务及产品';
COMMENT ON COLUMN t_stock_company.business_scope IS '经营范围';

-- ========================================================
-- 二、行情数据表 (8张)
-- ========================================================

-- 7. 股票日线行情表
DROP TABLE IF EXISTS t_stock_dailymarketdata CASCADE;
CREATE TABLE t_stock_dailymarketdata (
    ts_code VARCHAR(20) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    open DECIMAL(16,4),
    high DECIMAL(16,4),
    low DECIMAL(16,4),
    close DECIMAL(16,4),
    pre_close DECIMAL(16,4),
    change_amount DECIMAL(16,4),
    pct_chg DECIMAL(10,4),
    vol BIGINT,
    amount DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_daily_trade_date ON t_stock_dailymarketdata(trade_date);
CREATE INDEX idx_daily_vol ON t_stock_dailymarketdata(vol);
CREATE INDEX idx_daily_amount ON t_stock_dailymarketdata(amount);

COMMENT ON TABLE t_stock_dailymarketdata IS '股票日线行情表 - 来自Tushare daily';
COMMENT ON COLUMN t_stock_dailymarketdata.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_dailymarketdata.trade_date IS '交易日期 YYYYMMDD';
COMMENT ON COLUMN t_stock_dailymarketdata.open IS '开盘价';
COMMENT ON COLUMN t_stock_dailymarketdata.high IS '最高价';
COMMENT ON COLUMN t_stock_dailymarketdata.low IS '最低价';
COMMENT ON COLUMN t_stock_dailymarketdata.close IS '收盘价';
COMMENT ON COLUMN t_stock_dailymarketdata.pre_close IS '昨收价';
COMMENT ON COLUMN t_stock_dailymarketdata.change_amount IS '涨跌额';
COMMENT ON COLUMN t_stock_dailymarketdata.pct_chg IS '涨跌幅(%)';
COMMENT ON COLUMN t_stock_dailymarketdata.vol IS '成交量(手)';
COMMENT ON COLUMN t_stock_dailymarketdata.amount IS '成交额(千元)';

-- 8. 复权因子表
DROP TABLE IF EXISTS t_stock_adjfactor CASCADE;
CREATE TABLE t_stock_adjfactor (
    ts_code VARCHAR(20) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    adj_factor DECIMAL(20,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_adj_factor_date ON t_stock_adjfactor(trade_date);

COMMENT ON TABLE t_stock_adjfactor IS '复权因子表 - 来自Tushare adj_factor';
COMMENT ON COLUMN t_stock_adjfactor.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_adjfactor.trade_date IS '交易日期';
COMMENT ON COLUMN t_stock_adjfactor.adj_factor IS '复权因子';

-- 9. 每日指标表
DROP TABLE IF EXISTS t_stock_daily_basic CASCADE;
CREATE TABLE t_stock_daily_basic (
    ts_code VARCHAR(20) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    close DECIMAL(16,4),
    turnover_rate DECIMAL(10,4),
    turnover_rate_f DECIMAL(10,4),
    volume_ratio DECIMAL(10,4),
    pe DECIMAL(16,4),
    pe_ttm DECIMAL(16,4),
    pb DECIMAL(16,4),
    ps DECIMAL(16,4),
    ps_ttm DECIMAL(16,4),
    dv_ratio DECIMAL(10,4),
    dv_ttm DECIMAL(10,4),
    total_share DECIMAL(20,4),
    float_share DECIMAL(20,4),
    free_share DECIMAL(20,4),
    total_mv DECIMAL(20,4),
    circ_mv DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_daily_basic_date ON t_stock_daily_basic(trade_date);
CREATE INDEX idx_daily_basic_pe ON t_stock_daily_basic(pe);
CREATE INDEX idx_daily_basic_pb ON t_stock_daily_basic(pb);

COMMENT ON TABLE t_stock_daily_basic IS '每日指标表 - 来自Tushare daily_basic';
COMMENT ON COLUMN t_stock_daily_basic.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_daily_basic.trade_date IS '交易日期';
COMMENT ON COLUMN t_stock_daily_basic.close IS '当日收盘价';
COMMENT ON COLUMN t_stock_daily_basic.turnover_rate IS '换手率(%)';
COMMENT ON COLUMN t_stock_daily_basic.turnover_rate_f IS '换手率(自由流通股)';
COMMENT ON COLUMN t_stock_daily_basic.volume_ratio IS '量比';
COMMENT ON COLUMN t_stock_daily_basic.pe IS '市盈率(总市值/净利润)';
COMMENT ON COLUMN t_stock_daily_basic.pe_ttm IS '市盈率TTM';
COMMENT ON COLUMN t_stock_daily_basic.pb IS '市净率(总市值/净资产)';
COMMENT ON COLUMN t_stock_daily_basic.ps IS '市销率';
COMMENT ON COLUMN t_stock_daily_basic.ps_ttm IS '市销率TTM';
COMMENT ON COLUMN t_stock_daily_basic.dv_ratio IS '股息率(%)';
COMMENT ON COLUMN t_stock_daily_basic.dv_ttm IS '股息率TTM(%)';
COMMENT ON COLUMN t_stock_daily_basic.total_share IS '总股本(万股)';
COMMENT ON COLUMN t_stock_daily_basic.float_share IS '流通股本(万股)';
COMMENT ON COLUMN t_stock_daily_basic.free_share IS '自由流通股本(万股)';
COMMENT ON COLUMN t_stock_daily_basic.total_mv IS '总市值(万元)';
COMMENT ON COLUMN t_stock_daily_basic.circ_mv IS '流通市值(万元)';

-- 10. ST股票列表
DROP TABLE IF EXISTS t_stock_st_list CASCADE;
CREATE TABLE t_stock_st_list (
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    in_date VARCHAR(8),
    out_date VARCHAR(8),
    is_new INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, in_date)
);

CREATE INDEX idx_st_list_ts_code ON t_stock_st_list(ts_code);
CREATE INDEX idx_st_list_in_date ON t_stock_st_list(in_date);

COMMENT ON TABLE t_stock_st_list IS 'ST股票列表 - 来自Tushare stock_st';
COMMENT ON COLUMN t_stock_st_list.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_st_list.name IS '股票名称';
COMMENT ON COLUMN t_stock_st_list.in_date IS '纳入日期';
COMMENT ON COLUMN t_stock_st_list.out_date IS '剔除日期';
COMMENT ON COLUMN t_stock_st_list.is_new IS '是否最新';

-- 11. 每日涨跌停价格表
DROP TABLE IF EXISTS t_stock_dailylimitprice CASCADE;
CREATE TABLE t_stock_dailylimitprice (
    ts_code VARCHAR(20) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    name VARCHAR(100),
    close DECIMAL(16,4),
    pct_chg DECIMAL(10,4),
    amp DECIMAL(10,4),
    up_limit DECIMAL(16,4),
    down_limit DECIMAL(16,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_limit_price_date ON t_stock_dailylimitprice(trade_date);

COMMENT ON TABLE t_stock_dailylimitprice IS '每日涨跌停价格表 - 来自Tushare limit_list';
COMMENT ON COLUMN t_stock_dailylimitprice.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_dailylimitprice.trade_date IS '交易日期';
COMMENT ON COLUMN t_stock_dailylimitprice.name IS '股票名称';
COMMENT ON COLUMN t_stock_dailylimitprice.close IS '收盘价';
COMMENT ON COLUMN t_stock_dailylimitprice.pct_chg IS '涨跌幅(%)';
COMMENT ON COLUMN t_stock_dailylimitprice.amp IS '振幅(%)';
COMMENT ON COLUMN t_stock_dailylimitprice.up_limit IS '涨停板价';
COMMENT ON COLUMN t_stock_dailylimitprice.down_limit IS '跌停板价';

-- 12. 个股资金流向表
DROP TABLE IF EXISTS t_stock_moneyflow CASCADE;
CREATE TABLE t_stock_moneyflow (
    ts_code VARCHAR(20) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    buy_sm_vol BIGINT,
    buy_sm_amount DECIMAL(20,4),
    sell_sm_vol BIGINT,
    sell_sm_amount DECIMAL(20,4),
    buy_md_vol BIGINT,
    buy_md_amount DECIMAL(20,4),
    sell_md_vol BIGINT,
    sell_md_amount DECIMAL(20,4),
    buy_lg_vol BIGINT,
    buy_lg_amount DECIMAL(20,4),
    sell_lg_vol BIGINT,
    sell_lg_amount DECIMAL(20,4),
    buy_elg_vol BIGINT,
    buy_elg_amount DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_moneyflow_date ON t_stock_moneyflow(trade_date);

COMMENT ON TABLE t_stock_moneyflow IS '个股资金流向表 - 来自Tushare moneyflow';
COMMENT ON COLUMN t_stock_moneyflow.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_moneyflow.trade_date IS '交易日期';
COMMENT ON COLUMN t_stock_moneyflow.buy_sm_vol IS '小单买入量(手)';
COMMENT ON COLUMN t_stock_moneyflow.buy_sm_amount IS '小单买入金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.sell_sm_vol IS '小单卖出量(手)';
COMMENT ON COLUMN t_stock_moneyflow.sell_sm_amount IS '小单卖出金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.buy_md_vol IS '中单买入量(手)';
COMMENT ON COLUMN t_stock_moneyflow.buy_md_amount IS '中单买入金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.sell_md_vol IS '中单卖出量(手)';
COMMENT ON COLUMN t_stock_moneyflow.sell_md_amount IS '中单卖出金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.buy_lg_vol IS '大单买入量(手)';
COMMENT ON COLUMN t_stock_moneyflow.buy_lg_amount IS '大单买入金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.sell_lg_vol IS '大单卖出量(手)';
COMMENT ON COLUMN t_stock_moneyflow.sell_lg_amount IS '大单卖出金额(万元)';
COMMENT ON COLUMN t_stock_moneyflow.buy_elg_vol IS '特大单买入量(手)';
COMMENT ON COLUMN t_stock_moneyflow.buy_elg_amount IS '特大单买入金额(万元)';

-- 13. 沪深港通资金流向表
DROP TABLE IF EXISTS t_stock_moneyflow_market CASCADE;
CREATE TABLE t_stock_moneyflow_market (
    trade_date VARCHAR(8) PRIMARY KEY,
    ggt_ss DECIMAL(20,4),
    ggt_sz DECIMAL(20,4),
    hgt DECIMAL(20,4),
    sgt DECIMAL(20,4),
    north_money DECIMAL(20,4),
    south_money DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE t_stock_moneyflow_market IS '沪深港通资金流向表 - 来自Tushare moneyflow_hsgt';
COMMENT ON COLUMN t_stock_moneyflow_market.trade_date IS '交易日期';
COMMENT ON COLUMN t_stock_moneyflow_market.ggt_ss IS '港股通(上海)(亿元)';
COMMENT ON COLUMN t_stock_moneyflow_market.ggt_sz IS '港股通(深圳)(亿元)';
COMMENT ON COLUMN t_stock_moneyflow_market.hgt IS '沪股通(亿元)';
COMMENT ON COLUMN t_stock_moneyflow_market.sgt IS '深股通(亿元)';
COMMENT ON COLUMN t_stock_moneyflow_market.north_money IS '北向资金(亿元)';
COMMENT ON COLUMN t_stock_moneyflow_market.south_money IS '南向资金(亿元)';

-- ========================================================
-- 三、财务数据表 - 利润表 (4张)
-- ========================================================

-- 14. 利润表 - 一般工商业
DROP TABLE IF EXISTS t_stock_income CASCADE;
CREATE TABLE t_stock_income (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    basic_eps DECIMAL(20,4),
    diluted_eps DECIMAL(20,4),
    total_revenue DECIMAL(20,4),
    revenue DECIMAL(20,4),
    int_income DECIMAL(20,4),
    prem_earned DECIMAL(20,4),
    comm_income DECIMAL(20,4),
    n_commis_income DECIMAL(20,4),
    n_oth_income DECIMAL(20,4),
    n_oth_b_income DECIMAL(20,4),
    prem_income DECIMAL(20,4),
    out_prem DECIMAL(20,4),
    une_prem_reser DECIMAL(20,4),
    reins_income DECIMAL(20,4),
    n_sec_tb_income DECIMAL(20,4),
    n_sec_uw_income DECIMAL(20,4),
    n_asset_mg_income DECIMAL(20,4),
    oth_b_income DECIMAL(20,4),
    fv_value_chg_gain DECIMAL(20,4),
    invest_income DECIMAL(20,4),
    a_j_income DECIMAL(20,4),
    assets_dispos_income DECIMAL(20,4),
    total_cogs DECIMAL(20,4),
    operate_exp DECIMAL(20,4),
    int_exp DECIMAL(20,4),
    comm_exp DECIMAL(20,4),
    prem_refund DECIMAL(20,4),
    compens_payout DECIMAL(20,4),
    reser_insur_liab DECIMAL(20,4),
    policy_div_payt DECIMAL(20,4),
    reinsur_exp DECIMAL(20,4),
    operate_taxes DECIMAL(20,4),
    sale_exp DECIMAL(20,4),
    admin_exp DECIMAL(20,4),
    finan_exp DECIMAL(20,4),
    assets_impair_loss DECIMAL(20,4),
    credit_impair_loss DECIMAL(20,4),
    oth_loss DECIMAL(20,4),
    net_exp_other_business DECIMAL(20,4),
    operate_profit DECIMAL(20,4),
    noperate_income DECIMAL(20,4),
    noperate_exp DECIMAL(20,4),
    nca_disploss DECIMAL(20,4),
    total_profit DECIMAL(20,4),
    income_tax DECIMAL(20,4),
    n_income DECIMAL(20,4),
    n_income_attr_p DECIMAL(20,4),
    minority_gain DECIMAL(20,4),
    oth_compr_income DECIMAL(20,4),
    t_compr_income DECIMAL(20,4),
    compr_inc_attr_p DECIMAL(20,4),
    compr_inc_attr_m_s DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_income_ann_date ON t_stock_income(ann_date);
CREATE INDEX idx_income_f_ann_date ON t_stock_income(f_ann_date);
CREATE INDEX idx_income_end_date ON t_stock_income(end_date);

COMMENT ON TABLE t_stock_income IS '利润表 - 一般工商业 - 来自Tushare income';
COMMENT ON COLUMN t_stock_income.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_income.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_income.f_ann_date IS '实际公告日期';
COMMENT ON COLUMN t_stock_income.end_date IS '报告期';
COMMENT ON COLUMN t_stock_income.basic_eps IS '基本每股收益';
COMMENT ON COLUMN t_stock_income.diluted_eps IS '稀释每股收益';
COMMENT ON COLUMN t_stock_income.total_revenue IS '营业总收入';
COMMENT ON COLUMN t_stock_income.revenue IS '营业收入';
COMMENT ON COLUMN t_stock_income.operate_profit IS '营业利润';
COMMENT ON COLUMN t_stock_income.total_profit IS '利润总额';
COMMENT ON COLUMN t_stock_income.n_income IS '净利润';
COMMENT ON COLUMN t_stock_income.income_tax IS '所得税费用';

-- 15. 利润表 - 银行专用
DROP TABLE IF EXISTS t_stock_income_bank CASCADE;
CREATE TABLE t_stock_income_bank (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    basic_eps DECIMAL(20,4),
    diluted_eps DECIMAL(20,4),
    int_income DECIMAL(20,4),
    int_exp DECIMAL(20,4),
    n_commis_income DECIMAL(20,4),
    n_oth_income DECIMAL(20,4),
    n_oth_b_income DECIMAL(20,4),
    prem_income DECIMAL(20,4),
    out_prem DECIMAL(20,4),
    une_prem_reser DECIMAL(20,4),
    reins_income DECIMAL(20,4),
    n_sec_tb_income DECIMAL(20,4),
    n_sec_uw_income DECIMAL(20,4),
    n_asset_mg_income DECIMAL(20,4),
    oth_b_income DECIMAL(20,4),
    fv_value_chg_gain DECIMAL(20,4),
    invest_income DECIMAL(20,4),
    a_j_income DECIMAL(20,4),
    assets_dispos_income DECIMAL(20,4),
    total_cogs DECIMAL(20,4),
    operate_exp DECIMAL(20,4),
    comm_exp DECIMAL(20,4),
    prem_refund DECIMAL(20,4),
    compens_payout DECIMAL(20,4),
    reser_insur_liab DECIMAL(20,4),
    policy_div_payt DECIMAL(20,4),
    reinsur_exp DECIMAL(20,4),
    operate_taxes DECIMAL(20,4),
    sale_exp DECIMAL(20,4),
    admin_exp DECIMAL(20,4),
    finan_exp DECIMAL(20,4),
    assets_impair_loss DECIMAL(20,4),
    credit_impair_loss DECIMAL(20,4),
    oth_loss DECIMAL(20,4),
    net_exp_other_business DECIMAL(20,4),
    operate_profit DECIMAL(20,4),
    noperate_income DECIMAL(20,4),
    noperate_exp DECIMAL(20,4),
    nca_disploss DECIMAL(20,4),
    total_profit DECIMAL(20,4),
    income_tax DECIMAL(20,4),
    n_income DECIMAL(20,4),
    n_income_attr_p DECIMAL(20,4),
    minority_gain DECIMAL(20,4),
    oth_compr_income DECIMAL(20,4),
    t_compr_income DECIMAL(20,4),
    compr_inc_attr_p DECIMAL(20,4),
    compr_inc_attr_m_s DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_income_bank_ann_date ON t_stock_income_bank(ann_date);
CREATE INDEX idx_income_bank_end_date ON t_stock_income_bank(end_date);

COMMENT ON TABLE t_stock_income_bank IS '利润表 - 银行专用 - 来自Tushare income';

-- 16. 利润表 - 保险专用
DROP TABLE IF EXISTS t_stock_income_insurance CASCADE;
CREATE TABLE t_stock_income_insurance (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    basic_eps DECIMAL(20,4),
    diluted_eps DECIMAL(20,4),
    prem_earned DECIMAL(20,4),
    int_income DECIMAL(20,4),
    int_exp DECIMAL(20,4),
    comm_income DECIMAL(20,4),
    n_commis_income DECIMAL(20,4),
    n_oth_income DECIMAL(20,4),
    n_oth_b_income DECIMAL(20,4),
    out_prem DECIMAL(20,4),
    une_prem_reser DECIMAL(20,4),
    reins_income DECIMAL(20,4),
    n_sec_tb_income DECIMAL(20,4),
    n_sec_uw_income DECIMAL(20,4),
    n_asset_mg_income DECIMAL(20,4),
    oth_b_income DECIMAL(20,4),
    fv_value_chg_gain DECIMAL(20,4),
    invest_income DECIMAL(20,4),
    a_j_income DECIMAL(20,4),
    assets_dispos_income DECIMAL(20,4),
    total_cogs DECIMAL(20,4),
    operate_exp DECIMAL(20,4),
    comm_exp DECIMAL(20,4),
    prem_refund DECIMAL(20,4),
    compens_payout DECIMAL(20,4),
    reser_insur_liab DECIMAL(20,4),
    policy_div_payt DECIMAL(20,4),
    reinsur_exp DECIMAL(20,4),
    operate_taxes DECIMAL(20,4),
    sale_exp DECIMAL(20,4),
    admin_exp DECIMAL(20,4),
    finan_exp DECIMAL(20,4),
    assets_impair_loss DECIMAL(20,4),
    credit_impair_loss DECIMAL(20,4),
    oth_loss DECIMAL(20,4),
    net_exp_other_business DECIMAL(20,4),
    operate_profit DECIMAL(20,4),
    noperate_income DECIMAL(20,4),
    noperate_exp DECIMAL(20,4),
    nca_disploss DECIMAL(20,4),
    total_profit DECIMAL(20,4),
    income_tax DECIMAL(20,4),
    n_income DECIMAL(20,4),
    n_income_attr_p DECIMAL(20,4),
    minority_gain DECIMAL(20,4),
    oth_compr_income DECIMAL(20,4),
    t_compr_income DECIMAL(20,4),
    compr_inc_attr_p DECIMAL(20,4),
    compr_inc_attr_m_s DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_income_insurance_ann_date ON t_stock_income_insurance(ann_date);
CREATE INDEX idx_income_insurance_end_date ON t_stock_income_insurance(end_date);

COMMENT ON TABLE t_stock_income_insurance IS '利润表 - 保险专用 - 来自Tushare income';

-- 17. 利润表 - 证券专用
DROP TABLE IF EXISTS t_stock_income_securities CASCADE;
CREATE TABLE t_stock_income_securities (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    basic_eps DECIMAL(20,4),
    diluted_eps DECIMAL(20,4),
    comm_income DECIMAL(20,4),
    int_income DECIMAL(20,4),
    int_exp DECIMAL(20,4),
    n_commis_income DECIMAL(20,4),
    n_oth_income DECIMAL(20,4),
    n_oth_b_income DECIMAL(20,4),
    prem_income DECIMAL(20,4),
    out_prem DECIMAL(20,4),
    une_prem_reser DECIMAL(20,4),
    reins_income DECIMAL(20,4),
    n_sec_tb_income DECIMAL(20,4),
    n_sec_uw_income DECIMAL(20,4),
    n_asset_mg_income DECIMAL(20,4),
    oth_b_income DECIMAL(20,4),
    fv_value_chg_gain DECIMAL(20,4),
    invest_income DECIMAL(20,4),
    a_j_income DECIMAL(20,4),
    assets_dispos_income DECIMAL(20,4),
    total_cogs DECIMAL(20,4),
    operate_exp DECIMAL(20,4),
    comm_exp DECIMAL(20,4),
    prem_refund DECIMAL(20,4),
    compens_payout DECIMAL(20,4),
    reser_insur_liab DECIMAL(20,4),
    policy_div_payt DECIMAL(20,4),
    reinsur_exp DECIMAL(20,4),
    operate_taxes DECIMAL(20,4),
    sale_exp DECIMAL(20,4),
    admin_exp DECIMAL(20,4),
    finan_exp DECIMAL(20,4),
    assets_impair_loss DECIMAL(20,4),
    credit_impair_loss DECIMAL(20,4),
    oth_loss DECIMAL(20,4),
    net_exp_other_business DECIMAL(20,4),
    operate_profit DECIMAL(20,4),
    noperate_income DECIMAL(20,4),
    noperate_exp DECIMAL(20,4),
    nca_disploss DECIMAL(20,4),
    total_profit DECIMAL(20,4),
    income_tax DECIMAL(20,4),
    n_income DECIMAL(20,4),
    n_income_attr_p DECIMAL(20,4),
    minority_gain DECIMAL(20,4),
    oth_compr_income DECIMAL(20,4),
    t_compr_income DECIMAL(20,4),
    compr_inc_attr_p DECIMAL(20,4),
    compr_inc_attr_m_s DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_income_securities_ann_date ON t_stock_income_securities(ann_date);
CREATE INDEX idx_income_securities_end_date ON t_stock_income_securities(end_date);

COMMENT ON TABLE t_stock_income_securities IS '利润表 - 证券专用 - 来自Tushare income';

-- ========================================================
-- 四、财务数据表 - 资产负债表 (4张)
-- ========================================================

-- 18. 资产负债表 - 一般工商业
DROP TABLE IF EXISTS t_stock_balancesheet CASCADE;
CREATE TABLE t_stock_balancesheet (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    total_share DECIMAL(20,4),
    cap_rese DECIMAL(20,4),
    undistr_porfit DECIMAL(20,4),
    surplus_rese DECIMAL(20,4),
    special_rese DECIMAL(20,4),
    money_cap DECIMAL(20,4),
    trad_asset DECIMAL(20,4),
    notes_receiv DECIMAL(20,4),
    accounts_receiv DECIMAL(20,4),
    oth_receiv DECIMAL(20,4),
    prepayment DECIMAL(20,4),
    div_receiv DECIMAL(20,4),
    int_receiv DECIMAL(20,4),
    inventories DECIMAL(20,4),
    amor_exp DECIMAL(20,4),
    nca_within_1y DECIMAL(20,4),
    sett_rsrv DECIMAL(20,4),
    loanto_oth_bank_fi DECIMAL(20,4),
    premium_receiv DECIMAL(20,4),
    reinsur_receiv DECIMAL(20,4),
    reinsur_res_receiv DECIMAL(20,4),
    pur_resale_fa DECIMAL(20,4),
    oth_cur_assets DECIMAL(20,4),
    total_cur_assets DECIMAL(20,4),
    fa_avail_for_sale DECIMAL(20,4),
    htm_invest DECIMAL(20,4),
    lt_eqt_invest DECIMAL(20,4),
    invest_real_estate DECIMAL(20,4),
    time_deposits DECIMAL(20,4),
    oth_assets DECIMAL(20,4),
    lt_rec DECIMAL(20,4),
    fix_assets DECIMAL(20,4),
    cip DECIMAL(20,4),
    const_materials DECIMAL(20,4),
    fixed_assets_disp DECIMAL(20,4),
    produc_bio_assets DECIMAL(20,4),
    oil_and_gas_assets DECIMAL(20,4),
    intan_assets DECIMAL(20,4),
    r_and_d DECIMAL(20,4),
    goodwill DECIMAL(20,4),
    lt_amor_exp DECIMAL(20,4),
    defer_tax_assets DECIMAL(20,4),
    decr_in_disbur DECIMAL(20,4),
    oth_nca DECIMAL(20,4),
    total_nca DECIMAL(20,4),
    cash_reser_cb DECIMAL(20,4),
    depos_in_oth_bfi DECIMAL(20,4),
    prec_metals DECIMAL(20,4),
    deriv_assets DECIMAL(20,4),
    total_assets DECIMAL(20,4),
    c_borr_from_oth_fi DECIMAL(20,4),
    notes_payable DECIMAL(20,4),
    acct_payable DECIMAL(20,4),
    adv_receipts DECIMAL(20,4),
    sold_for_repur_fa DECIMAL(20,4),
    comm_payable DECIMAL(20,4),
    payroll_payable DECIMAL(20,4),
    taxes_payable DECIMAL(20,4),
    int_payable DECIMAL(20,4),
    div_payable DECIMAL(20,4),
    oth_payable DECIMAL(20,4),
    acc_exp DECIMAL(20,4),
    deferred_inc DECIMAL(20,4),
    st_bonds_payable DECIMAL(20,4),
    payable_to_reinsurer DECIMAL(20,4),
    rsrv_insur_cont DECIMAL(20,4),
    acting_trading_sec DECIMAL(20,4),
    acting_uw_sec DECIMAL(20,4),
    non_cur_liab_due_1y DECIMAL(20,4),
    oth_cur_liab DECIMAL(20,4),
    total_cur_liab DECIMAL(20,4),
    bonds_payable DECIMAL(20,4),
    lt_payable DECIMAL(20,4),
    specific_payables DECIMAL(20,4),
    estimated_liab DECIMAL(20,4),
    defer_tax_liab DECIMAL(20,4),
    defer_inc_non_cur_liab DECIMAL(20,4),
    oth_ncl DECIMAL(20,4),
    total_ncl DECIMAL(20,4),
    depos_oth_bfi DECIMAL(20,4),
    deriv_liab DECIMAL(20,4),
    depos_fr_non_bank DECIMAL(20,4),
    loan_oth_bank DECIMAL(20,4),
    trading_fl DECIMAL(20,4),
    notes_payable_1 DECIMAL(20,4),
    int_payable_1 DECIMAL(20,4),
    div_payable_1 DECIMAL(20,4),
    oth_payable_1 DECIMAL(20,4),
    acc_exp_1 DECIMAL(20,4),
    total_liab DECIMAL(20,4),
    rec_dep_invests DECIMAL(20,4),
    total_equity DECIMAL(20,4),
    minority_int DECIMAL(20,4),
    total_hldr_eqy_exc_min_int DECIMAL(20,4),
    total_hldr_eqy_inc_min_int DECIMAL(20,4),
    total_liab_hldr_eqy DECIMAL(20,4),
    lt_payroll_payable DECIMAL(20,4),
    oth_comp_income DECIMAL(20,4),
    oth_eqt_tools DECIMAL(20,4),
    oth_eqt_tools_p_shr DECIMAL(20,4),
    lending_funds DECIMAL(20,4),
    acc_receivable DECIMAL(20,4),
    st_fin_payable DECIMAL(20,4),
    payables DECIMAL(20,4),
    hfs_assets DECIMAL(20,4),
    hfs_sales DECIMAL(20,4),
    update_flag VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_balancesheet_ann_date ON t_stock_balancesheet(ann_date);
CREATE INDEX idx_balancesheet_end_date ON t_stock_balancesheet(end_date);

COMMENT ON TABLE t_stock_balancesheet IS '资产负债表 - 一般工商业 - 来自Tushare balancesheet';
COMMENT ON COLUMN t_stock_balancesheet.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_balancesheet.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_balancesheet.f_ann_date IS '实际公告日期';
COMMENT ON COLUMN t_stock_balancesheet.end_date IS '报告期';
COMMENT ON COLUMN t_stock_balancesheet.total_assets IS '资产总计';
COMMENT ON COLUMN t_stock_balancesheet.total_cur_assets IS '流动资产合计';
COMMENT ON COLUMN t_stock_balancesheet.total_nca IS '非流动资产合计';
COMMENT ON COLUMN t_stock_balancesheet.total_liab IS '负债合计';
COMMENT ON COLUMN t_stock_balancesheet.total_cur_liab IS '流动负债合计';
COMMENT ON COLUMN t_stock_balancesheet.total_ncl IS '非流动负债合计';
COMMENT ON COLUMN t_stock_balancesheet.total_equity IS '所有者权益合计';
COMMENT ON COLUMN t_stock_balancesheet.total_hldr_eqy_exc_min_int IS '归属于母公司所有者权益合计';

-- 19. 资产负债表 - 银行专用
DROP TABLE IF EXISTS t_stock_balancesheet_bank CASCADE;
CREATE TABLE t_stock_balancesheet_bank (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    money_cap DECIMAL(20,4),
    int_receiv DECIMAL(20,4),
    loans_to_oth_banks DECIMAL(20,4),
    trad_asset DECIMAL(20,4),
    red_monetary_cap_for_sale DECIMAL(20,4),
    notes_receiv DECIMAL(20,4),
    acct_receiv DECIMAL(20,4),
    deriv_asset DECIMAL(20,4),
    fin_receiv DECIMAL(20,4),
    pre_payment DECIMAL(20,4),
    oth_receiv DECIMAL(20,4),
    fix_assets DECIMAL(20,4),
    cip DECIMAL(20,4),
    intan_assets DECIMAL(20,4),
    oth_assets DECIMAL(20,4),
    total_cur_assets DECIMAL(20,4),
    total_nca DECIMAL(20,4),
    total_assets DECIMAL(20,4),
    loans_from_oth_banks DECIMAL(20,4),
    trad_liab DECIMAL(20,4),
    notes_payable DECIMAL(20,4),
    acct_payable DECIMAL(20,4),
    deriv_liab DECIMAL(20,4),
    funds_sold_for_repur DECIMAL(20,4),
    deposits DECIMAL(20,4),
    oth_payable DECIMAL(20,4),
    total_cur_liab DECIMAL(20,4),
    total_ncl DECIMAL(20,4),
    total_liab DECIMAL(20,4),
    deposits_in_oth_bfi DECIMAL(20,4),
    deriv_assets DECIMAL(20,4),
    prem_receiv DECIMAL(20,4),
    reinsur_receiv DECIMAL(20,4),
    oth_cur_assets DECIMAL(20,4),
    total_equity DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_balancesheet_bank_ann_date ON t_stock_balancesheet_bank(ann_date);
CREATE INDEX idx_balancesheet_bank_end_date ON t_stock_balancesheet_bank(end_date);

COMMENT ON TABLE t_stock_balancesheet_bank IS '资产负债表 - 银行专用 - 来自Tushare balancesheet';

-- 20. 资产负债表 - 保险专用
DROP TABLE IF EXISTS t_stock_balancesheet_insurance CASCADE;
CREATE TABLE t_stock_balancesheet_insurance (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    money_cap DECIMAL(20,4),
    prem_receiv DECIMAL(20,4),
    reinsur_receiv DECIMAL(20,4),
    oth_receiv DECIMAL(20,4),
    reser_insur_liab DECIMAL(20,4),
    total_cur_assets DECIMAL(20,4),
    total_nca DECIMAL(20,4),
    total_assets DECIMAL(20,4),
    oth_payable DECIMAL(20,4),
    total_cur_liab DECIMAL(20,4),
    total_ncl DECIMAL(20,4),
    total_liab DECIMAL(20,4),
    total_equity DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_balancesheet_insurance_ann_date ON t_stock_balancesheet_insurance(ann_date);
CREATE INDEX idx_balancesheet_insurance_end_date ON t_stock_balancesheet_insurance(end_date);

COMMENT ON TABLE t_stock_balancesheet_insurance IS '资产负债表 - 保险专用 - 来自Tushare balancesheet';

-- 21. 资产负债表 - 证券专用
DROP TABLE IF EXISTS t_stock_balancesheet_securities CASCADE;
CREATE TABLE t_stock_balancesheet_securities (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    money_cap DECIMAL(20,4),
    int_receiv DECIMAL(20,4),
    trad_asset DECIMAL(20,4),
    oth_receiv DECIMAL(20,4),
    fin_receiv DECIMAL(20,4),
    fix_assets DECIMAL(20,4),
    intan_assets DECIMAL(20,4),
    total_cur_assets DECIMAL(20,4),
    total_nca DECIMAL(20,4),
    total_assets DECIMAL(20,4),
    trad_liab DECIMAL(20,4),
    oth_payable DECIMAL(20,4),
    total_cur_liab DECIMAL(20,4),
    total_ncl DECIMAL(20,4),
    total_liab DECIMAL(20,4),
    total_equity DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_balancesheet_securities_ann_date ON t_stock_balancesheet_securities(ann_date);
CREATE INDEX idx_balancesheet_securities_end_date ON t_stock_balancesheet_securities(end_date);

COMMENT ON TABLE t_stock_balancesheet_securities IS '资产负债表 - 证券专用 - 来自Tushare balancesheet';

-- ========================================================
-- 五、财务数据表 - 现金流量表 (4张)
-- ========================================================

-- 22. 现金流量表 - 一般工商业
DROP TABLE IF EXISTS t_stock_cashflow CASCADE;
CREATE TABLE t_stock_cashflow (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    c_cash_equ_end_period DECIMAL(20,4),
    n_cashflow_act DECIMAL(20,4),
    c_recp_sell_goods DECIMAL(20,4),
    n_depos_incr_fi DECIMAL(20,4),
    n_incr_loans_cb DECIMAL(20,4),
    n_inc_borr_oth_fi DECIMAL(20,4),
    prem_fr_orig_contr DECIMAL(20,4),
    n_incr_insured_dep DECIMAL(20,4),
    n_reinsur_prem DECIMAL(20,4),
    n_incr_disp_tfa DECIMAL(20,4),
    ifc_cash_incr DECIMAL(20,4),
    n_incr_disp_faas DECIMAL(20,4),
    n_incr_loans_oth_bank DECIMAL(20,4),
    n_cap_incr_repur DECIMAL(20,4),
    c_fr_oth_operate_a DECIMAL(20,4),
    c_inf_fr_operate_a DECIMAL(20,4),
    c_paid_goods_s DECIMAL(20,4),
    c_paid_to_for_empl DECIMAL(20,4),
    c_paid_for_taxes DECIMAL(20,4),
    n_incr_clt_loan_adv DECIMAL(20,4),
    n_incr_dep_cbob DECIMAL(20,4),
    c_pay_claims_orig_inco DECIMAL(20,4),
    pay_handling_chrg DECIMAL(20,4),
    pay_comm_insur_plcy DECIMAL(20,4),
    oth_cash_pay_oper_act DECIMAL(20,4),
    st_cash_out_act DECIMAL(20,4),
    n_cashflow_inv_act DECIMAL(20,4),
    c_recp_disp_withdrwl_invest DECIMAL(20,4),
    c_recp_return_invest DECIMAL(20,4),
    n_recp_disp_fiolta DECIMAL(20,4),
    n_recp_disp_sobu DECIMAL(20,4),
    stot_inflows_inv_act DECIMAL(20,4),
    c_pay_acq_const_fiolta DECIMAL(20,4),
    c_paid_invest DECIMAL(20,4),
    n_disp_subs_oth_biz DECIMAL(20,4),
    oth_pay_ral_inv_act DECIMAL(20,4),
    n_incr_pledge_loan DECIMAL(20,4),
    stot_out_inv_act DECIMAL(20,4),
    n_recp_borrow_oth DECIMAL(20,4),
    n_recp_borr_from_cb DECIMAL(20,4),
    proc_issue_bonds DECIMAL(20,4),
    oth_cash_recp_ral_fnc_act DECIMAL(20,4),
    stot_cash_inflow_fnc_act DECIMAL(20,4),
    free_cashflow DECIMAL(20,4),
    c_prepay_amt_borr DECIMAL(20,4),
    c_pay_dist_dcpint_profits DECIMAL(20,4),
    c_pay_debts DECIMAL(20,4),
    stot_cashout_fnc_act DECIMAL(20,4),
    n_incr_cash_equ DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_cashflow_ann_date ON t_stock_cashflow(ann_date);
CREATE INDEX idx_cashflow_end_date ON t_stock_cashflow(end_date);

COMMENT ON TABLE t_stock_cashflow IS '现金流量表 - 一般工商业 - 来自Tushare cashflow';
COMMENT ON COLUMN t_stock_cashflow.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_cashflow.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_cashflow.f_ann_date IS '实际公告日期';
COMMENT ON COLUMN t_stock_cashflow.end_date IS '报告期';
COMMENT ON COLUMN t_stock_cashflow.c_cash_equ_end_period IS '期末现金及现金等价物余额';
COMMENT ON COLUMN t_stock_cashflow.n_cashflow_act IS '经营活动产生的现金流量净额';
COMMENT ON COLUMN t_stock_cashflow.c_recp_sell_goods IS '销售商品、提供劳务收到的现金';
COMMENT ON COLUMN t_stock_cashflow.c_paid_goods_s IS '购买商品、接受劳务支付的现金';
COMMENT ON COLUMN t_stock_cashflow.n_cashflow_inv_act IS '投资活动产生的现金流量净额';
COMMENT ON COLUMN t_stock_cashflow.free_cashflow IS '企业自由现金流量';

-- 23. 现金流量表 - 银行专用
DROP TABLE IF EXISTS t_stock_cashflow_bank CASCADE;
CREATE TABLE t_stock_cashflow_bank (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    c_cash_equ_end_period DECIMAL(20,4),
    n_cashflow_act DECIMAL(20,4),
    n_depos_incr_fi DECIMAL(20,4),
    n_incr_loans_cb DECIMAL(20,4),
    n_inc_borr_oth_fi DECIMAL(20,4),
    n_incr_disp_tfa DECIMAL(20,4),
    ifc_cash_incr DECIMAL(20,4),
    n_incr_disp_faas DECIMAL(20,4),
    n_incr_loans_oth_bank DECIMAL(20,4),
    n_cap_incr_repur DECIMAL(20,4),
    c_inf_fr_operate_a DECIMAL(20,4),
    n_incr_clt_loan_adv DECIMAL(20,4),
    n_incr_dep_cbob DECIMAL(20,4),
    st_cash_out_act DECIMAL(20,4),
    n_cashflow_inv_act DECIMAL(20,4),
    stot_inflows_inv_act DECIMAL(20,4),
    oth_pay_ral_inv_act DECIMAL(20,4),
    n_recp_borrow_oth DECIMAL(20,4),
    n_recp_borr_from_cb DECIMAL(20,4),
    stot_cash_inflow_fnc_act DECIMAL(20,4),
    c_prepay_amt_borr DECIMAL(20,4),
    stot_cashout_fnc_act DECIMAL(20,4),
    n_incr_cash_equ DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_cashflow_bank_ann_date ON t_stock_cashflow_bank(ann_date);
CREATE INDEX idx_cashflow_bank_end_date ON t_stock_cashflow_bank(end_date);

COMMENT ON TABLE t_stock_cashflow_bank IS '现金流量表 - 银行专用 - 来自Tushare cashflow';

-- 24. 现金流量表 - 保险专用
DROP TABLE IF EXISTS t_stock_cashflow_insurance CASCADE;
CREATE TABLE t_stock_cashflow_insurance (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    c_cash_equ_end_period DECIMAL(20,4),
    n_cashflow_act DECIMAL(20,4),
    prem_fr_orig_contr DECIMAL(20,4),
    n_incr_insured_dep DECIMAL(20,4),
    n_reinsur_prem DECIMAL(20,4),
    c_inf_fr_operate_a DECIMAL(20,4),
    c_pay_claims_orig_inco DECIMAL(20,4),
    pay_handling_chrg DECIMAL(20,4),
    pay_comm_insur_plcy DECIMAL(20,4),
    st_cash_out_act DECIMAL(20,4),
    n_cashflow_inv_act DECIMAL(20,4),
    stot_inflows_inv_act DECIMAL(20,4),
    oth_pay_ral_inv_act DECIMAL(20,4),
    n_recp_borrow_oth DECIMAL(20,4),
    proc_issue_bonds DECIMAL(20,4),
    stot_cash_inflow_fnc_act DECIMAL(20,4),
    c_pay_dist_dcpint_profits DECIMAL(20,4),
    stot_cashout_fnc_act DECIMAL(20,4),
    n_incr_cash_equ DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_cashflow_insurance_ann_date ON t_stock_cashflow_insurance(ann_date);
CREATE INDEX idx_cashflow_insurance_end_date ON t_stock_cashflow_insurance(end_date);

COMMENT ON TABLE t_stock_cashflow_insurance IS '现金流量表 - 保险专用 - 来自Tushare cashflow';

-- 25. 现金流量表 - 证券专用
DROP TABLE IF EXISTS t_stock_cashflow_securities CASCADE;
CREATE TABLE t_stock_cashflow_securities (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    f_ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    comp_type VARCHAR(10),
    c_cash_equ_end_period DECIMAL(20,4),
    n_cashflow_act DECIMAL(20,4),
    n_incr_disp_tfa DECIMAL(20,4),
    c_inf_fr_operate_a DECIMAL(20,4),
    st_cash_out_act DECIMAL(20,4),
    n_cashflow_inv_act DECIMAL(20,4),
    stot_inflows_inv_act DECIMAL(20,4),
    oth_pay_ral_inv_act DECIMAL(20,4),
    n_recp_borrow_oth DECIMAL(20,4),
    stot_cash_inflow_fnc_act DECIMAL(20,4),
    c_prepay_amt_borr DECIMAL(20,4),
    stot_cashout_fnc_act DECIMAL(20,4),
    n_incr_cash_equ DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
);

CREATE INDEX idx_cashflow_securities_ann_date ON t_stock_cashflow_securities(ann_date);
CREATE INDEX idx_cashflow_securities_end_date ON t_stock_cashflow_securities(end_date);

COMMENT ON TABLE t_stock_cashflow_securities IS '现金流量表 - 证券专用 - 来自Tushare cashflow';

-- ========================================================
-- 六、财务数据表 - 指标与衍生 (6张)
-- ========================================================

-- 26. 财务指标数据表
DROP TABLE IF EXISTS t_stock_fina_indicator CASCADE;
CREATE TABLE t_stock_fina_indicator (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    roe DECIMAL(10,4),
    roe_diluted DECIMAL(10,4),
    roe_avg DECIMAL(10,4),
    roa DECIMAL(10,4),
    roa_yearly DECIMAL(10,4),
    sales_margin DECIMAL(10,4),
    net_profit_margin DECIMAL(10,4),
    gross_profit_margin DECIMAL(10,4),
    sales_to_admin_ratio DECIMAL(10,4),
    sales_to_sale_ratio DECIMAL(10,4),
    asset_turnover DECIMAL(10,4),
    ca_turnover DECIMAL(10,4),
    fa_turnover DECIMAL(10,4),
    current_ratio DECIMAL(10,4),
    quick_ratio DECIMAL(10,4),
    cash_ratio DECIMAL(10,4),
    inv_days DECIMAL(10,4),
    ar_days DECIMAL(10,4),
    debt_to_assets DECIMAL(10,4),
    assets_to_eqt DECIMAL(10,4),
    debt_to_eqt DECIMAL(10,4),
    netdebt_to_eqt DECIMAL(10,4),
    ocf_to_shortdebt DECIMAL(10,4),
    ocf_to_debt DECIMAL(10,4),
    ocf_to_interest DECIMAL(10,4),
    profit_to_op DECIMAL(10,4),
    basic_eps_yoy DECIMAL(10,4),
    dt_eps_yoy DECIMAL(10,4),
    cfps_yoy DECIMAL(10,4),
    op_yoy DECIMAL(10,4),
    ebt_yoy DECIMAL(10,4),
    netprofit_yoy DECIMAL(10,4),
    dt_netprofit_yoy DECIMAL(10,4),
    roe_yoy DECIMAL(10,4),
    bps_yoy DECIMAL(10,4),
    assets_yoy DECIMAL(10,4),
    eqt_yoy DECIMAL(10,4),
    tr_yoy DECIMAL(10,4),
    or_yoy DECIMAL(10,4),
    q_sales_yoy DECIMAL(10,4),
    q_op_qoq DECIMAL(10,4),
    equity_yoy DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_fina_indicator_ann_date ON t_stock_fina_indicator(ann_date);
CREATE INDEX idx_fina_indicator_end_date ON t_stock_fina_indicator(end_date);
CREATE INDEX idx_fina_indicator_roe ON t_stock_fina_indicator(roe);

COMMENT ON TABLE t_stock_fina_indicator IS '财务指标数据表 - 来自Tushare fina_indicator';
COMMENT ON COLUMN t_stock_fina_indicator.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_fina_indicator.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_fina_indicator.end_date IS '报告期';
COMMENT ON COLUMN t_stock_fina_indicator.roe IS '净资产收益率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.roe_diluted IS '摊薄净资产收益率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.roa IS '总资产报酬率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.sales_margin IS '销售净利率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.gross_profit_margin IS '销售毛利率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.asset_turnover IS '总资产周转率';
COMMENT ON COLUMN t_stock_fina_indicator.current_ratio IS '流动比率';
COMMENT ON COLUMN t_stock_fina_indicator.quick_ratio IS '速动比率';
COMMENT ON COLUMN t_stock_fina_indicator.debt_to_assets IS '资产负债率(%)';
COMMENT ON COLUMN t_stock_fina_indicator.netprofit_yoy IS '归属母公司股东的净利润同比增长率(%)';

-- 27. 财务审计意见表
DROP TABLE IF EXISTS t_stock_fina_audit CASCADE;
CREATE TABLE t_stock_fina_audit (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    audit_result VARCHAR(200),
    audit_fees DECIMAL(20,4),
    audit_agency VARCHAR(200),
    sign_account VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_fina_audit_ann_date ON t_stock_fina_audit(ann_date);
CREATE INDEX idx_fina_audit_end_date ON t_stock_fina_audit(end_date);

COMMENT ON TABLE t_stock_fina_audit IS '财务审计意见表 - 来自Tushare fina_audit';
COMMENT ON COLUMN t_stock_fina_audit.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_fina_audit.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_fina_audit.end_date IS '报告期';
COMMENT ON COLUMN t_stock_fina_audit.audit_result IS '审计结果';
COMMENT ON COLUMN t_stock_fina_audit.audit_fees IS '审计总费用（元）';
COMMENT ON COLUMN t_stock_fina_audit.audit_agency IS '会计事务所';
COMMENT ON COLUMN t_stock_fina_audit.sign_account IS '签字会计师';

-- 28. 主营业务构成表
DROP TABLE IF EXISTS t_stock_fina_mainbz CASCADE;
CREATE TABLE t_stock_fina_mainbz (
    ts_code VARCHAR(20) NOT NULL,
    end_date VARCHAR(8) NOT NULL,
    bz_item VARCHAR(200),
    bz_sales DECIMAL(20,4),
    bz_profit DECIMAL(20,4),
    bz_cost DECIMAL(20,4),
    curr_type VARCHAR(10),
    update_flag VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, bz_item)
);

CREATE INDEX idx_fina_mainbz_end_date ON t_stock_fina_mainbz(end_date);
CREATE INDEX idx_fina_mainbz_bz_item ON t_stock_fina_mainbz(bz_item);

COMMENT ON TABLE t_stock_fina_mainbz IS '主营业务构成表 - 来自Tushare fina_mainbz';
COMMENT ON COLUMN t_stock_fina_mainbz.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_fina_mainbz.end_date IS '报告期';
COMMENT ON COLUMN t_stock_fina_mainbz.bz_item IS '主营业务项目';
COMMENT ON COLUMN t_stock_fina_mainbz.bz_sales IS '主营业务收入（元）';
COMMENT ON COLUMN t_stock_fina_mainbz.bz_profit IS '主营业务利润（元）';
COMMENT ON COLUMN t_stock_fina_mainbz.bz_cost IS '主营业务成本（元）';

-- 29. 业绩预告表
DROP TABLE IF EXISTS t_stock_forecast CASCADE;
CREATE TABLE t_stock_forecast (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    type VARCHAR(50),
    p_change_min DECIMAL(10,4),
    p_change_max DECIMAL(10,4),
    net_profit_min DECIMAL(20,4),
    net_profit_max DECIMAL(20,4),
    last_parent_net DECIMAL(20,4),
    first_ann_date VARCHAR(8),
    summary TEXT,
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_forecast_ann_date ON t_stock_forecast(ann_date);
CREATE INDEX idx_forecast_end_date ON t_stock_forecast(end_date);
CREATE INDEX idx_forecast_type ON t_stock_forecast(type);

COMMENT ON TABLE t_stock_forecast IS '业绩预告表 - 来自Tushare forecast';
COMMENT ON COLUMN t_stock_forecast.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_forecast.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_forecast.end_date IS '报告期';
COMMENT ON COLUMN t_stock_forecast.type IS '业绩预告类型';
COMMENT ON COLUMN t_stock_forecast.p_change_min IS '预告净利润变动幅度下限(%)';
COMMENT ON COLUMN t_stock_forecast.p_change_max IS '预告净利润变动幅度上限(%)';
COMMENT ON COLUMN t_stock_forecast.net_profit_min IS '预告净利润下限（万元）';
COMMENT ON COLUMN t_stock_forecast.net_profit_max IS '预告净利润上限（万元）';
COMMENT ON COLUMN t_stock_forecast.last_parent_net IS '上年同期归属母公司净利润（万元）';
COMMENT ON COLUMN t_stock_forecast.first_ann_date IS '首次公告日';
COMMENT ON COLUMN t_stock_forecast.summary IS '业绩预告摘要';
COMMENT ON COLUMN t_stock_forecast.change_reason IS '业绩变动原因';

-- 30. 业绩快报表
DROP TABLE IF EXISTS t_stock_express CASCADE;
CREATE TABLE t_stock_express (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    revenue DECIMAL(20,4),
    operate_profit DECIMAL(20,4),
    total_profit DECIMAL(20,4),
    n_income DECIMAL(20,4),
    total_assets DECIMAL(20,4),
    total_hldr_eqy_exc_min_int DECIMAL(20,4),
    diluted_eps DECIMAL(20,4),
    dps DECIMAL(20,4),
    yoy_sales DECIMAL(10,4),
    yoy_op DECIMAL(10,4),
    yoy_tp DECIMAL(10,4),
    yoy_netprofit DECIMAL(10,4),
    growth_assets DECIMAL(10,4),
    yoy_equity DECIMAL(10,4),
    growth_bps DECIMAL(10,4),
    or_last_year DECIMAL(20,4),
    op_last_year DECIMAL(20,4),
    tp_last_year DECIMAL(20,4),
    np_last_year DECIMAL(20,4),
    assets_last_year DECIMAL(20,4),
    equity_last_year DECIMAL(20,4),
    bps_last_year DECIMAL(20,4),
    update_flag VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_express_ann_date ON t_stock_express(ann_date);
CREATE INDEX idx_express_end_date ON t_stock_express(end_date);

COMMENT ON TABLE t_stock_express IS '业绩快报表 - 来自Tushare express';
COMMENT ON COLUMN t_stock_express.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_express.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_express.end_date IS '报告期';
COMMENT ON COLUMN t_stock_express.revenue IS '营业收入(元)';
COMMENT ON COLUMN t_stock_express.operate_profit IS '营业利润(元)';
COMMENT ON COLUMN t_stock_express.total_profit IS '利润总额(元)';
COMMENT ON COLUMN t_stock_express.n_income IS '净利润(元)';
COMMENT ON COLUMN t_stock_express.total_assets IS '总资产(元)';
COMMENT ON COLUMN t_stock_express.diluted_eps IS '摊薄每股收益';
COMMENT ON COLUMN t_stock_express.yoy_sales IS '同比增长率:营业收入';
COMMENT ON COLUMN t_stock_express.yoy_netprofit IS '同比增长率:净利润';

-- 31. 分红送股表
DROP TABLE IF EXISTS t_stock_dividend CASCADE;
CREATE TABLE t_stock_dividend (
    ts_code VARCHAR(20) NOT NULL,
    end_date VARCHAR(8) NOT NULL,
    ann_date VARCHAR(8),
    div_proc VARCHAR(50),
    stk_div DECIMAL(10,4),
    stk_bo_rate DECIMAL(10,4),
    stk_co_rate DECIMAL(10,4),
    cash_div DECIMAL(10,4),
    cash_div_tax DECIMAL(10,4),
    record_date VARCHAR(8),
    ex_date VARCHAR(8),
    pay_date VARCHAR(8),
    div_listdate VARCHAR(8),
    imp_ann_date VARCHAR(8),
    base_date VARCHAR(8),
    base_share DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_dividend_ann_date ON t_stock_dividend(ann_date);
CREATE INDEX idx_dividend_end_date ON t_stock_dividend(end_date);
CREATE INDEX idx_dividend_ex_date ON t_stock_dividend(ex_date);

COMMENT ON TABLE t_stock_dividend IS '分红送股表 - 来自Tushare dividend';
COMMENT ON COLUMN t_stock_dividend.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_dividend.end_date IS '分红年度';
COMMENT ON COLUMN t_stock_dividend.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_dividend.div_proc IS '实施进度';
COMMENT ON COLUMN t_stock_dividend.stk_div IS '每股送转';
COMMENT ON COLUMN t_stock_dividend.cash_div IS '每股分红（税后）';
COMMENT ON COLUMN t_stock_dividend.cash_div_tax IS '每股分红（税前）';
COMMENT ON COLUMN t_stock_dividend.record_date IS '股权登记日';
COMMENT ON COLUMN t_stock_dividend.ex_date IS '除权除息日';
COMMENT ON COLUMN t_stock_dividend.pay_date IS '派息日';
COMMENT ON COLUMN t_stock_dividend.div_listdate IS '红股上市日';

-- ========================================================
-- 七、市场行为与参考数据 (9张)
-- ========================================================

-- 32. 前十大股东表
DROP TABLE IF EXISTS t_stock_top10_holders CASCADE;
CREATE TABLE t_stock_top10_holders (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    holder_name VARCHAR(200),
    hold_amount DECIMAL(20,4),
    hold_ratio DECIMAL(10,4),
    hold_change DECIMAL(20,4),
    holder_rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, holder_rank)
);

CREATE INDEX idx_top10_holders_ann_date ON t_stock_top10_holders(ann_date);
CREATE INDEX idx_top10_holders_end_date ON t_stock_top10_holders(end_date);

COMMENT ON TABLE t_stock_top10_holders IS '前十大股东表 - 来自Tushare top10_holders';
COMMENT ON COLUMN t_stock_top10_holders.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_top10_holders.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_top10_holders.end_date IS '报告期';
COMMENT ON COLUMN t_stock_top10_holders.holder_name IS '股东名称';
COMMENT ON COLUMN t_stock_top10_holders.hold_amount IS '持有数量（股）';
COMMENT ON COLUMN t_stock_top10_holders.hold_ratio IS '持有比例(%)';
COMMENT ON COLUMN t_stock_top10_holders.hold_change IS '变动数量';
COMMENT ON COLUMN t_stock_top10_holders.holder_rank IS '股东排名';

-- 33. 前十大流通股东表
DROP TABLE IF EXISTS t_stock_top10_float_holders CASCADE;
CREATE TABLE t_stock_top10_float_holders (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    holder_name VARCHAR(200),
    hold_amount DECIMAL(20,4),
    hold_ratio DECIMAL(10,4),
    hold_change DECIMAL(20,4),
    holder_rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, holder_rank)
);

CREATE INDEX idx_top10_fh_ann_date ON t_stock_top10_float_holders(ann_date);
CREATE INDEX idx_top10_fh_end_date ON t_stock_top10_float_holders(end_date);

COMMENT ON TABLE t_stock_top10_float_holders IS '前十大流通股东表 - 来自Tushare top10_fh';
COMMENT ON COLUMN t_stock_top10_float_holders.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_top10_float_holders.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_top10_float_holders.end_date IS '报告期';
COMMENT ON COLUMN t_stock_top10_float_holders.holder_name IS '股东名称';
COMMENT ON COLUMN t_stock_top10_float_holders.hold_amount IS '持有数量（股）';
COMMENT ON COLUMN t_stock_top10_float_holders.hold_ratio IS '持有比例(%)';
COMMENT ON COLUMN t_stock_top10_float_holders.hold_change IS '变动数量';
COMMENT ON COLUMN t_stock_top10_float_holders.holder_rank IS '股东排名';

-- 34. 股东人数表
DROP TABLE IF EXISTS t_stock_holder_number CASCADE;
CREATE TABLE t_stock_holder_number (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    holder_num INTEGER,
    holder_num_change INTEGER,
    holder_num_ratio DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX idx_holder_num_ann_date ON t_stock_holder_number(ann_date);
CREATE INDEX idx_holder_num_end_date ON t_stock_holder_number(end_date);

COMMENT ON TABLE t_stock_holder_number IS '股东人数表 - 来自Tushare stk_holdernumber';
COMMENT ON COLUMN t_stock_holder_number.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_holder_number.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_holder_number.end_date IS '截止日期';
COMMENT ON COLUMN t_stock_holder_number.holder_num IS '股东户数';
COMMENT ON COLUMN t_stock_holder_number.holder_num_change IS '股东户数变动';
COMMENT ON COLUMN t_stock_holder_number.holder_num_ratio IS '股东户数变动比例(%)';

-- 35. 股东增减持表
DROP TABLE IF EXISTS t_stock_holder_trade CASCADE;
CREATE TABLE t_stock_holder_trade (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    holder_name VARCHAR(200),
    holder_type VARCHAR(50),
    in_de VARCHAR(10),
    change_vol DECIMAL(20,4),
    change_ratio DECIMAL(10,4),
    after_share DECIMAL(20,4),
    after_ratio DECIMAL(10,4),
    avg_price DECIMAL(16,4),
    total_share DECIMAL(20,4),
    begin_date VARCHAR(8),
    close_date VARCHAR(8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, ann_date, holder_name)
);

CREATE INDEX idx_holder_trade_ann_date ON t_stock_holder_trade(ann_date);
CREATE INDEX idx_holder_trade_holder_name ON t_stock_holder_trade(holder_name);

COMMENT ON TABLE t_stock_holder_trade IS '股东增减持表 - 来自Tushare stk_holdertrade';
COMMENT ON COLUMN t_stock_holder_trade.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_holder_trade.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_holder_trade.holder_name IS '股东名称';
COMMENT ON COLUMN t_stock_holder_trade.holder_type IS '股东类型';
COMMENT ON COLUMN t_stock_holder_trade.in_de IS '增减持方向';
COMMENT ON COLUMN t_stock_holder_trade.change_vol IS '变动数量';
COMMENT ON COLUMN t_stock_holder_trade.change_ratio IS '变动占总股本比例(%)';
COMMENT ON COLUMN t_stock_holder_trade.after_share IS '变动后持股数量';
COMMENT ON COLUMN t_stock_holder_trade.after_ratio IS '变动后持股比例(%)';
COMMENT ON COLUMN t_stock_holder_trade.avg_price IS '平均交易价格';
COMMENT ON COLUMN t_stock_holder_trade.total_share IS '持股总数';
COMMENT ON COLUMN t_stock_holder_trade.begin_date IS '增减持开始日期';
COMMENT ON COLUMN t_stock_holder_trade.close_date IS '增减持结束日期';

-- 36. 股权质押表
DROP TABLE IF EXISTS t_stock_cgq CASCADE;
CREATE TABLE t_stock_cgq (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    holder_name VARCHAR(200),
    hold_vol DECIMAL(20,4),
    hold_ratio DECIMAL(10,4),
    pledge_vol DECIMAL(20,4),
    pledge_ratio DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, ann_date, holder_name)
);

CREATE INDEX idx_cgq_ann_date ON t_stock_cgq(ann_date);
CREATE INDEX idx_cgq_holder_name ON t_stock_cgq(holder_name);

COMMENT ON TABLE t_stock_cgq IS '股权质押表 - 来自Tushare cgq';
COMMENT ON COLUMN t_stock_cgq.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_cgq.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_cgq.holder_name IS '股东名称';
COMMENT ON COLUMN t_stock_cgq.hold_vol IS '持有股份数量（万股）';
COMMENT ON COLUMN t_stock_cgq.hold_ratio IS '持有股份占总股本比例(%)';
COMMENT ON COLUMN t_stock_cgq.pledge_vol IS '质押股份数量（万股）';
COMMENT ON COLUMN t_stock_cgq.pledge_ratio IS '质押股份占持股比(%)';

-- 37. 机构持股汇总表
DROP TABLE IF EXISTS t_stock_jgcc CASCADE;
CREATE TABLE t_stock_jgcc (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    end_date VARCHAR(8) NOT NULL,
    org_type VARCHAR(50),
    org_num INTEGER,
    hold_vol DECIMAL(20,4),
    hold_ratio DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, org_type)
);

CREATE INDEX idx_jgcc_ann_date ON t_stock_jgcc(ann_date);
CREATE INDEX idx_jgcc_end_date ON t_stock_jgcc(end_date);
CREATE INDEX idx_jgcc_org_type ON t_stock_jgcc(org_type);

COMMENT ON TABLE t_stock_jgcc IS '机构持股汇总表 - 来自Tushare jgcc';
COMMENT ON COLUMN t_stock_jgcc.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_jgcc.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_jgcc.end_date IS '报告期';
COMMENT ON COLUMN t_stock_jgcc.org_type IS '机构类型';
COMMENT ON COLUMN t_stock_jgcc.org_num IS '机构数量';
COMMENT ON COLUMN t_stock_jgcc.hold_vol IS '持仓数量（万股）';
COMMENT ON COLUMN t_stock_jgcc.hold_ratio IS '持仓比例(%)';

-- 38. 机构调研表
DROP TABLE IF EXISTS t_stock_jgdy CASCADE;
CREATE TABLE t_stock_jgdy (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8) NOT NULL,
    end_date VARCHAR(8),
    org_name TEXT,
    org_type VARCHAR(50),
    org_num INTEGER,
    personnel TEXT,
    way VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, ann_date)
);

CREATE INDEX idx_jgdy_ann_date ON t_stock_jgdy(ann_date);
CREATE INDEX idx_jgdy_end_date ON t_stock_jgdy(end_date);

COMMENT ON TABLE t_stock_jgdy IS '机构调研表 - 来自Tushare jgdy';
COMMENT ON COLUMN t_stock_jgdy.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_jgdy.ann_date IS '调研日期';
COMMENT ON COLUMN t_stock_jgdy.end_date IS '报告期';
COMMENT ON COLUMN t_stock_jgdy.org_name IS '参与机构名称';
COMMENT ON COLUMN t_stock_jgdy.org_type IS '机构类型';
COMMENT ON COLUMN t_stock_jgdy.org_num IS '参与机构数量';
COMMENT ON COLUMN t_stock_jgdy.personnel IS '公司接待人员';
COMMENT ON COLUMN t_stock_jgdy.way IS '调研方式';
COMMENT ON COLUMN t_stock_jgdy.content IS '调研内容';

-- 39. 股权质押明细表
DROP TABLE IF EXISTS t_stock_gdfx CASCADE;
CREATE TABLE t_stock_gdfx (
    ts_code VARCHAR(20) NOT NULL,
    ann_date VARCHAR(8),
    holder_name VARCHAR(200),
    hold_vol DECIMAL(20,4),
    hold_ratio DECIMAL(10,4),
    pledge_vol DECIMAL(20,4),
    pledge_ratio DECIMAL(10,4),
    froze_vol DECIMAL(20,4),
    unfroze_vol DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, ann_date, holder_name)
);

CREATE INDEX idx_gdfx_ann_date ON t_stock_gdfx(ann_date);
CREATE INDEX idx_gdfx_holder_name ON t_stock_gdfx(holder_name);

COMMENT ON TABLE t_stock_gdfx IS '股权质押明细表 - 来自Tushare gdfx';
COMMENT ON COLUMN t_stock_gdfx.ts_code IS 'TS代码';
COMMENT ON COLUMN t_stock_gdfx.ann_date IS '公告日期';
COMMENT ON COLUMN t_stock_gdfx.holder_name IS '股东名称';
COMMENT ON COLUMN t_stock_gdfx.hold_vol IS '持股数量（万股）';
COMMENT ON COLUMN t_stock_gdfx.hold_ratio IS '持股比例(%)';
COMMENT ON COLUMN t_stock_gdfx.pledge_vol IS '累计质押（万股）';
COMMENT ON COLUMN t_stock_gdfx.pledge_ratio IS '累计质押占总股本比例(%)';
COMMENT ON COLUMN t_stock_gdfx.froze_vol IS '累计冻结（万股）';
COMMENT ON COLUMN t_stock_gdfx.unfroze_vol IS '累计解冻（万股）';

-- ========================================================
-- 触发器：自动更新 updated_at 字段
-- ========================================================

-- 创建触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为基础数据表添加触发器
CREATE TRIGGER update_t_stock_basic_updated_at
    BEFORE UPDATE ON t_stock_basic
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================================
-- 创建辅助视图
-- ========================================================

-- 股票基本信息视图
CREATE OR REPLACE VIEW v_stock_basic_info AS
SELECT
    ts_code,
    symbol,
    name,
    area,
    industry,
    market,
    list_status,
    list_date,
    delist_date,
    is_hs,
    CASE
        WHEN list_status = 'L' THEN '上市'
        WHEN list_status = 'D' THEN '退市'
        WHEN list_status = 'P' THEN '暂停上市'
        ELSE '其他'
    END as list_status_name
FROM t_stock_basic;

COMMENT ON VIEW v_stock_basic_info IS '股票基本信息视图';

-- 最新交易日行情视图
CREATE OR REPLACE VIEW v_latest_daily_market AS
SELECT
    d.*,
    b.name,
    b.industry,
    b.area
FROM t_stock_dailymarketdata d
JOIN t_stock_basic b ON d.ts_code = b.ts_code
WHERE d.trade_date = (SELECT MAX(trade_date) FROM t_stock_dailymarketdata);

COMMENT ON VIEW v_latest_daily_market IS '最新交易日行情视图';

-- 财务指标综合视图
CREATE OR REPLACE VIEW v_fina_indicator_summary AS
SELECT
    f.ts_code,
    f.end_date,
    b.name,
    b.industry,
    f.roe,
    f.roa,
    f.sales_margin,
    f.gross_profit_margin,
    f.current_ratio,
    f.quick_ratio,
    f.debt_to_assets,
    f.asset_turnover,
    f.netprofit_yoy
FROM t_stock_fina_indicator f
JOIN t_stock_basic b ON f.ts_code = b.ts_code;

COMMENT ON VIEW v_fina_indicator_summary IS '财务指标综合视图';

-- ========================================================
-- 初始化数据
-- ========================================================

-- 记录数据库版本
CREATE TABLE IF NOT EXISTS t_db_version (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO t_db_version (version, description) VALUES ('1.0.0', 'Initial schema with 40 Tushare tables');

COMMENT ON TABLE t_db_version IS '数据库版本记录表';
