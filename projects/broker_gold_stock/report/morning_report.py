"""
晨间报告生成器
生成每日投资报告
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from projects.broker_gold_stock.data.models import (
    StockAnalysis, MorningReport, DailyStrategy, GoldStock
)
from projects.broker_gold_stock.data.repository import (
    MorningReportRepository, GoldStockRepository
)
from projects.broker_gold_stock.shared.services.ai_service import get_ai_service


class MorningReportGenerator:
    """晨间报告生成器"""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            # 默认输出到项目目录下的output文件夹
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, 'report', 'output')

        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    async def generate(self, date: str = None, analyses: List[StockAnalysis] = None,
                       strategy: DailyStrategy = None) -> str:
        """
        生成晨间报告

        Args:
            date: 报告日期，默认今天
            analyses: 分析结果列表
            strategy: 投资策略

        Returns:
            生成的Markdown文件路径
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')

        print(f"📄 生成晨间报告: {date}")

        # 获取本月金股
        month = date[:6]
        gold_stocks = GoldStockRepository.get_gold_stocks_by_month(month)

        # 如果没有提供分析结果，生成简化报告
        if analyses is None:
            analyses = []

        # 生成报告数据
        report_data = self._prepare_report_data(date, gold_stocks, analyses, strategy)

        # 生成Markdown内容
        markdown_content = self._generate_markdown(report_data)

        # 保存文件
        file_path = os.path.join(self.output_dir, f"{date}_morning_report.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"✅ 报告已保存: {file_path}")

        # 保存到数据库
        self._save_report_to_db(report_data, file_path)

        return file_path

    def _prepare_report_data(self, date: str, gold_stocks: List[GoldStock],
                             analyses: List[StockAnalysis],
                             strategy: DailyStrategy) -> Dict[str, Any]:
        """准备报告数据"""

        # 统计信息
        anomaly_count = sum(len(a.anomalies) for a in analyses)
        buy_signals = sum(1 for a in analyses if a.composite_score >= 70)
        sell_signals = sum(1 for a in analyses if a.composite_score < 50)

        # 排序获取重点股票
        sorted_analyses = sorted(analyses, key=lambda x: x.composite_score, reverse=True)
        top_stocks = sorted_analyses[:20]

        # 获取有异常的股票
        anomaly_stocks = [a for a in analyses if a.anomalies]

        # 生成摘要
        summary = self._generate_summary(date, gold_stocks, analyses, strategy)

        return {
            'date': date,
            'month': date[:6],
            'gold_stock_count': len(gold_stocks),
            'anomaly_count': anomaly_count,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'top_stocks': top_stocks,
            'anomaly_stocks': anomaly_stocks,
            'summary': summary,
            'strategy': strategy,
            'all_analyses': analyses
        }

    def _generate_summary(self, date: str, gold_stocks: List[GoldStock],
                          analyses: List[StockAnalysis],
                          strategy: DailyStrategy) -> str:
        """生成报告摘要"""
        parts = []

        parts.append(f"本日监控券商金股{len(gold_stocks)}只，")

        if analyses:
            avg_score = sum(a.composite_score for a in analyses) / len(analyses)
            parts.append(f"综合评分均值{avg_score:.1f}分，")

            high_score = sum(1 for a in analyses if a.composite_score >= 75)
            parts.append(f"其中{high_score}只评分超过75分，")

        if strategy:
            parts.append(f"建议仓位{strategy.overall_position}，")
            parts.append(f"整体风格偏向{strategy.style_bias}。")

        return ''.join(parts)

    def _generate_markdown(self, data: Dict[str, Any]) -> str:
        """生成Markdown格式的报告内容"""
        date_str = datetime.strptime(data['date'], '%Y%m%d').strftime('%Y年%m月%d日')
        month_str = data['month']

        lines = [
            f"# 券商金股晨间投资报告",
            f"",
            f"**报告日期**: {date_str}",
            f"**报告周期**: {month_str[:4]}年{month_str[4:]}月",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"---",
            f"",
            f"## 一、市场概览",
            f"",
            f"### 执行摘要",
            f"{data['summary']}",
            f"",
            f"### 统计概览",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 监控金股数量 | {data['gold_stock_count']} |",
            f"| 异动股票数量 | {data['anomaly_count']} |",
            f"| 买入信号数量 | {data['buy_signals']} |",
            f"| 卖出/规避信号 | {data['sell_signals']} |",
            f"",
        ]

        # 行业板块分析
        lines.extend([
            f"## 二、行业板块分析",
            f"",
            f"### 热门行业分布",
            f"",
        ])

        # 计算行业分布
        industry_counts = {}
        for analysis in data.get('all_analyses', []):
            if analysis.industry:
                ind = analysis.industry
                if ind not in industry_counts:
                    industry_counts[ind] = {'count': 0, 'total_score': 0}
                industry_counts[ind]['count'] += 1
                industry_counts[ind]['total_score'] += analysis.composite_score

        # 排序并展示
        sorted_industries = sorted(industry_counts.items(),
                                   key=lambda x: x[1]['count'],
                                   reverse=True)[:10]

        if sorted_industries:
            lines.extend([
                f"| 行业 | 金股数量 | 平均评分 | 市场热度 |",
                f"|------|----------|----------|----------|",
            ])

            for ind, stats in sorted_industries:
                avg_score = stats['total_score'] / stats['count']
                heat = "🔥🔥🔥" if stats['count'] >= 5 else ("🔥🔥" if stats['count'] >= 3 else "🔥")
                lines.append(f"| {ind} | {stats['count']} | {avg_score:.0f} | {heat} |")

            lines.append(f"")

        # 今日策略
        if data.get('strategy'):
            strategy = data['strategy']
            lines.extend([
                f"## 三、今日策略",
                f"",
                f"**市场展望**: {strategy.market_outlook}",
                f"",
                f"**整体仓位**: {strategy.overall_position}",
                f"",
                f"**风格偏好**: {strategy.style_bias}",
                f"",
                f"**风险等级**: {strategy.risk_level}",
                f"",
            ])

            if strategy.focus_stocks:
                lines.extend([
                    f"**开盘关注**: {', '.join(strategy.focus_stocks[:5])}",
                    f"",
                ])
            if strategy.dip_buying:
                lines.extend([
                    f"**逢低布局**: {', '.join(strategy.dip_buying[:3])}",
                    f"",
                ])
            if strategy.profit_taking:
                lines.extend([
                    f"**止盈考虑**: {', '.join(strategy.profit_taking[:3])}",
                    f"",
                ])

            lines.extend([
                f"**策略总结**: {strategy.summary}",
                f"",
            ])

        # 重点金股推荐
        if data.get('top_stocks'):
            lines.extend([
                f"## 四、重点金股推荐",
                f"",
                f"### 买入机会 (综合评分>70)",
                f"",
            ])

            buy_opportunities = [a for a in data['top_stocks'] if a.composite_score >= 70][:10]

            if buy_opportunities:
                for i, analysis in enumerate(buy_opportunities, 1):
                    lines.extend(self._format_stock_detail(analysis, i))
            else:
                lines.append("暂无高评分买入机会\n")

        # 异动提醒
        if data.get('anomaly_stocks'):
            lines.extend([
                f"",
                f"## 五、异动提醒",
                f"",
            ])

            for analysis in data['anomaly_stocks'][:10]:
                lines.extend(self._format_anomaly_detail(analysis))

        # 风险提示
        if data.get('all_analyses'):
            low_score = [a for a in data['all_analyses'] if a.composite_score < 50][:5]
            if low_score:
                lines.extend([
                    f"",
                    f"## 六、风险提示",
                    f"",
                    f"### 需警惕股票 (综合评分<50)",
                    f"",
                    "| 排名 | 股票代码 | 股票名称 | 综合评分 | 技术 | 财务 |",
                    "|------|----------|----------|----------|------|------|",
                ])

                for i, a in enumerate(low_score, 1):
                    tech = a.technical.total if a.technical else 'N/A'
                    fin = a.financial.total if a.financial else 'N/A'
                    lines.append(f"| {i} | {a.ts_code} | {a.name} | {a.composite_score:.0f} | {tech} | {fin} |")

                lines.append("")

        # 数据附录
        if data.get('top_stocks'):
            lines.extend([
                f"",
                f"## 七、数据附录",
                f"",
                f"### 本月金股完整评分",
                f"",
                "| 排名 | 股票代码 | 股票名称 | 综合分 | 技术 | 财务 | 量化 | 建议 |",
                "|------|----------|----------|--------|------|------|------|------|",
            ])

            for i, a in enumerate(data['top_stocks'][:30], 1):
                tech = a.technical.total if a.technical else '-'
                fin = a.financial.total if a.financial else '-'
                quant = int(a.quant.total) if a.quant and a.quant.total else '-'

                if a.composite_score >= 80:
                    rec = "强烈推荐"
                elif a.composite_score >= 70:
                    rec = "推荐"
                elif a.composite_score >= 60:
                    rec = "关注"
                elif a.composite_score >= 50:
                    rec = "观望"
                else:
                    rec = "规避"

                lines.append(f"| {i} | {a.ts_code} | {a.name} | {a.composite_score:.0f} | {tech} | {fin} | {quant} | {rec} |")

            lines.append("")

        # 免责声明
        lines.extend([
            f"",
            f"---",
            f"",
            f"**免责声明**: 本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。",
            f"",
            f"*报告由券商金股监控分析系统自动生成*",
        ])

        return '\n'.join(lines)

    def _format_stock_detail(self, analysis, rank: int) -> List[str]:
        """格式化股票详情 - 包含数据溯源和详细指标"""
        lines = [
            f"#### {rank}. {analysis.name} ({analysis.ts_code}) - 综合评分: {analysis.composite_score:.0f}",
            f"",
        ]

        # 券商推荐信息
        if analysis.broker_count > 1:
            lines.append(f"**🔥 券商共识度**: 被 **{analysis.broker_count}** 家券商推荐 (+{analysis.consensus_score:.0f}分)")
            lines.append(f"")

        # 所属行业
        if analysis.industry:
            lines.append(f"**所属行业**: {analysis.industry}")
            lines.append(f"")

        # 数据来源说明 - 详细版本
        lines.extend([
            f"**数据溯源详情**:",
            f"",
            f"| 维度 | 数据表 | 数据日期/范围 | 记录数 | 评分 |",
            f"|------|--------|---------------|--------|------|",
        ])

        # 技术面数据源
        if analysis.technical and analysis.data_sources.get('technical'):
            tech_src = analysis.data_sources['technical']
            table_name = tech_src.get('table_name', '-')
            date_range = tech_src.get('data_date_range', tech_src.get('date_range', '-'))
            record_count = tech_src.get('record_count', 0)
            lines.append(f"| 技术面 | {table_name} | {date_range} | {record_count}条 | {analysis.technical.total} |")

        # 财务面数据源
        if analysis.financial and analysis.data_sources.get('financial'):
            fin_src = analysis.data_sources['financial']
            # daily_basic
            daily_info = fin_src.get('daily_basic', {})
            if daily_info.get('source'):
                table = daily_info.get('table', '-')
                date = daily_info.get('date', '-')
                records = daily_info.get('records', 0)
                lines.append(f"| 财务面-估值 | {table} | {date} | {records}条 | {analysis.financial.valuation_score} |")
            # income
            income_info = fin_src.get('income', {})
            if income_info.get('source'):
                table = income_info.get('table', '-')
                date = income_info.get('date', '-')
                records = income_info.get('records', 0)
                lines.append(f"| 财务面-利润 | {table} | {date} | {records}条 | {analysis.financial.profitability_score} |")
            # balance
            balance_info = fin_src.get('balance', {})
            if balance_info.get('source'):
                table = balance_info.get('table', '-')
                date = balance_info.get('date', '-')
                records = balance_info.get('records', 0)
                lines.append(f"| 财务面-资产负债 | {table} | {date} | {records}条 | {analysis.financial.health_score} |")

        # 量化因子数据源
        if analysis.quant and analysis.quant.total and analysis.data_sources.get('quant'):
            quant_src = analysis.data_sources['quant']
            # daily数据
            daily_data = quant_src.get('daily_data', {})
            if daily_data.get('source'):
                table = daily_data.get('table', '-')
                date_range = daily_data.get('date_range', '-')
                records = daily_data.get('record_count', 0)
                lines.append(f"| 量化-日线 | {table} | {date_range} | {records}条 | - |")
            # basic数据
            basic_data = quant_src.get('basic_data', {})
            if basic_data.get('source'):
                table = basic_data.get('table', '-')
                date = basic_data.get('date', '-')
                records = basic_data.get('record_count', 0)
                lines.append(f"| 量化-基本面 | {table} | {date} | {records}条 | {int(analysis.quant.total)} |")

        lines.append(f"")

        # 各维度评分详情
        lines.extend([
            f"**评分详情**:",
            f"| 维度 | 总分 | 分项 |",
            f"|------|------|------|",
        ])

        if analysis.technical:
            lines.append(f"| 技术面 | {analysis.technical.total} | 趋势:{analysis.technical.trend_score} 支撑:{analysis.technical.level_score} 动量:{analysis.technical.momentum_score} 量能:{analysis.technical.volume_score} |")

        if analysis.financial:
            lines.append(f"| 财务面 | {analysis.financial.total} | 估值:{analysis.financial.valuation_score} 盈利:{analysis.financial.profitability_score} 成长:{analysis.financial.growth_score} 健康:{analysis.financial.health_score} |")

        if analysis.quant and analysis.quant.total:
            lines.append(f"| 量化因子 | {int(analysis.quant.total)} | 价值:{analysis.quant.value or '-'} 质量:{analysis.quant.quality or '-'} 动量:{analysis.quant.momentum or '-'} |")

        lines.extend([
            f"",
            f"**投资建议**: ",
        ])

        if analysis.composite_score >= 85:
            lines.append("- **建议动作**: 强烈推荐买入 ⭐⭐⭐⭐⭐")
            lines.append("- **仓位建议**: 8-10%")
        elif analysis.composite_score >= 75:
            lines.append("- **建议动作**: 推荐买入 ⭐⭐⭐⭐")
            lines.append("- **仓位建议**: 5-8%")
        elif analysis.composite_score >= 60:
            lines.append("- **建议动作**: 关注")
            lines.append("- **仓位建议**: 3-5%")
        else:
            lines.append("- **建议动作**: 观望/规避")
            lines.append("- **仓位建议**: 0-2%")

        if analysis.anomalies:
            lines.append(f"- **⚠️ 注意**: 近期有{len(analysis.anomalies)}项异动，请注意风险")

        lines.append("")
        return lines

    def _format_anomaly_detail(self, analysis) -> List[str]:
        """格式化异动详情"""
        if not analysis.anomalies:
            return []

        lines = [
            f"#### {analysis.name} ({analysis.ts_code})",
            f"",
        ]

        for anomaly in analysis.anomalies[:3]:
            severity_icon = "🔴" if anomaly.severity.value in ['high', 'critical'] else "🟡"
            lines.append(f"{severity_icon} **{anomaly.anomaly_type}** - {anomaly.severity.value}")
            lines.append(f"- 检测日期: {anomaly.detect_date}")

            if anomaly.price_change:
                emoji = "📈" if anomaly.price_change > 0 else "📉"
                lines.append(f"- 价格变动: {emoji} {anomaly.price_change:+.2f}%")

            if anomaly.volume_ratio:
                lines.append(f"- 量比: {anomaly.volume_ratio:.1f}倍")

            if anomaly.ai_analysis:
                lines.append(f"- AI分析: {anomaly.ai_analysis[:100]}...")

            lines.append("")

        return lines

    def _save_report_to_db(self, data: Dict[str, Any], file_path: str):
        """保存报告记录到数据库"""
        try:
            report = MorningReport(
                report_date=data['date'],
                gold_stock_count=data['gold_stock_count'],
                anomaly_count=data['anomaly_count'],
                buy_signals=data['buy_signals'],
                sell_signals=data['sell_signals'],
                summary=data['summary'],
                highlight_stocks=[{
                    'ts_code': a.ts_code,
                    'name': a.name,
                    'score': a.composite_score
                } for a in data.get('top_stocks', [])[:10]],
                market_outlook=data.get('strategy', {}).market_outlook if data.get('strategy') else None,
                markdown_path=file_path,
                send_status='generated'
            )

            MorningReportRepository.save_report(report)

        except Exception as e:
            print(f"保存报告记录失败: {e}")


class ReportScheduler:
    """报告调度器 - 定时生成报告"""

    def __init__(self):
        self.generator = MorningReportGenerator()

    async def run_daily_report(self):
        """运行每日报告任务"""
        from datetime import datetime

        date = datetime.now().strftime('%Y%m%d')

        print(f"\n{'='*50}")
        print(f"🌅 开始生成晨间报告: {date}")
        print(f"{'='*50}\n")

        # 1. 获取本月金股（去重：同一只股票被多家券商推荐只保留一次）
        month = date[:6]
        gold_stocks = GoldStockRepository.get_gold_stocks_by_month(month)

        if not gold_stocks:
            print(f"⚠️ {month} 月无金股数据，请先同步数据")
            return None

        # 去重：按股票代码去重，保留第一个（记录被几家券商推荐）
        unique_stocks = {}
        broker_count = {}  # 记录每只股票被几家券商推荐
        industries = {}  # 记录每只股票所属行业
        for stock in gold_stocks:
            if stock.ts_code not in unique_stocks:
                unique_stocks[stock.ts_code] = stock
                broker_count[stock.ts_code] = 1
                industries[stock.ts_code] = stock.industry or "未知行业"
            else:
                broker_count[stock.ts_code] += 1

        gold_stocks = list(unique_stocks.values())
        total_recommendations = sum(broker_count.values())

        print(f"📊 本月共有 {len(gold_stocks)} 只独特金股（来自 {total_recommendations} 条券商推荐）\n")

        # 统计行业分布
        industry_stats = {}
        for stock in gold_stocks:
            ind = stock.industry or "未知行业"
            industry_stats[ind] = industry_stats.get(ind, 0) + 1
        top_industries = sorted(industry_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"🏭 热门行业Top5: {', '.join([f'{ind}({cnt})' for ind, cnt in top_industries])}\n")

        # 2. 多维度分析
        from projects.broker_gold_stock.analysis.composite_scorer import MultiDimensionAnalyzer

        analyzer = MultiDimensionAnalyzer()

        # 构建代码到各属性的映射
        names = {s.ts_code: s.name for s in gold_stocks}
        codes = [s.ts_code for s in gold_stocks]
        industries_map = {s.ts_code: s.industry for s in gold_stocks}

        # 批量分析（限制数量以控制时间）
        print("🔍 开始多维度分析...")
        analyses = analyzer.analyze_stocks(
            codes[:50],  # 限制分析数量
            names=names,
            broker_counts=broker_count,
            industries=industries_map
        )

        print(f"\n✅ 完成 {len(analyses)} 只股票分析\n")

        # 3. 生成投资策略
        print("🤖 生成投资策略...")
        ai_service = get_ai_service()
        strategy = await ai_service.generate_daily_strategy(analyses)
        print(f"✅ 策略: {strategy.summary[:100]}...\n")

        # 4. 生成报告
        print("📄 生成报告...")
        file_path = await self.generator.generate(date, analyses, strategy)

        print(f"\n{'='*50}")
        print(f"✅ 晨间报告生成完成!")
        print(f"📁 报告路径: {file_path}")
        print(f"{'='*50}\n")

        return file_path
