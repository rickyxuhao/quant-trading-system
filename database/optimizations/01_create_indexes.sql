-- 数据库索引优化脚本
-- 创建复合索引以提高查询性能

-- 日线数据复合索引
CREATE INDEX IF NOT EXISTS idx_daily_market
ON t_stock_dailymarketdata(ts_code, trade_date);

-- 复权因子复合索引
CREATE INDEX IF NOT EXISTS idx_adj_factor
ON t_stock_adjfactor(ts_code, trade_date);

-- 指数数据复合索引
CREATE INDEX IF NOT EXISTS idx_index_daily
ON t_index_dailymarketdata(ts_code, trade_date);

-- ST列表复合索引
CREATE INDEX IF NOT EXISTS idx_st_list
ON t_stock_st_list(ts_code, start_date, end_date);

-- 交易日历索引
CREATE INDEX IF NOT EXISTS idx_trade_date
ON t_stock_tradedate(cal_date, is_open);

-- 股票基础信息索引
CREATE INDEX IF NOT EXISTS idx_stock_basic
ON t_stock_basic(ts_code, market, industry);
