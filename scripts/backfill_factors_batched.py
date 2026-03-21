#!/usr/bin/env python3
"""
批量因子补全脚本（分批处理股票，解决大IN子句性能问题）

优化原理：
- 原方案：5395股票 IN子句 -> SQL超慢（17分钟/天）
- 优化方案：500股票分批 -> SQL快速（每批<2秒，全天~20秒）

用法:
    python scripts/backfill_factors_batched.py
    python scripts/backfill_factors_batched.py --start 2025-06-04 --end 2026-03-20
    python scripts/backfill_factors_batched.py --start 2025-06-04 --end 2026-03-20 --batch-size 500
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from projects.quant_trading.strategies.ml_prediction.precomputed_factors import (
    FactorPrecomputer, PrecomputeConfig
)
from projects.quant_trading.backtest.data_manager import DataManager
from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


def get_missing_dates(start_date: datetime, end_date: datetime, min_count: int = 1000):
    """获取缺失的交易日"""
    dm = DataManager()
    all_dates = dm.get_trade_dates(start_date, end_date)

    date_strs = [d.strftime('%Y%m%d') for d in all_dates]
    if not date_strs:
        return []

    placeholders = ','.join(['%s'] * len(date_strs))
    rows = DatabaseManager.fetchall(
        'interface',
        f'SELECT trade_date, COUNT(*) as cnt FROM t_precomputed_factors '
        f'WHERE trade_date IN ({placeholders}) GROUP BY trade_date',
        tuple(date_strs)
    )
    existing = {r['trade_date'] for r in rows if r['cnt'] >= min_count}
    missing = [d for d in all_dates if d.strftime('%Y%m%d') not in existing]
    return missing


def backfill_batched(start_date: datetime, end_date: datetime, batch_size: int = 500):
    """分批处理股票的因子补全"""
    config = PrecomputeConfig(
        workers=1,
        use_parallel=False,
        skip_existing=False,  # 我们自己控制跳过逻辑
        min_stock_count=1     # 允许小批量
    )
    pc = FactorPrecomputer(config=config)

    # 获取缺失日期
    logger.info(f"检查 {start_date.date()} 至 {end_date.date()} 的缺失日期...")
    missing_dates = get_missing_dates(start_date, end_date, min_count=1000)
    logger.info(f"需要补全: {len(missing_dates)} 个交易日")

    if not missing_dates:
        print("✅ 所有日期已完整，无需补全")
        return {"status": "skipped", "total_dates": 0}

    total_start = time.time()
    success = 0
    failed = 0
    failed_dates = []

    for i, trade_date in enumerate(missing_dates):
        date_str = trade_date.strftime('%Y%m%d')
        day_start = time.time()

        try:
            # 获取当天全量股票池
            stock_pool = pc._get_all_stocks(trade_date)
            if len(stock_pool) < 100:
                logger.warning(f"[{i+1}/{len(missing_dates)}] {date_str}: 股票数量不足 ({len(stock_pool)})")
                failed += 1
                failed_dates.append(date_str)
                continue

            # 分批处理
            total_rows = 0
            for j in range(0, len(stock_pool), batch_size):
                batch = stock_pool[j:j + batch_size]
                result = pc.precompute_for_date(trade_date, stock_pool=batch)
                if result.get('status') == 'success':
                    total_rows += result.get('rows_inserted', 0)

            day_elapsed = time.time() - day_start
            total_elapsed = time.time() - total_start
            avg_time = total_elapsed / (i + 1)
            eta = avg_time * (len(missing_dates) - i - 1)

            print(f"[{i+1}/{len(missing_dates)}] {date_str}: "
                  f"{len(stock_pool)}股 -> {total_rows}行 "
                  f"({day_elapsed:.1f}s | ETA: {eta/60:.1f}m)")
            success += 1

        except Exception as e:
            logger.error(f"[{i+1}/{len(missing_dates)}] {date_str} 失败: {e}")
            failed += 1
            failed_dates.append(date_str)

    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"补全完成: 成功 {success}, 失败 {failed}")
    print(f"总耗时: {total_time/60:.1f} 分钟")
    if failed_dates:
        print(f"失败日期: {failed_dates}")

    return {
        "status": "success",
        "total_dates": len(missing_dates),
        "success": success,
        "failed": failed,
        "failed_dates": failed_dates,
        "total_seconds": total_time
    }


def main():
    parser = argparse.ArgumentParser(description="分批因子补全脚本")
    parser.add_argument("--start", default="2025-06-04", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", default="2026-03-20", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--batch-size", type=int, default=500, help="每批股票数量")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    print(f"{'='*60}")
    print(f"因子补全任务")
    print(f"日期范围: {args.start} ~ {args.end}")
    print(f"批次大小: {args.batch_size} 股/批")
    print(f"{'='*60}")

    result = backfill_batched(start_date, end_date, batch_size=args.batch_size)
    return 0 if result.get('failed', 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
