#!/bin/bash
# 设置自动推送定时任务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PUSH_SCRIPT="$SCRIPT_DIR/auto_git_push.sh"

echo "🚀 设置自动 Git 推送定时任务"
echo "=============================="
echo ""

# 检查脚本是否存在
if [ ! -f "$PUSH_SCRIPT" ]; then
    echo "❌ 错误: 找不到推送脚本 $PUSH_SCRIPT"
    exit 1
fi

# 询问推送频率
echo "请选择推送频率："
echo "1) 每 15 分钟"
echo "2) 每 30 分钟（推荐）"
echo "3) 每小时"
echo "4) 每 2 小时"
echo "5) 每 6 小时"
read -p "请输入选项 (1-5): " choice

case $choice in
    1) CRON_SCHEDULE="*/15 * * * *" ;;
    2) CRON_SCHEDULE="*/30 * * * *" ;;
    3) CRON_SCHEDULE="0 * * * *" ;;
    4) CRON_SCHEDULE="0 */2 * * *" ;;
    5) CRON_SCHEDULE="0 */6 * * *" ;;
    *) echo "无效选项，使用默认（每30分钟）"; CRON_SCHEDULE="*/30 * * * *" ;;
esac

echo ""
echo "📋 定时任务配置："
echo "   频率: $CRON_SCHEDULE"
echo "   脚本: $PUSH_SCRIPT"
echo "   日志: /tmp/auto_git_push.log"
echo ""

# 添加到 crontab
CRON_JOB="$CRON_SCHEDULE $PUSH_SCRIPT"

# 检查是否已存在相同的任务
if crontab -l 2>/dev/null | grep -q "$PUSH_SCRIPT"; then
    echo "⚠️  定时任务已存在，是否更新？(y/n)"
    read confirm
    if [ "$confirm" != "y" ]; then
        echo "取消设置"
        exit 0
    fi
    # 删除旧任务
    crontab -l 2>/dev/null | grep -v "$PUSH_SCRIPT" | crontab -
fi

# 添加新任务
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ 定时任务已设置！"
echo ""
echo "📌 管理命令："
echo "   查看任务: crontab -l"
echo "   查看日志: tail -f /tmp/auto_git_push.log"
echo "   删除任务: crontab -e 然后删除对应行"
echo ""
echo "⚠️  注意事项："
echo "   1. 此脚本会提交所有更改（包括未手动提交的）"
echo "   2. 如果存在冲突，需要手动解决"
echo "   3. 敏感文件（如.env）已被.gitignore排除"
echo "   4. 建议定期查看日志确保正常运行"
