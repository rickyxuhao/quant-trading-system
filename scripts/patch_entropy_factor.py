"""
RFC: 数据补全脚本 - entropy_20d

按照 docs/rfc_data_patch.md 实现：
1. ALTER TABLE 添加 entropy_20d 列
2. 从 tushare_biz.t_stock_dailymarketdata 读取 close+vol
3. 计算 20日成交额分布 Shannon 熵
4. 批量写入 t_precomputed_factors.entropy_20d
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from typing import List, Tuple
from tqdm import tqdm

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)

START_DATE = '20240102'
END_DATE   = '20260320'
WINDOW     = 20
BATCH_SIZE = 300  # 每批股票数
EPS        = 1e-10


def add_entropy_column():
    """添加 entropy_20d 列（如不存在）"""
    try:
        DatabaseManager.execute('interface', '''
            ALTER TABLE t_precomputed_factors
            ADD COLUMN entropy_20d FLOAT DEFAULT NULL
            COMMENT '20日成交额分布Shannon熵，熵越小越集中（卖出信号）'
        ''')
        logger.info("entropy_20d 列已创建")
    except Exception as e:
        if 'Duplicate column' in str(e):
            logger.info("entropy_20d 列已存在，跳过 ALTER")
        else:
            raise


def get_stock_list() -> List[str]:
    """获取有效股票列表"""
    rows = DatabaseManager.fetchall('interface', f'''
        SELECT DISTINCT ts_code FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}'
        ORDER BY ts_code
    ''')
    return [r['ts_code'] for r in rows]


def load_price_data(ts_codes: List[str]) -> pd.DataFrame:
    """加载一批股票的价格和成交量数据（含 WINDOW 天预热期）"""
    placeholders = ','.join(['%s'] * len(ts_codes))
    # 多取 30 天用于窗口预热
    warmup_start = pd.Timestamp(START_DATE) - pd.Timedelta(days=40)
    warmup_str = warmup_start.strftime('%Y%m%d')

    rows = DatabaseManager.fetchall('tushare_biz', f'''
        SELECT ts_code, trade_date, close, vol
        FROM t_stock_dailymarketdata
        WHERE ts_code IN ({placeholders})
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY ts_code, trade_date
    ''', tuple(ts_codes) + (warmup_str, END_DATE))

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['vol']   = pd.to_numeric(df['vol'],   errors='coerce').fillna(0)
    df['trade_date'] = df['trade_date'].astype(str)
    return df


def compute_entropy_batch(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    对一批股票计算 entropy_20d

    Returns:
        DataFrame with [trade_date, ts_code, entropy_20d]
    """
    results = []
    for ts_code, grp in price_df.groupby('ts_code'):
        grp = grp.sort_values('trade_date').copy()
        close = grp['close'].values.astype(float)
        vol   = grp['vol'].values.astype(float)
        dates = grp['trade_date'].values
        n = len(grp)

        entropy_arr = np.full(n, np.nan)

        for i in range(WINDOW - 1, n):
            w_close = close[i - WINDOW + 1: i + 1]
            w_vol   = vol[i - WINDOW + 1: i + 1]
            money   = w_close * w_vol
            total   = money.sum()
            if total < EPS:
                continue
            ratio = money / total
            entropy_arr[i] = -np.sum(ratio * np.log(ratio + EPS))

        grp['entropy_20d'] = entropy_arr
        # 只保留目标日期范围内且有值的行
        valid = grp[(grp['trade_date'] >= START_DATE) & grp['entropy_20d'].notna()]
        if not valid.empty:
            results.append(valid[['trade_date', 'ts_code', 'entropy_20d']])

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def write_entropy_to_db(df: pd.DataFrame) -> int:
    """批量更新 t_precomputed_factors.entropy_20d"""
    if df.empty:
        return 0

    records = df[['trade_date', 'ts_code', 'entropy_20d']].values.tolist()
    updated = 0

    # 分小批写入
    chunk = 5000
    for i in range(0, len(records), chunk):
        batch = records[i: i + chunk]
        cases = ' '.join(
            f"WHEN ts_code='{r[1]}' AND trade_date='{r[0]}' THEN {r[2]}"
            for r in batch
        )
        ts_codes_in = ','.join(f"'{r[1]}'" for r in batch)
        dates_in    = ','.join(f"'{r[0]}'" for r in set((r[0],) for r in batch))

        sql = f'''
            UPDATE t_precomputed_factors
            SET entropy_20d = CASE {cases} END
            WHERE ts_code IN ({ts_codes_in})
              AND trade_date IN ({dates_in})
        '''
        DatabaseManager.execute('interface', sql)
        updated += len(batch)

    return updated


def main():
    logger.info("=== entropy_20d 补全脚本启动 ===")

    # Step 1: 建列
    add_entropy_column()

    # Step 2: 获取股票列表
    stocks = get_stock_list()
    logger.info(f"共 {len(stocks)} 只股票需要处理")

    # Step 3: 分批处理
    total_written = 0
    batches = [stocks[i:i+BATCH_SIZE] for i in range(0, len(stocks), BATCH_SIZE)]

    for idx, batch in enumerate(tqdm(batches, desc="计算 entropy_20d")):
        price_df = load_price_data(batch)
        if price_df.empty:
            continue
        entropy_df = compute_entropy_batch(price_df)
        if entropy_df.empty:
            continue
        written = write_entropy_to_db(entropy_df)
        total_written += written
        if (idx + 1) % 5 == 0:
            logger.info(f"  进度: {idx+1}/{len(batches)} 批，已写入 {total_written} 行")

    logger.info(f"=== 完成，总写入 {total_written} 行 ===")

    # Step 4: 验证
    r = DatabaseManager.fetchall('interface', f'''
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN entropy_20d IS NOT NULL THEN 1 ELSE 0 END) as non_null,
          AVG(entropy_20d) as avg_val,
          MIN(entropy_20d) as min_val,
          MAX(entropy_20d) as max_val
        FROM t_precomputed_factors
        WHERE trade_date >= '{START_DATE}'
    ''')
    stats = r[0]
    non_null_pct = float(stats['non_null']) / float(stats['total']) * 100
    logger.info(f"验证: 非空率={non_null_pct:.1f}%, avg={float(stats['avg_val'] or 0):.4f}, "
                f"range=[{float(stats['min_val'] or 0):.4f}, {float(stats['max_val'] or 0):.4f}]")

    if non_null_pct < 95:
        logger.warning(f"⚠️  非空率 {non_null_pct:.1f}% < 95%，请检查数据质量")
    else:
        logger.info(f"✅ 验证通过，entropy_20d 已完整写入")

    return non_null_pct


if __name__ == '__main__':
    main()
