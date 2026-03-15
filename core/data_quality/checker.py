"""
数据质量检查引擎
"""
from typing import Dict, List, Any, Optional
import yaml

from core.storage.relational.connection import DatabaseManager
from core.data_quality.rules import create_rule, Rule


class CheckResult:
    """检查结果"""
    
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def add_passed(self, rule_name: str, details: Dict):
        self.passed.append({"rule": rule_name, **details})
    
    def add_failed(self, rule_name: str, severity: str, message: str, details: Dict):
        self.failed.append({
            "rule": rule_name,
            "severity": severity,
            "message": message,
            **details
        })
    
    @property
    def is_valid(self) -> bool:
        """是否全部通过（无 error 级别失败）"""
        for failure in self.failed:
            if failure["severity"] == "error":
                return False
        return True
    
    def summary(self) -> Dict:
        """结果摘要"""
        error_count = sum(1 for f in self.failed if f["severity"] == "error")
        warning_count = sum(1 for f in self.failed if f["severity"] == "warning")
        info_count = sum(1 for f in self.failed if f["severity"] == "info")
        
        return {
            "total_rules": len(self.passed) + len(self.failed),
            "passed": len(self.passed),
            "failed": len(self.failed),
            "errors": error_count,
            "warnings": warning_count,
            "infos": info_count,
            "is_valid": self.is_valid
        }


class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.db_name = self.config.get("database")
        self.table_name = self.config.get("table")
        self.rules_config = self.config.get("rules", [])
        self.rules = []
        self._build_rules()
    
    def _load_config(self, path: str) -> Dict:
        """加载配置文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _build_rules(self):
        """构建规则列表"""
        for rule_config in self.rules_config:
            rule_type = rule_config.get("type")
            rule_name = rule_config.get("name")
            severity = rule_config.get("severity", "warning")
            
            # 提取其他参数
            kwargs = {k: v for k, v in rule_config.items() 
                     if k not in ["type", "name", "severity"]}
            
            rule = create_rule(rule_type, rule_name, severity=severity, **kwargs)
            self.rules.append({
                "rule": rule,
                "config": rule_config
            })
    
    def check(self) -> CheckResult:
        """执行所有检查"""
        result = CheckResult()
        
        print(f"开始检查表 {self.db_name}.{self.table_name}")
        print(f"规则数量: {len(self.rules)}")
        print("="*60)
        
        # 获取表数据
        df = self._fetch_data()
        total_rows = len(df)
        print(f"数据行数: {total_rows}")
        print()
        
        for rule_item in self.rules:
            rule = rule_item["rule"]
            config = rule_item["config"]
            rule_type = config.get("type")
            
            print(f"执行规则: {rule.name} [{rule_type}]")
            
            if rule_type == "custom_sql":
                # SQL 规则单独处理
                violations = self._check_sql_rule(config.get("sql"))
                if violations:
                    for violation in violations:
                        result.add_failed(
                            rule.name,
                            rule.severity,
                            rule.get_message(None, violation),
                            violation
                        )
                else:
                    result.add_passed(rule.name, {"type": "sql"})
            elif rule_type == "unique":
                # 唯一性检查
                column = config.get("column")
                duplicates = self._check_unique(df, column)
                if duplicates:
                    for dup in duplicates:
                        result.add_failed(
                            rule.name,
                            rule.severity,
                            f"值 '{dup['value']}' 重复 {dup['count']} 次",
                            dup
                        )
                else:
                    result.add_passed(rule.name, {"column": column})
            else:
                # 列级规则检查
                column = config.get("column")
                violations = self._check_column_rule(df, column, rule)
                if violations:
                    for v in violations:
                        result.add_failed(
                            rule.name,
                            rule.severity,
                            rule.get_message(v.get("value"), v.get("row")),
                            v
                        )
                else:
                    result.add_passed(rule.name, {"column": column})
        
        return result
    
    def _fetch_data(self) -> List[Dict]:
        """获取表数据"""
        sql = f"SELECT * FROM {self.table_name}"
        return DatabaseManager.fetchall(self.db_name, sql)
    
    def _check_column_rule(self, df: List[Dict], column: str, rule: Rule) -> List[Dict]:
        """检查列级规则"""
        violations = []
        for idx, row in enumerate(df):
            value = row.get(column)
            if not rule.check(value, row):
                violations.append({
                    "row_index": idx + 1,
                    "column": column,
                    "value": value,
                    "row": row
                })
        return violations
    
    def _check_unique(self, df: List[Dict], column: str) -> List[Dict]:
        """检查唯一性"""
        value_counts = {}
        for row in df:
            value = row.get(column)
            if value:
                value_counts[value] = value_counts.get(value, 0) + 1
        
        duplicates = []
        for value, count in value_counts.items():
            if count > 1:
                duplicates.append({
                    "column": column,
                    "value": value,
                    "count": count
                })
        return duplicates
    
    def _check_sql_rule(self, sql: str) -> List[Dict]:
        """执行 SQL 规则检查"""
        # SQL 应返回违反规则的数据行
        results = DatabaseManager.fetchall(self.db_name, sql)
        return results


def check_table(config_path: str) -> CheckResult:
    """便捷函数：检查指定配置的表"""
    checker = DataQualityChecker(config_path)
    return checker.check()
