#!/bin/bash
# 修复后的同步脚本 - 后台批量运行

cd /Users/xuhaoricky/ClawProject/Stock-trading-project
LOG_DIR="logs/sync_fixed_$(date +%Y%m%d_%H%M%S)"
mkdir -p $LOG_DIR

echo "========== 修复后同步脚本批量执行 =========="
echo "日志目录: $LOG_DIR"
echo "开始时间: $(date)"
echo ""

# 函数：后台运行同步脚本
run_sync() {
    local script=$1
    local name=$2
    echo "→ 启动 $name 同步..."
    python3 scripts/sync/$script --mode incremental > $LOG_DIR/$name.log 2>&1 &
}

# ===== 财务数据表（按股票代码循环）=====
echo "--- 1. 财务数据表（耗时较长，后台并行）---"
run_sync sync_t_stock_dividend.py dividend
run_sync sync_t_stock_forecast.py forecast
run_sync sync_t_stock_express.py express
run_sync sync_t_stock_fina_indicator.py fina_indicator
run_sync sync_t_stock_fina_mainbz.py fina_mainbz
run_sync sync_t_stock_fina_audit.py fina_audit
wait
echo "✓ 财务数据表同步完成"

# ===== 股东/机构数据（按股票代码循环）=====
echo ""
echo "--- 2. 股东/机构数据（耗时较长，后台并行）---"
run_sync sync_t_stock_holder_number.py holder_number
run_sync sync_t_stock_holder_trade.py holder_trade
run_sync sync_t_stock_jgcc.py jgcc
run_sync sync_t_stock_jgdy.py jgdy
run_sync sync_t_stock_cgq.py cgq
wait
echo "✓ 股东机构表同步完成"

# ===== Top10 股东（需要特殊处理 period 参数）=====
echo ""
echo "--- 3. Top10 股东数据（季度报告期）---"
run_sync sync_t_stock_top10_holders.py top10_holders
run_sync sync_t_stock_top10_float_holders.py top10_float_holders
wait
echo "✓ Top10 股东表同步完成"

echo ""
echo "========== 批量同步完成 =========="
echo "完成时间: $(date)"
echo "日志保存在: $LOG_DIR"

# 生成汇总
echo ""
echo "--- 同步结果 ---"
sleep 2
for log in $LOG_DIR/*.log; do
    name=$(basename $log .log)
    if [ -f "$log" ]; then
        lines=$(wc -l < "$log")
        if grep -q "同步完成" "$log" 2>/dev/null; then
            echo "✓ $name: 完成 ($lines 行日志)"
        else
            echo "⏳ $name: 进行中 ($lines 行日志)"
        fi
    fi
done
