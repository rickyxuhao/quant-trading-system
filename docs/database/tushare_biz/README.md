# tushare_biz 数据库文档

> 生成时间: 2026-03-13 21:36:43

## 统计概览

| 指标 | 数值 |
|:---|:---|
| 表数量 | 45 |
| 总数据行数 | 68,401,047 |
| 总数据大小 | 11.12 GB |
| 总索引大小 | 3.82 GB |
| 总存储大小 | 14.94 GB |

## 表清单

| 表名 | 中文名 | 数据行数 | 数据大小 | 说明 |
|:---|:---|---:|---:|:---|
| [etf_adj_factor](./etf_adj_factor.md) | ETF复权因子表 - 来自Tushare fund_adj | 2,967,204 | 251.00 MB | [详情](./etf_adj_factor.md) |
| [etf_basic](./etf_basic.md) | ETF基本信息表 - 来自Tushare fund_basic | 2,446 | 496.00 KB | [详情](./etf_basic.md) |
| [etf_daily](./etf_daily.md) | ETF日线行情表 - 来自Tushare fund_daily | 2,721,215 | 364.00 MB | [详情](./etf_daily.md) |
| [etf_share](./etf_share.md) | ETF份额规模表 - 来自Tushare fund_share | 1,964,431 | 133.86 MB | [详情](./etf_share.md) |
| [etf_update_log](./etf_update_log.md) | ETF更新日志表 | 0 | 16.00 KB | [详情](./etf_update_log.md) |
| [t_fund_basic](./t_fund_basic.md) | 公募基金基本信息表 - 来自Tushare fund_basic | 15,321 | 5.52 MB | [详情](./t_fund_basic.md) |
| [t_fund_manager](./t_fund_manager.md) | 基金经理表 - 来自Tushare fund_manager | 3,503 | 12.56 MB | [详情](./t_fund_manager.md) |
| [t_fund_nav](./t_fund_nav.md) | 基金净值表 - 来自Tushare fund_nav | 0 | 16.00 KB | [详情](./t_fund_nav.md) |
| [t_fund_portfolio](./t_fund_portfolio.md) | 基金持仓表 - 来自Tushare fund_portfolio | 0 | 16.00 KB | [详情](./t_fund_portfolio.md) |
| [t_fund_rating](./t_fund_rating.md) | 基金评级表 - 来自Tushare fund_rating | 0 | 16.00 KB | [详情](./t_fund_rating.md) |
| [t_fund_share](./t_fund_share.md) | 基金份额表 - 来自Tushare fund_share | 0 | 16.00 KB | [详情](./t_fund_share.md) |
| [t_index_basic](./t_index_basic.md) | 指数基本信息表 - 来自Tushare index_basic | 7,885 | 1.52 MB | [详情](./t_index_basic.md) |
| [t_index_daily](./t_index_daily.md) | 指数日线行情表 - 来自Tushare index_daily | 6,472 | 1.52 MB | [详情](./t_index_daily.md) |
| [t_index_indicator](./t_index_indicator.md) | 大盘指数每日指标表 - 来自Tushare index_dailybasic | 56,043 | 8.52 MB | [详情](./t_index_indicator.md) |
| [t_index_weight](./t_index_weight.md) | 指数成分和权重表 - 来自Tushare index_weight | 552,944 | 59.70 MB | [详情](./t_index_weight.md) |
| [t_market_sentiment](./t_market_sentiment.md) | 市场情绪指标表 - 基于每日行情统计 | 0 | 16.00 KB | [详情](./t_market_sentiment.md) |
| [t_stock_adjfactor](./t_stock_adjfactor.md) | 复权因子表 - 来自Tushare adj_factor | 12,858,788 | 1.08 GB | [详情](./t_stock_adjfactor.md) |
| [t_stock_balancesheet](./t_stock_balancesheet.md) | 资产负债表 - 一般工商业 - 来自Tushare balancesheet | 221,163 | 190.97 MB | [详情](./t_stock_balancesheet.md) |
| [t_stock_basic](./t_stock_basic.md) | 股票基础信息表 - 来自Tushare stock_basic | 6,005 | 2.44 MB | [详情](./t_stock_basic.md) |
| [t_stock_cashflow](./t_stock_cashflow.md) | 现金流量表 - 一般工商业 - 来自Tushare cashflow | 256,995 | 136.98 MB | [详情](./t_stock_cashflow.md) |
| [t_stock_company](./t_stock_company.md) | 上市公司基本信息表 - 来自Tushare stock_company | 4,504 | 26.55 MB | [详情](./t_stock_company.md) |
| [t_stock_daily_basic](./t_stock_daily_basic.md) | 每日指标表 - 来自Tushare daily_basic | 14,431,161 | 2.82 GB | [详情](./t_stock_daily_basic.md) |
| [t_stock_dailylimitprice](./t_stock_dailylimitprice.md) | 每日涨跌停价格表 - 来自Tushare limit_list | 152,872 | 35.59 MB | [详情](./t_stock_dailylimitprice.md) |
| [t_stock_dailymarketdata](./t_stock_dailymarketdata.md) | 股票日线行情表 - 来自Tushare daily | 14,531,714 | 2.23 GB | [详情](./t_stock_dailymarketdata.md) |
| [t_stock_dividend](./t_stock_dividend.md) | 分红送股表 - 来自Tushare dividend | 88,062 | 11.53 MB | [详情](./t_stock_dividend.md) |
| [t_stock_express](./t_stock_express.md) | 业绩快报表 - 来自Tushare express | 25,458 | 8.52 MB | [详情](./t_stock_express.md) |
| [t_stock_fina_audit](./t_stock_fina_audit.md) | 财务审计意见表 - 来自Tushare fina_audit | 66,075 | 19.56 MB | [详情](./t_stock_fina_audit.md) |
| [t_stock_fina_indicator](./t_stock_fina_indicator.md) | 财务指标数据表 - 来自Tushare fina_indicator | 164,909 | 93.77 MB | [详情](./t_stock_fina_indicator.md) |
| [t_stock_fina_mainbz](./t_stock_fina_mainbz.md) | 主营业务构成表 - 来自Tushare fina_mainbz | 1,019,370 | 148.98 MB | [详情](./t_stock_fina_mainbz.md) |
| [t_stock_forecast](./t_stock_forecast.md) | 业绩预告表 - 来自Tushare forecast | 109,643 | 80.53 MB | [详情](./t_stock_forecast.md) |
| [t_stock_holder_number](./t_stock_holder_number.md) | 股东人数表 - 来自Tushare stk_holdernumber | 351,865 | 52.64 MB | [详情](./t_stock_holder_number.md) |
| [t_stock_holder_trade](./t_stock_holder_trade.md) | 股东增减持表 - 来自Tushare stk_holdertrade | 96,670 | 25.59 MB | [详情](./t_stock_holder_trade.md) |
| [t_stock_hs_const](./t_stock_hs_const.md) | 沪深股通成分股表 - 来自Tushare hs_const | 823 | 80.00 KB | [详情](./t_stock_hs_const.md) |
| [t_stock_income](./t_stock_income.md) | 利润表 - 一般工商业 - 来自Tushare income | 217,350 | 124.97 MB | [详情](./t_stock_income.md) |
| [t_stock_ipo](./t_stock_ipo.md) | IPO新股列表 - 来自Tushare new_share | 1,986 | 432.00 KB | [详情](./t_stock_ipo.md) |
| [t_stock_moneyflow](./t_stock_moneyflow.md) | 个股资金流向表 - 来自Tushare moneyflow | 13,162,705 | 2.86 GB | [详情](./t_stock_moneyflow.md) |
| [t_stock_moneyflow_market](./t_stock_moneyflow_market.md) | 沪深港通资金流向表 - 来自Tushare moneyflow_hsgt | 2,454 | 256.00 KB | [详情](./t_stock_moneyflow_market.md) |
| [t_stock_name_history](./t_stock_name_history.md) | 股票曾用名表 - 来自Tushare namechange | 6,219 | 1.48 MB | [详情](./t_stock_name_history.md) |
| [t_stock_st_list](./t_stock_st_list.md) | ST股票列表表 - 来自Tushare stock_st | 347,723 | 52.66 MB | [详情](./t_stock_st_list.md) |
| [t_stock_technical](./t_stock_technical.md) | 股票技术指标表 - 基于日线行情计算 | 0 | 16.00 KB | [详情](./t_stock_technical.md) |
| [t_stock_top10_float_holders](./t_stock_top10_float_holders.md) | 前十大流通股东表 - 来自Tushare top10_fh | 16,579 | 4.42 MB | [详情](./t_stock_top10_float_holders.md) |
| [t_stock_top10_holders](./t_stock_top10_holders.md) | 前十大股东表 - 来自Tushare top10_holders | 0 | 16.00 KB | [详情](./t_stock_top10_holders.md) |
| [t_stock_tradedate](./t_stock_tradedate.md) | 交易日历表 - 来自Tushare trade_cal | 9,027 | 1.52 MB | [详情](./t_stock_tradedate.md) |
| [t_sw_daily](./t_sw_daily.md) | 申万行业指数日行情表 - 来自Tushare sw_daily | 1,953,463 | 325.00 MB | [详情](./t_sw_daily.md) |
| [t_sw_industry_rotation](./t_sw_industry_rotation.md) | 申万行业轮动指标表 - 基于sw_daily计算 | 0 | 16.00 KB | [详情](./t_sw_industry_rotation.md) |
