#!/bin/bash
# 修复后7张表的批量同步

cd /Users/xuhaoricky/ClawProject/Stock-trading-project
LOG_DIR="logs/sync_batch_fixed_$(date +%Y%m%d_%H%M%S)"
mkdir -p $LOG_DIR

echo "========== 修复后表批量同步 =========="
echo "开始时间: $(date)"
echo "日志: $LOG_DIR"
echo ""

# 需要全量同步的7张表（不支持日期过滤的API）
TABLES=(
    "dividend:t_stock_dividend"
    "express:t_stock_express"
    "forecast:t_stock_forecast"
    "fina_audit:t_stock_fina_audit"
    "fina_mainbz:t_stock_fina_mainbz"
    "holder_trade:t_stock_holder_trade"
    "jgdy:t_stock_jgdy"
)

# 逐个同步（避免并发导致API限流）
for item in "${TABLES[@]}"; do
    IFS=':' read -r name table <<< "$item"
    echo ""
    echo "--- 同步 $table ---"
    python3 scripts/sync/sync_t_stock_${name}.py --mode=full > $LOG_DIR/${name}.log 2>&1
    
    # 检查是否成功
    if tail -5 $LOG_DIR/${name}.log | grep -q "同步成功"; then
        echo "✓ $table 同步完成"
    else
        echo "✗ $table 可能失败，检查日志: $LOG_DIR/${name}.log"
    fi
done

echo ""
echo "========== 批量同步完成 =========="
echo "完成时间: $(date)"
echo ""

# 汇总结果
echo "--- 数据汇总 ---"
python3 -c "
import pymysql
from dotenv import load_dotenv
import os
load_dotenv()

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME_TUSHARE', 'tushare_biz'),
    charset='utf8mb4'
)
cursor = conn.cursor()

for table in ['t_stock_dividend', 't_stock_express', 't_stock_forecast', 
              't_stock_fina_audit', 't_stock_fina_mainbz', 
              't_stock_holder_trade', 't_stock_jgdy']:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    status = '✓' if count > 0 else '✗'
    print(f'{status} {table}: {count:,} 条')

conn.close()
"
