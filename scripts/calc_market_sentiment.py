#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪指标计算脚本
基于t_stock_dailymarketdata和t_stock_dailylimitprice计算市场情绪
"""

import os
import sys
import pymysql
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 配置日志
def setup_logging(log_file=None):
    logger = logging.getLogger("market_sentiment")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'KKR_cs123'),
        database='tushare_biz',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def calculate_sentiment(logger, start_date='20050101', end_date=None):
    """计算市场情绪指标"""
    
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    
    logger.info(f"开始计算市场情绪指标: {start_date} - {end_date}")
    
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            # 获取所有交易日
            cursor.execute("""
                SELECT DISTINCT trade_date 
                FROM t_stock_dailymarketdata 
                WHERE trade_date BETWEEN %s AND %s
                ORDER BY trade_date
            """, (start_date, end_date))
            
            trade_dates = [row['trade_date'] for row in cursor.fetchall()]
        
        logger.info(f"需要处理 {len(trade_dates)} 个交易日")
        
        total_inserted = 0
        
        for i, trade_date in enumerate(trade_dates, 1):
            try:
                with conn.cursor() as cursor:
                    # 1. 获取当日涨跌统计
                    cursor.execute("""
                        SELECT 
                            SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as rise_count,
                            SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as fall_count,
                            SUM(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END) as flat_count,
                            AVG(pct_chg) as avg_pct_chg,
                            SUM(amount) as total_amount
                        FROM t_stock_dailymarketdata
                        WHERE trade_date = %s
                    """, (trade_date,))
                    
                    row = cursor.fetchone()
                    rise_count = row['rise_count'] or 0
                    fall_count = row['fall_count'] or 0
                    flat_count = row['flat_count'] or 0
                    avg_pct_chg = row['avg_pct_chg'] or 0
                    total_amount = row['total_amount'] or 0
                    
                    # 2. 获取涨跌停统计 (使用涨跌价格表更准确)
                    cursor.execute("""
                        SELECT COUNT(*) as limit_up_count
                        FROM t_stock_dailylimitprice
                        WHERE trade_date = %s AND up_limit IS NOT NULL
                    """, (trade_date,))
                    row = cursor.fetchone()
                    limit_up_count = row['limit_up_count'] if row else 0
                    
                    cursor.execute("""
                        SELECT COUNT(*) as limit_down_count
                        FROM t_stock_dailylimitprice
                        WHERE trade_date = %s AND down_limit IS NOT NULL
                    """, (trade_date,))
                    row = cursor.fetchone()
                    limit_down_count = row['limit_down_count'] if row else 0
                    
                    # 如果没有涨跌停表数据，用涨跌幅估算
                    if limit_up_count == 0 and limit_down_count == 0:
                        cursor.execute("""
                            SELECT 
                                SUM(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up,
                                SUM(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down
                            FROM t_stock_dailymarketdata
                            WHERE trade_date = %s
                        """, (trade_date,))
                        row = cursor.fetchone()
                        limit_up_count = row['limit_up'] or 0
                        limit_down_count = row['limit_down'] or 0
                    
                    # 3. 获取成交额5日均值
                    cursor.execute("""
                        SELECT AVG(daily_amount) as amount_ma5
                        FROM (
                            SELECT trade_date, SUM(amount) as daily_amount
                            FROM t_stock_dailymarketdata
                            WHERE trade_date <= %s
                            GROUP BY trade_date
                            ORDER BY trade_date DESC
                            LIMIT 5
                        ) t
                    """, (trade_date,))
                    
                    row = cursor.fetchone()
                    amount_ma5 = row['amount_ma5'] if row and row['amount_ma5'] else total_amount
                    amount_ratio = (total_amount / amount_ma5) if amount_ma5 > 0 else 1
                    
                    # 4. 获取北向资金
                    cursor.execute("""
                        SELECT north_money
                        FROM t_stock_moneyflow_market
                        WHERE trade_date = %s
                    """, (trade_date,))
                    
                    row = cursor.fetchone()
                    north_money_in = row['north_money'] if row else 0
                    north_money_cum = north_money_in  # 简化处理
                    
                    # 计算情绪分数
                    base_score = (avg_pct_chg * 10) if avg_pct_chg else 0
                    
                    total_active = rise_count + fall_count
                    if total_active > 0:
                        rf_ratio_adj = (rise_count - fall_count) / total_active * 20
                    else:
                        rf_ratio_adj = 0
                    
                    if limit_up_count + limit_down_count > 0:
                        ld_ratio_adj = (limit_up_count - limit_down_count) / (limit_up_count + limit_down_count) * 10
                    else:
                        ld_ratio_adj = 0
                    
                    sentiment_score = base_score + rf_ratio_adj + ld_ratio_adj
                    sentiment_score = max(-100, min(100, sentiment_score))
                    
                    # 情绪等级
                    if sentiment_score >= 80:
                        sentiment_level = '极度乐观'
                    elif sentiment_score >= 40:
                        sentiment_level = '乐观'
                    elif sentiment_score >= -40:
                        sentiment_level = '中性'
                    elif sentiment_score >= -80:
                        sentiment_level = '恐慌'
                    else:
                        sentiment_level = '极度恐慌'
                    
                    rise_fall_ratio = rise_count / fall_count if fall_count > 0 else rise_count
                    limit_up_down_ratio = limit_up_count / limit_down_count if limit_down_count > 0 else limit_up_count
                    
                    # 插入数据
                    cursor.execute("""
                        INSERT INTO t_market_sentiment 
                        (trade_date, rise_count, fall_count, flat_count, rise_fall_ratio,
                         limit_up_count, limit_down_count, limit_up_down_ratio,
                         total_amount, amount_ma5, amount_ratio,
                         north_money_in, north_money_cum,
                         sentiment_score, sentiment_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        rise_count=VALUES(rise_count), fall_count=VALUES(fall_count), flat_count=VALUES(flat_count),
                        rise_fall_ratio=VALUES(rise_fall_ratio), limit_up_count=VALUES(limit_up_count),
                        limit_down_count=VALUES(limit_down_count), limit_up_down_ratio=VALUES(limit_up_down_ratio),
                        total_amount=VALUES(total_amount), amount_ma5=VALUES(amount_ma5), amount_ratio=VALUES(amount_ratio),
                        north_money_in=VALUES(north_money_in), north_money_cum=VALUES(north_money_cum),
                        sentiment_score=VALUES(sentiment_score), sentiment_level=VALUES(sentiment_level)
                    """, (trade_date, rise_count, fall_count, flat_count, rise_fall_ratio,
                          limit_up_count, limit_down_count, limit_up_down_ratio,
                          total_amount / 1e8, amount_ma5 / 1e8, amount_ratio,
                          north_money_in, north_money_cum,
                          sentiment_score, sentiment_level))
                    
                    conn.commit()
                
                total_inserted += 1
                
                if i % 100 == 0:
                    logger.info(f"  进度: {i}/{len(trade_dates)} 天, 情绪分数: {sentiment_score:.1f}")
                
            except Exception as e:
                logger.error(f"  处理 {trade_date} 失败: {e}")
                continue
        
        logger.info(f"完成! 共插入 {total_inserted} 条情绪指标")
        
    finally:
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='计算市场情绪指标')
    parser.add_argument('--start-date', default='20050101', help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', help='结束日期 (YYYYMMDD)，默认今天')
    parser.add_argument('--log-file', help='日志文件路径')
    args = parser.parse_args()
    
    logger = setup_logging(args.log_file)
    
    end_date = args.end_date if args.end_date else datetime.now().strftime('%Y%m%d')
    
    calculate_sentiment(logger, args.start_date, end_date)


if __name__ == "__main__":
    main()
