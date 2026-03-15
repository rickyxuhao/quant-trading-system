"""
价格数据质量校验器
包含价格连续性检查和涨跌幅合理性检查
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PriceContinuityViolation:
    """价格连续性违规记录"""
    ts_code: str
    current_date: str
    expected_prev_date: str
    actual_prev_date: Optional[str]
    missing_dates: List[str]
    severity: str = "warning"


@dataclass
class PriceChangeViolation:
    """价格涨跌幅违规记录"""
    ts_code: str
    trade_date: str
    pct_chg: float
    limit_pct: float
    is_st: bool
    market_type: str
    severity: str = "error"


class PriceContinuityChecker:
    """
    价格连续性检查器

    检查股票日线数据是否存在缺失的交易日（停牌除外）
    """

    def __init__(self, db_name: str = "tushare_biz"):
        self.db_name = db_name

    def check_continuity(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_missing_days: int = 5
    ) -> List[PriceContinuityViolation]:
        """
        检查价格数据连续性

        Args:
            ts_code: 股票代码，为None则检查所有股票
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            max_missing_days: 超过此天数视为严重错误

        Returns:
            违规记录列表
        """
        violations = []

        # 构建查询条件
        where_clauses = []
        params = []

        if ts_code:
            where_clauses.append("ts_code = %s")
            params.append(ts_code)

        date_range = self._get_date_range(start_date, end_date)

        # 获取需要检查的股票列表
        stocks = self._get_stocks_to_check(ts_code)

        for stock in stocks:
            stock_violations = self._check_stock_continuity(
                stock, date_range, max_missing_days
            )
            violations.extend(stock_violations)

        return violations

    def _get_date_range(
        self,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> Tuple[str, str]:
        """获取日期范围"""
        if not start_date or not end_date:
            # 查询数据中的最新日期范围
            sql = """
                SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date
                FROM t_stock_dailymarketdata
            """
            result = DatabaseManager.fetchone(self.db_name, sql)
            start_date = start_date or result.get("min_date", "20200101")
            end_date = end_date or result.get("max_date", datetime.now().strftime("%Y%m%d"))

        return start_date, end_date

    def _get_stocks_to_check(self, ts_code: Optional[str]) -> List[str]:
        """获取需要检查的股票列表"""
        if ts_code:
            return [ts_code]

        sql = """
            SELECT DISTINCT ts_code FROM t_stock_dailymarketdata
            WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            LIMIT 100
        """
        results = DatabaseManager.fetchall(self.db_name, sql)
        return [r["ts_code"] for r in results]

    def _check_stock_continuity(
        self,
        ts_code: str,
        date_range: Tuple[str, str],
        max_missing_days: int
    ) -> List[PriceContinuityViolation]:
        """检查单只股票的连续性"""
        violations = []
        start_date, end_date = date_range

        # 查询该股票的所有交易日期
        sql = """
            SELECT trade_date
            FROM t_stock_dailymarketdata
            WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date
        """
        results = DatabaseManager.fetchall(self.db_name, sql, (ts_code, start_date, end_date))
        actual_dates = [r["trade_date"] for r in results]

        if len(actual_dates) < 2:
            return []

        # 查询交易日历
        exchange = "SSE" if ts_code.endswith(".SH") else "SZSE"
        calendar_sql = """
            SELECT cal_date, pretrade_date
            FROM t_stock_tradedate
            WHERE exchange = %s AND cal_date BETWEEN %s AND %s AND is_open = 1
            ORDER BY cal_date
        """
        calendar_results = DatabaseManager.fetchall(
            self.db_name, calendar_sql, (exchange, start_date, end_date)
        )

        # 构建交易日字典
        trade_calendar = {}
        for row in calendar_results:
            trade_calendar[row["cal_date"]] = row["pretrade_date"]

        # 检查连续性
        for i in range(1, len(actual_dates)):
            current_date = actual_dates[i]
            prev_date = actual_dates[i-1]

            expected_prev = trade_calendar.get(current_date)

            if expected_prev and expected_prev != prev_date:
                # 计算缺失的日期
                missing_dates = self._get_missing_dates(
                    prev_date, current_date, trade_calendar
                )

                if missing_dates:
                    severity = "error" if len(missing_dates) > max_missing_days else "warning"
                    violations.append(PriceContinuityViolation(
                        ts_code=ts_code,
                        current_date=current_date,
                        expected_prev_date=expected_prev,
                        actual_prev_date=prev_date,
                        missing_dates=missing_dates,
                        severity=severity
                    ))

        return violations

    def _get_missing_dates(
        self,
        prev_date: str,
        current_date: str,
        trade_calendar: Dict[str, str]
    ) -> List[str]:
        """获取两个日期之间缺失的交易日"""
        missing = []

        # 从current_date往前回溯
        check_date = trade_calendar.get(current_date)
        while check_date and check_date > prev_date:
            missing.append(check_date)
            check_date = trade_calendar.get(check_date)

        return sorted(missing)


class PriceChangeValidator:
    """
    价格涨跌幅合理性检查器

    检查价格变动是否在合理范围内：
    - 普通股票：±10%
    - ST股票：±5%
    - 科创板(688)/创业板(300/301)：±20%
    - 北交所(8/9开头)：±30%
    """

    # 涨跌幅限制配置
    LIMIT_CONFIG = {
        "default": 10.0,
        "st": 5.0,
        "kcb": 20.0,  # 科创板
        "cyb": 20.0,  # 创业板
        "bjx": 30.0,  # 北交所
    }

    def __init__(self, db_name: str = "tushare_biz"):
        self.db_name = db_name

    def validate_price_changes(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_st_check: bool = True
    ) -> List[PriceChangeViolation]:
        """
        验证价格变动合理性

        Args:
            ts_code: 股票代码，为None则检查所有
            start_date: 开始日期
            end_date: 结束日期
            include_st_check: 是否检查ST状态

        Returns:
            违规记录列表
        """
        violations = []

        # 构建基础查询
        where_conditions = []
        params = []

        if ts_code:
            where_conditions.append("ts_code = %s")
            params.append(ts_code)

        if start_date:
            where_conditions.append("trade_date >= %s")
            params.append(start_date)

        if end_date:
            where_conditions.append("trade_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        # 查询日线数据
        sql = f"""
            SELECT ts_code, trade_date, pct_chg, close, pre_close
            FROM t_stock_dailymarketdata
            WHERE {where_clause}
            ORDER BY ts_code, trade_date
        """

        results = DatabaseManager.fetchall(self.db_name, sql, tuple(params) if params else None)

        if not results:
            return []

        # 获取ST状态
        st_dates = set()
        if include_st_check:
            st_dates = self._get_st_dates(results)

        # 检查每条记录
        for row in results:
            pct_chg = row.get("pct_chg")
            if pct_chg is None:
                continue

            code = row["ts_code"]
            date = row["trade_date"]

            # 确定限制
            is_st = (code, date) in st_dates
            market_type = self._get_market_type(code)
            limit_pct = self._get_limit_pct(is_st, market_type)

            # 检查是否超出限制
            if abs(pct_chg) > limit_pct + 0.01:  # 允许0.01的浮点误差
                # 检查是否是新股上市首日
                if not self._is_new_stock_first_day(row):
                    violations.append(PriceChangeViolation(
                        ts_code=code,
                        trade_date=date,
                        pct_chg=pct_chg,
                        limit_pct=limit_pct,
                        is_st=is_st,
                        market_type=market_type,
                        severity="error"
                    ))

        return violations

    def _get_st_dates(self, price_data: List[Dict]) -> set:
        """获取ST状态日期集合"""
        # 提取所有需要查询的日期
        dates = set(row["trade_date"] for row in price_data)
        codes = set(row["ts_code"] for row in price_data)

        if not dates or not codes:
            return set()

        # 批量查询ST状态
        date_list = sorted(dates)
        code_list = list(codes)

        placeholders = ', '.join(['%s'] * len(code_list))
        sql = f"""
            SELECT ts_code, trade_date
            FROM t_stock_st_list
            WHERE ts_code IN ({placeholders}) AND trade_date IN ({', '.join(['%s'] * len(date_list))})
        """
        params = code_list + date_list

        results = DatabaseManager.fetchall(self.db_name, sql, params)

        return set((r["ts_code"], r["trade_date"]) for r in results)

    def _get_market_type(self, ts_code: str) -> str:
        """
        获取市场类型

        Returns:
            default: 主板
            kcb: 科创板 (688xxx.SH)
            cyb: 创业板 (300xxx.SZ, 301xxx.SZ)
            bjx: 北交所 (8xxxxx.BJ, 9xxxxx.BJ)
        """
        if ts_code.startswith("688") and ts_code.endswith(".SH"):
            return "kcb"
        elif (ts_code.startswith("300") or ts_code.startswith("301")) and ts_code.endswith(".SZ"):
            return "cyb"
        elif ts_code.startswith(("8", "9")) and ".BJ" in ts_code:
            return "bjx"
        return "default"

    def _get_limit_pct(self, is_st: bool, market_type: str) -> float:
        """获取涨跌幅限制"""
        if is_st:
            return self.LIMIT_CONFIG["st"]
        return self.LIMIT_CONFIG.get(market_type, self.LIMIT_CONFIG["default"])

    def _is_new_stock_first_day(self, row: Dict) -> bool:
        """检查是否是新股上市首日"""
        # 新股首日涨跌幅无限制
        # 通过pre_close为0或特别小来判断
        pre_close = row.get("pre_close")
        if pre_close is None or pre_close == 0:
            return True

        # 检查是否是上市后第一天（可以通过查询IPO日期判断）
        # 简化处理：如果pre_close异常小（<0.1）则认为是新股
        if pre_close < 0.1:
            return True

        return False


class PriceDataQualityChecker:
    """价格数据质量检查统一入口"""

    def __init__(self, db_name: str = "tushare_biz"):
        self.db_name = db_name
        self.continuity_checker = PriceContinuityChecker(db_name)
        self.change_validator = PriceChangeValidator(db_name)

    def run_all_checks(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        运行所有价格数据质量检查

        Returns:
            {
                "continuity_violations": List[PriceContinuityViolation],
                "price_change_violations": List[PriceChangeViolation],
                "summary": {
                    "total_violations": int,
                    "error_count": int,
                    "warning_count": int
                }
            }
        """
        logger.info(f"开始价格数据质量检查: ts_code={ts_code}, date_range={start_date}~{end_date}")

        # 价格连续性检查
        continuity_violations = self.continuity_checker.check_continuity(
            ts_code, start_date, end_date
        )

        # 涨跌幅合理性检查
        change_violations = self.change_validator.validate_price_changes(
            ts_code, start_date, end_date
        )

        # 统计
        error_count = (
            sum(1 for v in continuity_violations if v.severity == "error") +
            sum(1 for v in change_violations if v.severity == "error")
        )
        warning_count = (
            sum(1 for v in continuity_violations if v.severity == "warning") +
            sum(1 for v in change_violations if v.severity == "warning")
        )

        result = {
            "continuity_violations": continuity_violations,
            "price_change_violations": change_violations,
            "summary": {
                "total_violations": len(continuity_violations) + len(change_violations),
                "error_count": error_count,
                "warning_count": warning_count,
                "continuity_count": len(continuity_violations),
                "price_change_count": len(change_violations)
            }
        }

        logger.info(f"检查完成: {result['summary']}")
        return result

    def generate_report(self, result: Dict, format: str = "text") -> str:
        """生成检查报告"""
        if format == "json":
            import json
            return json.dumps({
                "summary": result["summary"],
                "continuity_violations": [
                    {
                        "ts_code": v.ts_code,
                        "current_date": v.current_date,
                        "missing_dates": v.missing_dates,
                        "severity": v.severity
                    }
                    for v in result["continuity_violations"]
                ],
                "price_change_violations": [
                    {
                        "ts_code": v.ts_code,
                        "trade_date": v.trade_date,
                        "pct_chg": v.pct_chg,
                        "limit_pct": v.limit_pct,
                        "is_st": v.is_st,
                        "market_type": v.market_type,
                        "severity": v.severity
                    }
                    for v in result["price_change_violations"]
                ]
            }, ensure_ascii=False, indent=2)

        # Text format
        lines = []
        lines.append("=" * 70)
        lines.append("价格数据质量检查报告")
        lines.append("=" * 70)
        lines.append("")

        summary = result["summary"]
        lines.append("【摘要】")
        lines.append(f"  总违规数: {summary['total_violations']}")
        lines.append(f"  严重错误: {summary['error_count']} 🚨")
        lines.append(f"  警告: {summary['warning_count']} ⚠️")
        lines.append(f"  价格连续性违规: {summary['continuity_count']}")
        lines.append(f"  涨跌幅违规: {summary['price_change_count']}")
        lines.append("")

        # 连续性违规
        if result["continuity_violations"]:
            lines.append("【价格连续性违规】")
            for v in result["continuity_violations"][:20]:
                icon = "🚨" if v.severity == "error" else "⚠️"
                lines.append(f"  {icon} {v.ts_code}: {v.current_date}")
                lines.append(f"      期望前交易日: {v.expected_prev_date}, 实际: {v.actual_prev_date}")
                lines.append(f"      缺失日期数: {len(v.missing_dates)}")
            if len(result["continuity_violations"]) > 20:
                lines.append(f"  ... 还有 {len(result['continuity_violations']) - 20} 条")
            lines.append("")

        # 涨跌幅违规
        if result["price_change_violations"]:
            lines.append("【涨跌幅违规】")
            for v in result["price_change_violations"][:20]:
                st_flag = "[ST]" if v.is_st else ""
                lines.append(
                    f"  🚨 {v.ts_code}: {v.trade_date} "
                    f"涨跌幅={v.pct_chg:.2f}% 限制={v.limit_pct:.0f}% {st_flag}"
                )
            if len(result["price_change_violations"]) > 20:
                lines.append(f"  ... 还有 {len(result['price_change_violations']) - 20} 条")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)


def check_price_quality(
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_name: str = "tushare_biz"
) -> Dict:
    """
    便捷函数：检查价格数据质量

    Args:
        ts_code: 股票代码，None则检查所有
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        db_name: 数据库名

    Returns:
        检查结果字典
    """
    checker = PriceDataQualityChecker(db_name)
    return checker.run_all_checks(ts_code, start_date, end_date)
