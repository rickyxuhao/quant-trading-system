#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标计算脚本
基于t_stock_dailymarketdata计算技术指标并存储到t_stock_technical
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_sync import init_sync_env


def calculate_ma(prices, window):
    """计算简单移动平均线"""
    return prices.rolling(window=window, min_periods=1).mean()


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    bar = (dif - dea) * 2
    return dif, dea, bar


def calculate_kdj(high, low, close, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    lowest_low = low.rolling(window=n, min_periods=1).min()
    highest_high = high.rolling(window=n, min_periods=1).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j


def calculate_rsi(prices, window=6):
    """计算RSI指标"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window, min_periods=1).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_boll(prices, window=20, num_std=2):
    """计算布林带"""
    mid = prices.rolling(window=window, min_periods=1).mean()
    std = prices.rolling(window=window, min_periods=1).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def calculate_volatility(prices, window=20):
    """计算波动率"""
    log_returns = np.log(prices / prices.shift(1))
    volatility = log_returns.rolling(window=window, min_periods=1).std() * np.sqrt(252)
    return volatility


def process_stock_technical(config, db, logger, start_date='20050101', end_date=None, batch_size=100):
    """处理所有股票的技术指标"""
    
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    
    logger.info(f"开始计算技术指标: {start_date} - {end_date}")
    
    # 获取股票列表
    cursor = db.connection.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM t_stock_dailymarketdata WHERE trade_date BETWEEN %s AND %s", 
                   (start_date, end_date))
    stocks = [row[0] for row in cursor.fetchall()]
    cursor.close()
    
    logger.info(f"需要处理 {len(stocks)} 只股票")
    
    total_processed = 0
    total_inserted = 0
    
    for i, ts_code in enumerate(stocks, 1):
        try:
            # 获取股票历史数据（需要额外250天用于计算年线）
            query_start = (datetime.strptime(start_date, '%Y%m%d') - timedelta(days=400)).strftime('%Y%m%d')
            
            cursor = db.connection.cursor()
            cursor.execute("""
                SELECT trade_date, open, high, low, close, pre_close, vol, amount
                FROM t_stock_dailymarketdata
                WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date
            """, (ts_code, query_start, end_date))
            
            rows = cursor.fetchall()
            cursor.close()
            
            if len(rows) < 20:  # 数据太少，跳过
                continue
            
            # 转换为DataFrame
            df = pd.DataFrame(rows, columns=['trade_date', 'open', 'high', 'low', 'close', 'pre_close', 'vol', 'amount'])
            
            # 计算技术指标
            # 均线
            df['ma5'] = calculate_ma(df['close'], 5)
            df['ma10'] = calculate_ma(df['close'], 10)
            df['ma20'] = calculate_ma(df['close'], 20)
            df['ma60'] = calculate_ma(df['close'], 60)
            df['ma120'] = calculate_ma(df['close'], 120)
            df['ma250'] = calculate_ma(df['close'], 250)
            
            # MACD
            df['macd_dif'], df['macd_dea'], df['macd_bar'] = calculate_macd(df['close'])
            
            # KDJ
            df['kdj_k'], df['kdj_d'], df['kdj_j'] = calculate_kdj(df['high'], df['low'], df['close'])
            
            # RSI
            df['rsi6'] = calculate_rsi(df['close'], 6)
            df['rsi12'] = calculate_rsi(df['close'], 12)
            df['rsi24'] = calculate_rsi(df['close'], 24)
            
            # 布林带
            df['boll_upper'], df['boll_mid'], df['boll_lower'] = calculate_boll(df['close'])
            
            # 成交量均线
            df['vol_ma5'] = calculate_ma(df['vol'], 5)
            df['vol_ma10'] = calculate_ma(df['vol'], 10)
            df['vol_ma20'] = calculate_ma(df['vol'], 20)
            
            # 振幅
            df['amplitude'] = (df['high'] - df['low']) / df['pre_close'] * 100
            
            # 波动率
            df['volatility_20'] = calculate_volatility(df['close'], 20)
            
            # 价量相关系数
            df['price_vol_corr'] = df['close'].rolling(window=10, min_periods=1).corr(df['vol'])
            
            # 趋势强度（收盘价与20日均线偏离度）
            df['trend_strength'] = (df['close'] - df['ma20']) / df['ma20'] * 100
            
            # 过滤到目标日期范围
            df = df[df['trade_date'] >= start_date].copy()
            
            if len(df) == 0:
                continue
            
            # 准备插入数据
            columns = ['ts_code', 'trade_date', 'ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250',
                      'macd_dif', 'macd_dea', 'macd_bar', 'kdj_k', 'kdj_d', 'kdj_j',
                      'rsi6', 'rsi12', 'rsi24', 'boll_upper', 'boll_mid', 'boll_lower',
                      'vol_ma5', 'vol_ma10', 'vol_ma20', 'amplitude', 'volatility_20',
                      'price_vol_corr', 'trend_strength']
            
            df['ts_code'] = ts_code
            df = df[columns]
            
            # 处理NaN值
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.where(pd.notnull(df), None)
            
            # 批量插入
            rows = df.values.tolist()
            
            cursor = db.connection.cursor()
            cursor.executemany("""
                INSERT INTO t_stock_technical 
                (ts_code, trade_date, ma5, ma10, ma20, ma60, ma120, ma250,
                 macd_dif, macd_dea, macd_bar, kdj_k, kdj_d, kdj_j,
                 rsi6, rsi12, rsi24, boll_upper, boll_mid, boll_lower,
                 vol_ma5, vol_ma10, vol_ma20, amplitude, volatility_20,
                 price_vol_corr, trend_strength)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                ma5=VALUES(ma5), ma10=VALUES(ma10), ma20=VALUES(ma20), ma60=VALUES(ma60),
                ma120=VALUES(ma120), ma250=VALUES(ma250),
                macd_dif=VALUES(macd_dif), macd_dea=VALUES(macd_dea), macd_bar=VALUES(macd_bar),
                kdj_k=VALUES(kdj_k), kdj_d=VALUES(kdj_d), kdj_j=VALUES(kdj_j),
                rsi6=VALUES(rsi6), rsi12=VALUES(rsi12), rsi24=VALUES(rsi24),
                boll_upper=VALUES(boll_upper), boll_mid=VALUES(boll_mid), boll_lower=VALUES(boll_lower),
                vol_ma5=VALUES(vol_ma5), vol_ma10=VALUES(vol_ma10), vol_ma20=VALUES(vol_ma20),
                amplitude=VALUES(amplitude), volatility_20=VALUES(volatility_20),
                price_vol_corr=VALUES(price_vol_corr), trend_strength=VALUES(trend_strength)
            """, rows)
            
            db.connection.commit()
            cursor.close()
            
            total_processed += 1
            total_inserted += len(rows)
            
            if total_processed % 100 == 0:
                logger.info(f"  进度: {total_processed}/{len(stocks)} 只股票, 已插入 {total_inserted} 条")
            
        except Exception as e:
            logger.error(f"  处理 {ts_code} 失败: {e}")
            continue
    
    logger.info(f"完成! 处理 {total_processed} 只股票, 共插入 {total_inserted} 条")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='计算股票技术指标')
    parser.add_argument('--start-date', default='20050101', help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', help='结束日期 (YYYYMMDD)，默认今天')
    parser.add_argument('--log-file', help='日志文件路径')
    args = parser.parse_args()
    
    config, db, client, logger = init_sync_env(args.log_file)
    
    end_date = args.end_date if args.end_date else datetime.now().strftime('%Y%m%d')
    
    process_stock_technical(config, db, logger, args.start_date, end_date)


if __name__ == "__main__":
    main()
