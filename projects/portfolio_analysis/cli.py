#!/usr/bin/env python3
"""
持仓分析系统命令行工具

Usage:
    python -m projects.portfolio_analysis.cli [command] [options]

Commands:
    init        初始化数据库表
    sync        执行每日收盘同步
    analyze     分析持仓表现
    report      生成PDF报告
    dashboard   启动Streamlit仪表盘
    add-trade   添加交易记录
    positions   查看当前持仓

Example:
    python -m projects.portfolio_analysis.cli init
    python -m projects.portfolio_analysis.cli sync --date 2024-01-15
    python -m projects.portfolio_analysis.cli analyze --start 2024-01-01 --end 2024-01-31
    python -m projects.portfolio_analysis.cli report --weekly
"""

import argparse
import sys
from datetime import date, datetime, timedelta


def cmd_init(args):
    """初始化数据库"""
    print("🔄 初始化数据库...")
    from projects.portfolio_analysis.database.models import init_database
    init_database()
    print("✅ 数据库初始化完成")


def cmd_sync(args):
    """执行收盘同步"""
    print("🔄 执行收盘同步...")
    from projects.portfolio_analysis.sync.daily_sync import DailySync

    sync = DailySync()
    target_date = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else date.today()

    try:
        result = sync.run_eod_sync(target_date)
        print(f"\n✅ 同步完成:")
        print(f"   日期: {result['date']}")
        print(f"   持仓同步: {result['positions_synced']} 只")
        print(f"   快照创建: {'是' if result['snapshot_created'] else '否'}")
        print(f"   风险预警: {result['risks_found']} 条")
    except Exception as e:
        print(f"\n❌ 同步失败: {e}")
        sys.exit(1)


def cmd_analyze(args):
    """分析持仓"""
    print("🔄 分析持仓...")
    from projects.portfolio_analysis import PortfolioAnalyzer

    analyzer = PortfolioAnalyzer()

    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    else:
        end_date = date.today()

    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    try:
        result = analyzer.analyze(start_date, end_date)

        print("\n" + "=" * 60)
        print("持仓分析报告")
        print("=" * 60)
        print(f"分析区间: {start_date} ~ {end_date}")
        print("\n【收益指标】")
        print(f"  总收益率: {result.metrics.total_return*100:+.2f}%")
        print(f"  年化收益率: {result.metrics.annual_return*100:+.2f}%")
        print(f"  夏普比率: {result.metrics.sharpe_ratio:.2f}")

        print("\n【风险指标】")
        print(f"  最大回撤: {result.metrics.max_drawdown*100:.2f}%")
        print(f"  波动率: {result.metrics.volatility*100:.2f}%")
        print(f"  VaR(95%): {result.metrics.var_95*100:.2f}%")

        print("\n【持仓结构】")
        print(f"  持仓数量: {result.structure.position_count} 只")
        print(f"  现金比例: {result.structure.cash_ratio*100:.1f}%")

        if result.risks.alerts:
            print("\n【风险预警】")
            for alert in result.risks.alerts:
                emoji = "🔴" if alert.level == "critical" else "🟡"
                print(f"  {emoji} [{alert.level.upper()}] {alert.message}")
        else:
            print("\n✅ 未发现明显风险")

        if args.json:
            import json
            output_file = args.json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            print(f"\n📄 结果已保存: {output_file}")

    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_report(args):
    """生成报告"""
    print("🔄 生成报告...")
    from projects.portfolio_analysis.reporting.report_generator import ReportGenerator

    generator = ReportGenerator()

    try:
        if args.weekly:
            end_date = date.today()
            report_path = generator.generate_weekly_report(end_date)
        elif args.monthly:
            today = date.today()
            report_path = generator.generate_monthly_report(today.year, today.month)
        else:
            if args.start:
                start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
            else:
                start_date = date.today() - timedelta(days=30)

            if args.end:
                end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
            else:
                end_date = date.today()

            report_path = generator.generate_report(start_date, end_date)

        print(f"\n✅ 报告已生成: {report_path}")
    except Exception as e:
        print(f"\n❌ 报告生成失败: {e}")
        sys.exit(1)


def cmd_dashboard(args):
    """启动仪表盘"""
    import subprocess

    print("🚀 启动Streamlit仪表盘...")
    app_path = "projects/portfolio_analysis/visualization/streamlit_app.py"

    cmd = ["streamlit", "run", app_path]
    if args.port:
        cmd.extend(["--server.port", str(args.port)])

    subprocess.run(cmd)


def cmd_add_trade(args):
    """添加交易记录"""
    from decimal import Decimal
    from projects.portfolio_analysis.database.models import Transaction
    from projects.portfolio_analysis.database.repository import PositionRepository

    try:
        txn = Transaction(
            trade_date=datetime.strptime(args.date, '%Y-%m-%d').date(),
            code=args.code,
            name=args.name or "",
            trade_type=args.type,
            volume=args.volume,
            price=Decimal(str(args.price)),
            amount=Decimal(str(args.volume * args.price)),
            fee=Decimal(str(args.fee)) if args.fee else Decimal('0'),
            strategy=args.strategy
        )

        repo = PositionRepository()
        txn_id = repo.add_transaction(txn)

        print(f"✅ 交易已添加，ID: {txn_id}")

        # 显示更新后的持仓
        position = repo.get_position_by_code(args.code)
        if position:
            print(f"   当前持仓: {position.volume} 股，成本 {position.cost_price}")

    except Exception as e:
        print(f"❌ 添加交易失败: {e}")
        sys.exit(1)


def cmd_positions(args):
    """查看当前持仓"""
    from projects.portfolio_analysis import PortfolioAnalyzer

    analyzer = PortfolioAnalyzer()
    positions = analyzer.get_current_positions_with_price()

    if not positions:
        print("📭 当前无持仓")
        return

    print("\n" + "=" * 80)
    print(f"{'代码':<12} {'名称':<10} {'数量':>10} {'成本':>10} {'现价':>10} {'市值':>12} {'盈亏':>10} {'权重':>6}")
    print("=" * 80)

    total_value = sum(p.market_value for p in positions)

    for p in positions:
        pnl_str = f"{p.pnl:+,.0f}"
        print(f"{p.code:<12} {p.name:<10} {p.volume:>10} {p.cost_price:>10.2f} "
              f"{p.current_price:>10.2f} {p.market_value:>12,.0f} {pnl_str:>10} {p.weight*100:>5.1f}%")

    print("=" * 80)
    total_cost = sum(p.cost for p in positions)
    total_pnl = sum(p.pnl for p in positions)
    print(f"{'合计':<34} {total_cost:>12,.0f} {total_value:>12,.0f} {total_pnl:+,.0f}")


def cmd_backfill(args):
    """回补历史快照"""
    print("🔄 回补历史快照...")
    from projects.portfolio_analysis.sync.daily_sync import DailySync

    sync = DailySync()

    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()

    try:
        result = sync.backfill_snapshots(start_date, end_date)
        print(f"\n✅ 回补完成:")
        print(f"   交易日数: {result['trade_dates']}")
        print(f"   成功同步: {result['synced']}")
    except Exception as e:
        print(f"\n❌ 回补失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="持仓分析系统命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化数据库
  python -m projects.portfolio_analysis.cli init

  # 同步今日收盘数据
  python -m projects.portfolio_analysis.cli sync

  # 分析最近30天表现
  python -m projects.portfolio_analysis.cli analyze

  # 生成周报
  python -m projects.portfolio_analysis.cli report --weekly

  # 启动仪表盘
  python -m projects.portfolio_analysis.cli dashboard

  # 添加交易记录
  python -m projects.portfolio_analysis.cli add-trade --code 000001.SZ --name 平安银行 \\
      --type buy --volume 1000 --price 10.5 --date 2024-01-15
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # init 命令
    init_parser = subparsers.add_parser('init', help='初始化数据库表')

    # sync 命令
    sync_parser = subparsers.add_parser('sync', help='执行每日收盘同步')
    sync_parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)')

    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='分析持仓表现')
    analyze_parser.add_argument('--start', type=str, help='开始日期 (YYYY-MM-DD)')
    analyze_parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    analyze_parser.add_argument('--json', type=str, help='输出JSON文件路径')

    # report 命令
    report_parser = subparsers.add_parser('report', help='生成PDF报告')
    report_group = report_parser.add_mutually_exclusive_group()
    report_group.add_argument('--weekly', action='store_true', help='生成周报')
    report_group.add_argument('--monthly', action='store_true', help='生成月报')
    report_parser.add_argument('--start', type=str, help='开始日期')
    report_parser.add_argument('--end', type=str, help='结束日期')

    # dashboard 命令
    dashboard_parser = subparsers.add_parser('dashboard', help='启动Streamlit仪表盘')
    dashboard_parser.add_argument('--port', type=int, help='端口号')

    # add-trade 命令
    trade_parser = subparsers.add_parser('add-trade', help='添加交易记录')
    trade_parser.add_argument('--code', required=True, help='股票代码')
    trade_parser.add_argument('--name', help='股票名称')
    trade_parser.add_argument('--type', required=True, choices=['buy', 'sell'], help='交易类型')
    trade_parser.add_argument('--volume', required=True, type=int, help='交易数量')
    trade_parser.add_argument('--price', required=True, type=float, help='成交价格')
    trade_parser.add_argument('--date', required=True, help='交易日期 (YYYY-MM-DD)')
    trade_parser.add_argument('--fee', type=float, default=0, help='手续费')
    trade_parser.add_argument('--strategy', help='策略名称')

    # positions 命令
    positions_parser = subparsers.add_parser('positions', help='查看当前持仓')

    # backfill 命令
    backfill_parser = subparsers.add_parser('backfill', help='回补历史快照')
    backfill_parser.add_argument('--start', required=True, help='开始日期 (YYYY-MM-DD)')
    backfill_parser.add_argument('--end', required=True, help='结束日期 (YYYY-MM-DD)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 执行对应命令
    commands = {
        'init': cmd_init,
        'sync': cmd_sync,
        'analyze': cmd_analyze,
        'report': cmd_report,
        'dashboard': cmd_dashboard,
        'add-trade': cmd_add_trade,
        'positions': cmd_positions,
        'backfill': cmd_backfill,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
