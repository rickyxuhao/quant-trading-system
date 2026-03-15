"""
数据质量检查报告生成器
"""
from typing import Dict, List
from datetime import datetime

from core.data_quality.checker import CheckResult


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, result: CheckResult, table_name: str):
        self.result = result
        self.table_name = table_name
    
    def generate_text(self) -> str:
        """生成文本报告"""
        lines = []
        lines.append("="*70)
        lines.append(f"数据质量检查报告 - {self.table_name}")
        lines.append(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*70)
        lines.append("")
        
        # 摘要
        summary = self.result.summary()
        lines.append("【摘要】")
        lines.append(f"  总规则数: {summary['total_rules']}")
        lines.append(f"  通过: {summary['passed']} ✅")
        lines.append(f"  失败: {summary['failed']}")
        lines.append(f"    - 严重错误: {summary['errors']} 🚨")
        lines.append(f"    - 警告: {summary['warnings']} ⚠️")
        lines.append(f"    - 提示: {summary['infos']} ℹ️")
        lines.append(f"  状态: {'✅ 通过' if summary['is_valid'] else '❌ 未通过'}")
        lines.append("")
        
        # 通过的规则
        if self.result.passed:
            lines.append("【通过的规则】")
            for item in self.result.passed:
                lines.append(f"  ✅ {item['rule']}")
            lines.append("")
        
        # 失败的规则
        if self.result.failed:
            lines.append("【失败的规则】")
            
            # 按严重程度分组
            errors = [f for f in self.result.failed if f['severity'] == 'error']
            warnings = [f for f in self.result.failed if f['severity'] == 'warning']
            infos = [f for f in self.result.failed if f['severity'] == 'info']
            
            if errors:
                lines.append("  🚨 严重错误:")
                for item in errors[:20]:  # 最多显示20条
                    lines.append(f"    - {item['rule']}: {item['message']}")
                if len(errors) > 20:
                    lines.append(f"    ... 还有 {len(errors) - 20} 条")
                lines.append("")
            
            if warnings:
                lines.append("  ⚠️ 警告:")
                for item in warnings[:10]:
                    lines.append(f"    - {item['rule']}: {item['message']}")
                if len(warnings) > 10:
                    lines.append(f"    ... 还有 {len(warnings) - 10} 条")
                lines.append("")
        
        lines.append("="*70)
        lines.append("报告结束")
        lines.append("="*70)
        
        return "\n".join(lines)
    
    def generate_json(self) -> Dict:
        """生成 JSON 报告"""
        return {
            "table": self.table_name,
            "timestamp": datetime.now().isoformat(),
            "summary": self.result.summary(),
            "passed": self.result.passed,
            "failed": self.result.failed
        }
    
    def print_report(self):
        """打印报告到控制台"""
        print(self.generate_text())
    
    def save_report(self, filepath: str, format: str = "text"):
        """保存报告到文件"""
        if format == "text":
            content = self.generate_text()
        elif format == "json":
            import json
            content = json.dumps(self.generate_json(), ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"报告已保存到: {filepath}")


def print_check_result(result: CheckResult, table_name: str):
    """便捷函数：打印检查结果"""
    generator = ReportGenerator(result, table_name)
    generator.print_report()
