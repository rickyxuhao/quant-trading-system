#!/usr/bin/env python3
"""
批量预计算因子数据填充脚本

用法:
    python scripts/populate_factors.py --start 2019-01-01 --end 2024-12-31
    python scripts/populate_factors.py --years 2019,2020,2021,2022,2023,2024
    python scripts/populate_factors.py --recent 252  # 最近252个交易日
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from projects.quant_trading.strategies.ml_prediction.precomputed_factors import (
    FactorPrecomputer, PrecomputeConfig
)
from projects.quant_trading.backtest.data_manager import DataManager
from core.logger import get_logger

logger = get_logger(__name__)


def get_recent_trade_dates(n_days: int) -> tuple:
    """获取最近N个交易日"""
    dm = DataManager()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days * 2)

    try:
        trade_dates = dm.get_trade_dates(start_date, end_date)
        if len(trade_dates) >= n_days:
            return trade_dates[-n_days], trade_dates[-1]
        return trade_dates[0] if trade_dates else end_date - timedelta(days=n_days), end_date
    except Exception as e:
        logger.warning(f"Failed to get trade dates: {e}")
        return end_date - timedelta(days=n_days), end_date


def main():
    parser = argparse.ArgumentParser(description="Populate precomputed factors")
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--years",
        type=str,
        help="Comma-separated years (e.g., 2019,2020,2021)",
    )
    parser.add_argument(
        "--recent",
        type=int,
        help="Process recent N trading days",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Stocks per batch (default: 500)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip dates that already have data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recompute even if data exists",
    )

    args = parser.parse_args()

    # 确定日期范围
    if args.recent:
        start_date, end_date = get_recent_trade_dates(args.recent)
        logger.info(f"Processing recent {args.recent} trading days: {start_date.date()} to {end_date.date()}")
    elif args.years:
        years = [int(y.strip()) for y in args.years.split(",")]
        start_date = datetime(min(years), 1, 1)
        end_date = datetime(max(years), 12, 31)
        logger.info(f"Processing years {min(years)}-{max(years)}")
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
        logger.info(f"Processing date range: {args.start} to {args.end}")
    else:
        # 默认处理2019-2024
        start_date = datetime(2019, 1, 1)
        end_date = datetime(2024, 12, 31)
        logger.info(f"Processing default range: 2019-01-01 to 2024-12-31")

    # 配置
    config = PrecomputeConfig(
        batch_size=args.batch_size,
        workers=args.workers,
    )

    # 初始化预计算器
    logger.info("Initializing FactorPrecomputer...")
    precomputer = FactorPrecomputer(config)

    # 执行批量预计算
    logger.info("=" * 60)
    logger.info("Starting batch precomputation")
    logger.info("=" * 60)

    results = precomputer.batch_precompute(
        start_date=start_date,
        end_date=end_date,
        skip_existing=args.skip_existing and not args.force,
    )

    # 输出结果
    logger.info("=" * 60)
    logger.info("Batch Precomputation Completed")
    logger.info("=" * 60)
    logger.info(f"Total trading days: {results['total_dates']}")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Skipped: {results['skipped']}")
    logger.info(f"Failed: {results['failed']}")

    if results['failed'] > 0:
        logger.warning("Some dates failed. Check details for errors.")
        for detail in results['details']:
            if detail.get('status') == 'error':
                logger.warning(f"  Failed: {detail['date']} - {detail.get('error', 'Unknown error')}")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
