"""
PDF报告生成器

使用Jinja2模板和WeasyPrint生成专业的持仓分析报告。

Example:
    >>> from projects.portfolio_analysis import ReportGenerator
    >>> generator = ReportGenerator()
    >>> pdf_path = generator.generate_weekly_report(date(2024, 1, 15))
"""

import os
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from jinja2 import Template
import pandas as pd

from projects.portfolio_analysis import PortfolioAnalyzer
from projects.portfolio_analysis.core.analyzer import PortfolioAnalysisResult
from projects.portfolio_analysis.database.repository import PositionRepository

logger = logging.getLogger(__name__)

# HTML模板
WEEKLY_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>持仓周报</title>
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'SimSun', 'Microsoft YaHei', sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #333;
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #1f77b4;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #1f77b4;
            font-size: 24pt;
            margin: 0;
        }
        .header .subtitle {
            color: #666;
            font-size: 14pt;
            margin-top: 10px;
        }
        .section {
            margin: 25px 0;
        }
        .section h2 {
            color: #1f77b4;
            font-size: 16pt;
            border-left: 5px solid #1f77b4;
            padding-left: 15px;
            margin: 20px 0 15px 0;
        }
        .kpi-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 20px 0;
        }
        .kpi-card {
            flex: 1 1 calc(25% - 15px);
            min-width: 150px;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .kpi-label {
            font-size: 11pt;
            color: #666;
            margin-bottom: 5px;
        }
        .kpi-value {
            font-size: 18pt;
            font-weight: bold;
            color: #1f77b4;
        }
        .kpi-value.negative {
            color: #e74c3c;
        }
        .kpi-value.positive {
            color: #2ecc71;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background: #1f77b4;
            color: white;
        }
        tr:nth-child(even) {
            background: #f8f9fa;
        }
        .alert {
            padding: 12px 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .alert-critical {
            background: #fadbd8;
            border-left: 4px solid #e74c3c;
        }
        .alert-warning {
            background: #fef9e7;
            border-left: 4px solid #f39c12;
        }
        .alert-info {
            background: #ebf5fb;
            border-left: 4px solid #3498db;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 10pt;
            color: #999;
        }
        .chart-placeholder {
            background: #f0f0f0;
            border: 2px dashed #ccc;
            padding: 40px;
            text-align: center;
            color: #999;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>持仓分析报告</h1>
        <div class="subtitle">
            报告周期: {{ start_date }} ~ {{ end_date }}<br>
            生成时间: {{ generated_at }}
        </div>
    </div>

    <!-- 收益概览 -->
    <div class="section">
        <h2>一、收益概览</h2>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">总收益率</div>
                <div class="kpi-value {% if metrics.total_return >= 0 %}positive{% else %}negative{% endif %}">
                    {{ "%.2f" % (metrics.total_return * 100) }}%
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">年化收益率</div>
                <div class="kpi-value {% if metrics.annual_return >= 0 %}positive{% else %}negative{% endif %}">
                    {{ "%.2f" % (metrics.annual_return * 100) }}%
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">夏普比率</div>
                <div class="kpi-value">{{ "%.2f" % metrics.sharpe_ratio }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">最大回撤</div>
                <div class="kpi-value negative">{{ "%.2f" % (metrics.max_drawdown * 100) }}%</div>
            </div>
        </div>

        <table>
            <tr>
                <th>指标</th>
                <th>数值</th>
                <th>指标</th>
                <th>数值</th>
            </tr>
            <tr>
                <td>波动率</td>
                <td>{{ "%.2f" % (metrics.volatility * 100) }}%</td>
                <td>下行波动率</td>
                <td>{{ "%.2f" % (metrics.downside_volatility * 100) }}%</td>
            </tr>
            <tr>
                <td>索提诺比率</td>
                <td>{{ "%.2f" % metrics.sortino_ratio }}</td>
                <td>卡玛比率</td>
                <td>{{ "%.2f" % metrics.calmar_ratio }}</td>
            </tr>
            <tr>
                <td>Alpha</td>
                <td>{{ "%.4f" % metrics.alpha }}</td>
                <td>Beta</td>
                <td>{{ "%.4f" % metrics.beta }}</td>
            </tr>
            <tr>
                <td>信息比率</td>
                <td>{{ "%.2f" % metrics.information_ratio }}</td>
                <td>胜率</td>
                <td>{{ "%.1f" % (metrics.win_rate * 100) }}%</td>
            </tr>
        </table>
    </div>

    <!-- 持仓结构 -->
    <div class="section">
        <h2>二、持仓结构</h2>
        <p><strong>持仓数量:</strong> {{ structure.position_count }} 只</p>
        <p><strong>现金比例:</strong> {{ "%.1f" % (structure.cash_ratio * 100) }}%</p>
        <p><strong>持仓集中度(HHI):</strong> {{ "%.4f" % structure.concentration_hhi }}</p>

        {% if structure.top_holdings %}
        <h3>前十大重仓</h3>
        <table>
            <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>市值</th>
                <th>权重</th>
                <th>盈亏率</th>
            </tr>
            {% for pos in structure.top_holdings %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ pos.code }}</td>
                <td>{{ pos.name }}</td>
                <td>¥{{ "%,.0f" % pos.market_value }}</td>
                <td>{{ "%.1f" % (pos.weight * 100) }}%</td>
                <td class="{% if pos.pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
                    {{ "%.1f" % (pos.pnl_pct * 100) }}%
                </td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
    </div>

    <!-- 风险预警 -->
    <div class="section">
        <h2>三、风险预警</h2>
        <p><strong>风险分数:</strong> {{ risks.risk_score }}/100</p>

        {% if risks.alerts %}
            {% for alert in risks.alerts %}
            <div class="alert alert-{{ alert.level }}">
                <strong>[{{ alert.level | upper }}]</strong> {{ alert.message }}
                {% if alert.value is not none %}
                    (当前值: {{ "%.2f" % (alert.value * 100) }}%, 阈值: {{ "%.2f" % (alert.threshold * 100) }}%)
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="alert alert-info">
                ✅ 未发现明显风险
            </div>
        {% endif %}
    </div>

    <!-- 免责声明 -->
    <div class="section">
        <h2>四、免责声明</h2>
        <p style="font-size: 10pt; color: #666;">
            本报告仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。
            历史业绩不代表未来表现，投资者应根据自身情况独立做出投资决策。
        </p>
    </div>

    <div class="footer">
        <p>持仓分析系统生成 | 基于真实持仓数据</p>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """PDF报告生成器

    生成专业的持仓分析报告PDF。
    """

    def __init__(self, template_dir: Optional[str] = None):
        """初始化生成器

        Args:
            template_dir: 模板目录路径
        """
        self.template_dir = template_dir
        self.analyzer = PortfolioAnalyzer()

    def generate_weekly_report(
        self,
        week_ending: date,
        output_dir: Optional[str] = None
    ) -> str:
        """生成周报PDF

        Args:
            week_ending: 报告截止日期
            output_dir: 输出目录

        Returns:
            生成的PDF文件路径
        """
        week_start = week_ending - timedelta(days=6)

        return self.generate_report(
            start_date=week_start,
            end_date=week_ending,
            report_type="weekly",
            output_dir=output_dir
        )

    def generate_monthly_report(
        self,
        year: int,
        month: int,
        output_dir: Optional[str] = None
    ) -> str:
        """生成月报PDF

        Args:
            year: 年份
            month: 月份
            output_dir: 输出目录

        Returns:
            生成的PDF文件路径
        """
        import calendar

        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        return self.generate_report(
            start_date=start_date,
            end_date=end_date,
            report_type="monthly",
            output_dir=output_dir
        )

    def generate_report(
        self,
        start_date: date,
        end_date: date,
        report_type: str = "custom",
        output_dir: Optional[str] = None
    ) -> str:
        """生成报告

        Args:
            start_date: 开始日期
            end_date: 结束日期
            report_type: 报告类型
            output_dir: 输出目录

        Returns:
            生成的PDF文件路径
        """
        logger.info(f"生成{report_type}报告: {start_date} ~ {end_date}")

        # 获取分析数据
        analysis = self.analyzer.analyze(start_date, end_date)

        # 渲染HTML
        html_content = self._render_template(
            WEEKLY_REPORT_TEMPLATE,
            analysis,
            start_date,
            end_date
        )

        # 转换为PDF
        pdf_path = self._html_to_pdf(
            html_content,
            report_type,
            end_date,
            output_dir
        )

        logger.info(f"报告已生成: {pdf_path}")
        return pdf_path

    def _render_template(
        self,
        template_str: str,
        analysis: PortfolioAnalysisResult,
        start_date: date,
        end_date: date
    ) -> str:
        """渲染HTML模板

        Args:
            template_str: 模板字符串
            analysis: 分析结果
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            渲染后的HTML
        """
        template = Template(template_str)

        context = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': analysis.metrics,
            'structure': analysis.structure,
            'risks': analysis.risks,
            'positions': analysis.positions,
        }

        return template.render(**context)

    def _html_to_pdf(
        self,
        html_content: str,
        report_type: str,
        report_date: date,
        output_dir: Optional[str] = None
    ) -> str:
        """HTML转PDF

        Args:
            html_content: HTML内容
            report_type: 报告类型
            report_date: 报告日期
            output_dir: 输出目录

        Returns:
            PDF文件路径
        """
        try:
            from weasyprint import HTML, CSS

            # 确定输出路径
            if output_dir is None:
                output_dir = os.path.expanduser("~/Documents/portfolio_reports")

            os.makedirs(output_dir, exist_ok=True)

            filename = f"{report_type}_report_{report_date.strftime('%Y%m%d')}.pdf"
            pdf_path = os.path.join(output_dir, filename)

            # 生成PDF
            HTML(string=html_content).write_pdf(pdf_path)

            return pdf_path

        except ImportError:
            logger.error("weasyprint未安装，尝试使用替代方案")
            return self._html_to_pdf_alternative(
                html_content, report_type, report_date, output_dir
            )
        except Exception as e:
            logger.error(f"PDF生成失败: {e}")
            raise

    def _html_to_pdf_alternative(
        self,
        html_content: str,
        report_type: str,
        report_date: date,
        output_dir: Optional[str] = None
    ) -> str:
        """替代PDF生成方案（使用pdfkit）

        Args:
            html_content: HTML内容
            report_type: 报告类型
            report_date: 报告日期
            output_dir: 输出目录

        Returns:
            PDF文件路径
        """
        try:
            import pdfkit

            if output_dir is None:
                output_dir = os.path.expanduser("~/Documents/portfolio_reports")

            os.makedirs(output_dir, exist_ok=True)

            filename = f"{report_type}_report_{report_date.strftime('%Y%m%d')}.pdf"
            pdf_path = os.path.join(output_dir, filename)

            pdfkit.from_string(html_content, pdf_path)

            return pdf_path

        except ImportError:
            # 保存为HTML
            if output_dir is None:
                output_dir = os.path.expanduser("~/Documents/portfolio_reports")

            os.makedirs(output_dir, exist_ok=True)

            filename = f"{report_type}_report_{report_date.strftime('%Y%m%d')}.html"
            html_path = os.path.join(output_dir, filename)

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.warning(f"PDF库未安装，已保存为HTML: {html_path}")
            return html_path

    def generate_html_report(
        self,
        start_date: date,
        end_date: date,
        output_dir: Optional[str] = None
    ) -> str:
        """生成HTML报告（不带PDF转换）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            output_dir: 输出目录

        Returns:
            HTML文件路径
        """
        analysis = self.analyzer.analyze(start_date, end_date)

        html_content = self._render_template(
            WEEKLY_REPORT_TEMPLATE,
            analysis,
            start_date,
            end_date
        )

        if output_dir is None:
            output_dir = os.path.expanduser("~/Documents/portfolio_reports")

        os.makedirs(output_dir, exist_ok=True)

        filename = f"report_{end_date.strftime('%Y%m%d')}.html"
        html_path = os.path.join(output_dir, filename)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return html_path


if __name__ == "__main__":
    # 测试报告生成
    logging.basicConfig(level=logging.INFO)

    generator = ReportGenerator()

    print("\n" + "=" * 60)
    print("报告生成测试")
    print("=" * 60)

    try:
        # 生成周报
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        report_path = generator.generate_report(
            start_date=start_date,
            end_date=end_date,
            report_type="weekly"
        )

        print(f"\n✅ 报告已生成: {report_path}")

    except Exception as e:
        print(f"\n❌ 报告生成失败: {e}")
        import traceback
        traceback.print_exc()
