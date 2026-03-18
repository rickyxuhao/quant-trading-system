#!/usr/bin/env python3
"""
批量预计算因子数据填充脚本

用法:
    # 标准模式：全量计算（跳过已存在）
    python scripts/populate_factors.py --start 2019-01-01 --end 2024-12-31
    python scripts/populate_factors.py --years 2019,2020,2021,2022,2023,2024
    python scripts/populate_factors.py --recent 252  # 最近252个交易日

    # 增量更新：只计算新增的因子列
    python scripts/populate_factors.py --years 2010,2011,2012 --update-existing

    # 查看当前因子状态
    python scripts/populate_factors.py --status

场景示例：
    # 场景1：首次全量计算
    python scripts/populate_factors.py --years 2010-2024 --workers 6

    # 场景2：新增5个因子后，只更新新因子
    # 1. 修改 factor_registry.py 添加新因子
    # 2. 运行增量更新
    python scripts/populate_factors.py --years 2010-2024 --update-existing --workers 6

    # 场景3：新增2025年数据
    python scripts/populate_factors.py --years 2025 --workers 6
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
    parser.add_argument(
        "--update-existing",
        action="store_true",
        dest="update_existing",
        help="只更新新增的因子列（不重新计算所有因子）",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="查看当前因子覆盖状态",
    )

    args = parser.parse_args()

    # 查看状态模式
    if args.status:
        precomputer = FactorPrecomputer()
        existing_cols = set(precomputer._get_existing_columns())
        all_factor_cols = set(precomputer._schema.keys())
        missing_cols = all_factor_cols - existing_cols

        print("=" * 60)
        print("因子覆盖状态检查")
        print("=" * 60)
        print(f"已定义因子: {len(all_factor_cols)}")
        print(f"数据库已有: {len(existing_cols - {'trade_date', 'ts_code', 'updated_at'})}")
        print(f"缺失因子: {len(missing_cols)}")

        if missing_cols:
            print(f"\n缺失因子列表:")
            for col in sorted(missing_cols):
                print(f"  - {col}")

        # 获取数据库统计
        from core.storage.relational.connection import DatabaseManager
        stats = DatabaseManager.fetchone(
            precomputer.DB_NAME,
            f"SELECT COUNT(DISTINCT trade_date) as total_dates, COUNT(*) as total_rows FROM {precomputer.TABLE_NAME}"
        )
        if stats:
            print(f"\n数据统计:")
            print(f"  覆盖日期: {stats.get('total_dates', 0)} 天")
            print(f"  总记录数: {stats.get('total_rows', 0)} 条")
        print("=" * 60)
        return 0

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

    # 执行批量预计算或增量更新
    logger.info("=" * 60)
    if args.update_existing:
        logger.info("Starting incremental factor update (update-existing mode)")
    else:
        logger.info("Starting batch precomputation")
    logger.info("=" * 60)

    if args.update_existing:
        # 增量更新模式：只更新新增的因子列
        results = precomputer.update_missing_factors(
            start_date=start_date,
            end_date=end_date
        )
        # 输出结果
        logger.info("=" * 60)
        logger.info("Incremental Update Completed")
        logger.info("=" * 60)
        logger.info(f"Status: {results['status']}")
        if results.get('new_factors'):
            logger.info(f"New factors added: {len(results['new_factors'])}")
            logger.info(f"Factors: {results['new_factors']}")
        logger.info(f"Total trading days: {results.get('dates_processed', 0)}")
        logger.info(f"Success: {results.get('success_dates', 0)}")
        logger.info(f"Failed: {results.get('failed_dates', 0)}")
        logger.info(f"Total rows updated: {results.get('total_updated', 0)}")
    else:
        # 标准批量预计算模式
        results = precomputer.batch_precompute(
            start_date=start_date,
            end_date=end_date,
            skip_existing=args.skip_existing and not args.force,
        )
        # 输出结果
        logger.info("=" * 60)
        if results.get("status") == "skipped":
            logger.info("Batch Precomputation Skipped")
            logger.info(f"Message: {results.get('message', 'All dates already computed')}")
        else:
            logger.info("Batch Precomputation Completed")
            logger.info("=" * 60)
            logger.info(f"Total trading days: {results.get('total_dates', 0)}")
            logger.info(f"Success: {results.get('success', 0)}")
            logger.info(f"Failed: {results.get('failed', 0)}")

    # 检查失败结果（处理两种模式的字段差异）
    failed_count = results.get('failed', results.get('failed_dates', 0))
    if failed_count > 0:
        logger.warning("Some dates failed. Check details for errors.")
        for detail in results.get('details', []):
            if detail.get('status') == 'error':
                logger.warning(f"  Failed: {detail.get('date', 'unknown')} - {detail.get('error', 'Unknown error')}")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
