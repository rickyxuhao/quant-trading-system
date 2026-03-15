#!/usr/bin/env python3
"""
量化交易系统 CLI 入口

提供统一的命令行接口，简化日常数据同步、质量检查、数据库初始化等操作。

用法:
    # 数据同步
    poetry run python main.py sync --task stock_basic
    poetry run python main.py sync --all

    # 数据质量检查
    poetry run python main.py check --table t_stock_basic
    poetry run python main.py check --all

    # 初始化数据库
    poetry run python main.py init-db

    # 查看帮助
    poetry run python main.py --help
    poetry run python main.py sync --help
"""
import sys
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import click
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from core.logger import get_logger, init_logging

logger = get_logger(__name__)


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="日志级别"
)
@click.option(
    "--log-dir",
    default="logs",
    help="日志目录"
)
@click.pass_context
def cli(ctx, log_level, log_dir):
    """量化交易系统 CLI - 数据同步、质量检查、系统管理"""
    # 初始化日志
    init_logging(log_level=log_level, log_dir=log_dir)

    # 确保上下文对象存在
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["log_dir"] = log_dir

    logger.debug(f"CLI 启动，日志级别: {log_level}")


@cli.command()
@click.option(
    "--task",
    help="指定同步任务类型（如 stock_basic, trade_date 等）"
)
@click.option(
    "--all",
    "sync_all",
    is_flag=True,
    help="同步所有任务"
)
@click.option(
    "--incremental",
    is_flag=True,
    default=True,
    help="增量同步（默认）"
)
@click.option(
    "--full",
    is_flag=True,
    help="全量同步（覆盖已有数据）"
)
@click.pass_context
def sync(ctx, task, sync_all, incremental, full):
    """
    执行数据同步任务

    从 Tushare 同步股票数据到本地数据库

    示例:
        poetry run python main.py sync --task stock_basic
        poetry run python main.py sync --all
        poetry run python main.py sync --task stock_basic --full
    """
    from core.data_sync.tasks import TaskRegistry

    if not task and not sync_all:
        click.echo("错误: 必须指定 --task 或 --all", err=True)
        sys.exit(1)

    if task and sync_all:
        click.echo("错误: 不能同时指定 --task 和 --all", err=True)
        sys.exit(1)

    sync_type = "full" if full else "incremental"
    logger.info(f"启动数据同步，模式: {sync_type}")

    try:
        if sync_all:
            # 同步所有已注册的任务
            task_types = TaskRegistry.list_registered()
            logger.info(f"发现 {len(task_types)} 个同步任务: {task_types}")

            success_count = 0
            for task_type in task_types:
                try:
                    logger.info(f"执行任务: {task_type}")
                    task_instance = TaskRegistry.create(task_type, {"name": task_type})
                    task_instance.run()
                    success_count += 1
                except Exception as e:
                    logger.exception(f"任务 {task_type} 执行失败: {e}")

            logger.info(f"同步完成: {success_count}/{len(task_types)} 个任务成功")
            if success_count < len(task_types):
                sys.exit(1)
        else:
            # 执行单个任务
            try:
                task_instance = TaskRegistry.create(task, {"name": task})
                task_instance.run()
                logger.info(f"任务 {task} 执行完成")
            except ValueError as e:
                logger.error(f"任务创建失败: {e}")
                available = TaskRegistry.list_registered()
                logger.info(f"可用任务: {available}")
                sys.exit(1)
            except Exception as e:
                logger.exception(f"任务执行失败: {e}")
                sys.exit(1)

    except Exception as e:
        logger.exception(f"同步过程发生错误: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--table",
    help="指定要检查的表名（如 t_stock_basic）"
)
@click.option(
    "--all",
    "check_all",
    is_flag=True,
    help="检查所有支持的表"
)
@click.option(
    "--config",
    help="指定配置文件路径"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="显示详细检查结果"
)
@click.pass_context
def check(ctx, table, check_all, config, verbose):
    """
    执行数据质量检查

    检查数据库表的数据完整性和一致性

    示例:
        poetry run python main.py check --table t_stock_basic
        poetry run python main.py check --all
        poetry run python main.py check --table t_stock_basic --verbose
    """
    from scripts.run_data_quality_check import run_check, run_all_checks, SUPPORTED_TABLES

    if not table and not check_all:
        click.echo("错误: 必须指定 --table 或 --all", err=True)
        sys.exit(1)

    if table and check_all:
        click.echo("错误: 不能同时指定 --table 和 --all", err=True)
        sys.exit(1)

    try:
        if check_all:
            results = run_all_checks(verbose=verbose)
            all_passed = all(results.values())
            sys.exit(0 if all_passed else 1)
        else:
            passed = run_check(table, config, verbose)
            sys.exit(0 if passed else 1)

    except Exception as e:
        logger.exception(f"检查过程发生错误: {e}")
        sys.exit(2)


@cli.command()
@click.option(
    "--schema-dir",
    default="database/schema",
    help="数据库 schema 文件目录"
)
@click.option(
    "--force",
    is_flag=True,
    help="强制重新初始化（删除并重建表，谨慎使用）"
)
@click.pass_context
def init_db(ctx, schema_dir, force):
    """
    初始化数据库表结构

    根据 schema 文件创建数据库表和索引

    示例:
        poetry run python main.py init-db
        poetry run python main.py init-db --force  # 危险：将删除所有数据
    """
    from core.storage.relational.connection import DatabaseManager
    from core.data_sync.logger import SyncLogger

    schema_path = Path(schema_dir)

    if not schema_path.exists():
        logger.error(f"Schema 目录不存在: {schema_path}")
        sys.exit(1)

    logger.info(f"开始初始化数据库，schema 目录: {schema_path}")

    if force:
        click.confirm(
            "⚠️  警告: --force 将删除所有现有数据！确认继续?",
            abort=True
        )

    try:
        # 获取所有 SQL 文件
        sql_files = sorted(schema_path.glob("*.sql"))

        if not sql_files:
            logger.warning(f"未在 {schema_path} 找到 SQL 文件")
            sys.exit(1)

        logger.info(f"发现 {len(sql_files)} 个 schema 文件")

        # 执行 SQL 文件
        for sql_file in sql_files:
            logger.info(f"执行: {sql_file.name}")
            sql_content = sql_file.read_text(encoding="utf-8")

            # 分割多个 SQL 语句
            statements = [s.strip() for s in sql_content.split(";") if s.strip()]

            for statement in statements:
                # 跳过注释和空语句
                if statement.startswith("--") or statement.startswith("/*"):
                    continue

                try:
                    # 确定目标数据库
                    if "tushare_biz" in statement.lower():
                        db_name = "tushare_biz"
                    elif "interface" in statement.lower():
                        db_name = "interface"
                    else:
                        db_name = "tushare_biz"  # 默认

                    DatabaseManager.execute(db_name, statement)
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"表已存在，跳过: {e}")
                    else:
                        raise

        # 初始化同步日志表
        logger.info("初始化同步日志表...")
        SyncLogger.init_tables()

        logger.info("✅ 数据库初始化完成")

    except Exception as e:
        logger.exception(f"初始化失败: {e}")
        sys.exit(1)


@cli.command()
def version():
    """显示版本信息"""
    click.echo("量化交易系统 v0.1.0")
    click.echo("Phase 1: 基础设施与数据体系建设")


@cli.command()
@click.pass_context
def status(ctx):
    """检查系统状态和配置"""
    import os
    from core.data_sync.tasks import TaskRegistry

    click.echo("=" * 60)
    click.echo("系统状态检查")
    click.echo("=" * 60)

    # 检查环境变量
    click.echo("\n环境变量:")
    required_vars = ["TUSHARE_TOKEN", "DB_HOST", "DB_PASSWORD"]
    for var in required_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        display_value = value[:10] + "..." if value and len(value) > 10 else value
        click.echo(f"  {status} {var}: {display_value if value else '未设置'}")

    # 检查已注册任务
    click.echo("\n已注册的同步任务:")
    tasks = TaskRegistry.list_registered()
    for task in tasks:
        click.echo(f"  • {task}")

    # 检查日志目录
    log_dir = Path(ctx.obj.get("log_dir", "logs"))
    click.echo(f"\n日志目录: {log_dir.absolute()}")
    click.echo(f"  状态: {'✅ 存在' if log_dir.exists() else '❌ 不存在'}")

    click.echo("\n" + "=" * 60)


if __name__ == "__main__":
    cli()
