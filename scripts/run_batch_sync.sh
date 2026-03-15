#!/bin/bash
# 批量同步脚本 - 后台运行

cd /Users/xuhaoricky/ClawProject/Stock-trading-project

echo "========== Tushare 数据批量同步 =========="
echo "开始时间: $(date)"
echo ""

# 快速同步的表（不需要按日期循环）
echo "--- 同步基础数据表 ---"
python3 scripts/sync/sync_t_stock_company.py --mode full 2>&1 | tee logs/sync_company.log
python3 scripts/sync/sync_t_stock_tradedate.py --mode full 2>&1 | tee logs/sync_tradedate.log

# 耗时长的表（按日期循环）- 只同步最近一年数据
echo ""
echo "--- 同步最近一年行情数据 ---"
python3 scripts/sync/sync_t_stock_daily_basic.py --mode incremental 2>&1 | tee logs/sync_daily_basic.log
python3 scripts/sync/sync_t_stock_dailylimitprice.py --mode incremental 2>&1 | tee logs/sync_limitprice.log
python3 scripts/sync/sync_t_stock_moneyflow.py --mode incremental 2>&1 | tee logs/sync_moneyflow.log

echo ""
echo "完成时间: $(date)"
echo "日志保存在 logs/ 目录"
