#!/usr/bin/env python3
"""
调度器服务管理脚本

用于启动、停止、重启数据同步调度器服务

使用方法:
    python scripts/scheduler_service.py start    # 启动服务
    python scripts/scheduler_service.py stop     # 停止服务
    python scripts/scheduler_service.py restart  # 重启服务
    python scripts/scheduler_service.py status   # 查看状态
    python scripts/scheduler_service.py log      # 查看日志
"""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
PID_FILE = Path("/tmp/quant_scheduler.pid")
LOG_FILE = Path("/tmp/quant_scheduler.log")


def get_python() -> str:
    """获取Python解释器路径"""
    return sys.executable


def start_service():
    """启动服务"""
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        if pid and check_process_running(int(pid)):
            print(f"⚠️  服务已在运行 (PID: {pid})")
            return False

    print("🚀 启动数据同步调度器服务...")

    # 使用nohup启动后台进程
    cmd = [
        get_python(),
        "-m", "core.scheduler.daily_sync_scheduler"
    ]

    with open(LOG_FILE, 'a') as log:
        process = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            start_new_session=True
        )

    # 保存PID
    PID_FILE.write_text(str(process.pid))

    print(f"✅ 服务已启动 (PID: {process.pid})")
    print(f"📄 日志文件: {LOG_FILE}")
    return True


def stop_service():
    """停止服务"""
    if not PID_FILE.exists():
        print("⚠️  服务未运行")
        return False

    pid = int(PID_FILE.read_text().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"✅ 服务已停止 (PID: {pid})")
    except ProcessLookupError:
        print(f"⚠️  进程不存在 (PID: {pid})")
    except PermissionError:
        print(f"❌ 权限不足，无法停止进程 (PID: {pid})")
        return False

    PID_FILE.unlink(missing_ok=True)
    return True


def restart_service():
    """重启服务"""
    stop_service()
    return start_service()


def check_status():
    """检查服务状态"""
    if not PID_FILE.exists():
        print("⚪ 服务未运行")
        return False

    pid = int(PID_FILE.read_text().strip())

    if check_process_running(pid):
        print(f"🟢 服务运行中 (PID: {pid})")
        print(f"📄 日志文件: {LOG_FILE}")

        # 显示最后几行日志
        if LOG_FILE.exists():
            print("\n--- 最近日志 ---")
            result = subprocess.run(
                ["tail", "-n", "10", str(LOG_FILE)],
                capture_output=True,
                text=True
            )
            print(result.stdout)
        return True
    else:
        print(f"🔴 服务未运行 (残留 PID: {pid})")
        PID_FILE.unlink(missing_ok=True)
        return False


def check_process_running(pid: int) -> bool:
    """检查进程是否运行中"""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def view_log(lines: int = 50, follow: bool = False):
    """查看日志"""
    if not LOG_FILE.exists():
        print("⚠️  日志文件不存在")
        return

    cmd = ["tail", f"-n", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(str(LOG_FILE))

    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="调度器服务管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/scheduler_service.py start
    python scripts/scheduler_service.py stop
    python scripts/scheduler_service.py restart
    python scripts/scheduler_service.py status
    python scripts/scheduler_service.py log -n 100
    python scripts/scheduler_service.py log -f
        """
    )

    parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "status", "log"],
        help="操作命令"
    )

    parser.add_argument(
        "-n", "--lines",
        type=int,
        default=50,
        help="显示日志行数（默认50）"
    )

    parser.add_argument(
        "-f", "--follow",
        action="store_true",
        help="持续跟踪日志输出"
    )

    args = parser.parse_args()

    if args.action == "start":
        start_service()
    elif args.action == "stop":
        stop_service()
    elif args.action == "restart":
        restart_service()
    elif args.action == "status":
        check_status()
    elif args.action == "log":
        view_log(args.lines, args.follow)


if __name__ == "__main__":
    main()
