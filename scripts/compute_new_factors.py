"""
新增因子计算脚本 - Phase 2
计算并回填以下因子到 t_precomputed_factors:
- KDJ (K, D, J)
- RSI (6日, 12日, 24日)
- OBV normalized
- Amihud 非流动性
- Amount normalized (log成交额)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


def compute_kdj(high: pd.Series, low: pd.Series, close: pd.Series,
                n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """计算KDJ指标"""
    llv = low.rolling(n).min()
    hhv = high.rolling(n).max()
    rsv = (close - llv) / (hhv - llv + 1e-10) * 100
    rsv = rsv.fillna(50)

    k = pd.Series(index=close.index, dtype=float)
    d = pd.Series(index=close.index, dtype=float)

    k.iloc[0] = 50.0
    d.iloc[0] = 50.0
    for i in range(1, len(close)):
        k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
        d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]

    j = 3 * k - 2 * d
    return pd.DataFrame({'kdj_k': k, 'kdj_d': d, 'kdj_j': j})


def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """计算RSI指标"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_obv_norm(close: pd.Series, volume: pd.Series, window: int = 20) -> pd.Series:
    """计算OBV并做滚动Z-score标准化"""
    direction = np.sign(close.diff().fillna(0))
    obv = (volume * direction).cumsum()
    obv_mean = obv.rolling(window).mean()
    obv_std = obv.rolling(window).std()
    return (obv - obv_mean) / (obv_std + 1e-10)


def compute_amihud(close: pd.Series, amount: pd.Series, window: int = 20) -> pd.Series:
    """计算Amihud非流动性指标 = |daily_return| / amount, 滚动均值"""
    returns = close.pct_change().abs()
    amihud_daily = returns / (amount + 1e-10)
    # 滚动均值并取log
    amihud_roll = amihud_daily.rolling(window).mean()
    return np.log1p(amihud_roll * 1e6)  # scale up for readability


def compute_amount_norm(amount: pd.Series, window: int = 20) -> pd.Series:
    """成交额对数化+Z-score标准化"""
    log_amount = np.log1p(amount)
    mean = log_amount.rolling(window).mean()
    std = log_amount.rolling(window).std()
    return (log_amount - mean) / (std + 1e-10)


def compute_new_factors_for_stock(ts_code: str, price_df: pd.DataFrame) -> pd.DataFrame:
    """为单只股票计算所有新增因子"""
    if len(price_df) < 30:
        return pd.DataFrame()

    price_df = price_df.sort_values('trade_date').copy()

    close = price_df['close']
    high = price_df['high']
    low = price_df['low']
    vol = price_df['vol']
    amount = price_df['amount']

    # KDJ
    kdj_df = compute_kdj(high, low, close)
    price_df['kdj_k'] = kdj_df['kdj_k']
    price_df['kdj_d'] = kdj_df['kdj_d']
    price_df['kdj_j'] = kdj_df['kdj_j']

    # RSI variants
    price_df['rsi_6d'] = compute_rsi(close, 6)
    price_df['rsi_12d'] = compute_rsi(close, 12)
    price_df['rsi_24d'] = compute_rsi(close, 24)

    # OBV normalized
    price_df['obv_norm'] = compute_obv_norm(close, vol)

    # Amihud
    price_df['amihud'] = compute_amihud(close, amount)

    # Amount normalized
    price_df['amount_norm'] = compute_amount_norm(amount)

    result_cols = ['trade_date', 'ts_code', 'kdj_k', 'kdj_d', 'kdj_j',
                   'rsi_6d', 'rsi_12d', 'rsi_24d', 'obv_norm', 'amihud', 'amount_norm']
    return price_df[result_cols].dropna(subset=['kdj_k'])


def load_price_data(start_date: str, end_date: str,
                    stock_pool: Optional[List[str]] = None) -> pd.DataFrame:
    """加载价格数据"""
    stock_filter = ""
    if stock_pool:
        codes = "','".join(stock_pool)
        stock_filter = f" AND ts_code IN ('{codes}')"

    sql = f"""
    SELECT ts_code, trade_date, open, high, low, close, vol, amount
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    {stock_filter}
    ORDER BY ts_code, trade_date
    """
    return pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))


def update_factors_batch(records: List[dict]) -> int:
    """批量更新因子到数据库"""
    if not records:
        return 0

    sql = """
    UPDATE t_precomputed_factors
    SET kdj_k=%s, kdj_d=%s, kdj_j=%s,
        rsi_6d=%s, rsi_12d=%s, rsi_24d=%s,
        obv_norm=%s, amihud=%s, amount_norm=%s
    WHERE ts_code=%s AND trade_date=%s
    """
    params = [
        (r['kdj_k'], r['kdj_d'], r['kdj_j'],
         r['rsi_6d'], r['rsi_12d'], r['rsi_24d'],
         r['obv_norm'], r['amihud'], r['amount_norm'],
         r['ts_code'], r['trade_date'])
        for r in records
    ]

    with DatabaseManager.get_connection('interface') as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(sql, params)
            conn.commit()
            return len(params)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()


def main():
    """主函数 - 分批计算并回填新因子"""
    # 计算范围：所有有precomputed_factors的数据
    # 但需要从更早日期加载价格数据用于指标热身
    WARMUP_DAYS = 30  # 额外加载30天用于指标热身
    START_DATE = '20091001'  # 比precomputed_factors最早日期早一些
    END_DATE = '20260320'

    logger.info(f"Phase 2: Computing new factors {START_DATE} -> {END_DATE}")

    # 获取所有股票列表（有precomputed_factors记录的）
    res = DatabaseManager.fetchall('interface',
        "SELECT DISTINCT ts_code FROM t_precomputed_factors ORDER BY ts_code")
    all_stocks = [r['ts_code'] for r in res]
    logger.info(f"Total stocks: {len(all_stocks)}")

    # 分批处理（每批500只股票）
    BATCH_SIZE = 500
    total_updated = 0

    for batch_start in range(0, len(all_stocks), BATCH_SIZE):
        batch_stocks = all_stocks[batch_start:batch_start + BATCH_SIZE]
        logger.info(f"Processing batch {batch_start//BATCH_SIZE + 1}/{(len(all_stocks)-1)//BATCH_SIZE + 1}: "
                   f"{batch_stocks[0]} ... {batch_stocks[-1]}")

        # 加载这批股票的价格数据（含热身期）
        price_df = load_price_data(START_DATE, END_DATE, batch_stocks)

        if price_df.empty:
            continue

        price_df['trade_date'] = price_df['trade_date'].astype(str)
        price_df['close'] = pd.to_numeric(price_df['close'], errors='coerce')
        price_df['high'] = pd.to_numeric(price_df['high'], errors='coerce')
        price_df['low'] = pd.to_numeric(price_df['low'], errors='coerce')
        price_df['vol'] = pd.to_numeric(price_df['vol'], errors='coerce').fillna(0)
        price_df['amount'] = pd.to_numeric(price_df['amount'], errors='coerce').fillna(0)

        # 逐股计算
        all_records = []
        for ts_code, stock_price in price_df.groupby('ts_code'):
            factor_df = compute_new_factors_for_stock(ts_code, stock_price)
            if not factor_df.empty:
                # 只保留需要更新的记录（precomputed_factors里存在的）
                for _, row in factor_df.iterrows():
                    record = {
                        'ts_code': row['ts_code'],
                        'trade_date': row['trade_date'],
                        'kdj_k': None if pd.isna(row['kdj_k']) else float(row['kdj_k']),
                        'kdj_d': None if pd.isna(row['kdj_d']) else float(row['kdj_d']),
                        'kdj_j': None if pd.isna(row['kdj_j']) else float(row['kdj_j']),
                        'rsi_6d': None if pd.isna(row['rsi_6d']) else float(row['rsi_6d']),
                        'rsi_12d': None if pd.isna(row['rsi_12d']) else float(row['rsi_12d']),
                        'rsi_24d': None if pd.isna(row['rsi_24d']) else float(row['rsi_24d']),
                        'obv_norm': None if pd.isna(row['obv_norm']) else float(row['obv_norm']),
                        'amihud': None if pd.isna(row['amihud']) else float(row['amihud']),
                        'amount_norm': None if pd.isna(row['amount_norm']) else float(row['amount_norm']),
                    }
                    all_records.append(record)

        # 批量更新数据库
        if all_records:
            updated = update_factors_batch(all_records)
            total_updated += updated
            logger.info(f"  Updated {updated} records, total so far: {total_updated}")

    logger.info(f"Phase 2 complete. Total updated: {total_updated} records")
    return total_updated


if __name__ == '__main__':
    main()
