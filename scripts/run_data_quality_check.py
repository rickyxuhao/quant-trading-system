#!/usr/bin/env python3
"""
数据质量检查脚本

用法:
    # 检查指定表
    poetry run python scripts/run_data_quality_check.py --table t_stock_basic

    # 指定配置文件路径
    poetry run python scripts/run_data_quality_check.py --table t_stock_basic --config path/to/config.yaml

    # 显示详细检查结果
    poetry run python scripts/run_data_quality_check.py --table t_stock_basic --verbose

    # 检查所有表
    poetry run python scripts/run_data_quality_check.py --all

退出码:
    0 - 检查通过
    1 - 发现错误级别的问题
    2 - 配置错误或执行异常
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.data_quality.checker import check_table
from core.logger import get_logger, init_logging

logger = get_logger(__name__)

# 支持的表列表
SUPPORTED_TABLES = [
    "t_stock_basic",
    "t_stock_tradedate",
    "t_stock_st_list",
    "t_stock_dailymarketdata",
    "t_stock_adjfactor",
]


def find_config_file(table_name: str) -> Optional[Path]:
    """
    自动查找表的配置文件

    Args:
        table_name: 表名

    Returns:
        配置文件路径，如果不存在返回 None
    """
    config_path = project_root / "core" / "data_quality" / "config" / f"{table_name}.yaml"
    if config_path.exists():
        return config_path
    return None


def run_check(table_name: str, config_path: Optional[str] = None, verbose: bool = False) -> bool:
    """
    执行单表检查

    Args:
        table_name: 表名
        config_path: 配置文件路径，None 则自动查找
        verbose: 是否显示详细结果

    Returns:
        是否通过检查
    """
    # 确定配置文件路径
    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return False
    else:
        config_file = find_config_file(table_name)
        if not config_file:
            logger.error(f"未找到表 {table_name} 的配置文件")
            logger.info(f"支持的表: {', '.join(SUPPORTED_TABLES)}")
            return False

    logger.info(f"开始检查表: {table_name}")
    logger.info(f"配置文件: {config_file}")
    print("=" * 60)

    try:
        # 执行检查
        result = check_table(str(config_file))

        # 输出摘要
        summary = result.summary()
        print("\n" + "=" * 60)
        print("检查结果摘要:")
        print(f"  总规则数: {summary['total_rules']}")
        print(f"  通过: {summary['passed']}")
        print(f"  失败: {summary['failed']}")
        print(f"  - 错误: {summary['errors']}")
        print(f"  - 警告: {summary['warnings']}")
        print(f"  - 信息: {summary['infos']}")
        print(f"  是否有效: {'✅ 是' if summary['is_valid'] else '❌ 否'}")
        print("=" * 60)

        # 详细输出失败项
        if verbose and result.failed:
            print("\n失败项详情:")
            for failure in result.failed:
                print(f"\n  [{failure['severity'].upper()}] {failure['rule']}")
                print(f"    消息: {failure['message']}")
                if 'column' in failure:
                    print(f"    列: {failure['column']}")
                if 'value' in failure:
                    print(f"    值: {failure['value']}")
            print("=" * 60)

        if not summary['is_valid']:
            logger.error("存在错误级别的问题，请查看详情")
            return False
        else:
            logger.info("✅ 数据质量检查通过")
            return True

    except Exception as e:
        logger.exception(f"检查过程中发生异常: {e}")
        return False


def run_all_checks(verbose: bool = False) -> dict:
    """
    检查所有支持的表

    Args:
        verbose: 是否显示详细结果

    Returns:
        各表的检查结果字典
    """
    results = {}
    print("\n开始批量检查所有表...")
    print("=" * 60)

    for table_name in SUPPORTED_TABLES:
        print(f"\n检查表: {table_name}")
        results[table_name] = run_check(table_name, verbose=verbose)

    # 输出总体摘要
    print("\n" + "=" * 60)
    print("批量检查总体结果:")
    passed = sum(1 for r in results.values() if r)
    failed = sum(1 for r in results.values() if not r)
    print(f"  通过: {passed}/{len(results)}")
    print(f"  失败: {failed}/{len(results)}")
    for table, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {table}")
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="数据质量检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查股票基础信息表
  poetry run python scripts/run_data_quality_check.py --table t_stock_basic

  # 检查所有表
  poetry run python scripts/run_data_quality_check.py --all

  # 详细输出
  poetry run python scripts/run_data_quality_check.py --table t_stock_basic --verbose
        """
    )

    parser.add_argument(
        "--table",
        help="要检查的表名"
    )

    parser.add_argument(
        "--config",
        help="配置文件路径（默认自动查找）"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        dest="check_all",
        help="检查所有支持的表"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细检查结果"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)"
    )

    args = parser.parse_args()

    # 初始化日志
    init_logging(log_level=args.log_level)

    # 验证参数
    if not args.table and not args.check_all:
        parser.error("必须指定 --table 或 --all")

    if args.table and args.check_all:
        parser.error("不能同时指定 --table 和 --all")

    # 执行检查
    try:
        if args.check_all:
            results = run_all_checks(verbose=args.verbose)
            all_passed = all(results.values())
            sys.exit(0 if all_passed else 1)
        else:
            passed = run_check(args.table, args.config, args.verbose)
            sys.exit(0 if passed else 1)

    except KeyboardInterrupt:
        logger.info("用户中断检查")
        sys.exit(2)
    except Exception as e:
        logger.exception(f"执行失败: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
