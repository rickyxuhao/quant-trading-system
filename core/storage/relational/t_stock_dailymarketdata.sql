-- Tushare daily 股票日线行情表
-- 来源: Tushare API - daily
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_dailymarketdata (
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    PRIMARY KEY (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_vol (vol),
    INDEX idx_amount (amount)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票日线行情表 - 来自Tushare daily';
