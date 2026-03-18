#!/usr/bin/env python3
"""
补齐 2010-2024 年因子数据
"""

from datetime import datetime
from projects.quant_trading.strategies.ml_prediction.precomputed_factors import backfill_factors
import time

print('=' * 70)
print('开始补齐 2010-2024 年因子数据')
print('=' * 70)

start = time.time()

# Run backfill
result = backfill_factors(start_year=2010, end_year=2024, workers=4)

elapsed = time.time() - start

print('\n' + '=' * 70)
print('完成！')
print('=' * 70)
print(f'总耗时: {elapsed/60:.1f} 分钟')
print(f'处理日期: {result["total_dates"]}')
print(f'成功: {result["success"]}')
print(f'失败: {result["failed"]}')

# 显示失败的日期
if result['failed'] > 0:
    print('\n失败的日期:')
    for detail in result['details']:
        if detail['status'] != 'success':
            print(f'  {detail}')
