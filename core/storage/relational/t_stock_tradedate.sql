-- Tushare trade_cal 交易日历表
-- 来源: Tushare API - trade_cal
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_tradedate (
    exchange VARCHAR(20) NOT NULL COMMENT '交易所 SSE/SZSE',
    cal_date VARCHAR(8) NOT NULL COMMENT '日历日期 YYYYMMDD',
    is_open TINYINT(1) COMMENT '是否交易日 0否 1是',
    pretrade_date VARCHAR(8) COMMENT '上一个交易日 YYYYMMDD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    PRIMARY KEY (exchange, cal_date),
    INDEX idx_cal_date (cal_date),
    INDEX idx_is_open (is_open),
    INDEX idx_pretrade_date (pretrade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日历表 - 来自Tushare trade_cal';
