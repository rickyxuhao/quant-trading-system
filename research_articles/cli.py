"""
学术论文解析命令行工具

Usage:
    python -m research_articles.cli parse <pdf_path> [--output <output_path>]
    python -m research_articles.cli batch <pdf_dir> [--output <output_dir>]
"""

import sys
from datetime import datetime
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import init_logging, get_logger
from research_articles.parser import (
    PDFExtractor,
    SectionIdentifier,
    StrategyExtractor,
    ImprovementGenerator,
)

init_logging()
logger = get_logger(__name__)


def fill_template(elements, sections, improvements, content) -> str:
    """填充分析报告模板"""

    template_path = Path(__file__).parent / "templates" / "analysis_template.md"
    template = template_path.read_text(encoding="utf-8")

    # 准备特征表格
    features_table = ""
    for f in elements.features:
        features_table += f"| {f.name} | {f.var_type.value} | {f.description[:30]}... | {f.calculation_formula[:20]}... | {f.data_source} |\n"

    if not features_table:
        features_table = "| - | - | 未识别到特征 | - | - |\n"

    # 准备信号描述
    def get_signal_desc(signal_type):
        signals = [s for s in elements.signals if s.signal_type.value == signal_type]
        if signals:
            return "\n".join([f"- {s.description[:100]}" for s in signals[:3]])
        return "- 未明确识别"

    # 准备改进建议表格
    improvements_table = ""
    for i, imp in enumerate(improvements, 1):
        problem = imp.problem_description[:40].replace("\n", " ") + "..."
        solution = imp.solution[:40].replace("\n", " ") + "..."
        improvements_table += f"| {i} | {imp.title} | {problem} | {solution} | {imp.expected_effect[:20]}... | {imp.complexity.value} | P{imp.implementation_priority} |\n"

    if not improvements_table:
        improvements_table = "| - | - | - | - | - | - | - |\n"

    # 模型信息
    model = elements.model
    model_info = {
        "type": model.model_type.value if model else "未识别",
        "desc": model.description if model else "",
        "optimizer": model.optimizer if model else "未识别",
        "loss": model.loss_function if model else "未识别",
    }

    # 回测信息
    bt = elements.backtest

    # 填充模板
    filled = template.format(
        title=content.title or "未识别",
        authors=", ".join(content.authors) if content.authors else "未识别",
        venue="待补充",
        year="待补充",
        contribution=elements.strategy_description or "待补充",
        entry_signals=get_signal_desc("entry_long") + "\n" + get_signal_desc("entry_short"),
        exit_signals=get_signal_desc("exit_long") + "\n" + get_signal_desc("exit_short"),
        risk_signals=get_signal_desc("stop_loss") + "\n" + get_signal_desc("take_profit"),
        features_table=features_table,
        model_type=model_info["type"],
        model_description=model_info["desc"],
        layer_structure="待补充",
        hyperparameters=str(model.hyperparameters if model else {}),
        optimizer=model_info["optimizer"],
        loss_function=model_info["loss"],
        train_period="待补充",
        val_period="待补充",
        test_period="待补充",
        training_config="待补充",
        backtest_range=f"{bt.time_range_start}-{bt.time_range_end}" if bt else "未识别",
        rebalance_freq=bt.rebalance_frequency if bt else "未识别",
        transaction_cost=f"{bt.transaction_cost}%" if bt and bt.transaction_cost else "未识别",
        slippage="待补充",
        initial_capital=bt.initial_capital if bt and bt.initial_capital else "未识别",
        explicit_assumptions="\n".join([f"- {a}" for a in elements.limitations[:3]]) or "- 待补充",
        implicit_assumptions="- 待补充",
        methodology_weaknesses="- 待补充",
        t_plus_one_impact="T+1制度会限制日内交易，信号需在收盘前生成、次日执行",
        price_limit_impact="涨跌停限制可能导致信号无法执行，需增加过滤条件",
        data_availability="需评估论文使用的数据在国内的可得性",
        cost_comparison="A股成本更高（卖出印花税0.1%），高频策略影响显著",
        improvements_table=improvements_table,
        stage1_task="基础策略框架搭建",
        stage1_duration="1-2周",
        stage1_output="可运行的回测框架",
        stage1_criteria="通过基础回测验证",
        stage2_task="中国市场适配改进",
        stage2_duration="1-2周",
        stage2_output="适配后的策略版本",
        stage2_criteria="通过成本调整后的回测",
        stage3_task="实盘模拟与优化",
        stage3_duration="2-4周",
        stage3_output="模拟交易报告",
        stage3_criteria="夏普比率>1",
        data_requirements="| 价格数据 | open/high/low/close | 日频 | Tushare | P0 |\n| 成交量 | volume | 日频 | Tushare | P0 |\n",
        immediate_actions="成本精细化、T+1适配、流动性过滤",
        medium_term="模型优化、风险控制增强",
        long_term="多因子扩展、组合配置",
        key_findings="\n".join([f"- {f}" for f in elements.key_findings[:3]]) or "- 待用户补充",
        limitations="\n".join([f"- {l}" for l in elements.limitations[:3]]) or "- 待用户补充",
        generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        parser_version="0.1.0",
    )

    return filled


@click.group()
def cli():
    """学术论文解析工具"""
    pass


@cli.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--format", "-f", type=click.Choice(["markdown", "json"]), default="markdown")
def parse(pdf_path: str, output: str, format: str):
    """解析单个PDF论文"""
    pdf_path = Path(pdf_path)
    logger.info(f"开始解析: {pdf_path}")

    # 提取PDF内容
    extractor = PDFExtractor(pdf_path)
    content = extractor.extract()

    logger.info(f"PDF提取完成: {content.total_pages}页")

    # 识别章节
    identifier = SectionIdentifier(content)
    sections = identifier.identify()
    logger.info(f"识别到 {len(sections)} 个章节")

    # 提取策略要素
    strategy_extractor = StrategyExtractor(content)
    elements = strategy_extractor.extract()
    logger.info(f"提取到 {len(elements.signals)} 个信号, {len(elements.features)} 个特征")

    # 生成改进建议
    improver = ImprovementGenerator(elements)
    suggestions = improver.generate()
    logger.info(f"生成 {len(suggestions)} 条改进建议")

    # 生成输出
    if format == "markdown":
        result = fill_template(elements, sections, suggestions, content)
    else:
        import json
        result = json.dumps({
            "metadata": {
                "title": content.title,
                "authors": content.authors,
                "total_pages": content.total_pages,
            },
            "strategy": strategy_extractor.to_dict(),
            "improvements": improver.to_dict(),
        }, ensure_ascii=False, indent=2)

    # 输出结果
    if output:
        output_path = Path(output)
        output_path.write_text(result, encoding="utf-8")
        logger.info(f"已保存到: {output_path}")
    else:
        print(result)


@cli.command()
@click.argument("pdf_dir", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default="research_articles/examples")
def batch(pdf_dir: str, output: str):
    """批量解析目录下的PDF论文"""
    from .parser.pdf_extractor import PDFBatchExtractor

    pdf_dir = Path(pdf_dir)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    batch_extractor = PDFBatchExtractor(output_dir)
    results = batch_extractor.extract_batch(pdf_dir)

    logger.info(f"批量解析完成: {len(results)} 个文件")


if __name__ == "__main__":
    cli()
