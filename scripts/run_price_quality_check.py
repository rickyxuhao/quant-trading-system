#!/usr/bin/env python3
"""
价格数据质量检查脚本

检查项目：
1. 价格连续性 - 检查是否存在缺失的交易日数据
2. 涨跌幅合理性 - 检查价格变动是否在允许范围内（考虑ST状态、市场类型）

使用方法：
    python scripts/run_price_quality_check.py --ts-code 000001.SZ --start-date 20240301 --end-date 20240315
    python scripts/run_price_quality_check.py --start-date 20240301 --end-date 20240315
    python scripts/run_price_quality_check.py --all --output report.txt
"""
import argparse
import sys
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, '/Users/xuhaoricky/ClawProject/Stock-trading-project')

from core.data_quality import check_price_quality, PriceDataQualityChecker


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='价格数据质量检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查单只股票
  python %(prog)s --ts-code 000001.SZ --start-date 20240301 --end-date 20240315

  # 检查所有股票最近7天的数据
  python %(prog)s --start-date 20240301 --end-date 20240315

  # 检查所有股票并输出到文件
  python %(prog)s --all --output price_quality_report.txt

  # 只检查价格连续性
  python %(prog)s --ts-code 600519.SH --check-type continuity

  # 只检查涨跌幅
  python %(prog)s --ts-code 600519.SH --check-type price_change
        """
    )

    parser.add_argument(
        '--ts-code',
        type=str,
        help='股票代码，如 000001.SZ，不指定则检查所有'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
        help='开始日期 YYYYMMDD，默认30天前'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='结束日期 YYYYMMDD，默认今天'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='检查所有股票（默认只检查最近有数据的部分股票）'
    )

    parser.add_argument(
        '--check-type',
        type=str,
        choices=['all', 'continuity', 'price_change'],
        default='all',
        help='检查类型，默认 all'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='输出文件路径，默认输出到控制台'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['text', 'json'],
        default='text',
        help='输出格式，默认 text'
    )

    parser.add_argument(
        '--db-name',
        type=str,
        default='tushare_biz',
        help='数据库名称，默认 tushare_biz'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    print("=" * 70)
    print("价格数据质量检查")
    print("=" * 70)
    print(f"检查范围: {args.start_date} ~ {args.end_date}")
    if args.ts_code:
        print(f"股票代码: {args.ts_code}")
    else:
        print(f"股票代码: 所有股票{'(全部)' if args.all else '(最近活跃)'}")
    print(f"检查类型: {args.check_type}")
    print("=" * 70)
    print()

    # 执行检查
    checker = PriceDataQualityChecker(args.db_name)

    if args.check_type == 'continuity':
        from core.data_quality import PriceContinuityChecker
        c_checker = PriceContinuityChecker(args.db_name)
        violations = c_checker.check_continuity(
            args.ts_code, args.start_date, args.end_date
        )
        result = {
            "continuity_violations": violations,
            "price_change_violations": [],
            "summary": {
                "total_violations": len(violations),
                "error_count": sum(1 for v in violations if v.severity == "error"),
                "warning_count": sum(1 for v in violations if v.severity == "warning"),
                "continuity_count": len(violations),
                "price_change_count": 0
            }
        }
    elif args.check_type == 'price_change':
        from core.data_quality import PriceChangeValidator
        v_validator = PriceChangeValidator(args.db_name)
        violations = v_validator.validate_price_changes(
            args.ts_code, args.start_date, args.end_date
        )
        result = {
            "continuity_violations": [],
            "price_change_violations": violations,
            "summary": {
                "total_violations": len(violations),
                "error_count": sum(1 for v in violations if v.severity == "error"),
                "warning_count": sum(1 for v in violations if v.severity == "warning"),
                "continuity_count": 0,
                "price_change_count": len(violations)
            }
        }
    else:
        result = checker.run_all_checks(
            args.ts_code, args.start_date, args.end_date
        )

    # 生成报告
    report = checker.generate_report(result, format=args.format)

    # 输出报告
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {args.output}")
    else:
        print(report)

    # 返回码
    summary = result["summary"]
    if summary["error_count"] > 0:
        print(f"\n⚠️  发现 {summary['error_count']} 个严重错误")
        return 1
    elif summary["warning_count"] > 0:
        print(f"\n⚠️  发现 {summary['warning_count']} 个警告")
        return 0
    else:
        print("\n✅ 所有检查通过")
        return 0


if __name__ == '__main__':
    sys.exit(main())
