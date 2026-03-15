#!/bin/bash
#
# 券商金股监控分析系统 - Cron定时任务配置脚本
# 配置每天早上8:00自动生成晨间报告（工作日）
#

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_ROOT="/Users/xuhaoricky/ClawProject/Stock-trading-project"
GOLD_STOCK_DIR="${PROJECT_ROOT}/projects/broker_gold_stock"
PYTHON_PATH="/usr/bin/python3"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_LOG="${LOG_DIR}/gold_stock_report.log"

# 确保日志目录存在
mkdir -p "${LOG_DIR}"

# 创建执行脚本
SCRIPT_PATH="${GOLD_STOCK_DIR}/scripts/run_report.sh"

cat > "${SCRIPT_PATH}" << 'INNER_EOF'
#!/bin/bash
# 晨间报告执行脚本

PROJECT_ROOT="/Users/xuhaoricky/ClawProject/Stock-trading-project"
GOLD_STOCK_DIR="${PROJECT_ROOT}/projects/broker_gold_stock"
PYTHON_PATH="/usr/bin/python3"
LOG_FILE="${PROJECT_ROOT}/logs/gold_stock_report.log"

# 添加日志分隔
echo "========================================" >> "${LOG_FILE}"
echo "报告生成任务开始: $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"

# 切换到项目目录
cd "${GOLD_STOCK_DIR}"

# 执行报告生成
${PYTHON_PATH} -c "
import asyncio
import sys
sys.path.insert(0, '${PROJECT_ROOT}')

from projects.broker_gold_stock.report.morning_report import ReportScheduler

async def main():
    scheduler = ReportScheduler()
    try:
        result = await scheduler.run_daily_report()
        if result:
            print(f'✅ 报告生成成功: {result}')
        else:
            print('❌ 报告生成失败')
    except Exception as e:
        print(f'❌ 执行出错: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(main())
" >> "${LOG_FILE}" 2>&1

echo "任务结束: $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"
INNER_EOF

chmod +x "${SCRIPT_PATH}"

echo -e "${GREEN}✅ 已创建执行脚本: ${SCRIPT_PATH}${NC}"

# 设置cron任务
echo -e "${YELLOW}正在配置cron定时任务...${NC}"

# 获取当前用户的crontab
crontab -l > /tmp/current_crontab 2>/dev/null || true

# 检查是否已存在相同的任务
if grep -q "gold_stock_report" /tmp/current_crontab; then
    echo -e "${YELLOW}⚠️  检测到已存在定时任务，是否重新配置？(y/n)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}保持现有配置不变${NC}"
        rm -f /tmp/current_crontab
        exit 0
    fi
    # 删除旧任务
    grep -v "gold_stock_report" /tmp/current_crontab > /tmp/new_crontab
    mv /tmp/new_crontab /tmp/current_crontab
fi

# 添加新任务
# 每天早上8:00执行（工作日，周一到周五）
echo "" >> /tmp/current_crontab
echo "# 券商金股监控分析系统 - 晨间报告生成" >> /tmp/current_crontab
echo "0 8 * * 1-5 ${SCRIPT_PATH}" >> /tmp/current_crontab

# 应用新的crontab
crontab /tmp/current_crontab
rm -f /tmp/current_crontab

echo -e "${GREEN}✅ Cron定时任务配置成功！${NC}"
echo ""
echo -e "${GREEN}任务详情:${NC}"
echo "  执行时间: 每天早上8:00（周一至周五）"
echo "  执行命令: ${SCRIPT_PATH}"
echo "  日志文件: ${REPORT_LOG}"
echo ""
echo -e "${YELLOW}查看当前crontab:${NC}"
crontab -l | grep -A2 "券商金股监控分析系统"
echo ""
echo -e "${YELLOW}手动测试执行:${NC}"
echo "  ${SCRIPT_PATH}"
echo ""
echo -e "${YELLOW}查看日志:${NC}"
echo "  tail -f ${REPORT_LOG}"
echo ""
echo -e "${GREEN}配置完成！${NC}"
