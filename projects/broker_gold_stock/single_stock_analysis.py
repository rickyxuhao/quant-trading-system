"""
单只股票分析报告生成器
分析指定股票的多维度数据，生成详细投资报告
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from projects.broker_gold_stock.analysis.composite_scorer import MultiDimensionAnalyzer, CompositeScorer
from projects.broker_gold_stock.analysis.anomaly_detector import AnomalyDetector
from projects.broker_gold_stock.analysis.technical_analyzer import TechnicalAnalyzer
from projects.broker_gold_stock.data.models import StockAnalysis, Recommendation, InvestmentAdvice
from core.data_access.tushare.client import TushareClient


class SingleStockAnalyzer:
    """单只股票分析器"""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(base_dir, 'report', 'output')

        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.ts_client = TushareClient()
        self.multi_analyzer = MultiDimensionAnalyzer()
        self.scorer = CompositeScorer()
        self.anomaly_detector = AnomalyDetector()
        self.technical_analyzer = TechnicalAnalyzer()

    def analyze(self, ts_code: str, name: str = None, industry: str = None) -> str:
        """
        分析单只股票并生成报告

        Args:
            ts_code: 股票代码 (e.g., "002364.SZ")
            name: 股票名称 (可选，不提供则自动获取)
            industry: 所属行业 (可选)

        Returns:
            生成的报告文件路径
        """
        print(f"\n{'='*60}")
        print(f"📊 单只股票分析报告生成")
        print(f"{'='*60}")

        # 1. 获取股票基本信息
        print(f"\n1️⃣ 获取股票基本信息...")
        stock_info = self._get_stock_basic_info(ts_code)

        if name:
            stock_info['name'] = name
        if industry:
            stock_info['industry'] = industry

        print(f"   股票代码: {ts_code}")
        print(f"   股票名称: {stock_info.get('name', '未知')}")
        print(f"   所属行业: {stock_info.get('industry', '未知')}")
        print(f"   所属地区: {stock_info.get('area', '未知')}")

        # 2. 多维度分析
        print(f"\n2️⃣ 运行多维度分析...")
        analysis = self.multi_analyzer.analyze_stock(
            ts_code=ts_code,
            name=stock_info.get('name', ''),
            industry=stock_info.get('industry', ''),
            broker_count=1  # 单只股票分析，没有券商共识度
        )

        # 3. 异动检测
        print(f"\n3️⃣ 检测异动...")
        anomalies = self.anomaly_detector.detect(ts_code, stock_info.get('name', ''))
        analysis.anomalies = anomalies

        if anomalies:
            print(f"   ⚠️ 检测到 {len(anomalies)} 项异动")
            for a in anomalies:
                print(f"      - {a.anomaly_type}: {a.severity.value}")
        else:
            print(f"   ✅ 无异常")

        # 4. 生成投资建议
        print(f"\n4️⃣ 生成投资建议...")
        advice = self.scorer.generate_advice(analysis)

        # 5. 计算买入价格建议
        print(f"\n5️⃣ 计算买入价格建议...")
        price_advice = self._calculate_price_advice(ts_code, analysis)

        # 6. 生成报告
        print(f"\n6️⃣ 生成Markdown报告...")
        report_path = self._generate_report(analysis, stock_info, advice, price_advice)

        print(f"\n{'='*60}")
        print(f"✅ 报告生成完成!")
        print(f"📁 报告路径: {report_path}")
        print(f"{'='*60}\n")

        return report_path

    def _get_stock_basic_info(self, ts_code: str) -> Dict[str, Any]:
        """从Tushare获取股票基本信息"""
        try:
            df = self.ts_client.pro.stock_basic(
                ts_code=ts_code,
                fields='ts_code,name,industry,area,list_date'
            )

            if not df.empty:
                return {
                    'ts_code': df.iloc[0]['ts_code'],
                    'name': df.iloc[0]['name'],
                    'industry': df.iloc[0]['industry'] or '未知',
                    'area': df.iloc[0]['area'] or '未知',
                    'list_date': df.iloc[0]['list_date']
                }
        except Exception as e:
            print(f"   获取基本信息失败: {e}")

        return {'ts_code': ts_code, 'name': '', 'industry': '', 'area': ''}

    def _calculate_price_advice(self, ts_code: str, analysis: StockAnalysis) -> Dict[str, Any]:
        """
        计算买入价格建议

        基于技术分析计算支撑位、阻力位、买入区间和止损位
        """
        advice = {
            'current_price': None,
            'support_level': None,
            'resistance_level': None,
            'buy_range_low': None,
            'buy_range_high': None,
            'stop_loss': None,
            'details': {}
        }

        try:
            # 获取日线数据
            df, _ = self.technical_analyzer._get_price_data_with_source(ts_code, days=60)

            if df.empty or len(df) < 20:
                return advice

            latest = df.iloc[-1]
            current_price = latest['close']
            advice['current_price'] = round(current_price, 2)

            # 计算技术指标
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['std20'] = df['close'].rolling(window=20).std()
            df['upper_band'] = df['ma20'] + 2 * df['std20']
            df['lower_band'] = df['ma20'] - 2 * df['std20']

            latest = df.iloc[-1]

            # 支撑位计算 (取最低值作为强支撑)
            recent_low = df['low'].tail(20).min()  # 近20日低点
            ma20_price = latest['ma20']  # MA20均线
            lower_band = latest['lower_band']  # 布林带下轨

            support_candidates = [recent_low, ma20_price, lower_band]
            support_candidates = [x for x in support_candidates if pd.notna(x) and x > 0]

            if support_candidates:
                support_level = min(support_candidates)
            else:
                support_level = current_price * 0.95

            advice['support_level'] = round(support_level, 2)
            advice['details']['recent_low'] = round(recent_low, 2) if pd.notna(recent_low) else None
            advice['details']['ma20'] = round(ma20_price, 2) if pd.notna(ma20_price) else None
            advice['details']['lower_band'] = round(lower_band, 2) if pd.notna(lower_band) else None

            # 阻力位计算 (取最高值作为压力)
            recent_high = df['high'].tail(20).max()  # 近20日高点
            upper_band = latest['upper_band']  # 布林带上轨

            resistance_candidates = [recent_high, upper_band]
            resistance_candidates = [x for x in resistance_candidates if pd.notna(x) and x > 0]

            if resistance_candidates:
                resistance_level = max(resistance_candidates)
            else:
                resistance_level = current_price * 1.05

            advice['resistance_level'] = round(resistance_level, 2)
            advice['details']['recent_high'] = round(recent_high, 2) if pd.notna(recent_high) else None
            advice['details']['upper_band'] = round(upper_band, 2) if pd.notna(upper_band) else None

            # 建议买入区间: 支撑位 ~ 当前价格之间
            buy_range_low = support_level
            buy_range_high = current_price

            # 如果当前价格已经低于支撑位，调整买入区间
            if current_price < support_level * 1.02:
                buy_range_low = current_price * 0.98
                buy_range_high = current_price

            advice['buy_range_low'] = round(buy_range_low, 2)
            advice['buy_range_high'] = round(buy_range_high, 2)

            # 止损位: 支撑位下方 2-3%
            advice['stop_loss'] = round(support_level * 0.97, 2)

        except Exception as e:
            print(f"   计算价格建议失败: {e}")

        return advice

    def _generate_report(self, analysis: StockAnalysis, stock_info: Dict,
                         advice: InvestmentAdvice, price_advice: Dict) -> str:
        """生成Markdown格式报告"""

        date_str = datetime.now().strftime('%Y-%m-%d')
        trade_date = analysis.trade_date or datetime.now().strftime('%Y%m%d')

        lines = [
            f"# 股票分析报告 - {analysis.ts_code} ({stock_info.get('name', '未知')})",
            f"",
            f"## 一、基本信息",
            f"",
            f"| 项目 | 内容 |",
            f"|------|------|",
            f"| 股票代码 | {analysis.ts_code} |",
            f"| 股票名称 | {stock_info.get('name', '未知')} |",
            f"| 所属行业 | {stock_info.get('industry', '未知')} |",
            f"| 所属地区 | {stock_info.get('area', '未知')} |",
            f"| 分析日期 | {date_str} |",
            f"",
        ]

        # 综合评分
        tech_score = analysis.technical.total if analysis.technical else 0
        fin_score = analysis.financial.total if analysis.financial else 0
        quant_score = int(analysis.quant.total) if analysis.quant and analysis.quant.total else 0

        # 确定投资评级
        if analysis.composite_score >= 85:
            rating = "强烈推荐买入 ⭐⭐⭐⭐⭐"
        elif analysis.composite_score >= 70:
            rating = "推荐买入 ⭐⭐⭐⭐"
        elif analysis.composite_score >= 60:
            rating = "关注 ⭐⭐⭐"
        elif analysis.composite_score >= 50:
            rating = "观望 ⭐⭐"
        else:
            rating = "规避 ⭐"

        lines.extend([
            f"## 二、综合评分",
            f"",
            f"| 评分项目 | 得分 | 权重 |",
            f"|----------|------|------|",
            f"| **综合评分** | **{analysis.composite_score:.0f}/100** | - |",
            f"| 技术评分 | {tech_score}/100 | 30% |",
            f"| 财务评分 | {fin_score}/100 | 30% |",
            f"| 量化评分 | {quant_score}/100 | 30% |",
            f"",
            f"**投资评级**: {rating}",
            f"",
        ])

        # 数据溯源
        lines.extend([
            f"## 三、数据溯源",
            f"",
        ])

        # 构建数据溯源表格
        lines.extend([
            f"| 维度 | 数据表 | 数据日期 | 记录数 |",
            f"|------|--------|----------|--------|",
        ])

        # 技术面数据
        if analysis.data_sources.get('technical'):
            tech_src = analysis.data_sources['technical']
            table = tech_src.get('table_name', 'tushare_biz.t_stock_dailymarketdata')
            date_range = tech_src.get('data_date_range', '-')
            records = tech_src.get('record_count', 0)
            lines.append(f"| 技术面 | {table} | {date_range} | {records}条 |")

        # 财务面数据
        if analysis.data_sources.get('financial'):
            fin_src = analysis.data_sources['financial']
            daily_info = fin_src.get('daily_basic', {})
            if daily_info.get('source'):
                table = daily_info.get('table', 'tushare_biz.t_stock_daily_basic')
                date = daily_info.get('date', '-')
                records = daily_info.get('records', 0)
                lines.append(f"| 财务面-估值 | {table} | {date} | {records}条 |")

            income_info = fin_src.get('income', {})
            if income_info.get('source'):
                table = income_info.get('table', 'tushare_biz.t_stock_income')
                date = income_info.get('date', '-')
                records = income_info.get('records', 0)
                lines.append(f"| 财务面-利润 | {table} | {date} | {records}条 |")

            balance_info = fin_src.get('balance', {})
            if balance_info.get('source'):
                table = balance_info.get('table', 'tushare_biz.t_stock_balancesheet')
                date = balance_info.get('date', '-')
                records = balance_info.get('records', 0)
                lines.append(f"| 财务面-资产负债 | {table} | {date} | {records}条 |")

        # 量化因子数据
        if analysis.data_sources.get('quant'):
            quant_src = analysis.data_sources['quant']
            daily_data = quant_src.get('daily_data', {})
            if daily_data.get('source'):
                table = daily_data.get('table', 'tushare_biz.t_stock_dailymarketdata')
                date_range = daily_data.get('date_range', '-')
                records = daily_data.get('record_count', 0)
                lines.append(f"| 量化因子-日线 | {table} | {date_range} | {records}条 |")

            basic_data = quant_src.get('basic_data', {})
            if basic_data.get('source'):
                table = basic_data.get('table', 'tushare_biz.t_stock_daily_basic')
                date = basic_data.get('date', '-')
                records = basic_data.get('record_count', 0)
                lines.append(f"| 量化因子-基本面 | {table} | {date} | {records}条 |")

        lines.append("")

        # 技术面分析详情
        if analysis.technical:
            lines.extend([
                f"## 四、技术面分析详情",
                f"",
                f"| 分析项目 | 得分 | 说明 |",
                f"|----------|------|------|",
                f"| 趋势评分 | {analysis.technical.trend_score} | MA均线排列、价格位置 |",
                f"| 支撑压力 | {analysis.technical.level_score} | 布林带位置、近期高低点 |",
                f"| 动量指标 | {analysis.technical.momentum_score} | MACD、RSI指标 |",
                f"| 成交量 | {analysis.technical.volume_score} | 量比、OBV趋势 |",
                f"",
                f"**关键信号**:",
                f"",
            ])

            if analysis.technical.signals:
                # 分离正向和负向信号
                positive_signals = [s for s in analysis.technical.signals if isinstance(s, dict) and s.get('score', 0) > 0]
                negative_signals = [s for s in analysis.technical.signals if isinstance(s, dict) and s.get('score', 0) < 0]

                if positive_signals:
                    lines.append("- **积极信号**:")
                    for signal in positive_signals[:5]:  # 最多显示5个积极信号
                        name = signal.get('name', '')
                        value = signal.get('value', '')
                        score = signal.get('score', 0)
                        lines.append(f"  - 📈 **{name}**: {value} (+{score})")

                if negative_signals:
                    lines.append("- **消极信号**:")
                    for signal in negative_signals[:3]:  # 最多显示3个消极信号
                        name = signal.get('name', '')
                        value = signal.get('value', '')
                        score = signal.get('score', 0)
                        lines.append(f"  - 📉 **{name}**: {value} ({score})")

                if not positive_signals and not negative_signals:
                    lines.append("- 暂无显著信号")
            else:
                lines.append("- 暂无显著信号")

            lines.append("")

        # 财务面分析详情
        if analysis.financial:
            lines.extend([
                f"## 五、财务面分析详情",
                f"",
                f"| 分析项目 | 得分 | 权重 |",
                f"|----------|------|------|",
                f"| 估值水平 | {analysis.financial.valuation_score} | 35% |",
                f"| 盈利能力 | {analysis.financial.profitability_score} | 30% |",
                f"| 成长性 | {analysis.financial.growth_score} | 20% |",
                f"| 财务健康 | {analysis.financial.health_score} | 15% |",
                f"",
                f"**主要指标说明**:",
                f"",
                f"- **估值水平**: 基于PE TTM、PB、PEG等指标评分",
                f"- **盈利能力**: 基于ROE、ROA、毛利率、净利率评分",
                f"- **成长性**: 基于营收增长率、净利润增长率评分",
                f"- **财务健康**: 基于资产负债率、流动比率评分",
                f"",
            ])

        # 量化因子分析详情
        if analysis.quant:
            lines.extend([
                f"## 六、量化因子分析详情",
                f"",
                f"| 因子类型 | 得分 | 权重 | 说明 |",
                f"|----------|------|------|------|",
                f"| 价值因子 | {analysis.quant.value or '-'} | 20% | EP、BP、SP |",
                f"| 质量因子 | {analysis.quant.quality or '-'} | 20% | ROE稳定性 |",
                f"| 成长因子 | {analysis.quant.growth or '-'} | 20% | 营收/利润增长 |",
                f"| 动量因子 | {analysis.quant.momentum or '-'} | 20% | 20日/60日收益率 |",
                f"| 波动率因子 | {analysis.quant.volatility or '-'} | 10% | 20日波动率 |",
                f"| 流动性因子 | {analysis.quant.liquidity or '-'} | 10% | 日均成交额 |",
                f"",
            ])

        # 异动检测
        lines.extend([
            f"## 七、异动检测",
            f"",
        ])

        if analysis.anomalies:
            lines.append(f"**检测结果**: ⚠️ 检测到 {len(analysis.anomalies)} 项异常")
            lines.append(f"")
            lines.append(f"| 异动类型 | 严重程度 | 触发价格 | 变动 | 量比 |")
            lines.append(f"|----------|----------|----------|------|------|")

            for anomaly in analysis.anomalies:
                severity_emoji = "🔴" if anomaly.severity.value in ['high', 'critical'] else "🟡"
                price = f"¥{anomaly.trigger_price:.2f}" if anomaly.trigger_price else "-"
                change = f"{anomaly.price_change:+.2f}%" if anomaly.price_change else "-"
                vol_ratio = f"{anomaly.volume_ratio:.1f}" if anomaly.volume_ratio else "-"
                lines.append(f"| {anomaly.anomaly_type} | {severity_emoji} {anomaly.severity.value} | {price} | {change} | {vol_ratio} |")
        else:
            lines.append(f"**检测结果**: ✅ 无异常")
            lines.append(f"")
            lines.append(f"近期价格和成交量未检测到显著异动。")

        lines.append("")

        # 投资建议
        action_emoji = {
            Recommendation.STRONG_BUY: "🟢",
            Recommendation.BUY: "🟢",
            Recommendation.HOLD: "🟡",
            Recommendation.REDUCE: "🟠",
            Recommendation.SELL: "🔴",
            Recommendation.AVOID: "🔴"
        }.get(advice.action, "➖")

        lines.extend([
            f"## 八、投资建议",
            f"",
            f"| 项目 | 内容 |",
            f"|------|------|",
            f"| 建议动作 | {action_emoji} {self._get_action_text(advice.action)} |",
            f"| 置信度 | {advice.confidence*100:.0f}% |",
            f"| 仓位建议 | {advice.position_suggestion or '3-5%'} |",
            f"",
        ])

        # 买入价格建议
        if price_advice.get('current_price'):
            lines.extend([
                f"### 买入价格建议",
                f"",
                f"| 项目 | 价格 | 说明 |",
                f"|------|------|------|",
                f"| 当前价格 | ¥{price_advice['current_price']:.2f} | 最新收盘价 |",
                f"| 建议买入区间 | ¥{price_advice['buy_range_low']:.2f} - ¥{price_advice['buy_range_high']:.2f} | 支撑位~当前价 |",
                f"| 支撑位参考 | ¥{price_advice['support_level']:.2f} | 强支撑位 |",
                f"| 阻力位参考 | ¥{price_advice['resistance_level']:.2f} | 压力位 |",
                f"| 止损位建议 | ¥{price_advice['stop_loss']:.2f} | 跌破关键支撑 |",
                f"",
                f"**支撑位计算详情**:",
                f"- 近期20日低点: ¥{price_advice['details'].get('recent_low', '-')}",
                f"- MA20均线价格: ¥{price_advice['details'].get('ma20', '-')}",
                f"- 布林带下轨: ¥{price_advice['details'].get('lower_band', '-')}",
                f"- 最终支撑位: ¥{price_advice['support_level']:.2f} (取最低值)",
                f"",
                f"**阻力位计算详情**:",
                f"- 近期20日高点: ¥{price_advice['details'].get('recent_high', '-')}",
                f"- 布林带上轨: ¥{price_advice['details'].get('upper_band', '-')}",
                f"- 最终阻力位: ¥{price_advice['resistance_level']:.2f} (取最高值)",
                f"",
            ])

        # 核心理由
        lines.extend([
            f"### 核心理由",
            f"",
            advice.reasoning or "综合评分中性，建议观望",
            f"",
        ])

        # 风险提示
        lines.extend([
            f"### 风险提示",
            f"",
        ])

        if advice.risk_factors and advice.risk_factors != ["暂无重大风险"]:
            for risk in advice.risk_factors:
                lines.append(f"- ⚠️ {risk}")
        else:
            lines.append("- 暂无重大风险")

        # 技术面风险提示
        if analysis.technical and analysis.technical.total < 40:
            lines.append(f"- ⚠️ 技术走势偏弱，注意下行风险")

        # 异动风险提示
        if analysis.anomalies:
            high_severity = [a for a in analysis.anomalies if a.severity.value in ['high', 'critical']]
            if high_severity:
                lines.append(f"- ⚠️ 近期有{len(high_severity)}项高风险异动，请谨慎操作")

        lines.append("")

        # 免责声明
        lines.extend([
            f"---",
            f"",
            f"## 九、免责声明",
            f"",
            f"本报告仅供参考，不构成投资建议。投资者应独立做出投资决策，并自行承担投资风险。",
            f"",
            f"**风险提示**:",
            f"1. 股市有风险，投资需谨慎",
            f"2. 本报告基于历史数据分析，不构成对未来走势的预测",
            f"3. 技术分析和量化因子存在局限性，不能保证投资收益",
            f"4. 建议结合自身风险承受能力和投资目标做出决策",
            f"",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        # 保存报告
        file_name = f"{analysis.ts_code.replace('.', '_')}_{trade_date}_analysis.md"
        file_path = os.path.join(self.output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return file_path

    def _get_action_text(self, action: Recommendation) -> str:
        """获取建议动作的文本描述"""
        mapping = {
            Recommendation.STRONG_BUY: "强烈推荐买入",
            Recommendation.BUY: "推荐买入",
            Recommendation.HOLD: "持有观望",
            Recommendation.REDUCE: "建议减仓",
            Recommendation.SELL: "建议卖出",
            Recommendation.AVOID: "建议规避"
        }
        return mapping.get(action, "观望")


def main():
    """主函数 - 分析股票 002364"""
    analyzer = SingleStockAnalyzer()

    # 分析 002364 中恒电气
    ts_code = "002364.SZ"
    name = "中恒电气"
    industry = "电气设备"

    report_path = analyzer.analyze(ts_code, name, industry)

    print(f"\n📊 分析报告已生成: {report_path}")

    return report_path


if __name__ == "__main__":
    main()
