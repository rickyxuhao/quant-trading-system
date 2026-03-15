-- Tushare adj_factor 复权因子表
-- 来源: Tushare API - adj_factor
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_adjfactor (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
    adj_factor DECIMAL(16,6) COMMENT '复权因子',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    PRIMARY KEY (ts_code, trade_date),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='复权因子表 - 来自Tushare adj_factor';
