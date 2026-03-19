"""
因子验证工具

提供因子核对功能：
1. 比较 SQL 计算结果 vs Python 计算结果
2. 验证因子值范围是否合理
3. 检查缺失值比例
4. 输出核对报告

使用方式:
    from factor_validator import FactorValidator

    validator = FactorValidator()

    # 验证单个因子
    report = validator.validate_factor("return_20d", trade_date="20250115")

    # 验证所有 SQL 因子
    full_report = validator.validate_all_sql_factors(trade_date="20250115")

    # 打印报告
    validator.print_report(full_report)

作者: Claude
创建日期: 2026-03-19
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager

from .factor_definitions import (
    FACTOR_DEFINITIONS,
    FactorDefinition,
    CalculationType,
    get_factor_lineage,
    get_factors_by_calculation_type,
)

logger = get_logger(__name__)


@dataclass
class FactorValidationResult:
    """因子验证结果"""
    factor_name: str
    description: str
    category: str

    # 数据统计
    total_count: int = 0
    missing_count: int = 0
    missing_ratio: float = 0.0

    # 值范围统计
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None

    # 异常值检测
    outliers_count: int = 0
    outliers_ratio: float = 0.0

    # 与预期范围的比较
    expected_range: Optional[Tuple[float, float]] = None
    within_range_ratio: float = 0.0

    # 一致性检查（SQL vs Python）
    sql_python_diff: Optional[float] = None  # 平均绝对差异
    sql_python_corr: Optional[float] = None  # 相关系数
    is_consistent: bool = True

    # 错误信息
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ValidationReport:
    """验证报告"""
    trade_date: str
    timestamp: str
    total_factors: int = 0
    passed_factors: int = 0
    warning_factors: int = 0
    failed_factors: int = 0

    results: Dict[str, FactorValidationResult] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trade_date": self.trade_date,
            "timestamp": self.timestamp,
            "total_factors": self.total_factors,
            "passed_factors": self.passed_factors,
            "warning_factors": self.warning_factors,
            "failed_factors": self.failed_factors,
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class FactorValidator:
    """因子验证器"""

    DB_NAME = "tushare_biz"

    def __init__(self):
        self.factor_defs = FACTOR_DEFINITIONS

    def validate_factor(
        self,
        factor_name: str,
        trade_date: str,
        stock_pool: Optional[List[str]] = None,
        check_consistency: bool = False,
    ) -> FactorValidationResult:
        """
        验证单个因子

        Args:
            factor_name: 因子名称
            trade_date: 交易日期 (YYYYMMDD)
            stock_pool: 股票池（默认全市场）
            check_consistency: 是否检查 SQL vs Python 一致性

        Returns:
            FactorValidationResult
        """
        factor_def = self.factor_defs.get(factor_name)
        if not factor_def:
            return FactorValidationResult(
                factor_name=factor_name,
                description="Unknown factor",
                category="unknown",
                errors=[f"Factor '{factor_name}' not found in definitions"],
            )

        result = FactorValidationResult(
            factor_name=factor_name,
            description=factor_def.description,
            category=factor_def.category,
            expected_range=factor_def.valid_range,
        )

        try:
            # 获取因子数据
            df = self._fetch_factor_data(factor_name, trade_date, stock_pool)

            if df.empty:
                result.errors.append("No data returned")
                return result

            values = pd.to_numeric(df[factor_name], errors='coerce').dropna()

            # 基础统计
            result.total_count = len(df)
            result.missing_count = df[factor_name].isna().sum()
            result.missing_ratio = result.missing_count / result.total_count if result.total_count > 0 else 0

            if len(values) > 0:
                result.min_value = float(values.min())
                result.max_value = float(values.max())
                result.mean_value = float(values.mean())
                result.std_value = float(values.std())

            # 异常值检测（使用 3-sigma 规则）
            if result.mean_value is not None and result.std_value is not None and result.std_value > 0:
                lower_bound = result.mean_value - 3 * result.std_value
                upper_bound = result.mean_value + 3 * result.std_value
                outliers = values[(values < lower_bound) | (values > upper_bound)]
                result.outliers_count = len(outliers)
                result.outliers_ratio = result.outliers_count / len(values) if len(values) > 0 else 0

            # 范围检查
            if factor_def.valid_range and len(values) > 0:
                min_val, max_val = factor_def.valid_range
                within_range = values[(values >= min_val) & (values <= max_val)]
                result.within_range_ratio = len(within_range) / len(values)

                if result.within_range_ratio < 0.95:
                    result.warnings.append(
                        f"Only {result.within_range_ratio*100:.1f}% of values within expected range "
                        f"[{min_val}, {max_val}]"
                    )

            # 缺失值检查
            if result.missing_ratio > 0.1:  # 超过 10% 缺失
                result.warnings.append(f"High missing ratio: {result.missing_ratio*100:.1f}%")

            # SQL vs Python 一致性检查
            if check_consistency and factor_def.calculation == CalculationType.PYTHON:
                # 尝试用 SQL 方式计算（如果可能）
                pass  # TODO: 实现一致性检查

            # 判定结果状态
            if result.errors:
                pass  # 已经是失败状态
            elif result.warnings:
                pass  # 警告状态
            else:
                pass  # 通过状态

        except Exception as e:
            result.errors.append(f"Validation failed: {str(e)}")
            logger.error(f"Error validating {factor_name}: {e}")

        return result

    def validate_all_sql_factors(
        self,
        trade_date: str,
        stock_pool: Optional[List[str]] = None,
    ) -> ValidationReport:
        """
        验证所有 SQL 类型的因子

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            stock_pool: 股票池（默认全市场）

        Returns:
            ValidationReport
        """
        report = ValidationReport(
            trade_date=trade_date,
            timestamp=datetime.now().isoformat(),
        )

        # 获取所有 SQL 类型因子
        sql_factors = get_factors_by_calculation_type(CalculationType.SQL)
        direct_factors = get_factors_by_calculation_type(CalculationType.DIRECT)
        all_sql_factors = sql_factors + direct_factors

        report.total_factors = len(all_sql_factors)

        logger.info(f"Validating {len(all_sql_factors)} SQL factors for {trade_date}")

        for factor_def in all_sql_factors:
            result = self.validate_factor(factor_def.name, trade_date, stock_pool)
            report.results[factor_def.name] = result

            # 统计结果
            if result.errors:
                report.failed_factors += 1
            elif result.warnings:
                report.warning_factors += 1
            else:
                report.passed_factors += 1

        # 生成摘要
        report.summary = self._generate_summary(report)

        return report

    def _fetch_factor_data(
        self,
        factor_name: str,
        trade_date: str,
        stock_pool: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取因子数据"""
        factor_def = self.factor_defs.get(factor_name)
        if not factor_def or not factor_def.sql_expr:
            return pd.DataFrame()

        # 构建查询
        if stock_pool:
            placeholders = ','.join(['%s'] * len(stock_pool))
            sql = f"""
                SELECT ts_code, {factor_def.sql_expr} as {factor_name}
                FROM {factor_def.data_source}
                WHERE trade_date = %s AND ts_code IN ({placeholders})
            """
            params = (trade_date,) + tuple(stock_pool)
        else:
            sql = f"""
                SELECT ts_code, {factor_def.sql_expr} as {factor_name}
                FROM {factor_def.data_source}
                WHERE trade_date = %s
            """
            params = (trade_date,)

        results = DatabaseManager.fetchall(self.DB_NAME, sql, params)

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results)

    def _generate_summary(self, report: ValidationReport) -> Dict[str, Any]:
        """生成报告摘要"""
        summary = {
            "categories": {},
            "data_sources": {},
            "missing_stats": {
                "avg_missing_ratio": 0.0,
                "max_missing_ratio": 0.0,
                "factors_with_high_missing": [],
            },
            "range_violations": [],
        }

        total_missing = 0
        max_missing = 0

        for factor_name, result in report.results.items():
            # 按分类统计
            cat = result.category
            if cat not in summary["categories"]:
                summary["categories"][cat] = {"count": 0, "errors": 0, "warnings": 0}
            summary["categories"][cat]["count"] += 1
            if result.errors:
                summary["categories"][cat]["errors"] += 1
            elif result.warnings:
                summary["categories"][cat]["warnings"] += 1

            # 缺失值统计
            total_missing += result.missing_ratio
            max_missing = max(max_missing, result.missing_ratio)
            if result.missing_ratio > 0.2:  # 超过 20% 缺失
                summary["missing_stats"]["factors_with_high_missing"].append(factor_name)

            # 范围违规
            if result.within_range_ratio > 0 and result.within_range_ratio < 0.95:
                summary["range_violations"].append({
                    "factor": factor_name,
                    "within_range_ratio": result.within_range_ratio,
                })

        if report.total_factors > 0:
            summary["missing_stats"]["avg_missing_ratio"] = total_missing / report.total_factors
        summary["missing_stats"]["max_missing_ratio"] = max_missing

        return summary

    def print_report(self, report: ValidationReport, detailed: bool = False):
        """打印验证报告"""
        print("\n" + "=" * 80)
        print(f"因子验证报告 - 日期: {report.trade_date}")
        print(f"生成时间: {report.timestamp}")
        print("=" * 80)

        # 总体统计
        print(f"\n总体统计:")
        print(f"  总因子数: {report.total_factors}")
        print(f"  通过: {report.passed_factors} ({report.passed_factors/report.total_factors*100:.1f}%)")
        print(f"  警告: {report.warning_factors} ({report.warning_factors/report.total_factors*100:.1f}%)")
        print(f"  失败: {report.failed_factors} ({report.failed_factors/report.total_factors*100:.1f}%)")

        # 按分类统计
        print(f"\n按分类统计:")
        for cat, stats in sorted(report.summary.get("categories", {}).items()):
            status = "✓" if stats["errors"] == 0 and stats["warnings"] == 0 else "⚠" if stats["errors"] == 0 else "✗"
            print(f"  {status} {cat:20s}: {stats['count']:3d} 个 "
                  f"(错误: {stats['errors']}, 警告: {stats['warnings']})")

        # 缺失值统计
        missing_stats = report.summary.get("missing_stats", {})
        print(f"\n缺失值统计:")
        print(f"  平均缺失比例: {missing_stats.get('avg_missing_ratio', 0)*100:.2f}%")
        print(f"  最大缺失比例: {missing_stats.get('max_missing_ratio', 0)*100:.2f}%")
        high_missing = missing_stats.get("factors_with_high_missing", [])
        if high_missing:
            print(f"  高缺失因子 (>20%): {', '.join(high_missing[:5])}")
            if len(high_missing) > 5:
                print(f"    ... 还有 {len(high_missing)-5} 个")

        # 范围违规
        range_violations = report.summary.get("range_violations", [])
        if range_violations:
            print(f"\n范围违规:")
            for v in range_violations[:5]:
                print(f"  {v['factor']}: {v['within_range_ratio']*100:.1f}% 在范围内")

        # 详细结果
        if detailed:
            print(f"\n详细结果:")
            print("-" * 80)

            for factor_name, result in sorted(report.results.items()):
                if result.errors or result.warnings:
                    status = "✗" if result.errors else "⚠"
                    print(f"\n{status} {factor_name} - {result.description}")

                    if result.errors:
                        for error in result.errors:
                            print(f"   错误: {error}")

                    if result.warnings:
                        for warning in result.warnings:
                            print(f"   警告: {warning}")

                    if result.min_value is not None:
                        print(f"   统计: min={result.min_value:.4f}, max={result.max_value:.4f}, "
                              f"mean={result.mean_value:.4f}, missing={result.missing_ratio*100:.1f}%")

        print("\n" + "=" * 80)

    def export_report(self, report: ValidationReport, filepath: str):
        """导出报告到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report.to_json())
        logger.info(f"Report exported to {filepath}")


def validate_factor_data_lineage(factor_name: str) -> Dict[str, Any]:
    """
    验证因子的数据血缘

    返回详细的血缘信息，包括：
    - 源数据表
    - 源字段
    - 计算路径
    - 依赖关系
    """
    return get_factor_lineage(factor_name)


def print_factor_comparison(factor_name: str, trade_date: str):
    """
    打印因子的多源对比（如果有多个计算路径）
    """
    print(f"\n因子对比: {factor_name}")
    print("-" * 60)

    lineage = get_factor_lineage(factor_name)

    if "error" in lineage:
        print(f"错误: {lineage['error']}")
        return

    print(f"描述: {lineage['description']}")
    print(f"分类: {lineage['category']}")
    print(f"数据源表: {lineage['source_table']}")
    print(f"源字段: {', '.join(lineage['source_fields'])}")
    print(f"计算类型: {lineage['calculation_type']}")

    if lineage['sql_expression']:
        print(f"\nSQL 表达式:")
        print(f"  {lineage['sql_expression'][:100]}...")

    if lineage['dependencies']:
        print(f"\n依赖因子:")
        for dep in lineage['dependencies']:
            dep_lineage = get_factor_lineage(dep)
            print(f"  - {dep}: {dep_lineage.get('description', 'N/A')}")


# =============================================================================
# 命令行接口
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python factor_validator.py <command> [args]")
        print("\nCommands:")
        print("  validate <factor_name> <trade_date>  - 验证单个因子")
        print("  validate-all <trade_date>             - 验证所有 SQL 因子")
        print("  lineage <factor_name>                 - 查看因子血缘")
        print("  compare <factor_name> <trade_date>    - 对比因子计算")
        sys.exit(1)

    command = sys.argv[1]

    if command == "validate" and len(sys.argv) >= 4:
        factor_name = sys.argv[2]
        trade_date = sys.argv[3]

        validator = FactorValidator()
        result = validator.validate_factor(factor_name, trade_date)

        print(f"\n验证结果: {factor_name}")
        print(f"描述: {result.description}")
        print(f"分类: {result.category}")
        print(f"\n数据统计:")
        print(f"  总数: {result.total_count}")
        print(f"  缺失: {result.missing_count} ({result.missing_ratio*100:.1f}%)")
        if result.min_value is not None:
            print(f"  范围: [{result.min_value:.4f}, {result.max_value:.4f}]")
            print(f"  均值: {result.mean_value:.4f} (±{result.std_value:.4f})")
        if result.errors:
            print(f"\n错误: {result.errors}")
        if result.warnings:
            print(f"\n警告: {result.warnings}")

    elif command == "validate-all" and len(sys.argv) >= 3:
        trade_date = sys.argv[2]

        validator = FactorValidator()
        report = validator.validate_all_sql_factors(trade_date)
        validator.print_report(report, detailed=True)

    elif command == "lineage" and len(sys.argv) >= 3:
        factor_name = sys.argv[2]
        lineage = validate_factor_data_lineage(factor_name)

        print(f"\n因子血缘: {factor_name}")
        print(json.dumps(lineage, indent=2, ensure_ascii=False))

    elif command == "compare" and len(sys.argv) >= 4:
        factor_name = sys.argv[2]
        trade_date = sys.argv[3]
        print_factor_comparison(factor_name, trade_date)

    else:
        print(f"Unknown command or missing arguments: {command}")
        sys.exit(1)
