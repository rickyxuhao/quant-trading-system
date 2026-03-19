"""
Qlib Alpha 因子解析与注册模块

将 Qlib 的 Alpha158/Alpha360 因子公式解析并注册到项目的因子系统中。
支持：
1. 解析 Qlib 表达式语法（$close, Ref(), Mean() 等）
2. 转换为 SQL（简单因子）或 Python（复杂因子）
3. 自动注册到 factor_definitions

Alpha158: ~150 个因子（K线特征 + 价量特征 + 滚动指标）
Alpha360: 360 个因子（60 日原始价量数据）

作者: Claude
创建日期: 2026-03-19
"""

import re
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

import pandas as pd
import numpy as np

from core.logger import get_logger
from .factor_definitions import (
    FACTOR_DEFINITIONS,
    FactorDefinition,
    CalculationType,
    _register_factor,
)

logger = get_logger(__name__)


class QlibOpType(Enum):
    """Qlib 操作符类型"""
    FIELD = "field"          # $close, $open, etc.
    REF = "ref"              # Ref($close, n)
    MEAN = "mean"            # Mean($close, n)
    STD = "std"              # Std($close, n)
    SLOPE = "slope"          # Slope($close, n)
    RSQUARE = "rsquare"      # Rsquare($close, n)
    RESI = "resi"            # Resi($close, n)
    MAX = "max"              # Max($high, n)
    MIN = "min"              # Min($low, n)
    QUANTILE = "quantile"    # Quantile($close, n, q)
    RANK = "rank"            # Rank($close, n)
    IDXMAX = "idxmax"        # IdxMax($high, n)
    IDXMIN = "idxmin"        # IdxMin($low, n)
    CORR = "corr"            # Corr($close, $volume, n)
    SUM = "sum"              # Sum($close, n)
    ABS = "abs"              # Abs($close)
    LOG = "log"              # Log($volume)
    GREATER = "greater"      # Greater($open, $close)
    LESS = "less"            # Less($open, $close)
    ADD = "add"              # $close + $open
    SUB = "sub"              # $close - $open
    MUL = "mul"              # $close * $volume
    DIV = "div"              # $close / $open
    CONST = "const"          # 1e-12, 0.8, etc.


# Qlib 字段到项目数据源的映射
QLIB_FIELD_MAPPING = {
    "$close": "close",
    "$open": "open",
    "$high": "high",
    "$low": "low",
    "$volume": "vol",  # tushare 使用 vol 而不是 volume
    "$vwap": None,  # 需要计算
    "$amount": "amount",
}

# Qlib 操作符到 SQL 的映射
QLIB_TO_SQL = {
    "Ref": "LAG",
    "Mean": "AVG",
    "Std": "STDDEV",
    "Max": "MAX",
    "Min": "MIN",
    "Sum": "SUM",
    "Abs": "ABS",
}


@dataclass
class QlibFactorDef:
    """Qlib 因子定义"""
    name: str
    expression: str
    category: str
    description: str = ""
    calculation_type: CalculationType = CalculationType.SQL
    window_days: Optional[int] = None
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class QlibExpressionParser:
    """
    Qlib 表达式解析器

    将 Qlib 表达式解析为可执行的 SQL 或 Python 代码。
    Qlib 语法: https://qlib.readthedocs.io/en/latest/reference/qlib.data.ops.html
    """

    def __init__(self):
        self.sql_converters = {
            "Ref": self._convert_ref,
            "Mean": self._convert_mean,
            "Std": self._convert_std,
            "Max": self._convert_max,
            "Min": self._convert_min,
            "Sum": self._convert_sum,
            "Abs": self._convert_abs,
            "Log": self._convert_log,
            "Greater": self._convert_greater,
            "Less": self._convert_less,
            "Slope": self._convert_slope_sql,  # 复杂，可能需要 Python
            "Rsquare": self._convert_rsquare_sql,  # 复杂，需要 Python
            "Resi": self._convert_resi_sql,  # 复杂，需要 Python
            "Quantile": self._convert_quantile_sql,  # MySQL 8.0+ 支持
            "Rank": self._convert_rank_sql,  # 使用 PERCENT_RANK
            "IdxMax": self._convert_idxmax_sql,  # 复杂
            "IdxMin": self._convert_idxmin_sql,  # 复杂
            "Corr": self._convert_corr_sql,  # 复杂
        }

    def parse(self, expr: str) -> Dict[str, Any]:
        """
        解析 Qlib 表达式

        Args:
            expr: Qlib 表达式，如 "Mean($close, 20)/$close"

        Returns:
            解析树字典
        """
        expr = expr.strip()

        # 简单字段
        if expr.startswith("$") and "(" not in expr:
            field = expr[1:]
            return {
                "type": QlibOpType.FIELD,
                "field": field,
                "sql": QLIB_FIELD_MAPPING.get(expr, field),
            }

        # 常量
        if re.match(r"^[\d.]+(e[+-]?\d+)?$", expr):
            return {
                "type": QlibOpType.CONST,
                "value": float(expr),
                "sql": expr,
            }

        # 二元操作符
        for op, op_type in [
            ("/", QlibOpType.DIV),
            ("*", QlibOpType.MUL),
            ("-", QlibOpType.SUB),
            ("+", QlibOpType.ADD),
        ]:
            if op in expr and not self._is_in_parentheses(expr, op):
                parts = self._split_by_op(expr, op)
                if len(parts) == 2:
                    left, right = parts
                    return {
                        "type": op_type,
                        "left": self.parse(left.strip()),
                        "right": self.parse(right.strip()),
                        "op": op,
                    }

        # 函数调用
        func_match = re.match(r"(\w+)\((.*)\)$", expr)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)
            args = self._parse_args(args_str)

            return {
                "type": QlibOpType.FIELD,  # 默认类型
                "func": func_name,
                "args": [self.parse(arg) for arg in args],
            }

        return {"type": QlibOpType.FIELD, "raw": expr}

    def to_sql(self, expr: str) -> Optional[str]:
        """
        将 Qlib 表达式转换为 SQL

        Args:
            expr: Qlib 表达式

        Returns:
            SQL 表达式，如果无法转换则返回 None
        """
        try:
            tree = self.parse(expr)
            return self._tree_to_sql(tree)
        except Exception as e:
            logger.debug(f"Cannot convert to SQL: {expr}, error: {e}")
            return None

    def to_python(self, expr: str) -> str:
        """
        将 Qlib 表达式转换为 Python 代码

        Args:
            expr: Qlib 表达式

        Returns:
            Python 表达式字符串
        """
        tree = self.parse(expr)
        return self._tree_to_python(tree)

    def _tree_to_sql(self, tree: Dict) -> Optional[str]:
        """将解析树转换为 SQL"""
        if "sql" in tree:
            return tree["sql"]

        op_type = tree.get("type")

        # 二元操作符
        if op_type in (QlibOpType.DIV, QlibOpType.MUL, QlibOpType.SUB, QlibOpType.ADD):
            left = self._tree_to_sql(tree["left"])
            right = self._tree_to_sql(tree["right"])
            if left and right:
                # 处理除零
                if tree["op"] == "/":
                    return f"({left}) / NULLIF({right}, 0)"
                return f"({left}) {tree['op']} ({right})"
            return None

        # 函数调用
        if "func" in tree:
            func_name = tree["func"]
            if func_name in self.sql_converters:
                return self.sql_converters[func_name](tree["args"])
            return None

        return None

    def _tree_to_python(self, tree: Dict) -> str:
        """将解析树转换为 Python"""
        if "raw" in tree:
            return tree["raw"]

        op_type = tree.get("type")

        # 字段
        if op_type == QlibOpType.FIELD:
            field = tree.get("field", tree.get("raw", ""))
            return f"df['{field}']"

        # 常量
        if op_type == QlibOpType.CONST:
            return str(tree["value"])

        # 二元操作符
        if op_type in (QlibOpType.DIV, QlibOpType.MUL, QlibOpType.SUB, QlibOpType.ADD):
            left = self._tree_to_python(tree["left"])
            right = self._tree_to_python(tree["right"])
            op = tree["op"]
            if op == "/":
                return f"({left}) / ({right} + 1e-12)"
            return f"({left}) {op} ({right})"

        # 函数调用
        if "func" in tree:
            func_name = tree["func"]
            args = [self._tree_to_python(arg) for arg in tree["args"]]
            return self._convert_to_python_func(func_name, args)

        return ""

    def _convert_to_python_func(self, func_name: str, args: List[str]) -> str:
        """转换为 Python 函数调用"""
        converters = {
            "Ref": lambda a: f"{a[0]}.shift({a[1]})",
            "Mean": lambda a: f"{a[0]}.rolling(window={a[1]}).mean()",
            "Std": lambda a: f"{a[0]}.rolling(window={a[1]}).std()",
            "Max": lambda a: f"{a[0]}.rolling(window={a[1]}).max()",
            "Min": lambda a: f"{a[0]}.rolling(window={a[1]}).min()",
            "Sum": lambda a: f"{a[0]}.rolling(window={a[1]}).sum()",
            "Abs": lambda a: f"np.abs({a[0]})",
            "Log": lambda a: f"np.log({a[0]} + 1)",
            "Greater": lambda a: f"np.maximum({a[0]}, {a[1]})",
            "Less": lambda a: f"np.minimum({a[0]}, {a[1]})",
            "Slope": lambda a: f"_calc_slope({a[0]}, {a[1]})",
            "Rsquare": lambda a: f"_calc_rsquare({a[0]}, {a[1]})",
            "Resi": lambda a: f"_calc_resi({a[0]}, {a[1]})",
            "Quantile": lambda a: f"{a[0]}.rolling(window={a[1]}).quantile({a[2]})",
            "Rank": lambda a: f"{a[0]}.rolling(window={a[1]}).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])",
            "IdxMax": lambda a: f"{a[0]}.rolling(window={a[1]}).apply(lambda x: len(x) - 1 - np.argmax(x[::-1]))",
            "IdxMin": lambda a: f"{a[0]}.rolling(window={a[1]}).apply(lambda x: len(x) - 1 - np.argmin(x[::-1]))",
            "Corr": lambda a: f"{a[0]}.rolling(window={a[2]}).corr({a[1]})",
        }

        if func_name in converters:
            return converters[func_name](args)
        return f"{func_name}({', '.join(args)})"

    # SQL 转换器方法
    def _convert_ref(self, args: List[Dict]) -> str:
        """Ref($close, n) -> LAG(close, n)"""
        field = self._tree_to_sql(args[0])
        n = args[1].get("value", 0)
        return f"LAG({field}, {int(n)}) OVER w"

    def _convert_mean(self, args: List[Dict]) -> str:
        """Mean($close, n) -> AVG(close) OVER (ROWS n-1 PRECEDING)"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"AVG({field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_std(self, args: List[Dict]) -> str:
        """Std($close, n) -> STDDEV(close) OVER (...)"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"STDDEV({field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_max(self, args: List[Dict]) -> str:
        """Max($high, n) -> MAX(high) OVER (...)"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"MAX({field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_min(self, args: List[Dict]) -> str:
        """Min($low, n) -> MIN(low) OVER (...)"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"MIN({field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_sum(self, args: List[Dict]) -> str:
        """Sum($close, n) -> SUM(close) OVER (...)"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"SUM({field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_abs(self, args: List[Dict]) -> str:
        """Abs($close) -> ABS(close)"""
        field = self._tree_to_sql(args[0])
        return f"ABS({field})"

    def _convert_log(self, args: List[Dict]) -> str:
        """Log($volume) -> LN(volume)"""
        field = self._tree_to_sql(args[0])
        return f"LN({field})"

    def _convert_greater(self, args: List[Dict]) -> str:
        """Greater($open, $close) -> GREATEST(open, close)"""
        left = self._tree_to_sql(args[0])
        right = self._tree_to_sql(args[1])
        return f"GREATEST({left}, {right})"

    def _convert_less(self, args: List[Dict]) -> str:
        """Less($open, $close) -> LEAST(open, close)"""
        left = self._tree_to_sql(args[0])
        right = self._tree_to_sql(args[1])
        return f"LEAST({left}, {right})"

    def _convert_slope_sql(self, args: List[Dict]) -> Optional[str]:
        """Slope - 线性回归斜率，SQL 实现较复杂"""
        return None  # 使用 Python 实现

    def _convert_rsquare_sql(self, args: List[Dict]) -> Optional[str]:
        """Rsquare - R平方，SQL 实现较复杂"""
        return None  # 使用 Python 实现

    def _convert_resi_sql(self, args: List[Dict]) -> Optional[str]:
        """Resi - 残差，SQL 实现较复杂"""
        return None  # 使用 Python 实现

    def _convert_quantile_sql(self, args: List[Dict]) -> str:
        """Quantile($close, n, q) - MySQL 8.0+ 支持"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        q = float(args[2].get("value", 0.5))
        return f"PERCENTILE_CONT({q}) WITHIN GROUP (ORDER BY {field}) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {n-1} PRECEDING)"

    def _convert_rank_sql(self, args: List[Dict]) -> str:
        """Rank($close, n) - 百分位排名"""
        field = self._tree_to_sql(args[0])
        n = int(args[1].get("value", 20))
        return f"PERCENT_RANK() OVER (PARTITION BY ts_code ORDER BY {field})"

    def _convert_idxmax_sql(self, args: List[Dict]) -> Optional[str]:
        """IdxMax - 距离最高点的天数，SQL 复杂"""
        return None  # 使用 Python 实现

    def _convert_idxmin_sql(self, args: List[Dict]) -> Optional[str]:
        """IdxMin - 距离最低点的天数，SQL 复杂"""
        return None  # 使用 Python 实现

    def _convert_corr_sql(self, args: List[Dict]) -> Optional[str]:
        """Corr - 相关系数，SQL 较复杂"""
        return None  # 使用 Python 实现

    # 辅助方法
    def _is_in_parentheses(self, expr: str, pos: str) -> bool:
        """检查操作符是否在括号内"""
        idx = expr.find(pos)
        if idx == -1:
            return False
        before = expr[:idx]
        paren_count = before.count("(") - before.count(")")
        return paren_count > 0

    def _split_by_op(self, expr: str, op: str) -> List[str]:
        """按操作符分割表达式"""
        # 找到最外层操作符
        paren_count = 0
        for i, c in enumerate(expr):
            if c == "(":
                paren_count += 1
            elif c == ")":
                paren_count -= 1
            elif c == op and paren_count == 0:
                return [expr[:i], expr[i+1:]]
        return [expr]

    def _parse_args(self, args_str: str) -> List[str]:
        """解析函数参数"""
        args = []
        current = ""
        paren_count = 0
        for c in args_str:
            if c == "(":
                paren_count += 1
                current += c
            elif c == ")":
                paren_count -= 1
                current += c
            elif c == "," and paren_count == 0:
                args.append(current.strip())
                current = ""
            else:
                current += c
        if current.strip():
            args.append(current.strip())
        return args


class QlibFactorRegistry:
    """
    Qlib 因子注册表

    将 Qlib Alpha158/Alpha360 因子注册到项目因子系统
    """

    def __init__(self):
        self.parser = QlibExpressionParser()
        self._alpha158_defs: List[QlibFactorDef] = []
        self._alpha360_defs: List[QlibFactorDef] = []

    def parse_alpha158(self, windows: List[int] = None) -> List[QlibFactorDef]:
        """
        解析 Alpha158 因子定义

        Args:
            windows: 滚动窗口大小，默认 [5, 10, 20, 30, 60]

        Returns:
            Alpha158 因子定义列表
        """
        if windows is None:
            windows = [5, 10, 20, 30, 60]

        defs = []

        # K线特征
        kbar_fields = [
            "($close-$open)/$open",
            "($high-$low)/$open",
            "($close-$open)/($high-$low+1e-12)",
            "($high-Greater($open, $close))/$open",
            "($high-Greater($open, $close))/($high-$low+1e-12)",
            "(Less($open, $close)-$low)/$open",
            "(Less($open, $close)-$low)/($high-$low+1e-12)",
            "(2*$close-$high-$low)/$open",
            "(2*$close-$high-$low)/($high-$low+1e-12)",
        ]
        kbar_names = ["KMID", "KLEN", "KMID2", "KUP", "KUP2", "KLOW", "KLOW2", "KSFT", "KSFT2"]

        for expr, name in zip(kbar_fields, kbar_names):
            defs.append(QlibFactorDef(
                name=name,
                expression=expr,
                category="qlib_kbar",
                description=f"K线特征: {name}",
                window_days=1,
            ))

        # 滚动窗口指标
        rolling_configs = [
            ("ROC", "Ref($close, {d})/$close", "d日收益率"),
            ("MA", "Mean($close, {d})/$close", "d日移动平均线"),
            ("STD", "Std($close, {d})/$close", "d日标准差"),
            ("BETA", "Slope($close, {d})/$close", "d日价格趋势斜率"),
            ("RSQR", "Rsquare($close, {d})", "d日线性回归R平方"),
            ("RESI", "Resi($close, {d})/$close", "d日线性回归残差"),
            ("MAX", "Max($high, {d})/$close", "d日最高价"),
            ("MIN", "Min($low, {d})/$close", "d日最低价"),
            ("QTLU", "Quantile($close, {d}, 0.8)/$close", "d日80%分位数"),
            ("QTLD", "Quantile($close, {d}, 0.2)/$close", "d日20%分位数"),
            ("RANK", "Rank($close, {d})", "d日价格排名分位"),
            ("RSV", "($close-Min($low, {d}))/(Max($high, {d})-Min($low, {d})+1e-12)", "d日RSV"),
            ("IMAX", "IdxMax($high, {d})/{d}", "距d日最高点天数比例"),
            ("IMIN", "IdxMin($low, {d})/{d}", "距d日最低点天数比例"),
            ("IMXD", "(IdxMax($high, {d})-IdxMin($low, {d}))/{d}", "高低点天数差比例"),
            ("CORR", "Corr($close, Log($volume+1), {d})", "价格与成交量对数相关性"),
            ("CORD", "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), {d})", "价量变比相关性"),
            ("CNTP", "Mean($close>Ref($close, 1), {d})", "d日上涨比例"),
            ("CNTN", "Mean($close<Ref($close, 1), {d})", "d日下跌比例"),
            ("CNTD", "Mean($close>Ref($close, 1), {d})-Mean($close<Ref($close, 1), {d})", "d日涨跌比例差"),
            ("SUMP", "Sum(Greater($close-Ref($close, 1), 0), {d})/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)", "d日上涨动量占比"),
            ("SUMN", "Sum(Greater(Ref($close, 1)-$close, 0), {d})/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)", "d日下跌动量占比"),
            ("SUMD", "(Sum(Greater($close-Ref($close, 1), 0), {d})-Sum(Greater(Ref($close, 1)-$close, 0), {d}))/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)", "d日涨跌动量差"),
            ("VMA", "Mean($volume, {d})/($volume+1e-12)", "d日成交量移动平均"),
            ("VSTD", "Std($volume, {d})/($volume+1e-12)", "d日成交量标准差"),
            ("WVMA", "Std(Abs($close/Ref($close, 1)-1)*$volume, {d})/(Mean(Abs($close/Ref($close, 1)-1)*$volume, {d})+1e-12)", "成交量加权价格波动率"),
            ("VSUMP", "Sum(Greater($volume-Ref($volume, 1), 0), {d})/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)", "d日成交量增加占比"),
            ("VSUMN", "Sum(Greater(Ref($volume, 1)-$volume, 0), {d})/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)", "d日成交量减少占比"),
            ("VSUMD", "(Sum(Greater($volume-Ref($volume, 1), 0), {d})-Sum(Greater(Ref($volume, 1)-$volume, 0), {d}))/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)", "d日成交量增减差"),
        ]

        for prefix, template, desc in rolling_configs:
            for d in windows:
                expr = template.format(d=d)
                name = f"{prefix}{d}"
                defs.append(QlibFactorDef(
                    name=name,
                    expression=expr,
                    category="qlib_rolling",
                    description=f"{desc.format(d=d)}",
                    window_days=d,
                ))

        self._alpha158_defs = defs
        return defs

    def parse_alpha360(self) -> List[QlibFactorDef]:
        """
        解析 Alpha360 因子定义

        Alpha360 提供 60 天的原始价量数据（标准化）

        Returns:
            Alpha360 因子定义列表
        """
        defs = []

        fields = ["close", "open", "high", "low", "vwap", "volume"]

        for field in fields:
            for i in range(59, -1, -1):
                if i == 0:
                    # 当前值
                    if field == "volume":
                        expr = "$volume/($volume+1e-12)"
                    else:
                        expr = f"${field}/$close"
                    name = f"{field.upper()}0"
                else:
                    # 历史值
                    if field == "volume":
                        expr = f"Ref($volume, {i})/($volume+1e-12)"
                    else:
                        expr = f"Ref(${field}, {i})/$close"
                    name = f"{field.upper()}{i}"

                defs.append(QlibFactorDef(
                    name=name,
                    expression=expr,
                    category="qlib_alpha360",
                    description=f"{field} at t-{i} normalized by current close/volume",
                    window_days=i,
                ))

        self._alpha360_defs = defs
        return defs

    def register_factors(self, alpha158: bool = True, alpha360: bool = True):
        """
        注册所有 Qlib 因子到 factor_definitions

        Args:
            alpha158: 是否注册 Alpha158 因子
            alpha360: 是否注册 Alpha360 因子
        """
        if alpha158:
            logger.info("Registering Alpha158 factors...")
            defs = self._alpha158_defs or self.parse_alpha158()
            for def_ in defs:
                self._register_single_factor(def_)
            logger.info(f"Registered {len(defs)} Alpha158 factors")

        if alpha360:
            logger.info("Registering Alpha360 factors...")
            defs = self._alpha360_defs or self.parse_alpha360()
            for def_ in defs:
                self._register_single_factor(def_)
            logger.info(f"Registered {len(defs)} Alpha360 factors")

    def _register_single_factor(self, def_: QlibFactorDef):
        """注册单个因子"""
        # 尝试转换为 SQL
        sql_expr = self.parser.to_sql(def_.expression)

        if sql_expr:
            # SQL 可计算
            calc_type = CalculationType.SQL
            dependencies = []
        else:
            # 需要 Python 计算
            calc_type = CalculationType.PYTHON
            sql_expr = None
            dependencies = self._extract_dependencies(def_.expression)

        # 创建 FactorDefinition
        factor_def = FactorDefinition(
            name=def_.name,
            description=def_.description,
            category=def_.category,
            calculation=calc_type,
            data_source="t_stock_dailymarketdata",
            source_field="close,open,high,low,vol",  # 依赖的字段
            sql_expr=sql_expr,
            window_days=def_.window_days,
            dependencies=dependencies,
            winsorize=True,
        )

        # 注册到全局定义
        _register_factor(factor_def)

    def _extract_dependencies(self, expr: str) -> List[str]:
        """从表达式中提取依赖的因子"""
        deps = []
        # 简单提取 Ref, Mean 等中的字段
        for match in re.finditer(r'\$(\w+)', expr):
            field = match.group(1)
            if field not in deps:
                deps.append(field)
        return deps


# 便捷函数
def register_qlib_factors(alpha158: bool = True, alpha360: bool = True):
    """
    注册所有 Qlib 因子

    Example:
        >>> from projects.quant_trading.strategies.ml_prediction.qlib_factors import register_qlib_factors
        >>> register_qlib_factors(alpha158=True, alpha360=False)  # 只注册 Alpha158
    """
    registry = QlibFactorRegistry()
    registry.parse_alpha158()
    registry.parse_alpha360()
    registry.register_factors(alpha158=alpha158, alpha360=alpha360)


def get_alpha158_factors() -> List[str]:
    """获取所有 Alpha158 因子名称"""
    registry = QlibFactorRegistry()
    defs = registry.parse_alpha158()
    return [d.name for d in defs]


def get_alpha360_factors() -> List[str]:
    """获取所有 Alpha360 因子名称"""
    registry = QlibFactorRegistry()
    defs = registry.parse_alpha360()
    return [d.name for d in defs]


def get_all_qlib_factors() -> List[str]:
    """获取所有 Qlib 因子名称"""
    return get_alpha158_factors() + get_alpha360_factors()


# Python 计算辅助函数（用于复杂因子）
def _calc_slope(series: pd.Series, window: int) -> pd.Series:
    """计算线性回归斜率"""
    def _slope(x):
        if len(x) < 2:
            return 0
        y = np.array(x)
        x_vals = np.arange(len(y))
        return np.polyfit(x_vals, y, 1)[0]

    return series.rolling(window=window).apply(_slope, raw=True)


def _calc_rsquare(series: pd.Series, window: int) -> pd.Series:
    """计算线性回归 R 平方"""
    def _rsq(x):
        if len(x) < 2:
            return 0
        y = np.array(x)
        x_vals = np.arange(len(y))
        slope, intercept = np.polyfit(x_vals, y, 1)
        y_pred = slope * x_vals + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        if ss_tot == 0:
            return 0
        return 1 - ss_res / ss_tot

    return series.rolling(window=window).apply(_rsq, raw=True)


def _calc_resi(series: pd.Series, window: int) -> pd.Series:
    """计算线性回归残差（最新值）"""
    def _resi(x):
        if len(x) < 2:
            return 0
        y = np.array(x)
        x_vals = np.arange(len(y))
        slope, intercept = np.polyfit(x_vals, y, 1)
        y_pred = slope * (len(y) - 1) + intercept
        return y[-1] - y_pred

    return series.rolling(window=window).apply(_resi, raw=True)


if __name__ == "__main__":
    # 测试
    print("Alpha158 factors:")
    alpha158 = get_alpha158_factors()
    print(f"Total: {len(alpha158)}")
    print(f"First 10: {alpha158[:10]}")

    print("\nAlpha360 factors:")
    alpha360 = get_alpha360_factors()
    print(f"Total: {len(alpha360)}")
    print(f"First 10: {alpha360[:10]}")

    # 测试表达式解析
    parser = QlibExpressionParser()

    test_exprs = [
        "$close",
        "Ref($close, 5)",
        "Mean($close, 20)/$close",
        "($close-$open)/$open",
        "Slope($close, 20)/$close",
    ]

    print("\nExpression parsing tests:")
    for expr in test_exprs:
        sql = parser.to_sql(expr)
        python = parser.to_python(expr)
        print(f"\n{expr}")
        print(f"  SQL: {sql}")
        print(f"  Python: {python}")
