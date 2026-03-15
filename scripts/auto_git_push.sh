#!/bin/bash
# 自动推送代码到 GitHub
# 建议每30分钟运行一次：*/30 * * * *

PROJECT_DIR="/Users/xuhaoricky/ClawProject/Stock-trading-project"
LOG_FILE="/tmp/auto_git_push.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] 开始检查代码更新..." >> "$LOG_FILE"

cd "$PROJECT_DIR" || exit 1

# 检查是否有未提交的更改
if git diff --quiet && git diff --staged --quiet; then
    echo "[$DATE] 没有本地更改需要提交" >> "$LOG_FILE"
else
    echo "[$DATE] 发现本地更改，准备提交..." >> "$LOG_FILE"

    # 添加所有更改
    git add -A

    # 提交（使用时间戳作为提交信息）
    git commit -m "Auto commit: $DATE" >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        echo "[$DATE] 本地提交成功" >> "$LOG_FILE"
    else
        echo "[$DATE] 本地提交失败" >> "$LOG_FILE"
        exit 1
    fi
fi

# 检查是否有远程更新需要先拉取
if git fetch origin main 2>/dev/null; then
    LOCAL=$(git rev-parse main)
    REMOTE=$(git rev-parse origin/main)

    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "[$DATE] 远程有更新，尝试同步..." >> "$LOG_FILE"

        # 尝试快速合并
        if git merge origin/main --ff-only >> "$LOG_FILE" 2>&1; then
            echo "[$DATE] 远程更新已合并" >> "$LOG_FILE"
        else
            echo "[$DATE] 警告: 存在冲突，需要手动解决" >> "$LOG_FILE"
            echo "[$DATE] 请运行: cd $PROJECT_DIR && git status" >> "$LOG_FILE"
            # 可选：发送通知（邮件/Slack等）
            exit 1
        fi
    fi
fi

# 推送到 GitHub
git push origin main >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$DATE] ✅ 成功推送到 GitHub" >> "$LOG_FILE"
else
    echo "[$DATE] ❌ 推送失败" >> "$LOG_FILE"
fi

echo "[$DATE] ---" >> "$LOG_FILE"
