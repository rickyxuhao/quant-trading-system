#!/usr/bin/env python3
"""
券商金股监控分析系统 - 命令行工具

Usage:
    python cli.py sync [month]          # 同步金股数据
    python cli.py analyze [ts_code]     # 分析股票
    python cli.py detect [ts_code]      # 检测异动
    python cli.py report [date]         # 生成报告
    python cli.py schedule              # 启动定时任务
    python cli.py init                  # 初始化数据库
"""
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import argparse
from datetime import datetime


def init_database():
    """初始化数据库"""
    print("🗄️  初始化数据库...")

    try:
        # 读取SQL文件并执行
        import os
        import re
        sql_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')

        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 移除注释
        sql_content = re.sub(r'--.*$', '', sql_content, flags=re.MULTILINE)
        sql_content = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)

        # 按分号分割并过滤空语句
        statements = []
        for stmt in sql_content.split(';'):
            stmt = stmt.strip()
            if stmt and len(stmt) > 10:  # 过滤掉太短的无意义语句
                statements.append(stmt)

        # 执行SQL
        from core.storage.relational.connection import DatabaseManager

        created_tables = 0
        for statement in statements:
            try:
                # 添加分号
                sql = statement + ';'
                DatabaseManager.execute('interface', sql)
                created_tables += 1
            except Exception as e:
                error_msg = str(e).lower()
                # 忽略表已存在的错误
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    continue
                # 忽略其他非关键错误
                if '1050' in str(e):  # MySQL table exists error code
                    continue
                print(f"⚠️  执行SQL警告: {e}")

        print(f"✅ 数据库初始化完成 ({created_tables} 个表)")

    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()


def sync_data(month: str = None, months: int = None):
    """同步金股数据"""
    from projects.broker_gold_stock.data.sync.gold_stock_sync import sync_gold_stock_data

    print("📊 同步券商金股数据...")

    try:
        result = sync_gold_stock_data(month=month, months=months)
        print(f"✅ 同步完成: {result}")
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()


def analyze_stock(ts_code: str = None):
    """分析股票"""
    from projects.broker_gold_stock.analysis.composite_scorer import MultiDimensionAnalyzer
    from projects.broker_gold_stock.analysis.composite_scorer import CompositeScorer

    analyzer = MultiDimensionAnalyzer()
    scorer = CompositeScorer()

    if ts_code:
        # 分析单只股票
        print(f"🔍 分析股票: {ts_code}")
        analysis = analyzer.analyze_stock(ts_code)

        # 检查是否有多家券商推荐
        from projects.broker_gold_stock.data.repository import GoldStockRepository
        month = datetime.now().strftime('%Y%m')
        gold_stocks = GoldStockRepository.get_gold_stocks_by_month(month)
        broker_count = sum(1 for s in gold_stocks if s.ts_code == ts_code)
        if broker_count > 1:
            analysis.broker_count = broker_count
            # 重新计算综合评分（包含共识度加分）
            analysis.composite_score = scorer.calculate_composite_score(analysis)
            print(f"   券商共识度: {broker_count}家推荐 (+{analysis.consensus_score:.0f}分)")

        # 生成投资建议
        advice = scorer.generate_advice(analysis)

        print(f"\n{'='*50}")
        print(f"📊 分析结果 - {ts_code}")
        print(f"{'='*50}")
        print(f"综合评分: {analysis.composite_score}/100")

        if analysis.technical:
            print(f"技术评分: {analysis.technical.total}/100")
        if analysis.financial:
            print(f"财务评分: {analysis.financial.total}/100")
        if analysis.quant and analysis.quant.total:
            print(f"量化评分: {analysis.quant.total:.0f}/100")

        print(f"\n投资建议:")
        print(f"  建议动作: {advice.action.value}")
        print(f"  置信度: {advice.confidence:.0%}")
        print(f"  理由: {advice.reasoning}")
        print(f"  仓位建议: {advice.position_suggestion}")

        if advice.risk_factors:
            print(f"\n风险提示:")
            for risk in advice.risk_factors[:3]:
                print(f"  - {risk}")
    else:
        # 分析本月所有金股（去重）
        from projects.broker_gold_stock.data.repository import GoldStockRepository

        month = datetime.now().strftime('%Y%m')
        stocks = GoldStockRepository.get_gold_stocks_by_month(month)

        if not stocks:
            print(f"⚠️ {month} 月无金股数据，请先同步数据")
            return

        # 去重：同一只股票被多家券商推荐只分析一次
        unique_stocks = {}
        broker_count = {}
        for stock in stocks:
            if stock.ts_code not in unique_stocks:
                unique_stocks[stock.ts_code] = stock
                broker_count[stock.ts_code] = 1
            else:
                broker_count[stock.ts_code] += 1

        stocks = list(unique_stocks.values())
        total_recommendations = sum(broker_count.values())

        print(f"📊 分析 {month} 月 {len(stocks)} 只独特金股（来自 {total_recommendations} 条券商推荐）...")

        # 统计行业分布
        industry_stats = {}
        for stock in stocks:
            ind = stock.industry or "未知行业"
            industry_stats[ind] = industry_stats.get(ind, 0) + 1
        top_industries = sorted(industry_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"🏭 热门行业Top5: {', '.join([f'{ind}({cnt})' for ind, cnt in top_industries])}")

        codes = [s.ts_code for s in stocks]
        names = {s.ts_code: s.name for s in stocks}
        industries_map = {s.ts_code: s.industry for s in stocks}

        analyses = analyzer.analyze_stocks(codes, names=names, broker_counts=broker_count, industries=industries_map)

        # 排名
        ranked = scorer.rank_stocks(analyses, top_n=20)

        print(f"\n{'='*100}")
        print(f"🏆 金股综合排名 - Top 20")
        print(f"{'='*100}")
        print(f"{'排名':<6}{'代码':<12}{'名称':<10}{'综合分':<8}{'券商数':<8}{'技术':<8}{'财务':<8}{'建议':<10}")
        print(f"{'-'*100}")

        for i, item in enumerate(ranked, 1):
            broker_str = f"{item.get('broker_count', 1)}家"
            print(f"{i:<6}{item['ts_code']:<12}{item['name']:<10}"
                  f"{item['composite_score']:<8.0f}"
                  f"{broker_str:<8}"
                  f"{item['technical_score'] or '-':<8}"
                  f"{item['financial_score'] or '-':<8}"
                  f"{item['recommendation']:<10}")


def detect_anomaly(ts_code: str = None):
    """检测异动"""
    from projects.broker_gold_stock.analysis.anomaly_detector import AnomalyDetector
    from projects.broker_gold_stock.data.repository import GoldStockRepository

    detector = AnomalyDetector()

    if ts_code:
        # 检测单只股票
        print(f"🔍 检测异动: {ts_code}")
        anomalies = detector.detect(ts_code)

        if anomalies:
            print(f"\n⚠️  检测到 {len(anomalies)} 项异动:")
            for a in anomalies:
                print(f"  - {a.anomaly_type} ({a.severity.value})")
                if a.price_change:
                    print(f"    价格变动: {a.price_change:+.2f}%")
                if a.volume_ratio:
                    print(f"    量比: {a.volume_ratio:.1f}倍")
        else:
            print("\n✅ 无异常")
    else:
        # 检测本月所有金股（去重）
        month = datetime.now().strftime('%Y%m')
        stocks = GoldStockRepository.get_gold_stocks_by_month(month)

        # 去重
        unique_stocks = {}
        for stock in stocks:
            if stock.ts_code not in unique_stocks:
                unique_stocks[stock.ts_code] = stock
        stocks = list(unique_stocks.values())

        if not stocks:
            print(f"⚠️ {month} 月无金股数据")
            return

        print(f"📊 检测 {len(stocks)} 只金股异动...")

        codes = [s.ts_code for s in stocks]
        names = {s.ts_code: s.name for s in stocks}

        results = detector.detect_batch(codes, names)

        if results:
            print(f"\n⚠️  发现 {len(results)} 只股票有异动:")
            for code, anomalies in results.items():
                name = names.get(code, '')
                print(f"\n  {code} ({name}):")
                for a in anomalies:
                    print(f"    - {a.anomaly_type} ({a.severity.value})")
        else:
            print("\n✅ 未发现异常")


async def generate_report(date: str = None):
    """生成报告"""
    from projects.broker_gold_stock.report.morning_report import ReportScheduler

    scheduler = ReportScheduler()
    file_path = await scheduler.run_daily_report()

    if file_path:
        print(f"\n✅ 报告已生成: {file_path}")
    else:
        print("\n❌ 报告生成失败")


def start_schedule():
    """启动定时任务"""
    from projects.broker_gold_stock.scheduler.morning_task import start_scheduler
    start_scheduler()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='券商金股监控分析系统 CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py init                  # 初始化数据库
  python cli.py sync                  # 同步最近3个月数据
  python cli.py sync 202603           # 同步2026年3月数据
  python cli.py analyze 000001.SZ     # 分析单只股票
  python cli.py analyze               # 分析本月所有金股
  python cli.py report                # 生成今日报告
  python cli.py schedule              # 启动定时任务
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # init 命令
    subparsers.add_parser('init', help='初始化数据库')

    # sync 命令
    sync_parser = subparsers.add_parser('sync', help='同步金股数据')
    sync_parser.add_argument('month', nargs='?', help='指定月份 (YYYYMM)')
    sync_parser.add_argument('--months', type=int, help='同步最近N个月')

    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='分析股票')
    analyze_parser.add_argument('ts_code', nargs='?', help='股票代码')

    # detect 命令
    detect_parser = subparsers.add_parser('detect', help='检测异动')
    detect_parser.add_argument('ts_code', nargs='?', help='股票代码')

    # report 命令
    report_parser = subparsers.add_parser('report', help='生成报告')
    report_parser.add_argument('date', nargs='?', help='报告日期 (YYYYMMDD)')

    # schedule 命令
    subparsers.add_parser('schedule', help='启动定时任务')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'init':
        init_database()
    elif args.command == 'sync':
        sync_data(month=args.month, months=args.months)
    elif args.command == 'analyze':
        analyze_stock(args.ts_code)
    elif args.command == 'detect':
        detect_anomaly(args.ts_code)
    elif args.command == 'report':
        asyncio.run(generate_report(args.date))
    elif args.command == 'schedule':
        start_schedule()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
