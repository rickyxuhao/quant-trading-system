#!/bin/bash
# 安装systemd服务脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="quant-scheduler"

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行"
    exit 1
fi

echo "安装 $SERVICE_NAME 服务..."

# 复制服务文件
cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}@.service"

# 创建日志目录
mkdir -p /var/log
touch "/var/log/${SERVICE_NAME}.log"
chmod 666 "/var/log/${SERVICE_NAME}.log"

# 重新加载systemd
systemctl daemon-reload

echo "✅ 服务已安装"
echo ""
echo "使用方法:"
echo "  sudo systemctl start ${SERVICE_NAME}@$USER    # 启动服务"
echo "  sudo systemctl stop ${SERVICE_NAME}@$USER     # 停止服务"
echo "  sudo systemctl restart ${SERVICE_NAME}@$USER  # 重启服务"
echo "  sudo systemctl status ${SERVICE_NAME}@$USER   # 查看状态"
echo "  sudo systemctl enable ${SERVICE_NAME}@$USER   # 开机自启"
echo ""
echo "查看日志:"
echo "  tail -f /var/log/${SERVICE_NAME}.log"
