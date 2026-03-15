"""
Markdown策略提取器 - 从人工总结的论文Markdown中提取策略要素

功能：
- 解析人工撰写的论文总结文档
- 提取信号逻辑、特征变量、模型架构、回测设置
- 生成结构化的策略实现建议

使用场景：
用户先人工阅读论文，总结成Markdown，然后使用本工具提取策略要素
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyBlueprint:
    """策略蓝图 - 从Markdown提取的结构化信息"""
    # 论文元数据
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""

    # 策略核心
    strategy_name: str = ""
    strategy_type: str = ""  # 趋势跟踪、均值回归、统计套利等
    description: str = ""

    # 信号逻辑
    entry_conditions: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    position_sizing: str = ""

    # 特征变量
    features: List[Dict[str, Any]] = field(default_factory=list)

    # 模型架构
    model_type: str = ""  # XGBoost, LSTM, Linear, etc.
    model_params: Dict[str, Any] = field(default_factory=dict)

    # 回测设置
    backtest_period: str = ""
    trading_costs: Dict[str, float] = field(default_factory=dict)
    rebalance_frequency: str = ""

    # 中国市场适配
    china_adaptations: List[str] = field(default_factory=list)

    # 原始Markdown内容
    raw_content: str = ""


class MarkdownStrategyExtractor:
    """Markdown策略提取器"""

    def __init__(self):
        self.blueprint = StrategyBlueprint()

    def extract(self, markdown_path: str) -> StrategyBlueprint:
        """
        从Markdown文件提取策略蓝图

        Args:
            markdown_path: Markdown文件路径

        Returns:
            StrategyBlueprint: 结构化的策略信息
        """
        md_path = Path(markdown_path)
        if not md_path.exists():
            raise FileNotFoundError(f"文件不存在: {markdown_path}")

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.blueprint.raw_content = content

        # 提取各部分内容
        self._extract_metadata(content)
        self._extract_strategy_core(content)
        self._extract_signals(content)
        self._extract_features(content)
        self._extract_model(content)
        self._extract_backtest(content)
        self._extract_china_adaptations(content)

        logger.info(f"从 {markdown_path} 提取策略蓝图: {self.blueprint.strategy_name}")

        return self.blueprint

    def _extract_metadata(self, content: str):
        """提取元数据"""
        # 标题 - 通常是第一个#开头的行
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            self.blueprint.title = title_match.group(1).strip()

        # 作者
        author_match = re.search(r'[-*]\s*作者[:：]\s*(.+)', content)
        if author_match:
            authors = author_match.group(1).split(',')
            self.blueprint.authors = [a.strip() for a in authors]

        # 年份
        year_match = re.search(r'[-*]\s*年份[:：]\s*(\d{4})', content)
        if year_match:
            self.blueprint.year = year_match.group(1)

        # 期刊
        journal_match = re.search(r'[-*]\s*期刊/会议[:：]\s*(.+)', content)
        if journal_match:
            self.blueprint.journal = journal_match.group(1).strip()

    def _extract_strategy_core(self, content: str):
        """提取策略核心信息"""
        # 策略名称 - 支持 "策略名称: XXX" 或 "策略名称\nXXX" 格式
        name_match = re.search(r'(?:^##?\s*)?策略名称[:：]?\s*\n?(.+)', content, re.MULTILINE)
        if name_match:
            self.blueprint.strategy_name = name_match.group(1).strip()

        # 策略类型
        type_match = re.search(r'(?:^##?\s*)?策略类型[:：]?\s*\n?(.+)', content, re.MULTILINE)
        if type_match:
            self.blueprint.strategy_type = type_match.group(1).strip()

        # 描述 - 核心贡献或策略描述部分
        desc_section = self._extract_section(content, ['核心贡献', '策略描述', '策略概述'])
        if desc_section:
            # 取前3行非空行作为描述
            lines = [l.strip() for l in desc_section.split('\n') if l.strip()]
            self.blueprint.description = ' '.join(lines[:3])

    def _extract_signals(self, content: str):
        """提取信号逻辑"""
        # 入场条件
        entry_section = self._extract_section(content, ['入场条件', '买入信号', '做多条件'])
        if entry_section:
            self.blueprint.entry_conditions = self._extract_list_items(entry_section)

        # 出场条件
        exit_section = self._extract_section(content, ['出场条件', '卖出信号', '平仓条件'])
        if exit_section:
            self.blueprint.exit_conditions = self._extract_list_items(exit_section)

        # 仓位管理
        position_match = re.search(
            r'(?:##?\s*)?仓位管理[:：](.+?)(?=\n##|\n\n|$)',
            content,
            re.DOTALL
        )
        if position_match:
            self.blueprint.position_sizing = position_match.group(1).strip()

    def _extract_features(self, content: str):
        """提取特征变量"""
        feature_section = self._extract_section(
            content,
            ['特征变量', '特征列表', '技术指标', '因子列表']
        )

        if not feature_section:
            return

        features = []

        # 尝试解析表格
        table_rows = re.findall(r'\|([^|]+)\|([^|]+)\|([^|]+)\|', feature_section)
        if len(table_rows) > 1:  # 至少表头+一行数据
            for row in table_rows[1:]:  # 跳过表头
                if len(row) >= 2:
                    feature = {
                        'name': row[0].strip(),
                        'description': row[1].strip(),
                        'calculation': row[2].strip() if len(row) > 2 else ''
                    }
                    features.append(feature)

        # 如果没有表格，尝试解析列表
        if not features:
            list_items = self._extract_list_items(feature_section)
            for item in list_items:
                # 尝试提取"名称: 描述"格式
                match = re.match(r'(.+?)[:：]\s*(.+)', item)
                if match:
                    features.append({
                        'name': match.group(1).strip(),
                        'description': match.group(2).strip(),
                        'calculation': ''
                    })
                else:
                    features.append({
                        'name': item,
                        'description': '',
                        'calculation': ''
                    })

        self.blueprint.features = features

    def _extract_model(self, content: str):
        """提取模型架构"""
        model_section = self._extract_section(
            content,
            ['模型架构', '模型结构', '模型配置', '模型参数']
        )

        if not model_section:
            return

        # 模型类型
        model_types = ['XGBoost', 'LSTM', 'RandomForest', 'SVM', 'Linear', '神经网络']
        for mt in model_types:
            if mt.lower() in model_section.lower():
                self.blueprint.model_type = mt
                break

        # 提取关键参数
        param_patterns = [
            (r'n_estimators[:：\s]+(\d+)', 'n_estimators', int),
            (r'max_depth[:：\s]+(\d+)', 'max_depth', int),
            (r'learning_rate[:：\s]+([\d.]+)', 'learning_rate', float),
            (r'LSTM units[:：\s]+(\[?[\d,\s]+\]?)', 'lstm_units', str),
            (r'dropout[:：\s]+([\d.]+)', 'dropout', float),
            (r'batch_size[:：\s]+(\d+)', 'batch_size', int),
            (r'epochs[:：\s]+(\d+)', 'epochs', int),
        ]

        for pattern, key, cast in param_patterns:
            match = re.search(pattern, model_section, re.IGNORECASE)
            if match:
                try:
                    self.blueprint.model_params[key] = cast(match.group(1))
                except (ValueError, TypeError):
                    self.blueprint.model_params[key] = match.group(1)

    def _extract_backtest(self, content: str):
        """提取回测设置"""
        backtest_section = self._extract_section(
            content,
            ['回测设置', '回测设计', '回测配置']
        )

        if not backtest_section:
            return

        # 回测周期
        period_match = re.search(r'(\d{4}[\-\.年]\d{1,2}[\-\.]?\d{0,2}).{0,5}(\d{4}[\-\.年]\d{1,2}[\-\.]?\d{0,2})', backtest_section)
        if period_match:
            self.blueprint.backtest_period = f"{period_match.group(1)} 至 {period_match.group(2)}"

        # 交易成本
        commission_match = re.search(r'佣金[:：\s]+([\d.]+)%?', backtest_section)
        if commission_match:
            val = float(commission_match.group(1))
            self.blueprint.trading_costs['commission'] = val / 100 if val > 0.01 else val

        tax_match = re.search(r'印花税[:：\s]+([\d.]+)%?', backtest_section)
        if tax_match:
            val = float(tax_match.group(1))
            self.blueprint.trading_costs['stamp_tax'] = val / 100 if val > 0.01 else val

        # 再平衡频率
        rebalance_match = re.search(r'再平衡[:：\s]+(.+)', backtest_section)
        if rebalance_match:
            self.blueprint.rebalance_frequency = rebalance_match.group(1).strip()

    def _extract_china_adaptations(self, content: str):
        """提取中国市场适配建议"""
        china_section = self._extract_section(
            content,
            ['中国市场适配', '中国市场改进', '本土化建议', '改进建议']
        )

        if china_section:
            self.blueprint.china_adaptations = self._extract_list_items(china_section)

    def _extract_section(self, content: str, section_names: List[str]) -> str:
        """提取特定章节内容"""
        for name in section_names:
            # 匹配 ## 标题格式
            pattern = rf'##\s*{name}[\s:：]*\n(.*?)(?=\n##|\n\n##|$)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

            # 匹配 ### 标题格式
            pattern = rf'###\s*{name}[\s:：]*\n(.*?)(?=\n###|\n##|$)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_list_items(self, content: str) -> List[str]:
        """提取列表项"""
        # 匹配 - 或 * 或 1. 开头的列表项
        items = re.findall(r'^[\s]*[-*\d.][\s]+(.+)$', content, re.MULTILINE)
        return [item.strip() for item in items if item.strip()]

    def generate_implementation_plan(self, output_path: Optional[str] = None) -> str:
        """
        生成策略实现计划

        Args:
            output_path: 输出文件路径（可选）

        Returns:
            str: 实现计划文档
        """
        if not self.blueprint.strategy_name:
            raise ValueError("请先调用extract()提取策略蓝图")

        plan = f"""# 策略实现计划: {self.blueprint.strategy_name}

## 1. 策略概述

**策略名称**: {self.blueprint.strategy_name}
**策略类型**: {self.blueprint.strategy_type}
**原始论文**: {self.blueprint.title}

**描述**:
{self.blueprint.description}

## 2. 信号逻辑

### 2.1 入场条件
"""

        for i, condition in enumerate(self.blueprint.entry_conditions, 1):
            plan += f"{i}. {condition}\n"

        plan += "\n### 2.2 出场条件\n"
        for i, condition in enumerate(self.blueprint.exit_conditions, 1):
            plan += f"{i}. {condition}\n"

        if self.blueprint.position_sizing:
            plan += f"\n### 2.3 仓位管理\n{self.blueprint.position_sizing}\n"

        plan += "\n## 3. 特征变量\n\n"
        if self.blueprint.features:
            plan += "| 名称 | 描述 | 计算方法 |\n"
            plan += "|:---|:---|:---|\n"
            for f in self.blueprint.features:
                plan += f"| {f['name']} | {f['description']} | {f['calculation']} |\n"
        else:
            plan += "待补充...\n"

        plan += f"\n## 4. 模型架构\n\n"
        plan += f"**模型类型**: {self.blueprint.model_type or '待确定'}\n\n"
        if self.blueprint.model_params:
            plan += "**关键参数**:\n"
            for key, val in self.blueprint.model_params.items():
                plan += f"- {key}: {val}\n"

        plan += f"\n## 5. 回测设置\n\n"
        plan += f"- **回测周期**: {self.blueprint.backtest_period or '待确定'}\n"
        plan += f"- **再平衡频率**: {self.blueprint.rebalance_frequency or '待确定'}\n"
        if self.blueprint.trading_costs:
            plan += "- **交易成本**:\n"
            for cost_name, cost_val in self.blueprint.trading_costs.items():
                plan += f"  - {cost_name}: {cost_val:.4f}\n"

        if self.blueprint.china_adaptations:
            plan += "\n## 6. 中国市场适配\n\n"
            for i, adaptation in enumerate(self.blueprint.china_adaptations, 1):
                plan += f"{i}. {adaptation}\n"

        plan += """\n## 7. 实现步骤

### 7.1 文件创建
```
projects/quant_trading/strategies/
├── {strategy_snake_case}.py          # 主策略文件
└── tests/
    └── test_{strategy_snake_case}.py  # 单元测试
```

### 7.2 待确认事项
- [ ] 确认标的池（股票/ETF列表）
- [ ] 确认数据频率（日线/分钟线）
- [ ] 确认具体参数值
- [ ] 补充缺失的特征计算方法

### 7.3 下一步行动
1. 基于本计划创建策略框架
2. 实现核心信号逻辑
3. 编写回测脚本
4. 参数调优与验证
"""

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(plan)
            logger.info(f"实现计划已保存: {output_path}")

        return plan


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="从Markdown提取策略蓝图")
    parser.add_argument("markdown", help="输入Markdown文件路径")
    parser.add_argument("-o", "--output", help="输出实现计划路径")
    parser.add_argument("--yaml", action="store_true", help="同时输出YAML格式")

    args = parser.parse_args()

    extractor = MarkdownStrategyExtractor()
    blueprint = extractor.extract(args.markdown)

    # 打印摘要
    print("\n" + "="*60)
    print(f"策略蓝图: {blueprint.strategy_name or '未命名'}")
    print("="*60)
    print(f"类型: {blueprint.strategy_type or '未指定'}")
    print(f"模型: {blueprint.model_type or '未指定'}")
    print(f"特征数: {len(blueprint.features)}")
    print(f"入场条件: {len(blueprint.entry_conditions)}条")
    print(f"出场条件: {len(blueprint.exit_conditions)}条")

    # 生成实现计划
    plan = extractor.generate_implementation_plan(args.output)

    if args.output:
        print(f"\n实现计划已保存: {args.output}")
    else:
        print("\n" + plan)

    # 输出YAML
    if args.yaml:
        yaml_path = args.output.replace('.md', '.yaml') if args.output else 'strategy_blueprint.yaml'
        blueprint_dict = {
            'strategy_name': blueprint.strategy_name,
            'strategy_type': blueprint.strategy_type,
            'description': blueprint.description,
            'entry_conditions': blueprint.entry_conditions,
            'exit_conditions': blueprint.exit_conditions,
            'features': blueprint.features,
            'model': {
                'type': blueprint.model_type,
                'params': blueprint.model_params
            },
            'backtest': {
                'period': blueprint.backprint_period,
                'rebalance_frequency': blueprint.rebalance_frequency,
                'trading_costs': blueprint.trading_costs
            },
            'china_adaptations': blueprint.china_adaptations
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(blueprint_dict, f, allow_unicode=True, sort_keys=False)
        print(f"YAML配置已保存: {yaml_path}")


if __name__ == "__main__":
    main()
