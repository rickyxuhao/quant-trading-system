"""
复权价格计算工具
支持前复权（分析用）和后复权（回测用）的动态计算

前复权：以最新价格为基准，历史价格按比例调整
后复权：以历史价格为基准，累计复权因子
"""
from typing import Literal, Optional
import pandas as pd
import numpy as np

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)

AdjType = Literal["forward", "backward"]


def calculate_adjusted_price(
    df: pd.DataFrame,
    adj_factor_df: pd.DataFrame,
    adj_type: AdjType = "forward",
    price_cols: Optional[list] = None
) -> pd.DataFrame:
    """
    计算复权价格

    复权原理：
    - 前复权: adj_price = raw_price * adj_factor / latest_adj_factor
      以最新交易日为基准（最新价格不变），历史价格按比例缩小
      适合：技术分析、近期走势观察

    - 后复权: adj_price = raw_price * adj_factor / first_adj_factor
      以最早交易日为基准（最早价格不变），后续价格按比例放大
      适合：长期收益计算、回测

    Args:
        df: 原始行情数据，需包含 ts_code, trade_date 和价格列
        adj_factor_df: 复权因子数据，需包含 ts_code, trade_date, adj_factor
        adj_type: forward=前复权, backward=后复权
        price_cols: 需要复权的价格列，默认 ["open", "high", "low", "close"]

    Returns:
        添加了 adj_open, adj_high, adj_low, adj_close 列的 DataFrame
    """
    if price_cols is None:
        price_cols = ["open", "high", "low", "close"]

    # 数据验证
    required_cols = ["ts_code", "trade_date"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"原始数据缺少必要列: {col}")
        if col not in adj_factor_df.columns:
            raise ValueError(f"复权因子数据缺少必要列: {col}")

    if "adj_factor" not in adj_factor_df.columns:
        raise ValueError("复权因子数据缺少 adj_factor 列")

    # 确保日期格式一致
    df = df.copy()
    adj_factor_df = adj_factor_df.copy()

    df["trade_date"] = df["trade_date"].astype(str)
    adj_factor_df["trade_date"] = adj_factor_df["trade_date"].astype(str)

    # 合并复权因子（左连接保留所有行情数据）
    merged = df.merge(
        adj_factor_df[["ts_code", "trade_date", "adj_factor"]],
        on=["ts_code", "trade_date"],
        how="left"
    )

    # 检查缺失的复权因子
    missing_factor = merged["adj_factor"].isna()
    if missing_factor.any():
        missing_count = missing_factor.sum()
        logger.warning(f"有 {missing_count} 条记录缺少复权因子，将使用原始价格")
        # 对缺失复权因子的记录，使用 1.0（不复权）
        merged.loc[missing_factor, "adj_factor"] = 1.0

    # 计算复权价格
    # 按股票代码分组计算基准因子
    if adj_type == "forward":
        # 前复权：以每组最新 adj_factor 为基准
        merged["base_factor"] = merged.groupby("ts_code")["adj_factor"].transform("last")
        merged["adj_type"] = "forward"
    else:
        # 后复权：以每组最早 adj_factor 为基准
        merged["base_factor"] = merged.groupby("ts_code")["adj_factor"].transform("first")
        merged["adj_type"] = "backward"

    # 计算复权价格
    for col in price_cols:
        if col in merged.columns:
            # 复权公式：原始价格 * (当前复权因子 / 基准复权因子)
            merged[f"adj_{col}"] = merged[col] * merged["adj_factor"] / merged["base_factor"]

    # 清理中间列
    merged = merged.drop(columns=["base_factor"])

    return merged


def get_adjusted_price_from_db(
    ts_code: str,
    start_date: str,
    end_date: str,
    adj_type: AdjType = "forward",
    db_name: str = "tushare_biz"
) -> pd.DataFrame:
    """
    从数据库查询并计算复权价格

    Args:
        ts_code: 股票代码，如 "000001.SZ"
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        adj_type: forward=前复权, backward=后复权
        db_name: 数据库名称

    Returns:
        包含复权价格的 DataFrame
    """
    logger.info(f"查询 {ts_code} 从 {start_date} 到 {end_date} 的{adj_type}复权数据")

    # 查询日线行情
    price_sql = """
        SELECT ts_code, trade_date, open, high, low, close, vol, amount
        FROM t_stock_dailymarketdata
        WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date
    """
    price_data = DatabaseManager.fetchall(db_name, price_sql, (ts_code, start_date, end_date))

    if not price_data:
        logger.warning(f"未找到 {ts_code} 在指定日期范围的行情数据")
        return pd.DataFrame()

    price_df = pd.DataFrame(price_data)

    # 查询复权因子（扩大日期范围以获取基准因子）
    # 前复权需要最新日期的因子，后复权需要最早日期的因子
    adj_sql = """
        SELECT ts_code, trade_date, adj_factor
        FROM t_stock_adjfactor
        WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date
    """
    adj_data = DatabaseManager.fetchall(db_name, adj_sql, (ts_code, start_date, end_date))

    if not adj_data:
        logger.warning(f"未找到 {ts_code} 的复权因子，返回原始价格")
        return price_df

    adj_df = pd.DataFrame(adj_data)

    # 计算复权价格
    result = calculate_adjusted_price(price_df, adj_df, adj_type)

    logger.info(f"成功计算 {len(result)} 条复权记录")
    return result


def get_batch_adjusted_prices(
    ts_codes: list,
    start_date: str,
    end_date: str,
    adj_type: AdjType = "forward",
    db_name: str = "tushare_biz"
) -> pd.DataFrame:
    """
    批量查询多只股票的复权价格

    Args:
        ts_codes: 股票代码列表
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        adj_type: forward=前复权, backward=后复权
        db_name: 数据库名称

    Returns:
        包含复权价格的 DataFrame
    """
    if not ts_codes:
        return pd.DataFrame()

    logger.info(f"批量查询 {len(ts_codes)} 只股票的复权数据")

    # 构建 IN 查询参数
    placeholders = ', '.join(['%s'] * len(ts_codes))

    # 查询日线行情
    price_sql = f"""
        SELECT ts_code, trade_date, open, high, low, close, vol, amount
        FROM t_stock_dailymarketdata
        WHERE ts_code IN ({placeholders})
        AND trade_date BETWEEN %s AND %s
        ORDER BY ts_code, trade_date
    """
    params = ts_codes + [start_date, end_date]
    price_data = DatabaseManager.fetchall(db_name, price_sql, params)

    if not price_data:
        logger.warning("未找到指定股票的行情数据")
        return pd.DataFrame()

    price_df = pd.DataFrame(price_data)

    # 查询复权因子
    adj_sql = f"""
        SELECT ts_code, trade_date, adj_factor
        FROM t_stock_adjfactor
        WHERE ts_code IN ({placeholders})
        AND trade_date BETWEEN %s AND %s
        ORDER BY ts_code, trade_date
    """
    adj_data = DatabaseManager.fetchall(db_name, adj_sql, params)

    if not adj_data:
        logger.warning("未找到复权因子，返回原始价格")
        return price_df

    adj_df = pd.DataFrame(adj_data)

    # 计算复权价格
    result = calculate_adjusted_price(price_df, adj_df, adj_type)

    logger.info(f"成功计算 {len(result)} 条复权记录")
    return result


def adjust_price_for_split_dividend(
    prices: pd.Series,
    adj_factors: pd.Series,
    adj_type: AdjType = "forward"
) -> pd.Series:
    """
    对单只股票价格序列进行复权调整

    Args:
        prices: 原始价格序列
        adj_factors: 复权因子序列（与prices同长度）
        adj_type: forward=前复权, backward=后复权

    Returns:
        复权后的价格序列
    """
    if len(prices) != len(adj_factors):
        raise ValueError("价格序列和复权因子序列长度不一致")

    if adj_type == "forward":
        base_factor = adj_factors.iloc[-1]  # 最新因子为基准
    else:
        base_factor = adj_factors.iloc[0]   # 最早因子为基准

    return prices * adj_factors / base_factor
