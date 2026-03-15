-- ========================================================  
-- 数据库CHECK约束补充脚本 - PostgreSQL
-- 来源: Tushare Pro API 数据质量检查
-- 作用: 为关键表添加数据完整性约束
-- 版本: 1.1.0
-- 生成日期: 2026-03-08
-- ========================================================  

-- ========================================================  
-- 一、基础数据表约束
-- ========================================================  

-- 1. 股票基础信息表 - 状态枚举约束
ALTER TABLE t_stock_basic DROP CONSTRAINT IF EXISTS chk_list_status;
ALTER TABLE t_stock_basic ADD CONSTRAINT chk_list_status 
    CHECK (list_status IS NULL OR list_status IN ('L', 'D', 'G', 'P'));

ALTER TABLE t_stock_basic DROP CONSTRAINT IF EXISTS chk_is_hs;
ALTER TABLE t_stock_basic ADD CONSTRAINT chk_is_hs 
    CHECK (is_hs IS NULL OR is_hs IN ('N', 'H', 'S'));

-- 日期格式约束 (8位数字)
ALTER TABLE t_stock_basic DROP CONSTRAINT IF EXISTS chk_list_date_format;
ALTER TABLE t_stock_basic ADD CONSTRAINT chk_list_date_format 
    CHECK (list_date IS NULL OR list_date ~ '^[0-9]{8}$');

ALTER TABLE t_stock_basic DROP CONSTRAINT IF EXISTS chk_delist_date_format;
ALTER TABLE t_stock_basic ADD CONSTRAINT chk_delist_date_format 
    CHECK (delist_date IS NULL OR delist_date ~ '^[0-9]{8}$');

-- 2. 交易日历表 - 是否交易只能是0或1
ALTER TABLE t_stock_tradedate DROP CONSTRAINT IF EXISTS chk_is_open;
ALTER TABLE t_stock_tradedate ADD CONSTRAINT chk_is_open 
    CHECK (is_open IS NULL OR is_open IN (0, 1));

ALTER TABLE t_stock_tradedate DROP CONSTRAINT IF EXISTS chk_cal_date_format;
ALTER TABLE t_stock_tradedate ADD CONSTRAINT chk_cal_date_format 
    CHECK (cal_date ~ '^[0-9]{8}$');

-- 3. IPO新股列表 - 价格和数量非负约束
ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_amount;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_amount 
    CHECK (amount IS NULL OR amount >= 0);

ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_market_amount;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_market_amount 
    CHECK (market_amount IS NULL OR market_amount >= 0);

ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_price;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_price 
    CHECK (price IS NULL OR price >= 0);

ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_pe;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_pe 
    CHECK (pe IS NULL OR pe >= 0);

ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_funds;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_funds 
    CHECK (funds IS NULL OR funds >= 0);

ALTER TABLE t_stock_ipo DROP CONSTRAINT IF EXISTS chk_ipo_ballot;
ALTER TABLE t_stock_ipo ADD CONSTRAINT chk_ipo_ballot 
    CHECK (ballot IS NULL OR (ballot >= 0 AND ballot <= 100));

-- 4. 上市公司基本信息 - 员工人数和注册资本非负
ALTER TABLE t_stock_company DROP CONSTRAINT IF EXISTS chk_company_employees;
ALTER TABLE t_stock_company ADD CONSTRAINT chk_company_employees 
    CHECK (employees IS NULL OR employees >= 0);

ALTER TABLE t_stock_company DROP CONSTRAINT IF EXISTS chk_company_reg_capital;
ALTER TABLE t_stock_company ADD CONSTRAINT chk_company_reg_capital 
    CHECK (reg_capital IS NULL OR reg_capital >= 0);

-- ========================================================  
-- 二、行情数据表约束
-- ========================================================  

-- 5. 股票日线行情表 - 价格逻辑约束
ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_open;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_open 
    CHECK (open IS NULL OR open >= 0);

ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_high;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_high 
    CHECK (high IS NULL OR high >= 0);

ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_low;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_low 
    CHECK (low IS NULL OR low >= 0);

ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_close;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_close 
    CHECK (close IS NULL OR close >= 0);

ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_pre_close;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_pre_close 
    CHECK (pre_close IS NULL OR pre_close >= 0);

-- 最高价必须大于等于最低价
ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_high_low;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_high_low 
    CHECK (high IS NULL OR low IS NULL OR high >= low);

-- 成交量和成交额非负
ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_vol;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_vol 
    CHECK (vol IS NULL OR vol >= 0);

ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_amount;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_amount 
    CHECK (amount IS NULL OR amount >= 0);

-- 涨跌幅合理范围 (考虑ST股和新股可能超过10%，放宽到-30%~+30%)
ALTER TABLE t_stock_dailymarketdata DROP CONSTRAINT IF EXISTS chk_daily_pct_chg;
ALTER TABLE t_stock_dailymarketdata ADD CONSTRAINT chk_daily_pct_chg 
    CHECK (pct_chg IS NULL OR (pct_chg >= -50 AND pct_chg <= 50));

-- 6. 复权因子表 - 复权因子必须为正数
ALTER TABLE t_stock_adjfactor DROP CONSTRAINT IF EXISTS chk_adj_factor;
ALTER TABLE t_stock_adjfactor ADD CONSTRAINT chk_adj_factor 
    CHECK (adj_factor IS NULL OR adj_factor > 0);

-- 7. 每日指标表 - 估值指标约束
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_close;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_close 
    CHECK (close IS NULL OR close >= 0);

-- 换手率非负
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_turnover;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_turnover 
    CHECK (turnover_rate IS NULL OR turnover_rate >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_turnover_f;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_turnover_f 
    CHECK (turnover_rate_f IS NULL OR turnover_rate_f >= 0);

-- 量比非负
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_volume_ratio;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_volume_ratio 
    CHECK (volume_ratio IS NULL OR volume_ratio >= 0);

-- 估值指标合理范围 (允许极端值，但排除负数)
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_pe;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_pe 
    CHECK (pe IS NULL OR pe >= 0 OR pe = -99999999);  -- -99999999可能表示亏损

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_pe_ttm;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_pe_ttm 
    CHECK (pe_ttm IS NULL OR pe_ttm >= 0 OR pe_ttm = -99999999);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_pb;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_pb 
    CHECK (pb IS NULL OR pb >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_ps;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_ps 
    CHECK (ps IS NULL OR ps >= 0);

-- 股息率非负
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_dv;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_dv 
    CHECK (dv_ratio IS NULL OR dv_ratio >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_dv_ttm;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_dv_ttm 
    CHECK (dv_ttm IS NULL OR dv_ttm >= 0);

-- 股本和市值非负
ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_total_share;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_total_share 
    CHECK (total_share IS NULL OR total_share >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_float_share;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_float_share 
    CHECK (float_share IS NULL OR float_share >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_free_share;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_free_share 
    CHECK (free_share IS NULL OR free_share >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_total_mv;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_total_mv 
    CHECK (total_mv IS NULL OR total_mv >= 0);

ALTER TABLE t_stock_daily_basic DROP CONSTRAINT IF EXISTS chk_daily_basic_circ_mv;
ALTER TABLE t_stock_daily_basic ADD CONSTRAINT chk_daily_basic_circ_mv 
    CHECK (circ_mv IS NULL OR circ_mv >= 0);

-- 8. ST股票列表 - is_new只能是0或1
ALTER TABLE t_stock_st_list DROP CONSTRAINT IF EXISTS chk_st_list_is_new;
ALTER TABLE t_stock_st_list ADD CONSTRAINT chk_st_list_is_new 
    CHECK (is_new IS NULL OR is_new IN (0, 1));

-- 9. 每日涨跌停价格表 - 价格逻辑
ALTER TABLE t_stock_dailylimitprice DROP CONSTRAINT IF EXISTS chk_limit_close;
ALTER TABLE t_stock_dailylimitprice ADD CONSTRAINT chk_limit_close 
    CHECK (close IS NULL OR close >= 0);

ALTER TABLE t_stock_dailylimitprice DROP CONSTRAINT IF EXISTS chk_limit_up;
ALTER TABLE t_stock_dailylimitprice ADD CONSTRAINT chk_limit_up 
    CHECK (up_limit IS NULL OR up_limit >= 0);

ALTER TABLE t_stock_dailylimitprice DROP CONSTRAINT IF EXISTS chk_limit_down;
ALTER TABLE t_stock_dailylimitprice ADD CONSTRAINT chk_limit_down 
    CHECK (down_limit IS NULL OR down_limit >= 0);

-- 涨停板必须大于等于跌停板
ALTER TABLE t_stock_dailylimitprice DROP CONSTRAINT IF EXISTS chk_limit_up_down;
ALTER TABLE t_stock_dailylimitprice ADD CONSTRAINT chk_limit_up_down 
    CHECK (up_limit IS NULL OR down_limit IS NULL OR up_limit >= down_limit);

-- 振幅非负
ALTER TABLE t_stock_dailylimitprice DROP CONSTRAINT IF EXISTS chk_limit_amp;
ALTER TABLE t_stock_dailylimitprice ADD CONSTRAINT chk_limit_amp 
    CHECK (amp IS NULL OR amp >= 0);

-- 10. 个股资金流向表 - 成交量和金额非负
ALTER TABLE t_stock_moneyflow DROP CONSTRAINT IF EXISTS chk_moneyflow_buy_sm_vol;
ALTER TABLE t_stock_moneyflow ADD CONSTRAINT chk_moneyflow_buy_sm_vol 
    CHECK (buy_sm_vol IS NULL OR buy_sm_vol >= 0);

ALTER TABLE t_stock_moneyflow DROP CONSTRAINT IF EXISTS chk_moneyflow_buy_sm_amount;
ALTER TABLE t_stock_moneyflow ADD CONSTRAINT chk_moneyflow_buy_sm_amount 
    CHECK (buy_sm_amount IS NULL OR buy_sm_amount >= 0);

ALTER TABLE t_stock_moneyflow DROP CONSTRAINT IF EXISTS chk_moneyflow_sell_sm_vol;
ALTER TABLE t_stock_moneyflow ADD CONSTRAINT chk_moneyflow_sell_sm_vol 
    CHECK (sell_sm_vol IS NULL OR sell_sm_vol >= 0);

ALTER TABLE t_stock_moneyflow DROP CONSTRAINT IF EXISTS chk_moneyflow_sell_sm_amount;
ALTER TABLE t_stock_moneyflow ADD CONSTRAINT chk_moneyflow_sell_sm_amount 
    CHECK (sell_sm_amount IS NULL OR sell_sm_amount >= 0);

-- ========================================================  
-- 三、财务数据表约束
-- ========================================================  

-- 11. 财务指标数据表 - 财务比率合理范围
ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_roe;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_roe 
    CHECK (roe IS NULL OR (roe >= -1000 AND roe <= 1000));

ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_roa;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_roa 
    CHECK (roa IS NULL OR (roa >= -1000 AND roa <= 1000));

-- 销售净利率和毛利率 (-100% 到 100%)
ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_sales_margin;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_sales_margin 
    CHECK (sales_margin IS NULL OR (sales_margin >= -100 AND sales_margin <= 100));

ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_gross_margin;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_gross_margin 
    CHECK (gross_profit_margin IS NULL OR (gross_profit_margin >= -100 AND gross_profit_margin <= 100));

-- 资产负债率 (0% 到 200%，允许极端负债情况)
ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_debt_ratio;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_debt_ratio 
    CHECK (debt_to_assets IS NULL OR (debt_to_assets >= 0 AND debt_to_assets <= 200));

-- 流动比率和速动比率 (非负)
ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_current_ratio;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_current_ratio 
    CHECK (current_ratio IS NULL OR current_ratio >= 0);

ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_quick_ratio;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_quick_ratio 
    CHECK (quick_ratio IS NULL OR quick_ratio >= 0);

-- 周转率非负
ALTER TABLE t_stock_fina_indicator DROP CONSTRAINT IF EXISTS chk_fina_asset_turnover;
ALTER TABLE t_stock_fina_indicator ADD CONSTRAINT chk_fina_asset_turnover 
    CHECK (asset_turnover IS NULL OR asset_turnover >= 0);

-- 12. 财务审计意见表 - 审计费用非负
ALTER TABLE t_stock_fina_audit DROP CONSTRAINT IF EXISTS chk_fina_audit_fees;
ALTER TABLE t_stock_fina_audit ADD CONSTRAINT chk_fina_audit_fees 
    CHECK (audit_fees IS NULL OR audit_fees >= 0);

-- 13. 主营业务构成表 - 收入/成本/利润逻辑
ALTER TABLE t_stock_fina_mainbz DROP CONSTRAINT IF EXISTS chk_mainbz_sales;
ALTER TABLE t_stock_fina_mainbz ADD CONSTRAINT chk_mainbz_sales 
    CHECK (bz_sales IS NULL OR bz_sales >= 0);

ALTER TABLE t_stock_fina_mainbz DROP CONSTRAINT IF EXISTS chk_mainbz_cost;
ALTER TABLE t_stock_fina_mainbz ADD CONSTRAINT chk_mainbz_cost 
    CHECK (bz_cost IS NULL OR bz_cost >= 0);

-- 14. 业绩预告表 - 利润变动幅度合理范围
ALTER TABLE t_stock_forecast DROP CONSTRAINT IF EXISTS chk_forecast_p_change_min;
ALTER TABLE t_stock_forecast ADD CONSTRAINT chk_forecast_p_change_min 
    CHECK (p_change_min IS NULL OR (p_change_min >= -10000 AND p_change_min <= 10000));

ALTER TABLE t_stock_forecast DROP CONSTRAINT IF EXISTS chk_forecast_p_change_max;
ALTER TABLE t_stock_forecast ADD CONSTRAINT chk_forecast_p_change_max 
    CHECK (p_change_max IS NULL OR (p_change_max >= -10000 AND p_change_max <= 10000));

-- 15. 业绩快报表 - 同比增长率合理范围
ALTER TABLE t_stock_express DROP CONSTRAINT IF EXISTS chk_express_yoy_sales;
ALTER TABLE t_stock_express ADD CONSTRAINT chk_express_yoy_sales 
    CHECK (yoy_sales IS NULL OR (yoy_sales >= -10000 AND yoy_sales <= 10000));

ALTER TABLE t_stock_express DROP CONSTRAINT IF EXISTS chk_express_yoy_netprofit;
ALTER TABLE t_stock_express ADD CONSTRAINT chk_express_yoy_netprofit 
    CHECK (yoy_netprofit IS NULL OR (yoy_netprofit >= -10000 AND yoy_netprofit <= 10000));

-- 16. 分红送股表 - 送转和分红非负
ALTER TABLE t_stock_dividend DROP CONSTRAINT IF EXISTS chk_dividend_stk_div;
ALTER TABLE t_stock_dividend ADD CONSTRAINT chk_dividend_stk_div 
    CHECK (stk_div IS NULL OR stk_div >= 0);

ALTER TABLE t_stock_dividend DROP CONSTRAINT IF EXISTS chk_dividend_cash_div;
ALTER TABLE t_stock_dividend ADD CONSTRAINT chk_dividend_cash_div 
    CHECK (cash_div IS NULL OR cash_div >= 0);

-- ========================================================  
-- 四、市场行为数据表约束
-- ========================================================  

-- 17. 前十大股东表 - 持股比例和数量约束
ALTER TABLE t_stock_top10_holders DROP CONSTRAINT IF EXISTS chk_top10_hold_amount;
ALTER TABLE t_stock_top10_holders ADD CONSTRAINT chk_top10_hold_amount 
    CHECK (hold_amount IS NULL OR hold_amount >= 0);

ALTER TABLE t_stock_top10_holders DROP CONSTRAINT IF EXISTS chk_top10_hold_ratio;
ALTER TABLE t_stock_top10_holders ADD CONSTRAINT chk_top10_hold_ratio 
    CHECK (hold_ratio IS NULL OR (hold_ratio >= 0 AND hold_ratio <= 100));

ALTER TABLE t_stock_top10_holders DROP CONSTRAINT IF EXISTS chk_top10_holder_rank;
ALTER TABLE t_stock_top10_holders ADD CONSTRAINT chk_top10_holder_rank 
    CHECK (holder_rank IS NULL OR (holder_rank >= 1 AND holder_rank <= 10));

-- 18. 前十大流通股东表 - 同上
ALTER TABLE t_stock_top10_float_holders DROP CONSTRAINT IF EXISTS chk_top10_fh_hold_amount;
ALTER TABLE t_stock_top10_float_holders ADD CONSTRAINT chk_top10_fh_hold_amount 
    CHECK (hold_amount IS NULL OR hold_amount >= 0);

ALTER TABLE t_stock_top10_float_holders DROP CONSTRAINT IF EXISTS chk_top10_fh_hold_ratio;
ALTER TABLE t_stock_top10_float_holders ADD CONSTRAINT chk_top10_fh_hold_ratio 
    CHECK (hold_ratio IS NULL OR (hold_ratio >= 0 AND hold_ratio <= 100));

ALTER TABLE t_stock_top10_float_holders DROP CONSTRAINT IF EXISTS chk_top10_fh_holder_rank;
ALTER TABLE t_stock_top10_float_holders ADD CONSTRAINT chk_top10_fh_holder_rank 
    CHECK (holder_rank IS NULL OR (holder_rank >= 1 AND holder_rank <= 10));

-- 19. 股东人数表 - 人数非负
ALTER TABLE t_stock_holder_number DROP CONSTRAINT IF EXISTS chk_holder_num;
ALTER TABLE t_stock_holder_number ADD CONSTRAINT chk_holder_num 
    CHECK (holder_num IS NULL OR holder_num >= 0);

-- 20. 股东增减持表 - 数量和价格约束
ALTER TABLE t_stock_holder_trade DROP CONSTRAINT IF EXISTS chk_holder_trade_change_vol;
ALTER TABLE t_stock_holder_trade ADD CONSTRAINT chk_holder_trade_change_vol 
    CHECK (change_vol IS NULL OR change_vol >= 0);

ALTER TABLE t_stock_holder_trade DROP CONSTRAINT IF EXISTS chk_holder_trade_change_ratio;
ALTER TABLE t_stock_holder_trade ADD CONSTRAINT chk_holder_trade_change_ratio 
    CHECK (change_ratio IS NULL OR (change_ratio >= 0 AND change_ratio <= 100));

ALTER TABLE t_stock_holder_trade DROP CONSTRAINT IF EXISTS chk_holder_trade_after_share;
ALTER TABLE t_stock_holder_trade ADD CONSTRAINT chk_holder_trade_after_share 
    CHECK (after_share IS NULL OR after_share >= 0);

ALTER TABLE t_stock_holder_trade DROP CONSTRAINT IF EXISTS chk_holder_trade_after_ratio;
ALTER TABLE t_stock_holder_trade ADD CONSTRAINT chk_holder_trade_after_ratio 
    CHECK (after_ratio IS NULL OR (after_ratio >= 0 AND after_ratio <= 100));

ALTER TABLE t_stock_holder_trade DROP CONSTRAINT IF EXISTS chk_holder_trade_avg_price;
ALTER TABLE t_stock_holder_trade ADD CONSTRAINT chk_holder_trade_avg_price 
    CHECK (avg_price IS NULL OR avg_price >= 0);

-- 21. 股权质押表 - 质押比例约束
ALTER TABLE t_stock_cgq DROP CONSTRAINT IF EXISTS chk_cgq_hold_vol;
ALTER TABLE t_stock_cgq ADD CONSTRAINT chk_cgq_hold_vol 
    CHECK (hold_vol IS NULL OR hold_vol >= 0);

ALTER TABLE t_stock_cgq DROP CONSTRAINT IF EXISTS chk_cgq_hold_ratio;
ALTER TABLE t_stock_cgq ADD CONSTRAINT chk_cgq_hold_ratio 
    CHECK (hold_ratio IS NULL OR (hold_ratio >= 0 AND hold_ratio <= 100));

ALTER TABLE t_stock_cgq DROP CONSTRAINT IF EXISTS chk_cgq_pledge_vol;
ALTER TABLE t_stock_cgq ADD CONSTRAINT chk_cgq_pledge_vol 
    CHECK (pledge_vol IS NULL OR pledge_vol >= 0);

ALTER TABLE t_stock_cgq DROP CONSTRAINT IF EXISTS chk_cgq_pledge_ratio;
ALTER TABLE t_stock_cgq ADD CONSTRAINT chk_cgq_pledge_ratio 
    CHECK (pledge_ratio IS NULL OR (pledge_ratio >= 0 AND pledge_ratio <= 100));

-- 22. 机构持股汇总表 - 机构数量和持仓约束
ALTER TABLE t_stock_jgcc DROP CONSTRAINT IF EXISTS chk_jgcc_org_num;
ALTER TABLE t_stock_jgcc ADD CONSTRAINT chk_jgcc_org_num 
    CHECK (org_num IS NULL OR org_num >= 0);

ALTER TABLE t_stock_jgcc DROP CONSTRAINT IF EXISTS chk_jgcc_hold_vol;
ALTER TABLE t_stock_jgcc ADD CONSTRAINT chk_jgcc_hold_vol 
    CHECK (hold_vol IS NULL OR hold_vol >= 0);

ALTER TABLE t_stock_jgcc DROP CONSTRAINT IF EXISTS chk_jgcc_hold_ratio;
ALTER TABLE t_stock_jgcc ADD CONSTRAINT chk_jgcc_hold_ratio 
    CHECK (hold_ratio IS NULL OR (hold_ratio >= 0 AND hold_ratio <= 100));

-- 23. 机构调研表 - 机构数量非负
ALTER TABLE t_stock_jgdy DROP CONSTRAINT IF EXISTS chk_jgdy_org_num;
ALTER TABLE t_stock_jgdy ADD CONSTRAINT chk_jgdy_org_num 
    CHECK (org_num IS NULL OR org_num >= 0);

-- 24. 股权质押明细表 - 质押和冻结数量约束
ALTER TABLE t_stock_gdfx DROP CONSTRAINT IF EXISTS chk_gdfx_hold_vol;
ALTER TABLE t_stock_gdfx ADD CONSTRAINT chk_gdfx_hold_vol 
    CHECK (hold_vol IS NULL OR hold_vol >= 0);

ALTER TABLE t_stock_gdfx DROP CONSTRAINT IF EXISTS chk_gdfx_hold_ratio;
ALTER TABLE t_stock_gdfx ADD CONSTRAINT chk_gdfx_hold_ratio 
    CHECK (hold_ratio IS NULL OR (hold_ratio >= 0 AND hold_ratio <= 100));

ALTER TABLE t_stock_gdfx DROP CONSTRAINT IF EXISTS chk_gdfx_pledge_vol;
ALTER TABLE t_stock_gdfx ADD CONSTRAINT chk_gdfx_pledge_vol 
    CHECK (pledge_vol IS NULL OR pledge_vol >= 0);

ALTER TABLE t_stock_gdfx DROP CONSTRAINT IF EXISTS chk_gdfx_froze_vol;
ALTER TABLE t_stock_gdfx ADD CONSTRAINT chk_gdfx_froze_vol 
    CHECK (froze_vol IS NULL OR froze_vol >= 0);

ALTER TABLE t_stock_gdfx DROP CONSTRAINT IF EXISTS chk_gdfx_unfroze_vol;
ALTER TABLE t_stock_gdfx ADD CONSTRAINT chk_gdfx_unfroze_vol 
    CHECK (unfroze_vol IS NULL OR unfroze_vol >= 0);

-- ========================================================  
-- 五、数据库版本更新
-- ========================================================  

-- 记录约束添加版本
INSERT INTO t_db_version (version, description) 
VALUES ('1.1.0', 'Added CHECK constraints for data integrity validation');

-- ========================================================  
-- 六、验证查询（可选）
-- ========================================================  
/*
-- 查看所有约束
SELECT 
    conrelid::regclass AS table_name,
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE contype = 'c' 
  AND conrelid::regclass::text LIKE 't_stock_%'
ORDER BY conrelid::regclass::text, conname;

-- 统计各表约束数量
SELECT 
    conrelid::regclass AS table_name,
    COUNT(*) AS check_constraint_count
FROM pg_constraint
WHERE contype = 'c' 
  AND conrelid::regclass::text LIKE 't_stock_%'
GROUP BY conrelid::regclass
ORDER BY conrelid::regclass;
*/
