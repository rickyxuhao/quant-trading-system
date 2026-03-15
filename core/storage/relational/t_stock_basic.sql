-- Tushare stock_basic 原始数据表
-- 来源: Tushare API - stock_basic
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY COMMENT 'TS代码',
    symbol VARCHAR(20) COMMENT '股票代码',
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    INDEX idx_symbol (symbol),
    INDEX idx_industry (industry),
    INDEX idx_market (market),
    INDEX idx_list_status (list_status),
    INDEX idx_list_date (list_date),
    INDEX idx_area (area)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表 - 来自Tushare stock_basic';
