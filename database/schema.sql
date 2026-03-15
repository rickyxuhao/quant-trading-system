-- ========================================================
-- Tushare 数据表结构 - MySQL 版本
-- 来源: Tushare Pro API
-- 数据库: tushare_biz
-- 表数量: 40张
-- 生成日期: 2026-03-07
-- ========================================================

-- 设置字符集和时区
SET NAMES utf8mb4;

-- ========================================================
-- 一、基础数据表 (6张)
-- ========================================================

-- 1. 股票基础信息表
DROP TABLE IF EXISTS t_stock_basic;
CREATE TABLE t_stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY COMMENT 'TS代码',
    symbol VARCHAR(20) NOT NULL COMMENT '股票代码',
    name VARCHAR(100) COMMENT '股票名称',
    area VARCHAR(50) COMMENT '地域',
    industry VARCHAR(100) COMMENT '所属行业',
    fullname VARCHAR(200) COMMENT '股票全称',
    enname VARCHAR(200) COMMENT '英文全称',
    cnspell VARCHAR(100) COMMENT '拼音缩写',
    market VARCHAR(20) COMMENT '市场类型（主板/创业板/科创板/CDR）',
    exchange VARCHAR(20) COMMENT '交易所代码',
    curr_type VARCHAR(20) COMMENT '交易货币',
    list_status VARCHAR(10) COMMENT '上市状态 L上市 D退市 G过会未交易 P暂停上市',
    list_date VARCHAR(8) COMMENT '上市日期 YYYYMMDD',
    delist_date VARCHAR(8) COMMENT '退市日期 YYYYMMDD',
    is_hs VARCHAR(10) COMMENT '是否沪深港通标的 N否 H沪股通 S深股通',
    act_name VARCHAR(100) COMMENT '实控人名称',
    act_ent_type VARCHAR(50) COMMENT '实控人企业性质',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='股票基础信息表 - 来自Tushare stock_basic';

CREATE INDEX idx_stock_basic_symbol ON t_stock_basic(symbol);
CREATE INDEX idx_stock_basic_industry ON t_stock_basic(industry);
CREATE INDEX idx_stock_basic_market ON t_stock_basic(market);
CREATE INDEX idx_stock_basic_list_status ON t_stock_basic(list_status);
CREATE INDEX idx_stock_basic_list_date ON t_stock_basic(list_date);
CREATE INDEX idx_stock_basic_area ON t_stock_basic(area);

-- 2. 交易日历表
DROP TABLE IF EXISTS t_stock_tradedate;
CREATE TABLE t_stock_tradedate (
    exchange VARCHAR(20) NOT NULL COMMENT '交易所 SSE/SZSE',
    cal_date VARCHAR(8) NOT NULL COMMENT '日历日期 YYYYMMDD',
    is_open INTEGER COMMENT '是否交易 0休市 1交易',
    pretrade_date VARCHAR(8) COMMENT '上一个交易日',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exchange, cal_date)
) COMMENT='交易日历表 - 来自Tushare trade_cal';

CREATE INDEX idx_tradedate_date ON t_stock_tradedate(cal_date);
CREATE INDEX idx_tradedate_is_open ON t_stock_tradedate(is_open);

-- 3. 股票曾用名表
DROP TABLE IF EXISTS t_stock_name_history;
CREATE TABLE t_stock_name_history (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '证券名称',
    start_date VARCHAR(8) COMMENT '开始日期',
    end_date VARCHAR(8) COMMENT '结束日期',
    ann_date VARCHAR(8) COMMENT '公告日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, start_date)
) COMMENT='股票曾用名表 - 来自Tushare namechange';

CREATE INDEX idx_name_history_ts_code ON t_stock_name_history(ts_code);
CREATE INDEX idx_name_history_start_date ON t_stock_name_history(start_date);

-- 4. 沪深股通成分股表
DROP TABLE IF EXISTS t_stock_hs_const;
CREATE TABLE t_stock_hs_const (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    hs_type VARCHAR(10) NOT NULL COMMENT '沪深港通类型 SH沪股通 SZ深股通',
    in_date VARCHAR(8) COMMENT '纳入日期',
    out_date VARCHAR(8) COMMENT '剔除日期',
    is_new INTEGER COMMENT '是否最新 1是 0否',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, hs_type)
) COMMENT='沪深股通成分股表 - 来自Tushare hs_const';

CREATE INDEX idx_hs_const_ts_code ON t_stock_hs_const(ts_code);
CREATE INDEX idx_hs_const_type ON t_stock_hs_const(hs_type);

-- 5. IPO新股列表
DROP TABLE IF EXISTS t_stock_ipo;
CREATE TABLE t_stock_ipo (
    ts_code VARCHAR(20) PRIMARY KEY COMMENT 'TS代码',
    sub_code VARCHAR(20) COMMENT '申购代码',
    name VARCHAR(100) COMMENT '股票名称',
    ipo_date VARCHAR(8) COMMENT '上网发行日期',
    issue_date VARCHAR(8) COMMENT '上市日期',
    amount DECIMAL(20,4) COMMENT '发行总量（万股）',
    market_amount DECIMAL(20,4) COMMENT '上网发行数量（万股）',
    price DECIMAL(16,4) COMMENT '发行价格',
    pe DECIMAL(16,4) COMMENT '市盈率',
    limit_amount DECIMAL(16,4) COMMENT '个人申购上限（万股）',
    funds DECIMAL(20,4) COMMENT '募集资金总额（亿元）',
    ballot DECIMAL(10,4) COMMENT '中签率(%)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='IPO新股列表 - 来自Tushare new_share';

CREATE INDEX idx_ipo_ipo_date ON t_stock_ipo(ipo_date);
CREATE INDEX idx_ipo_issue_date ON t_stock_ipo(issue_date);

-- 6. 上市公司基本信息表
DROP TABLE IF EXISTS t_stock_company;
CREATE TABLE t_stock_company (
    ts_code VARCHAR(20) PRIMARY KEY COMMENT 'TS代码',
    exchange VARCHAR(20) COMMENT '交易所代码',
    chairman VARCHAR(100) COMMENT '董事长',
    manager VARCHAR(100) COMMENT '总经理',
    secretary VARCHAR(100) COMMENT '董秘',
    reg_capital DECIMAL(20,4) COMMENT '注册资本',
    setup_date VARCHAR(8) COMMENT '注册日期',
    province VARCHAR(50) COMMENT '所在省份',
    city VARCHAR(50) COMMENT '所在城市',
    introduction TEXT COMMENT '公司介绍',
    website VARCHAR(200) COMMENT '公司主页',
    email VARCHAR(100) COMMENT '电子邮件',
    office VARCHAR(200) COMMENT '办公室',
    employees INTEGER COMMENT '员工人数',
    main_business TEXT COMMENT '主要业务及产品',
    business_scope TEXT COMMENT '经营范围',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='上市公司基本信息表 - 来自Tushare stock_company';

CREATE INDEX idx_company_exchange ON t_stock_company(exchange);
CREATE INDEX idx_company_province ON t_stock_company(province);
CREATE INDEX idx_company_city ON t_stock_company(city);

-- ========================================================
-- 二、行情数据表 (8张)
-- ========================================================

-- 7. 股票日线行情表
DROP TABLE IF EXISTS t_stock_dailymarketdata;
CREATE TABLE t_stock_dailymarketdata (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
    open DECIMAL(16,4) COMMENT '开盘价',
    high DECIMAL(16,4) COMMENT '最高价',
    low DECIMAL(16,4) COMMENT '最低价',
    close DECIMAL(16,4) COMMENT '收盘价',
    pre_close DECIMAL(16,4) COMMENT '昨收价',
    change_amount DECIMAL(16,4) COMMENT '涨跌额',
    pct_chg DECIMAL(10,4) COMMENT '涨跌幅(%)',
    vol BIGINT COMMENT '成交量(手)',
    amount DECIMAL(20,4) COMMENT '成交额(千元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='股票日线行情表 - 来自Tushare daily';

CREATE INDEX idx_daily_trade_date ON t_stock_dailymarketdata(trade_date);
CREATE INDEX idx_daily_vol ON t_stock_dailymarketdata(vol);
CREATE INDEX idx_daily_amount ON t_stock_dailymarketdata(amount);

-- 8. 复权因子表
DROP TABLE IF EXISTS t_stock_adjfactor;
CREATE TABLE t_stock_adjfactor (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    adj_factor DECIMAL(20,8) COMMENT '复权因子',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='复权因子表 - 来自Tushare adj_factor';

CREATE INDEX idx_adj_factor_date ON t_stock_adjfactor(trade_date);

-- 9. 每日指标表
DROP TABLE IF EXISTS t_stock_daily_basic;
CREATE TABLE t_stock_daily_basic (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    close DECIMAL(16,4) COMMENT '当日收盘价',
    turnover_rate DECIMAL(10,4) COMMENT '换手率(%)',
    turnover_rate_f DECIMAL(10,4) COMMENT '换手率(自由流通股)',
    volume_ratio DECIMAL(10,4) COMMENT '量比',
    pe DECIMAL(16,4) COMMENT '市盈率(总市值/净利润)',
    pe_ttm DECIMAL(16,4) COMMENT '市盈率TTM',
    pb DECIMAL(16,4) COMMENT '市净率(总市值/净资产)',
    ps DECIMAL(16,4) COMMENT '市销率',
    ps_ttm DECIMAL(16,4) COMMENT '市销率TTM',
    dv_ratio DECIMAL(10,4) COMMENT '股息率(%)',
    dv_ttm DECIMAL(10,4) COMMENT '股息率TTM(%)',
    total_share DECIMAL(20,4) COMMENT '总股本(万股)',
    float_share DECIMAL(20,4) COMMENT '流通股本(万股)',
    free_share DECIMAL(20,4) COMMENT '自由流通股本(万股)',
    total_mv DECIMAL(20,4) COMMENT '总市值(万元)',
    circ_mv DECIMAL(20,4) COMMENT '流通市值(万元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='每日指标表 - 来自Tushare daily_basic';

CREATE INDEX idx_daily_basic_date ON t_stock_daily_basic(trade_date);
CREATE INDEX idx_daily_basic_pe ON t_stock_daily_basic(pe);
CREATE INDEX idx_daily_basic_pb ON t_stock_daily_basic(pb);

-- 10. ST股票列表
DROP TABLE IF EXISTS t_stock_st_list;
CREATE TABLE t_stock_st_list (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    name VARCHAR(100) COMMENT '股票名称',
    in_date VARCHAR(8) COMMENT '纳入日期',
    out_date VARCHAR(8) COMMENT '剔除日期',
    is_new INTEGER COMMENT '是否最新',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, in_date)
) COMMENT='ST股票列表 - 来自Tushare stock_st';

CREATE INDEX idx_st_list_ts_code ON t_stock_st_list(ts_code);
CREATE INDEX idx_st_list_in_date ON t_stock_st_list(in_date);

-- 11. 每日涨跌停价格表
DROP TABLE IF EXISTS t_stock_dailylimitprice;
CREATE TABLE t_stock_dailylimitprice (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    name VARCHAR(100) COMMENT '股票名称',
    close DECIMAL(16,4) COMMENT '收盘价',
    pct_chg DECIMAL(10,4) COMMENT '涨跌幅(%)',
    amp DECIMAL(10,4) COMMENT '振幅(%)',
    up_limit DECIMAL(16,4) COMMENT '涨停板价',
    down_limit DECIMAL(16,4) COMMENT '跌停板价',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='每日涨跌停价格表 - 来自Tushare limit_list';

CREATE INDEX idx_limit_price_date ON t_stock_dailylimitprice(trade_date);

-- 12. 个股资金流向表
DROP TABLE IF EXISTS t_stock_moneyflow;
CREATE TABLE t_stock_moneyflow (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
    buy_sm_vol BIGINT COMMENT '小单买入量(手)',
    buy_sm_amount DECIMAL(20,4) COMMENT '小单买入金额(万元)',
    sell_sm_vol BIGINT COMMENT '小单卖出量(手)',
    sell_sm_amount DECIMAL(20,4) COMMENT '小单卖出金额(万元)',
    buy_md_vol BIGINT COMMENT '中单买入量(手)',
    buy_md_amount DECIMAL(20,4) COMMENT '中单买入金额(万元)',
    sell_md_vol BIGINT COMMENT '中单卖出量(手)',
    sell_md_amount DECIMAL(20,4) COMMENT '中单卖出金额(万元)',
    buy_lg_vol BIGINT COMMENT '大单买入量(手)',
    buy_lg_amount DECIMAL(20,4) COMMENT '大单买入金额(万元)',
    sell_lg_vol BIGINT COMMENT '大单卖出量(手)',
    sell_lg_amount DECIMAL(20,4) COMMENT '大单卖出金额(万元)',
    buy_elg_vol BIGINT COMMENT '特大单买入量(手)',
    buy_elg_amount DECIMAL(20,4) COMMENT '特大单买入金额(万元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date)
) COMMENT='个股资金流向表 - 来自Tushare moneyflow';

CREATE INDEX idx_moneyflow_date ON t_stock_moneyflow(trade_date);

-- 13. 沪深港通资金流向表
DROP TABLE IF EXISTS t_stock_moneyflow_market;
CREATE TABLE t_stock_moneyflow_market (
    trade_date VARCHAR(8) PRIMARY KEY COMMENT '交易日期',
    ggt_ss DECIMAL(20,4) COMMENT '港股通(上海)(亿元)',
    ggt_sz DECIMAL(20,4) COMMENT '港股通(深圳)(亿元)',
    hgt DECIMAL(20,4) COMMENT '沪股通(亿元)',
    sgt DECIMAL(20,4) COMMENT '深股通(亿元)',
    north_money DECIMAL(20,4) COMMENT '北向资金(亿元)',
    south_money DECIMAL(20,4) COMMENT '南向资金(亿元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='沪深港通资金流向表 - 来自Tushare moneyflow_hsgt';

-- ========================================================
-- 三、财务数据表 - 利润表 (4张)
-- ========================================================

-- 14. 利润表 - 一般工商业
DROP TABLE IF EXISTS t_stock_income;
CREATE TABLE t_stock_income (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    f_ann_date VARCHAR(8) COMMENT '实际公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    comp_type VARCHAR(10),
    basic_eps DECIMAL(20,4) COMMENT '基本每股收益',
    diluted_eps DECIMAL(20,4) COMMENT '稀释每股收益',
    total_revenue DECIMAL(20,4) COMMENT '营业总收入',
    revenue DECIMAL(20,4) COMMENT '营业收入',
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
    operate_profit DECIMAL(20,4) COMMENT '营业利润',
    noperate_income DECIMAL(20,4),
    noperate_exp DECIMAL(20,4),
    nca_disploss DECIMAL(20,4),
    total_profit DECIMAL(20,4) COMMENT '利润总额',
    income_tax DECIMAL(20,4) COMMENT '所得税费用',
    n_income DECIMAL(20,4) COMMENT '净利润',
    n_income_attr_p DECIMAL(20,4),
    minority_gain DECIMAL(20,4),
    oth_compr_income DECIMAL(20,4),
    t_compr_income DECIMAL(20,4),
    compr_inc_attr_p DECIMAL(20,4),
    compr_inc_attr_m_s DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
) COMMENT='利润表 - 一般工商业 - 来自Tushare income';

CREATE INDEX idx_income_ann_date ON t_stock_income(ann_date);
CREATE INDEX idx_income_f_ann_date ON t_stock_income(f_ann_date);
CREATE INDEX idx_income_end_date ON t_stock_income(end_date);

-- 15. 利润表 - 银行专用
DROP TABLE IF EXISTS t_stock_income_bank;
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
) COMMENT='利润表 - 银行专用 - 来自Tushare income';

CREATE INDEX idx_income_bank_ann_date ON t_stock_income_bank(ann_date);
CREATE INDEX idx_income_bank_end_date ON t_stock_income_bank(end_date);

-- 16. 利润表 - 保险专用
DROP TABLE IF EXISTS t_stock_income_insurance;
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
) COMMENT='利润表 - 保险专用 - 来自Tushare income';

CREATE INDEX idx_income_insurance_ann_date ON t_stock_income_insurance(ann_date);
CREATE INDEX idx_income_insurance_end_date ON t_stock_income_insurance(end_date);

-- 17. 利润表 - 证券专用
DROP TABLE IF EXISTS t_stock_income_securities;
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
) COMMENT='利润表 - 证券专用 - 来自Tushare income';

CREATE INDEX idx_income_securities_ann_date ON t_stock_income_securities(ann_date);
CREATE INDEX idx_income_securities_end_date ON t_stock_income_securities(end_date);

-- ========================================================
-- 四、财务数据表 - 资产负债表 (4张)
-- ========================================================

-- 18. 资产负债表 - 一般工商业
DROP TABLE IF EXISTS t_stock_balancesheet;
CREATE TABLE t_stock_balancesheet (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    f_ann_date VARCHAR(8) COMMENT '实际公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
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
    total_cur_assets DECIMAL(20,4) COMMENT '流动资产合计',
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
    total_nca DECIMAL(20,4) COMMENT '非流动资产合计',
    cash_reser_cb DECIMAL(20,4),
    depos_in_oth_bfi DECIMAL(20,4),
    prec_metals DECIMAL(20,4),
    deriv_assets DECIMAL(20,4),
    total_assets DECIMAL(20,4) COMMENT '资产总计',
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
    total_cur_liab DECIMAL(20,4) COMMENT '流动负债合计',
    bonds_payable DECIMAL(20,4),
    lt_payable DECIMAL(20,4),
    specific_payables DECIMAL(20,4),
    estimated_liab DECIMAL(20,4),
    defer_tax_liab DECIMAL(20,4),
    defer_inc_non_cur_liab DECIMAL(20,4),
    oth_ncl DECIMAL(20,4),
    total_ncl DECIMAL(20,4) COMMENT '非流动负债合计',
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
    total_liab DECIMAL(20,4) COMMENT '负债合计',
    rec_dep_invests DECIMAL(20,4),
    total_equity DECIMAL(20,4) COMMENT '所有者权益合计',
    minority_int DECIMAL(20,4),
    total_hldr_eqy_exc_min_int DECIMAL(20,4) COMMENT '归属于母公司所有者权益合计',
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
) COMMENT='资产负债表 - 一般工商业 - 来自Tushare balancesheet';

CREATE INDEX idx_balancesheet_ann_date ON t_stock_balancesheet(ann_date);
CREATE INDEX idx_balancesheet_end_date ON t_stock_balancesheet(end_date);

-- 19. 资产负债表 - 银行专用
DROP TABLE IF EXISTS t_stock_balancesheet_bank;
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
) COMMENT='资产负债表 - 银行专用 - 来自Tushare balancesheet';

CREATE INDEX idx_balancesheet_bank_ann_date ON t_stock_balancesheet_bank(ann_date);
CREATE INDEX idx_balancesheet_bank_end_date ON t_stock_balancesheet_bank(end_date);

-- 20. 资产负债表 - 保险专用
DROP TABLE IF EXISTS t_stock_balancesheet_insurance;
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
) COMMENT='资产负债表 - 保险专用 - 来自Tushare balancesheet';

CREATE INDEX idx_balancesheet_insurance_ann_date ON t_stock_balancesheet_insurance(ann_date);
CREATE INDEX idx_balancesheet_insurance_end_date ON t_stock_balancesheet_insurance(end_date);

-- 21. 资产负债表 - 证券专用
DROP TABLE IF EXISTS t_stock_balancesheet_securities;
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
) COMMENT='资产负债表 - 证券专用 - 来自Tushare balancesheet';

CREATE INDEX idx_balancesheet_securities_ann_date ON t_stock_balancesheet_securities(ann_date);
CREATE INDEX idx_balancesheet_securities_end_date ON t_stock_balancesheet_securities(end_date);

-- ========================================================
-- 五、财务数据表 - 现金流量表 (4张)
-- ========================================================

-- 22. 现金流量表 - 一般工商业
DROP TABLE IF EXISTS t_stock_cashflow;
CREATE TABLE t_stock_cashflow (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    f_ann_date VARCHAR(8) COMMENT '实际公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    comp_type VARCHAR(10),
    c_cash_equ_end_period DECIMAL(20,4) COMMENT '期末现金及现金等价物余额',
    n_cashflow_act DECIMAL(20,4) COMMENT '经营活动产生的现金流量净额',
    c_recp_sell_goods DECIMAL(20,4) COMMENT '销售商品、提供劳务收到的现金',
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
    c_paid_goods_s DECIMAL(20,4) COMMENT '购买商品、接受劳务支付的现金',
    c_paid_to_for_empl DECIMAL(20,4),
    c_paid_for_taxes DECIMAL(20,4),
    n_incr_clt_loan_adv DECIMAL(20,4),
    n_incr_dep_cbob DECIMAL(20,4),
    c_pay_claims_orig_inco DECIMAL(20,4),
    pay_handling_chrg DECIMAL(20,4),
    pay_comm_insur_plcy DECIMAL(20,4),
    oth_cash_pay_oper_act DECIMAL(20,4),
    st_cash_out_act DECIMAL(20,4),
    n_cashflow_inv_act DECIMAL(20,4) COMMENT '投资活动产生的现金流量净额',
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
    free_cashflow DECIMAL(20,4) COMMENT '企业自由现金流量',
    c_prepay_amt_borr DECIMAL(20,4),
    c_pay_dist_dcpint_profits DECIMAL(20,4),
    c_pay_debts DECIMAL(20,4),
    stot_cashout_fnc_act DECIMAL(20,4),
    n_incr_cash_equ DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, f_ann_date)
) COMMENT='现金流量表 - 一般工商业 - 来自Tushare cashflow';

CREATE INDEX idx_cashflow_ann_date ON t_stock_cashflow(ann_date);
CREATE INDEX idx_cashflow_end_date ON t_stock_cashflow(end_date);

-- 23. 现金流量表 - 银行专用
DROP TABLE IF EXISTS t_stock_cashflow_bank;
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
) COMMENT='现金流量表 - 银行专用 - 来自Tushare cashflow';

CREATE INDEX idx_cashflow_bank_ann_date ON t_stock_cashflow_bank(ann_date);
CREATE INDEX idx_cashflow_bank_end_date ON t_stock_cashflow_bank(end_date);

-- 24. 现金流量表 - 保险专用
DROP TABLE IF EXISTS t_stock_cashflow_insurance;
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
) COMMENT='现金流量表 - 保险专用 - 来自Tushare cashflow';

CREATE INDEX idx_cashflow_insurance_ann_date ON t_stock_cashflow_insurance(ann_date);
CREATE INDEX idx_cashflow_insurance_end_date ON t_stock_cashflow_insurance(end_date);

-- 25. 现金流量表 - 证券专用
DROP TABLE IF EXISTS t_stock_cashflow_securities;
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
) COMMENT='现金流量表 - 证券专用 - 来自Tushare cashflow';

CREATE INDEX idx_cashflow_securities_ann_date ON t_stock_cashflow_securities(ann_date);
CREATE INDEX idx_cashflow_securities_end_date ON t_stock_cashflow_securities(end_date);

-- ========================================================
-- 六、财务数据表 - 指标与衍生 (6张)
-- ========================================================

-- 26. 财务指标数据表
DROP TABLE IF EXISTS t_stock_fina_indicator;
CREATE TABLE t_stock_fina_indicator (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    roe DECIMAL(10,4) COMMENT '净资产收益率(%)',
    roe_diluted DECIMAL(10,4) COMMENT '摊薄净资产收益率(%)',
    roe_avg DECIMAL(10,4),
    roa DECIMAL(10,4) COMMENT '总资产报酬率(%)',
    roa_yearly DECIMAL(10,4),
    sales_margin DECIMAL(10,4) COMMENT '销售净利率(%)',
    net_profit_margin DECIMAL(10,4),
    gross_profit_margin DECIMAL(10,4) COMMENT '销售毛利率(%)',
    sales_to_admin_ratio DECIMAL(10,4),
    sales_to_sale_ratio DECIMAL(10,4),
    asset_turnover DECIMAL(10,4) COMMENT '总资产周转率',
    ca_turnover DECIMAL(10,4),
    fa_turnover DECIMAL(10,4),
    current_ratio DECIMAL(10,4) COMMENT '流动比率',
    quick_ratio DECIMAL(10,4) COMMENT '速动比率',
    cash_ratio DECIMAL(10,4),
    inv_days DECIMAL(10,4),
    ar_days DECIMAL(10,4),
    debt_to_assets DECIMAL(10,4) COMMENT '资产负债率(%)',
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
    netprofit_yoy DECIMAL(10,4) COMMENT '归属母公司股东的净利润同比增长率(%)',
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
) COMMENT='财务指标数据表 - 来自Tushare fina_indicator';

CREATE INDEX idx_fina_indicator_ann_date ON t_stock_fina_indicator(ann_date);
CREATE INDEX idx_fina_indicator_end_date ON t_stock_fina_indicator(end_date);
CREATE INDEX idx_fina_indicator_roe ON t_stock_fina_indicator(roe);

-- 27. 财务审计意见表
DROP TABLE IF EXISTS t_stock_fina_audit;
CREATE TABLE t_stock_fina_audit (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    audit_result VARCHAR(200) COMMENT '审计结果',
    audit_fees DECIMAL(20,4) COMMENT '审计总费用（元）',
    audit_agency VARCHAR(200) COMMENT '会计事务所',
    sign_account VARCHAR(200) COMMENT '签字会计师',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
) COMMENT='财务审计意见表 - 来自Tushare fina_audit';

CREATE INDEX idx_fina_audit_ann_date ON t_stock_fina_audit(ann_date);
CREATE INDEX idx_fina_audit_end_date ON t_stock_fina_audit(end_date);

-- 28. 主营业务构成表
DROP TABLE IF EXISTS t_stock_fina_mainbz;
CREATE TABLE t_stock_fina_mainbz (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    bz_item VARCHAR(200) COMMENT '主营业务项目',
    bz_sales DECIMAL(20,4) COMMENT '主营业务收入（元）',
    bz_profit DECIMAL(20,4) COMMENT '主营业务利润（元）',
    bz_cost DECIMAL(20,4) COMMENT '主营业务成本（元）',
    curr_type VARCHAR(10),
    update_flag VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, bz_item)
) COMMENT='主营业务构成表 - 来自Tushare fina_mainbz';

CREATE INDEX idx_fina_mainbz_end_date ON t_stock_fina_mainbz(end_date);
CREATE INDEX idx_fina_mainbz_bz_item ON t_stock_fina_mainbz(bz_item);

-- 29. 业绩预告表
DROP TABLE IF EXISTS t_stock_forecast;
CREATE TABLE t_stock_forecast (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    type VARCHAR(50) COMMENT '业绩预告类型',
    p_change_min DECIMAL(10,4) COMMENT '预告净利润变动幅度下限(%)',
    p_change_max DECIMAL(10,4) COMMENT '预告净利润变动幅度上限(%)',
    net_profit_min DECIMAL(20,4) COMMENT '预告净利润下限（万元）',
    net_profit_max DECIMAL(20,4) COMMENT '预告净利润上限（万元）',
    last_parent_net DECIMAL(20,4) COMMENT '上年同期归属母公司净利润（万元）',
    first_ann_date VARCHAR(8) COMMENT '首次公告日',
    summary TEXT COMMENT '业绩预告摘要',
    change_reason TEXT COMMENT '业绩变动原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
) COMMENT='业绩预告表 - 来自Tushare forecast';

CREATE INDEX idx_forecast_ann_date ON t_stock_forecast(ann_date);
CREATE INDEX idx_forecast_end_date ON t_stock_forecast(end_date);
CREATE INDEX idx_forecast_type ON t_stock_forecast(type);

-- 30. 业绩快报表
DROP TABLE IF EXISTS t_stock_express;
CREATE TABLE t_stock_express (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    revenue DECIMAL(20,4) COMMENT '营业收入(元)',
    operate_profit DECIMAL(20,4) COMMENT '营业利润(元)',
    total_profit DECIMAL(20,4) COMMENT '利润总额(元)',
    n_income DECIMAL(20,4) COMMENT '净利润(元)',
    total_assets DECIMAL(20,4) COMMENT '总资产(元)',
    total_hldr_eqy_exc_min_int DECIMAL(20,4),
    diluted_eps DECIMAL(20,4) COMMENT '摊薄每股收益',
    dps DECIMAL(20,4),
    yoy_sales DECIMAL(10,4) COMMENT '同比增长率:营业收入',
    yoy_op DECIMAL(10,4),
    yoy_tp DECIMAL(10,4),
    yoy_netprofit DECIMAL(10,4) COMMENT '同比增长率:净利润',
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
) COMMENT='业绩快报表 - 来自Tushare express';

CREATE INDEX idx_express_ann_date ON t_stock_express(ann_date);
CREATE INDEX idx_express_end_date ON t_stock_express(end_date);

-- 31. 分红送股表
DROP TABLE IF EXISTS t_stock_dividend;
CREATE TABLE t_stock_dividend (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    end_date VARCHAR(8) NOT NULL COMMENT '分红年度',
    ann_date VARCHAR(8) COMMENT '公告日期',
    div_proc VARCHAR(50) COMMENT '实施进度',
    stk_div DECIMAL(10,4) COMMENT '每股送转',
    stk_bo_rate DECIMAL(10,4),
    stk_co_rate DECIMAL(10,4),
    cash_div DECIMAL(10,4) COMMENT '每股分红（税后）',
    cash_div_tax DECIMAL(10,4) COMMENT '每股分红（税前）',
    record_date VARCHAR(8) COMMENT '股权登记日',
    ex_date VARCHAR(8) COMMENT '除权除息日',
    pay_date VARCHAR(8) COMMENT '派息日',
    div_listdate VARCHAR(8) COMMENT '红股上市日',
    imp_ann_date VARCHAR(8),
    base_date VARCHAR(8),
    base_share DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
) COMMENT='分红送股表 - 来自Tushare dividend';

CREATE INDEX idx_dividend_ann_date ON t_stock_dividend(ann_date);
CREATE INDEX idx_dividend_end_date ON t_stock_dividend(end_date);
CREATE INDEX idx_dividend_ex_date ON t_stock_dividend(ex_date);

-- ========================================================
-- 七、市场行为与参考数据 (9张)
-- ========================================================

-- 32. 前十大股东表
DROP TABLE IF EXISTS t_stock_top10_holders;
CREATE TABLE t_stock_top10_holders (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    holder_name VARCHAR(200) COMMENT '股东名称',
    hold_amount DECIMAL(20,4) COMMENT '持有数量（股）',
    hold_ratio DECIMAL(10,4) COMMENT '持有比例(%)',
    hold_change DECIMAL(20,4) COMMENT '变动数量',
    holder_rank INTEGER COMMENT '股东排名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, holder_rank)
) COMMENT='前十大股东表 - 来自Tushare top10_holders';

CREATE INDEX idx_top10_holders_ann_date ON t_stock_top10_holders(ann_date);
CREATE INDEX idx_top10_holders_end_date ON t_stock_top10_holders(end_date);

-- 33. 前十大流通股东表
DROP TABLE IF EXISTS t_stock_top10_float_holders;
CREATE TABLE t_stock_top10_float_holders (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '报告期',
    holder_name VARCHAR(200) COMMENT '股东名称',
    hold_amount DECIMAL(20,4) COMMENT '持有数量（股）',
    hold_ratio DECIMAL(10,4) COMMENT '持有比例(%)',
    hold_float_ratio DECIMAL(10,4) COMMENT '流通股本持股比例(%)',
    hold_change DECIMAL(20,4) COMMENT '变动数量',
    holder_type VARCHAR(100) COMMENT '股东类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date, holder_name)
) COMMENT='前十大流通股东表 - 来自Tushare top10_floatholders';

CREATE INDEX idx_top10_fh_ann_date ON t_stock_top10_float_holders(ann_date);
CREATE INDEX idx_top10_fh_end_date ON t_stock_top10_float_holders(end_date);
CREATE INDEX idx_top10_fh_holder_name ON t_stock_top10_float_holders(holder_name);

-- 34. 股东人数表
DROP TABLE IF EXISTS t_stock_holder_number;
CREATE TABLE t_stock_holder_number (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    end_date VARCHAR(8) NOT NULL COMMENT '截止日期',
    holder_num INTEGER COMMENT '股东户数',
    holder_num_change INTEGER COMMENT '股东户数变动',
    holder_num_ratio DECIMAL(10,4) COMMENT '股东户数变动比例(%)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, end_date)
) COMMENT='股东人数表 - 来自Tushare stk_holdernumber';

CREATE INDEX idx_holder_num_ann_date ON t_stock_holder_number(ann_date);
CREATE INDEX idx_holder_num_end_date ON t_stock_holder_number(end_date);

-- 35. 股东增减持表
DROP TABLE IF EXISTS t_stock_holder_trade;
CREATE TABLE t_stock_holder_trade (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    ann_date VARCHAR(8) COMMENT '公告日期',
    holder_name VARCHAR(200) COMMENT '股东名称',
    holder_type VARCHAR(50) COMMENT '股东类型',
    in_de VARCHAR(10) COMMENT '增减持方向',
    change_vol DECIMAL(20,4) COMMENT '变动数量',
    change_ratio DECIMAL(10,4) COMMENT '变动占总股本比例(%)',
    after_share DECIMAL(20,4) COMMENT '变动后持股数量',
    after_ratio DECIMAL(10,4) COMMENT '变动后持股比例(%)',
    avg_price DECIMAL(16,4) COMMENT '平均交易价格',
    total_share DECIMAL(20,4) COMMENT '持股总数',
    begin_date VARCHAR(8) COMMENT '增减持开始日期',
    close_date VARCHAR(8) COMMENT '增减持结束日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, ann_date, holder_name)
) COMMENT='股东增减持表 - 来自Tushare stk_holdertrade';

CREATE INDEX idx_holder_trade_ann_date ON t_stock_holder_trade(ann_date);
CREATE INDEX idx_holder_trade_holder_name ON t_stock_holder_trade(holder_name);

-- ========================================================
-- 触发器：自动更新 updated_at 字段
-- ========================================================

-- 创建触发器函数

-- 为基础数据表添加触发器

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

-- ========================================================
-- 初始化数据
-- ========================================================

-- 记录数据库版本
CREATE TABLE IF NOT EXISTS t_db_version (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='数据库版本记录表';

INSERT INTO t_db_version (version, description) VALUES ('1.0.0', 'Initial schema with 40 Tushare tables');

