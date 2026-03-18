"""
数据完整性检查脚本

功能：
- 检查日线数据覆盖
- 检查估值指标完整性
- 检查财务数据完整性
- 检查资金流向数据
- 检查股票池完整性

原则：使用聚合查询，避免加载大量数据到内存
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse

import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


class DataIntegrityChecker:
    """数据完整性检查器"""

    def __init__(self, db_name: str = "tushare_biz"):
        self.db_name = db_name
        self.results: Dict[str, Any] = {}

    def run_all_checks(self, start_year: int = 2010, end_year: int = 2024) -> Dict[str, Any]:
        """运行所有检查"""
        logger.info("=" * 60)
        logger.info("Starting Data Integrity Checks")
        logger.info("=" * 60)

        # 1. 日线数据覆盖检查
        logger.info("\n1. Checking daily market data coverage...")
        self.results["daily_market"] = self.check_daily_coverage(start_year, end_year)

        # 2. 估值指标数据检查
        logger.info("\n2. Checking valuation data coverage...")
        self.results["valuation"] = self.check_valuation_data(start_year, end_year)

        # 3. 财务指标数据检查
        logger.info("\n3. Checking financial indicator data...")
        self.results["financial"] = self.check_financial_data(start_year, end_year)

        # 4. 资金流向数据检查
        logger.info("\n4. Checking money flow data...")
        self.results["moneyflow"] = self.check_moneyflow_data(start_year, end_year)

        # 5. 股票池检查
        logger.info("\n5. Checking stock universe...")
        self.results["universe"] = self.check_stock_universe()

        # 6. ST股票列表检查
        logger.info("\n6. Checking ST stock records...")
        self.results["st_stocks"] = self.check_st_records()

        # 7. 申万行业分类数据检查
        logger.info("\n7. Checking SW industry classification...")
        self.results["sw_classify"] = self.check_sw_classify()

        # 8. 申万行业成分股数据检查
        logger.info("\n8. Checking SW industry members...")
        self.results["sw_member"] = self.check_sw_member()

        # 9. 申万行业指数日线数据检查
        logger.info("\n9. Checking SW industry daily prices...")
        self.results["sw_daily"] = self.check_sw_daily()

        # 生成报告
        report = self.generate_report()

        logger.info("\n" + "=" * 60)
        logger.info("Data Integrity Checks Completed")
        logger.info("=" * 60)

        return self.results

    def check_daily_coverage(self, start_year: int, end_year: int) -> pd.DataFrame:
        """
        检查日线数据覆盖

        按年统计：交易日数、股票数、总记录数
        """
        CHECK_DAILY_COVERAGE = """
        SELECT
            SUBSTRING(trade_date, 1, 4) as year,
            COUNT(DISTINCT trade_date) as trading_days,
            COUNT(DISTINCT ts_code) as stock_count,
            COUNT(*) as total_records
        FROM t_stock_dailymarketdata
        WHERE trade_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY SUBSTRING(trade_date, 1, 4)
        ORDER BY year
        """

        try:
            results = DatabaseManager.fetchall(
                self.db_name,
                CHECK_DAILY_COVERAGE,
                {
                    "start_date": f"{start_year}0101",
                    "end_date": f"{end_year}1231",
                }
            )

            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No daily market data found")
                return pd.DataFrame()

            # 计算预期交易日（每年约242个交易日）
            df["expected_days"] = 242
            df["coverage_ratio"] = df["trading_days"] / df["expected_days"]

            logger.info(f"Daily market data: {len(df)} years")
            for _, row in df.iterrows():
                logger.info(
                    f"  {row['year']}: {row['trading_days']} days, "
                    f"{row['stock_count']} stocks, "
                    f"coverage: {row['coverage_ratio']:.1%}"
                )

            return df

        except Exception as e:
            logger.error(f"Error checking daily coverage: {e}")
            return pd.DataFrame()

    def check_valuation_data(self, start_year: int, end_year: int) -> pd.DataFrame:
        """
        检查估值指标数据覆盖（PE/PB等）
        """
        CHECK_DAILY_BASIC = """
        SELECT
            SUBSTRING(trade_date, 1, 4) as year,
            COUNT(DISTINCT trade_date) as days_with_data,
            COUNT(DISTINCT ts_code) as stock_count,
            AVG(CASE WHEN pe IS NOT NULL THEN 1 ELSE 0 END) as pe_coverage,
            AVG(CASE WHEN pb IS NOT NULL THEN 1 ELSE 0 END) as pb_coverage,
            AVG(CASE WHEN ps_ttm IS NOT NULL THEN 1 ELSE 0 END) as ps_coverage,
            AVG(CASE WHEN total_mv IS NOT NULL THEN 1 ELSE 0 END) as mv_coverage
        FROM t_stock_daily_basic
        WHERE trade_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY SUBSTRING(trade_date, 1, 4)
        ORDER BY year
        """

        try:
            results = DatabaseManager.fetchall(
                self.db_name,
                CHECK_DAILY_BASIC,
                {
                    "start_date": f"{start_year}0101",
                    "end_date": f"{end_year}1231",
                }
            )

            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No valuation data found")
                return pd.DataFrame()

            # 转换为百分比
            for col in ["pe_coverage", "pb_coverage", "ps_coverage", "mv_coverage"]:
                if col in df.columns:
                    df[col] = df[col] * 100

            logger.info(f"Valuation data: {len(df)} years")
            for _, row in df.iterrows():
                logger.info(
                    f"  {row['year']}: PE={row['pe_coverage']:.1f}%, "
                    f"PB={row['pb_coverage']:.1f}%, "
                    f"MV={row['mv_coverage']:.1f}%"
                )

            return df

        except Exception as e:
            logger.error(f"Error checking valuation data: {e}")
            return pd.DataFrame()

    def check_financial_data(self, start_year: int, end_year: int) -> pd.DataFrame:
        """
        检查财务指标数据覆盖
        """
        CHECK_FINA_INDICATOR = """
        SELECT
            SUBSTRING(end_date, 1, 4) as year,
            COUNT(DISTINCT ts_code) as stock_count,
            COUNT(*) as record_count,
            AVG(CASE WHEN roe IS NOT NULL THEN 1 ELSE 0 END) as roe_coverage,
            AVG(CASE WHEN netprofit_yoy IS NOT NULL THEN 1 ELSE 0 END) as profit_growth_coverage
        FROM t_stock_fina_indicator
        WHERE end_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY SUBSTRING(end_date, 1, 4)
        ORDER BY year
        """

        try:
            results = DatabaseManager.fetchall(
                self.db_name,
                CHECK_FINA_INDICATOR,
                {
                    "start_date": f"{start_year}0101",
                    "end_date": f"{end_year}1231",
                }
            )

            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No financial indicator data found")
                return pd.DataFrame()

            # 转换为百分比
            for col in ["roe_coverage", "profit_growth_coverage"]:
                if col in df.columns:
                    df[col] = df[col] * 100

            logger.info(f"Financial data: {len(df)} years")
            for _, row in df.iterrows():
                logger.info(
                    f"  {row['year']}: {row['stock_count']} stocks, "
                    f"ROE coverage={row['roe_coverage']:.1f}%"
                )

            return df

        except Exception as e:
            logger.error(f"Error checking financial data: {e}")
            return pd.DataFrame()

    def check_moneyflow_data(self, start_year: int, end_year: int) -> pd.DataFrame:
        """
        检查资金流向数据覆盖
        """
        CHECK_MONEYFLOW = """
        SELECT
            SUBSTRING(trade_date, 1, 4) as year,
            COUNT(DISTINCT trade_date) as trading_days,
            COUNT(DISTINCT ts_code) as stock_count,
            COUNT(*) as total_records
        FROM t_stock_moneyflow
        WHERE trade_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY SUBSTRING(trade_date, 1, 4)
        ORDER BY year
        """

        try:
            results = DatabaseManager.fetchall(
                self.db_name,
                CHECK_MONEYFLOW,
                {
                    "start_date": f"{start_year}0101",
                    "end_date": f"{end_year}1231",
                }
            )

            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No moneyflow data found")
                return pd.DataFrame()

            logger.info(f"Moneyflow data: {len(df)} years")
            for _, row in df.iterrows():
                logger.info(
                    f"  {row['year']}: {row['trading_days']} days, "
                    f"{row['stock_count']} stocks"
                )

            return df

        except Exception as e:
            logger.error(f"Error checking moneyflow data: {e}")
            return pd.DataFrame()

    def check_stock_universe(self) -> Dict[str, Any]:
        """
        检查股票池完整性
        """
        CHECK_STOCK_UNIVERSE = """
        SELECT
            list_status,
            COUNT(*) as count,
            MIN(list_date) as earliest_list,
            MAX(list_date) as latest_list,
            COUNT(DISTINCT industry) as industry_count
        FROM t_stock_basic
        GROUP BY list_status
        """

        try:
            results = DatabaseManager.fetchall(self.db_name, CHECK_STOCK_UNIVERSE)

            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No stock basic data found")
                return {}

            logger.info("Stock universe summary:")
            for _, row in df.iterrows():
                logger.info(
                    f"  Status {row['list_status']}: {row['count']} stocks, "
                    f"{row['industry_count']} industries"
                )

            return df.to_dict("records")

        except Exception as e:
            logger.error(f"Error checking stock universe: {e}")
            return {}

    def check_st_records(self) -> Dict[str, Any]:
        """
        检查ST股票记录
        """
        CHECK_ST_RECORDS = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT ts_code) as unique_stocks,
            MIN(trade_date) as earliest_record,
            MAX(trade_date) as latest_record
        FROM t_stock_st_list
        """

        try:
            results = DatabaseManager.fetchall(self.db_name, CHECK_ST_RECORDS)

            if results:
                record = results[0]
                logger.info("ST stock records:")
                logger.info(f"  Total records: {record['total_records']}")
                logger.info(f"  Unique stocks: {record['unique_stocks']}")
                logger.info(f"  Date range: {record['earliest_record']} to {record['latest_record']}")

                return record

            return {}

        except Exception as e:
            logger.error(f"Error checking ST records: {e}")
            return {}

    def check_sw_classify(self) -> Dict[str, Any]:
        """
        检查申万行业分类数据
        """
        CHECK_SW_CLASSIFY = """
        SELECT
            level,
            COUNT(*) as industry_count
        FROM t_sw_classify
        GROUP BY level
        ORDER BY level
        """

        try:
            results = DatabaseManager.fetchall(self.db_name, CHECK_SW_CLASSIFY)

            if results:
                logger.info("SW Industry Classification:")
                total = 0
                for row in results:
                    level_name = {1: "一级", 2: "二级", 3: "三级"}.get(row['level'], f"Level {row['level']}")
                    logger.info(f"  {level_name}: {row['industry_count']} industries")
                    total += row['industry_count']
                logger.info(f"  Total: {total} industries")
                return {"levels": results, "total": total}

            logger.warning("No SW industry classification data found")
            return {}

        except Exception as e:
            logger.error(f"Error checking SW classification: {e}")
            return {}

    def check_sw_member(self) -> Dict[str, Any]:
        """
        检查申万行业成分股数据
        """
        CHECK_SW_MEMBER = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT index_code) as industry_count,
            COUNT(DISTINCT con_code) as unique_stocks,
            COUNT(DISTINCT CASE WHEN is_new = 1 THEN con_code END) as current_stocks,
            MAX(trade_date) as latest_date
        FROM t_sw_member
        """

        try:
            results = DatabaseManager.fetchall(self.db_name, CHECK_SW_MEMBER)

            if results and results[0]['total_records']:
                record = results[0]
                logger.info("SW Industry Members:")
                logger.info(f"  Total records: {record['total_records']}")
                logger.info(f"  Industries: {record['industry_count']}")
                logger.info(f"  Unique stocks (all time): {record['unique_stocks']}")
                logger.info(f"  Current stocks: {record['current_stocks']}")
                logger.info(f"  Latest date: {record['latest_date']}")
                return record

            logger.warning("No SW industry member data found")
            return {}

        except Exception as e:
            logger.error(f"Error checking SW members: {e}")
            return {}

    def check_sw_daily(self) -> pd.DataFrame:
        """
        检查申万行业指数日线数据
        """
        CHECK_SW_DAILY = """
        SELECT
            SUBSTRING(trade_date, 1, 4) as year,
            COUNT(DISTINCT trade_date) as trading_days,
            COUNT(DISTINCT ts_code) as industry_count,
            COUNT(*) as total_records
        FROM t_sw_daily
        GROUP BY SUBSTRING(trade_date, 1, 4)
        ORDER BY year
        """

        try:
            results = DatabaseManager.fetchall(self.db_name, CHECK_SW_DAILY)

            if not results:
                logger.warning("No SW industry daily data found")
                return pd.DataFrame()

            df = pd.DataFrame(results)

            logger.info("SW Industry Daily Prices:")
            for _, row in df.iterrows():
                logger.info(
                    f"  {row['year']}: {row['trading_days']} days, "
                    f"{row['industry_count']} industries"
                )

            return df

        except Exception as e:
            logger.error(f"Error checking SW daily: {e}")
            return pd.DataFrame()

    def check_data_gaps(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        检查特定股票的数据缺口
        """
        CHECK_GAPS = """
        SELECT trade_date
        FROM t_stock_dailymarketdata
        WHERE ts_code = %(ts_code)s
          AND trade_date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY trade_date
        """

        try:
            results = DatabaseManager.fetchall(
                self.db_name,
                CHECK_GAPS,
                {
                    "ts_code": ts_code,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

            # 计算日期差
            df["date_diff"] = df["trade_date"].diff().dt.days

            # 找出大于5天的缺口（可能是停牌或数据缺失）
            gaps = df[df["date_diff"] > 5]

            return gaps

        except Exception as e:
            logger.error(f"Error checking data gaps: {e}")
            return pd.DataFrame()

    def generate_report(self) -> str:
        """生成检查报告"""
        lines = [
            "=" * 70,
            "Data Integrity Check Report",
            "=" * 70,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # 日线数据总结
        if "daily_market" in self.results and not self.results["daily_market"].empty:
            df = self.results["daily_market"]
            lines.extend([
                "Daily Market Data:",
                f"  Years covered: {df['year'].min()} - {df['year'].max()}",
                f"  Average trading days per year: {df['trading_days'].mean():.0f}",
                f"  Latest stock count: {df['stock_count'].iloc[-1]}",
                "",
            ])

        # 估值数据总结
        if "valuation" in self.results and not self.results["valuation"].empty:
            df = self.results["valuation"]
            lines.extend([
                "Valuation Data:",
                f"  PE coverage (latest year): {df['pe_coverage'].iloc[-1]:.1f}%",
                f"  PB coverage (latest year): {df['pb_coverage'].iloc[-1]:.1f}%",
                "",
            ])

        # 财务数据总结
        if "financial" in self.results and not self.results["financial"].empty:
            df = self.results["financial"]
            lines.extend([
                "Financial Data:",
                f"  Latest year stocks: {df['stock_count'].iloc[-1]}",
                f"  ROE coverage: {df['roe_coverage'].iloc[-1]:.1f}%",
                "",
            ])

        # 资金流向数据
        if "moneyflow" in self.results:
            if not self.results["moneyflow"].empty:
                df = self.results["moneyflow"]
                lines.extend([
                    "Money Flow Data:",
                    f"  Years covered: {len(df)}",
                    f"  Latest year trading days: {df['trading_days'].iloc[-1]}",
                    "",
                ])
            else:
                lines.extend([
                    "Money Flow Data: NOT AVAILABLE",
                    "",
                ])

        # 股票池
        if "universe" in self.results:
            lines.append("Stock Universe:")
            for record in self.results["universe"]:
                lines.append(f"  Status {record['list_status']}: {record['count']} stocks")
            lines.append("")

        # 申万行业分类
        if "sw_classify" in self.results and self.results["sw_classify"]:
            lines.append("SW Industry Classification:")
            lines.append(f"  Total industries: {self.results['sw_classify'].get('total', 0)}")
            lines.append("")

        # 申万行业成分股
        if "sw_member" in self.results and self.results["sw_member"]:
            lines.append("SW Industry Members:")
            lines.append(f"  Industries: {self.results['sw_member'].get('industry_count', 0)}")
            lines.append(f"  Current stocks: {self.results['sw_member'].get('current_stocks', 0)}")
            lines.append("")

        # 申万行业日线数据
        if "sw_daily" in self.results and not self.results["sw_daily"].empty:
            df = self.results["sw_daily"]
            lines.append("SW Industry Daily Prices:")
            lines.append(f"  Years covered: {df['year'].min()} - {df['year'].max()}")
            lines.append(f"  Latest year days: {df['trading_days'].iloc[-1]}")
            lines.append("")

        lines.append("=" * 70)

        report = "\n".join(lines)
        return report

    def export_report(self, output_path: str) -> None:
        """导出报告到文件"""
        report = self.generate_report()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(report)

        logger.info(f"Report exported to {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Check data integrity")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2010,
        help="Start year for checking (default: 2010)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
        help="End year for checking (default: 2024)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data_integrity_report.txt",
        help="Output file path",
    )
    parser.add_argument(
        "--check-gaps",
        type=str,
        help="Check data gaps for specific stock (ts_code)",
    )

    args = parser.parse_args()

    # 运行检查
    checker = DataIntegrityChecker()

    if args.check_gaps:
        # 检查特定股票的数据缺口
        gaps = checker.check_data_gaps(
            args.check_gaps,
            f"{args.start_year}0101",
            f"{args.end_year}1231",
        )
        if not gaps.empty:
            print(f"\nData gaps for {args.check_gaps}:")
            print(gaps.to_string())
        else:
            print(f"\nNo significant data gaps found for {args.check_gaps}")
    else:
        # 运行完整检查
        checker.run_all_checks(args.start_year, args.end_year)
        checker.export_report(args.output)


if __name__ == "__main__":
    main()
