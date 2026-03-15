"""
每日数据同步定时任务调度器

调度策略:
- 交易日盘后 17:30: 同步日线行情、资金流向等高频数据
- 交易日盘后 18:00: 同步复权因子、每日指标
- 交易日盘后 18:30: 同步ST列表、交易日历
- 每周一 19:00: 同步基本面数据（财务、股东等）
- 每月1日 20:00: 同步月度数据（IPO、分红等）

使用方法:
    # 启动调度器（后台运行）
    python -m core.scheduler.daily_sync_scheduler

    # 立即执行一次同步
    python -m core.scheduler.daily_sync_scheduler --run-once

    # 执行特定任务组
    python -m core.scheduler.daily_sync_scheduler --group daily_market
"""
import argparse
import asyncio
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    print("⚠️ apscheduler 未安装，请运行: pip install apscheduler")

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger

logger = get_logger(__name__)


# 同步任务配置
SYNC_JOBS = {
    # ========== 每日高频数据（交易日 17:30）==========
    "daily_market": {
        "name": "日线行情同步",
        "trigger": CronTrigger(hour=17, minute=30, day_of_week='mon-fri'),
        "scripts": [
            "scripts/sync/sync_t_stock_dailymarketdata.py",
            "scripts/sync/sync_t_stock_moneyflow.py",
            "scripts/sync/sync_t_stock_moneyflow_market.py",
            "scripts/sync/sync_t_index_daily.py",
            "scripts/sync/sync_t_sw_daily.py",
        ],
        "description": "同步日线行情、资金流向等高频数据",
    },

    # ========== 每日指标数据（交易日 18:00）==========
    "daily_indicators": {
        "name": "每日指标同步",
        "trigger": CronTrigger(hour=18, minute=0, day_of_week='mon-fri'),
        "scripts": [
            "scripts/sync/sync_t_stock_daily_basic.py",
            "scripts/sync/sync_t_stock_adjfactor.py",
            "scripts/sync/sync_t_stock_dailylimitprice.py",
            "scripts/sync/sync_t_index_indicator.py",
            "scripts/sync/sync_t_index_weight.py",
        ],
        "description": "同步每日指标、复权因子等",
        "depends_on": ["daily_market"],  # 依赖日线行情
    },

    # ========== 每日状态数据（交易日 18:30）==========
    "daily_status": {
        "name": "每日状态同步",
        "trigger": CronTrigger(hour=18, minute=30, day_of_week='mon-fri'),
        "scripts": [
            "scripts/sync/sync_t_stock_st_list.py",
            "scripts/sync/sync_t_stock_tradedate.py",
            "scripts/sync/sync_t_stock_hs_const.py",
        ],
        "description": "同步ST列表、交易日历、沪深股通",
    },

    # ========== 基金数据（交易日 19:00）==========
    "daily_fund": {
        "name": "基金数据同步",
        "trigger": CronTrigger(hour=19, minute=0, day_of_week='mon-fri'),
        "scripts": [
            "scripts/sync/sync_t_fund_nav.py",
            "scripts/sync/sync_t_fund_share.py",
        ],
        "description": "同步基金净值、份额数据",
    },

    # ========== 每周基本面数据（每周一 19:00）==========
    "weekly_fundamental": {
        "name": "基本面数据同步",
        "trigger": CronTrigger(hour=19, minute=0, day_of_week='mon'),
        "scripts": [
            "scripts/sync/sync_t_stock_finaindicator.py",
            "scripts/sync/sync_t_stock_holder_number.py",
            "scripts/sync/sync_t_stock_top10_holders.py",
            "scripts/sync/sync_t_stock_top10_float_holders.py",
        ],
        "description": "同步财务指标、股东数据",
    },

    # ========== 每周财务数据（每周三 19:00）==========
    "weekly_financial": {
        "name": "财务报表同步",
        "trigger": CronTrigger(hour=19, minute=0, day_of_week='wed'),
        "scripts": [
            "scripts/sync/sync_t_stock_income.py",
            "scripts/sync/sync_t_stock_balancesheet.py",
            "scripts/sync/sync_t_stock_cashflow.py",
        ],
        "description": "同步三张财务报表",
    },

    # ========== 每月基础数据（每月1日 20:00）==========
    "monthly_basic": {
        "name": "月度基础数据同步",
        "trigger": CronTrigger(hour=20, minute=0, day=1),
        "scripts": [
            "scripts/sync/sync_t_stock_basic.py",
            "scripts/sync/sync_t_stock_company.py",
            "scripts/sync/sync_t_stock_name_history.py",
            "scripts/sync/sync_t_fund_basic.py",
            "scripts/sync/sync_t_index_basic.py",
        ],
        "description": "同步股票、基金、指数基础信息",
    },

    # ========== 每月事件数据（每月5日 20:00）==========
    "monthly_events": {
        "name": "月度事件数据同步",
        "trigger": CronTrigger(hour=20, minute=0, day=5),
        "scripts": [
            "scripts/sync/sync_t_stock_ipo.py",
            "scripts/sync/sync_t_stock_dividend.py",
            "scripts/sync/sync_t_stock_forecast.py",
            "scripts/sync/sync_t_stock_express.py",
            "scripts/sync/sync_t_stock_fina_audit.py",
        ],
        "description": "同步IPO、分红、业绩预告等",
    },

    # ========== 每月其他数据（每月10日 20:00）==========
    "monthly_other": {
        "name": "月度其他数据同步",
        "trigger": CronTrigger(hour=20, minute=0, day=10),
        "scripts": [
            "scripts/sync/sync_t_stock_fina_mainbz.py",
            "scripts/sync/sync_t_stock_holder_trade.py",
            "scripts/sync/sync_t_fund_portfolio.py",
            "scripts/sync/sync_t_fund_manager.py",
            "scripts/sync/sync_t_fund_rating.py",
        ],
        "description": "同步主营业务、基金组合等",
    },

    # ========== 数据质量检查（每日 21:00）==========
    "daily_quality_check": {
        "name": "数据质量检查",
        "trigger": CronTrigger(hour=21, minute=0, day_of_week='mon-fri'),
        "scripts": [
            "scripts/run_data_quality_check.py",
        ],
        "description": "执行数据质量检查",
        "depends_on": ["daily_indicators"],
    },
}


class DailySyncScheduler:
    """每日数据同步调度器"""

    def __init__(self):
        self.scheduler = None
        self.job_status: Dict[str, Dict] = {}

        if HAS_SCHEDULER:
            self.scheduler = AsyncIOScheduler()
            # 添加事件监听
            self.scheduler.add_listener(
                self._on_job_executed,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )

    def _on_job_executed(self, event):
        """任务执行完成回调"""
        job_id = event.job_id
        if event.exception:
            logger.error(f"任务 {job_id} 执行失败: {event.exception}")
            self.job_status[job_id] = {
                "last_run": datetime.now(),
                "status": "failed",
                "error": str(event.exception)
            }
        else:
            logger.info(f"任务 {job_id} 执行成功")
            self.job_status[job_id] = {
                "last_run": datetime.now(),
                "status": "success",
                "retval": event.retval
            }

    def start(self):
        """启动调度器"""
        if not self.scheduler:
            logger.error("APScheduler 未安装")
            return False

        # 注册所有任务
        for job_id, job_config in SYNC_JOBS.items():
            self._add_job(job_id, job_config)

        # 启动调度器
        self.scheduler.start()
        logger.info("✅ 每日数据同步调度器已启动")
        self._print_schedule()

        # 保持运行
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

        return True

    def _add_job(self, job_id: str, job_config: Dict):
        """添加单个任务"""
        self.scheduler.add_job(
            func=self._run_sync_group,
            trigger=job_config["trigger"],
            id=job_id,
            name=job_config["name"],
            args=[job_id, job_config],
            replace_existing=True
        )
        logger.info(f"📅 已添加任务: {job_id} - {job_config['name']}")

    def _run_sync_group(self, job_id: str, job_config: Dict):
        """执行同步任务组"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 开始执行任务组: {job_config['name']} ({job_id})")
        logger.info(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        scripts = job_config.get("scripts", [])
        results = []

        for script_path in scripts:
            result = self._run_script(script_path)
            results.append(result)

            # 如果脚本失败，记录但继续执行其他脚本
            if result["status"] != "success":
                logger.warning(f"⚠️ 脚本执行失败: {script_path}")

        # 汇总结果
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"\n📊 任务组 {job_id} 执行完成: {success_count}/{len(results)} 成功")

        return {
            "job_id": job_id,
            "success_count": success_count,
            "total_count": len(results),
            "results": results
        }

    def _run_script(self, script_path: str) -> Dict:
        """执行单个同步脚本"""
        full_path = project_root / script_path

        if not full_path.exists():
            logger.error(f"❌ 脚本不存在: {full_path}")
            return {"script": script_path, "status": "failed", "error": "文件不存在"}

        logger.info(f"📄 执行脚本: {script_path}")

        try:
            result = subprocess.run(
                [sys.executable, str(full_path)],
                capture_output=True,
                text=True,
                timeout=3600,  # 1小时超时
                cwd=str(project_root)
            )

            if result.returncode == 0:
                logger.info(f"✅ 脚本执行成功: {script_path}")
                return {
                    "script": script_path,
                    "status": "success",
                    "stdout": result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout
                }
            else:
                logger.error(f"❌ 脚本执行失败: {script_path}")
                logger.error(f"错误输出: {result.stderr[-500:]}")
                return {
                    "script": script_path,
                    "status": "failed",
                    "returncode": result.returncode,
                    "stderr": result.stderr[-500:]
                }

        except subprocess.TimeoutExpired:
            logger.error(f"⏱️ 脚本执行超时: {script_path}")
            return {"script": script_path, "status": "timeout"}
        except Exception as e:
            logger.error(f"❌ 脚本执行异常: {script_path} - {e}")
            return {"script": script_path, "status": "error", "error": str(e)}

    def _print_schedule(self):
        """打印任务调度表"""
        print("\n" + "="*60)
        print("📅 定时任务调度表")
        print("="*60)

        # 按时间排序
        sorted_jobs = sorted(
            SYNC_JOBS.items(),
            key=lambda x: self._get_sort_key(x[1])
        )

        for job_id, config in sorted_jobs:
            trigger = config["trigger"]
            print(f"\n⏰ {config['name']} ({job_id})")
            print(f"   触发器: {trigger}")
            print(f"   说明: {config['description']}")
            print(f"   脚本数: {len(config.get('scripts', []))}")

        print("\n" + "="*60)
        print("按 Ctrl+C 停止调度器")
        print("="*60 + "\n")

    def _get_sort_key(self, config: Dict) -> str:
        """获取排序键"""
        trigger = config["trigger"]
        # 简化的排序逻辑
        return str(trigger)

    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("✅ 调度器已停止")

    def get_job_status(self) -> Dict:
        """获取所有任务状态"""
        if not self.scheduler:
            return {"error": "调度器未启动"}

        jobs = []
        for job in self.scheduler.get_jobs():
            status = self.job_status.get(job.id, {})
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None,
                "last_status": status.get("status"),
                "last_run": status.get("last_run", {}).strftime("%Y-%m-%d %H:%M:%S") if status.get("last_run") else None,
            })

        return {"jobs": jobs, "running": self.scheduler.running}

    def run_job_now(self, job_id: str) -> Optional[Dict]:
        """立即执行指定任务"""
        if job_id not in SYNC_JOBS:
            return {"error": f"未知任务: {job_id}"}

        config = SYNC_JOBS[job_id]
        return self._run_sync_group(job_id, config)


def start_scheduler():
    """启动调度器（入口函数）"""
    scheduler = DailySyncScheduler()
    return scheduler.start()


def run_sync_job(job_id: str = None, group: str = None):
    """运行同步任务（立即执行）"""
    scheduler = DailySyncScheduler()

    if job_id:
        # 执行指定任务
        if job_id not in SYNC_JOBS:
            print(f"❌ 未知任务: {job_id}")
            print(f"可用任务: {', '.join(SYNC_JOBS.keys())}")
            return
        result = scheduler.run_job_now(job_id)
        print(f"\n执行结果: {result}")
    elif group:
        # 执行指定分组的所有任务
        matching_jobs = {
            k: v for k, v in SYNC_JOBS.items()
            if group in k or any(group in s for s in v.get("scripts", []))
        }
        for job_id, config in matching_jobs.items():
            print(f"\n执行: {job_id}")
            scheduler.run_job_now(job_id)
    else:
        # 执行所有任务
        for job_id, config in SYNC_JOBS.items():
            print(f"\n执行: {job_id}")
            scheduler.run_job_now(job_id)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="每日数据同步调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动调度器（后台定时运行）
  python -m core.scheduler.daily_sync_scheduler

  # 立即执行一次所有任务
  python -m core.scheduler.daily_sync_scheduler --run-once

  # 立即执行指定任务
  python -m core.scheduler.daily_sync_scheduler --run-once --job daily_market

  # 查看任务列表
  python -m core.scheduler.daily_sync_scheduler --list
        """
    )

    parser.add_argument(
        "--run-once",
        action="store_true",
        help="立即执行一次，不启动调度器"
    )

    parser.add_argument(
        "--job",
        type=str,
        help="指定任务ID（配合 --run-once 使用）"
    )

    parser.add_argument(
        "--group",
        type=str,
        help="按分组执行任务（如 daily, weekly, monthly）"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_jobs",
        help="列出所有定时任务"
    )

    args = parser.parse_args()

    if args.list_jobs:
        print("\n" + "="*60)
        print("📋 可用任务列表")
        print("="*60)
        for job_id, config in SYNC_JOBS.items():
            print(f"\n{job_id}:")
            print(f"  名称: {config['name']}")
            print(f"  说明: {config['description']}")
            print(f"  触发器: {config['trigger']}")
        print("\n" + "="*60)
        return

    if args.run_once:
        run_sync_job(args.job, args.group)
    else:
        start_scheduler()


if __name__ == '__main__':
    main()
