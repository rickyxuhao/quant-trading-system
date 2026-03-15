"""
数据质量检查规则定义
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import re


class Rule(ABC):
    """规则基类"""
    
    def __init__(self, name: str, severity: str = "warning", **kwargs):
        self.name = name
        self.severity = severity  # error, warning, info
        self.kwargs = kwargs
    
    @abstractmethod
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        """执行检查，返回是否通过"""
        pass
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        """获取错误信息"""
        return f"规则 {self.name} 检查失败: 值={value}"


class NotNullRule(Rule):
    """非空检查"""
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        return True
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"字段不能为空，当前值为: {value}"


class UniqueRule(Rule):
    """唯一性检查（需要在表级别进行）"""
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        # 唯一性检查在表级别进行，这里只检查值是否有效
        return True
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"值 {value} 重复"


class FormatRule(Rule):
    """格式检查"""
    
    def __init__(self, name: str, pattern: str, severity: str = "warning", **kwargs):
        super().__init__(name, severity, **kwargs)
        self.pattern = pattern
        self.regex = re.compile(pattern)
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        if value is None or value == "":
            return True  # 空值由 NotNullRule 检查
        return bool(self.regex.match(str(value)))
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"值 '{value}' 不符合格式 '{self.pattern}'"


class EnumRule(Rule):
    """枚举值检查"""
    
    def __init__(self, name: str, values: List[str], severity: str = "warning", **kwargs):
        super().__init__(name, severity, **kwargs)
        self.values = set(values)
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        if value is None or value == "":
            return True  # 空值由 NotNullRule 检查
        return str(value) in self.values
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"值 '{value}' 不在允许列表中: {self.values}"


class CustomSQLRule(Rule):
    """自定义SQL检查"""
    
    def __init__(self, name: str, sql: str, severity: str = "warning", **kwargs):
        super().__init__(name, severity, **kwargs)
        self.sql = sql
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        # SQL 检查在表级别执行，这里仅作为标记
        return True
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"SQL 规则检查失败: {self.name}"


class ReferentialRule(Rule):
    """引用一致性检查"""
    
    def __init__(self, name: str, ref_table: str, ref_column: str, 
                 severity: str = "error", **kwargs):
        super().__init__(name, severity, **kwargs)
        self.ref_table = ref_table
        self.ref_column = ref_column
    
    def check(self, value: Any, row: Optional[Dict] = None) -> bool:
        # 外键检查在表级别执行
        return True
    
    def get_message(self, value: Any, row: Optional[Dict] = None) -> str:
        return f"值 '{value}' 在引用表 {self.ref_table}.{self.ref_column} 中不存在"


# 规则工厂
RULE_MAPPING = {
    "not_null": NotNullRule,
    "unique": UniqueRule,
    "format": FormatRule,
    "enum": EnumRule,
    "custom_sql": CustomSQLRule,
    "referential": ReferentialRule,
}


def create_rule(rule_type: str, name: str, **kwargs) -> Rule:
    """创建规则实例"""
    if rule_type not in RULE_MAPPING:
        raise ValueError(f"未知规则类型: {rule_type}")
    
    rule_class = RULE_MAPPING[rule_type]
    return rule_class(name=name, **kwargs)
