"""
晨间任务调度器
每天早上8点执行金股分析和报告生成
"""
import asyncio
from datetime import datetime
from typing import Optional

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    print("⚠️ apscheduler 未安装，定时功能不可用")

from projects.broker_gold_stock.report.morning_report import ReportScheduler


class MorningTaskScheduler:
    """晨间任务调度器"""

    def __init__(self):
        self.scheduler = None
        self.report_scheduler = ReportScheduler()

        if HAS_SCHEDULER:
            self.scheduler = AsyncIOScheduler()

    def start(self):
        """启动调度器"""
        if not self.scheduler:
            print("❌ 调度器不可用")
            return

        # 添加定时任务 - 每天早上8:00执行（工作日）
        self.scheduler.add_job(
            self._run_morning_task,
            trigger=CronTrigger(hour=8, minute=0, day_of_week='mon-fri'),
            id='morning_report_task',
            name='晨间报告生成任务',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ 晨间任务调度器已启动")
        print("⏰ 定时任务: 每天早上8:00（工作日）")

        # 保持运行
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            print("✅ 调度器已停止")

    async def _run_morning_task(self):
        """执行晨间任务"""
        print(f"\n{'='*60}")
        print(f"🌅 晨间任务开始执行 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        try:
            await self.report_scheduler.run_daily_report()
        except Exception as e:
            print(f"❌ 晨间任务执行失败: {e}")
            import traceback
            traceback.print_exc()

    async def run_once(self):
        """立即执行一次"""
        await self._run_morning_task()


def start_scheduler():
    """启动调度器（入口函数）"""
    scheduler = MorningTaskScheduler()
    scheduler.start()


async def run_once():
    """立即执行一次（入口函数）"""
    scheduler = MorningTaskScheduler()
    await scheduler.run_once()


if __name__ == '__main__':
    # 立即执行一次测试
    asyncio.run(run_once())
