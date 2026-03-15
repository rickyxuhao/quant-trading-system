#!/bin/bash
# 批量同步脚本 - 后台运行所有空表

cd /Users/xuhaoricky/ClawProject/Stock-trading-project
LOG_DIR="logs/sync_$(date +%Y%m%d_%H%M%S)"
mkdir -p $LOG_DIR

echo "========== Tushare 批量数据同步 =========="
echo "日志目录: $LOG_DIR"
echo "开始时间: $(date)"
echo ""

# ===== 基础数据表（快速）=====
echo "--- 1. 基础数据表 ---"
python3 scripts/sync/sync_t_stock_company.py --mode full > $LOG_DIR/company.log 2>&1 &
python3 scripts/sync/sync_t_stock_hs_const.py --mode full > $LOG_DIR/hs_const.log 2>&1 &
wait
echo "✓ 基础表同步完成"

# ===== 行情数据表（增量 - 最近30天）=====
echo ""
echo "--- 2. 行情数据表（增量: 最近30天）---"
# 修改脚本支持 start-date 参数，或使用全量中的增量逻辑
python3 scripts/sync/sync_t_stock_daily_basic.py --mode incremental > $LOG_DIR/daily_basic.log 2>&1 &
python3 scripts/sync/sync_t_stock_dailylimitprice.py --mode incremental > $LOG_DIR/limitprice.log 2>&1 &
python3 scripts/sync/sync_t_stock_moneyflow.py --mode incremental > $LOG_DIR/moneyflow.log 2>&1 &
python3 scripts/sync/sync_t_stock_moneyflow_market.py --mode incremental > $LOG_DIR/moneyflow_market.log 2>&1 &
wait
echo "✓ 行情表同步完成"

# ===== 财务数据表（按季度增量）=====
echo ""
echo "--- 3. 财务数据表（增量）---"
python3 scripts/sync/sync_t_stock_income.py --mode incremental > $LOG_DIR/income.log 2>&1 &
python3 scripts/sync/sync_t_stock_balancesheet.py --mode incremental > $LOG_DIR/balancesheet.log 2>&1 &
python3 scripts/sync/sync_t_stock_cashflow.py --mode incremental > $LOG_DIR/cashflow.log 2>&1 &
python3 scripts/sync/sync_t_stock_fina_indicator.py --mode incremental > $LOG_DIR/fina_indicator.log 2>&1 &
python3 scripts/sync/sync_t_stock_fina_audit.py --mode incremental > $LOG_DIR/fina_audit.log 2>&1 &
python3 scripts/sync/sync_t_stock_fina_mainbz.py --mode incremental > $LOG_DIR/fina_mainbz.log 2>&1 &
python3 scripts/sync/sync_t_stock_forecast.py --mode incremental > $LOG_DIR/forecast.log 2>&1 &
python3 scripts/sync/sync_t_stock_express.py --mode incremental > $LOG_DIR/express.log 2>&1 &
python3 scripts/sync/sync_t_stock_dividend.py --mode incremental > $LOG_DIR/dividend.log 2>&1 &
wait
echo "✓ 财务表同步完成"

# ===== 股东/机构数据（季度）=====
echo ""
echo "--- 4. 股东/机构数据（增量）---"
python3 scripts/sync/sync_t_stock_top10_holders.py --mode incremental > $LOG_DIR/top10_holders.log 2>&1 &
python3 scripts/sync/sync_t_stock_top10_float_holders.py --mode incremental > $LOG_DIR/top10_float_holders.log 2>&1 &
python3 scripts/sync/sync_t_stock_holder_number.py --mode incremental > $LOG_DIR/holder_number.log 2>&1 &
python3 scripts/sync/sync_t_stock_holder_trade.py --mode incremental > $LOG_DIR/holder_trade.log 2>&1 &
python3 scripts/sync/sync_t_stock_jgcc.py --mode incremental > $LOG_DIR/jgcc.log 2>&1 &
python3 scripts/sync/sync_t_stock_jgdy.py --mode incremental > $LOG_DIR/jgdy.log 2>&1 &
python3 scripts/sync/sync_t_stock_cgq.py --mode incremental > $LOG_DIR/cgq.log 2>&1 &
python3 scripts/sync/sync_t_stock_gdfx.py --mode incremental > $LOG_DIR/gdfx.log 2>&1 &
wait
echo "✓ 股东机构表同步完成"

echo ""
echo "========== 批量同步完成 =========="
echo "完成时间: $(date)"
echo "日志保存在: $LOG_DIR"

# 生成汇总报告
echo ""
echo "--- 同步结果汇总 ---"
for log in $LOG_DIR/*.log; do
    name=$(basename $log .log)
    if grep -q "同步成功" $log 2>/dev/null; then
        echo "✓ $name: 成功"
    elif grep -q "失败\|错误\|ERROR" $log 2>/dev/null; then
        echo "✗ $name: 失败"
    else
        echo "? $name: 状态未知"
    fi
done
