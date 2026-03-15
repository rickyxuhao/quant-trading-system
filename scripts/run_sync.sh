#!/bin/bash
# 数据同步任务执行脚本
# 用于 crontab 调用

# 设置项目路径
PROJECT_DIR="/Users/xuhaoricky/ClawProject/Stock-trading-project"
LOG_DIR="$PROJECT_DIR/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 获取当前日期
DATE=$(date +"%Y%m%d")
DATETIME=$(date +"%Y%m%d_%H%M%S")

# 默认执行任务
TASK_NAME=${1:-"all"}

# 执行同步任务
cd "$PROJECT_DIR" || exit 1

# 记录开始
echo "[$DATETIME] 开始执行任务: $TASK_NAME" >> "$LOG_DIR/sync_${DATE}.log"

# 执行 Python 任务
python3 << EOF
import sys
sys.path.insert(0, '.')

from core.data_sync.engine import create_sync_engine

# 使用配置文件初始化引擎
CONFIG_PATH = 'core/data_sync/config/sync_tasks.yaml'
engine = create_sync_engine(CONFIG_PATH)

# 初始化日志表
engine.init_log_tables()

# 执行
task_name = "$TASK_NAME"
if task_name == "all":
    results = engine.run_all()
    for r in results:
        print(f"任务 {r['task_name']}: {r['status']}")
else:
    result = engine.run_task(task_name)
    print(f"任务 {result['task_name']}: {result['status']}")
EOF

# 记录结束
EXIT_CODE=$?
DATETIME_END=$(date +"%Y%m%d_%H%M%S")

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATETIME_END] 任务完成: $TASK_NAME ✅" >> "$LOG_DIR/sync_${DATE}.log"
else
    echo "[$DATETIME_END] 任务失败: $TASK_NAME ❌ (exit code: $EXIT_CODE)" >> "$LOG_DIR/sync_${DATE}.log"
fi

exit $EXIT_CODE
