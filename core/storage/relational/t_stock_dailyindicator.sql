-- Tushare daily_basic 每日指标表
-- 来源: Tushare API - daily_basic
-- 数据库: tushare_biz

CREATE TABLE IF NOT EXISTS t_stock_dailyindicator (
    ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期 YYYYMMDD',
    close DECIMAL(16,4) COMMENT '当日收盘价',
    turnover_rate DECIMAL(10,4) COMMENT '换手率(%)',
    turnover_rate_f DECIMAL(10,4) COMMENT '换手率(自由流通股)',
    volume_ratio DECIMAL(10,4) COMMENT '量比',
    pe DECIMAL(16,4) COMMENT '市盈率（总市值/净利润）',
    pe_ttm DECIMAL(16,4) COMMENT '市盈率TTM',
    pb DECIMAL(16,4) COMMENT '市净率（总市值/净资产）',
    ps DECIMAL(16,4) COMMENT '市销率',
    ps_ttm DECIMAL(16,4) COMMENT '市销率TTM',
    dv_ratio DECIMAL(10,4) COMMENT '股息率(%)',
    dv_ttm DECIMAL(10,4) COMMENT '股息率TTM(%)',
    total_share DECIMAL(20,4) COMMENT '总股本（万股）',
    float_share DECIMAL(20,4) COMMENT '流通股本（万股）',
    free_share DECIMAL(20,4) COMMENT '自由流通股本（万股）',
    total_mv DECIMAL(20,4) COMMENT '总市值（万元）',
    circ_mv DECIMAL(20,4) COMMENT '流通市值（万元）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    PRIMARY KEY (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_pe (pe),
    INDEX idx_pb (pb),
    INDEX idx_turnover_rate (turnover_rate),
    INDEX idx_total_mv (total_mv),
    INDEX idx_circ_mv (circ_mv)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日指标表（估值/市值/换手）- 来自Tushare daily_basic';
