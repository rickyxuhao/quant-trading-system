-- Tushare ST股票列表表
-- 来源: Tushare API - stock_st
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_st_list (
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    name VARCHAR(100) COMMENT '股票名称',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
    type VARCHAR(20) COMMENT '类型',
    type_name VARCHAR(50) COMMENT '类型名称',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    PRIMARY KEY (ts_code, trade_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ST股票列表表 - 来自Tushare stock_st';
