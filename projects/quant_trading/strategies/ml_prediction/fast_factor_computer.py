"""
快速因子计算器 - 使用Python向量化计算替代SQL窗口函数

优化策略：
1. 批量加载历史数据（260天）到内存
2. 使用pandas向量化计算所有窗口函数
3. 避免SQL复杂JOIN和嵌套窗口函数
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FastComputeConfig:
    """快速计算配置"""
    max_window: int = 250  # 最大窗口天数
    workers: int = 6
    batch_size: int = 1000


class FastFactorComputer:
    """
    快速因子计算器

    核心优化：
    - 单次查询加载所有历史数据
    - pandas向量化计算窗口函数
    - 避免SQL窗口函数嵌套
    """

    def __init__(self, config: Optional[FastComputeConfig] = None):
        self.config = config or FastComputeConfig()

    def compute_factors_for_dates(
        self,
        trade_dates: List[datetime],
        stock_pool: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        为多个日期批量计算因子

        优化：一次性加载所有需要的日期范围数据
        """
        if not trade_dates:
            return {}

        # 确定数据范围
        min_date = min(trade_dates) - timedelta(days=self.config.max_window + 10)
        max_date = max(trade_dates)

        logger.info(f"Loading data from {min_date.date()} to {max_date.date()}")

        # 获取股票池
        if stock_pool is None:
            stock_pool = self._get_stock_pool(max_date)

        # 批量加载所有原始数据
        price_data = self._load_price_data(min_date, max_date, stock_pool)
        valuation_data = self._load_valuation_data(trade_dates, stock_pool)
        moneyflow_data = self._load_moneyflow_data(min_date, max_date, stock_pool)
        financial_data = self._load_financial_data(max_date, stock_pool)

        logger.info(f"Loaded: price={len(price_data)}, valuation={len(valuation_data)}, "
                   f"moneyflow={len(moneyflow_data)}, financial={len(financial_data)}")

        # 为每个日期计算因子
        results = {}
        for trade_date in trade_dates:
            factors_df = self._compute_factors_for_date(
                trade_date, stock_pool, price_data, valuation_data,
                moneyflow_data, financial_data
            )
            if not factors_df.empty:
                results[trade_date.strftime('%Y%m%d')] = factors_df

        return results

    def _load_price_data(
        self, start_date: datetime, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """加载价格数据"""
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        placeholders = ','.join(['%s'] * len(stock_pool))

        sql = f"""
            SELECT ts_code, trade_date, open, high, low, close, vol, amount, pct_chg
            FROM t_stock_dailymarketdata
            WHERE trade_date BETWEEN %s AND %s
              AND ts_code IN ({placeholders})
            ORDER BY ts_code, trade_date
        """

        results = DatabaseManager.fetchall(
            'tushare_biz', sql,
            (start_str, end_str) + tuple(stock_pool)
        )

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        return df

    def _load_valuation_data(
        self, trade_dates: List[datetime], stock_pool: List[str]
    ) -> pd.DataFrame:
        """加载估值数据（只需要具体日期）"""
        date_strs = [d.strftime('%Y%m%d') for d in trade_dates]
        placeholders_dates = ','.join(['%s'] * len(date_strs))
        placeholders_stocks = ','.join(['%s'] * len(stock_pool))

        sql = f"""
            SELECT ts_code, trade_date, pe_ttm, pb, ps_ttm, dv_ttm,
                   total_mv, circ_mv, turnover_rate, turnover_rate_f
            FROM t_stock_daily_basic
            WHERE trade_date IN ({placeholders_dates})
              AND ts_code IN ({placeholders_stocks})
        """

        results = DatabaseManager.fetchall(
            'tushare_biz', sql,
            tuple(date_strs) + tuple(stock_pool)
        )

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        return df

    def _load_moneyflow_data(
        self, start_date: datetime, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """加载资金流数据"""
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        placeholders = ','.join(['%s'] * len(stock_pool))

        sql = f"""
            SELECT ts_code, trade_date, buy_lg_amount, sell_lg_amount
            FROM t_stock_moneyflow
            WHERE trade_date BETWEEN %s AND %s
              AND ts_code IN ({placeholders})
            ORDER BY ts_code, trade_date
        """

        results = DatabaseManager.fetchall(
            'tushare_biz', sql,
            (start_str, end_str) + tuple(stock_pool)
        )

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        return df

    def _load_financial_data(
        self, end_date: datetime, stock_pool: List[str]
    ) -> pd.DataFrame:
        """加载财务数据（每个股票最新一条）"""
        end_str = end_date.strftime('%Y%m%d')
        placeholders = ','.join(['%s'] * len(stock_pool))

        sql = f"""
            SELECT ts_code, roe, roa, gross_profit_margin, net_profit_margin,
                   debt_to_assets, current_ratio, quick_ratio, asset_turnover,
                   ca_turnover, basic_eps_yoy, bps_yoy
            FROM t_stock_fina_indicator
            WHERE (ts_code, end_date) IN (
                SELECT ts_code, MAX(end_date)
                FROM t_stock_fina_indicator
                WHERE end_date <= %s
                GROUP BY ts_code
            )
            AND ts_code IN ({placeholders})
        """

        results = DatabaseManager.fetchall(
            'tushare_biz', sql,
            (end_str,) + tuple(stock_pool)
        )

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results)

    def _compute_factors_for_date(
        self,
        trade_date: datetime,
        stock_pool: List[str],
        price_data: pd.DataFrame,
        valuation_data: pd.DataFrame,
        moneyflow_data: pd.DataFrame,
        financial_data: pd.DataFrame
    ) -> pd.DataFrame:
        """为单个日期计算所有因子"""
        date_str = trade_date.strftime('%Y%m%d')

        # 筛选截至当日的价格数据
        price_hist = price_data[price_data['trade_date'] <= trade_date].copy()

        if price_hist.empty:
            return pd.DataFrame()

        # 计算所有因子
        factors_list = []

        for ts_code in stock_pool:
            stock_price = price_hist[price_hist['ts_code'] == ts_code].sort_values('trade_date')

            if len(stock_price) < 2:
                continue

            factors = self._compute_price_factors(stock_price)
            factors['ts_code'] = ts_code
            factors_list.append(factors)

        if not factors_list:
            return pd.DataFrame()

        # 合并所有股票的因子
        factors_df = pd.DataFrame(factors_list).set_index('ts_code')

        # 添加估值因子
        val_today = valuation_data[valuation_data['trade_date'] == trade_date]
        if not val_today.empty:
            val_factors = self._compute_valuation_factors(val_today)
            factors_df = factors_df.join(val_factors, how='left')

        # 添加资金流因子
        mf_hist = moneyflow_data[moneyflow_data['trade_date'] <= trade_date]
        if not mf_hist.empty:
            mf_factors = self._compute_moneyflow_factors(mf_hist, trade_date)
            factors_df = factors_df.join(mf_factors, how='left')

        # 添加财务因子
        if not financial_data.empty:
            factors_df = factors_df.join(financial_data.set_index('ts_code'), how='left')

        return factors_df

    def _compute_price_factors(self, df: pd.DataFrame) -> Dict:
        """计算价格相关因子（向量化）"""
        close = df['close'].astype(float).values
        pct_chg = df['pct_chg'].fillna(0).astype(float).values
        vol = df['vol'].astype(float).values
        high = df['high'].astype(float).values
        low = df['low'].astype(float).values

        factors = {}

        # 收益率因子
        if len(close) >= 5:
            factors['return_5d'] = close[-1] / close[-5] - 1
        if len(close) >= 10:
            factors['return_10d'] = close[-1] / close[-10] - 1
        if len(close) >= 20:
            factors['return_20d'] = close[-1] / close[-20] - 1
        if len(close) >= 60:
            factors['return_60d'] = close[-1] / close[-60] - 1
        if len(close) >= 120:
            factors['return_120d'] = close[-1] / close[-120] - 1
        if len(close) >= 250:
            factors['return_250d'] = close[-1] / close[-250] - 1

        # 波动率因子
        pct_chg = np.array([float(x) if x is not None else 0.0 for x in pct_chg])

        def calc_volatility(pct, window):
            if len(pct) >= window:
                return float(pct[-window:].std()) * np.sqrt(252)
            return np.nan

        factors['volatility_5d'] = calc_volatility(pct_chg, 5)
        factors['volatility_10d'] = calc_volatility(pct_chg, 10)
        factors['volatility_20d'] = calc_volatility(pct_chg, 20)
        factors['volatility_60d'] = calc_volatility(pct_chg, 60)
        factors['volatility_120d'] = calc_volatility(pct_chg, 120)
        factors['volatility_250d'] = calc_volatility(pct_chg, 250)

        # 成交量因子
        if len(vol) >= 20:
            factors['turnover_20d'] = vol[-20:].mean()
        if len(vol) >= 5 and len(vol) >= 20:
            factors['volume_ratio'] = vol[-5:].mean() / vol[-20:].mean()

        # 价格位置
        if len(high) >= 20 and len(low) >= 20:
            hh = high[-20:].max()
            ll = low[-20:].min()
            factors['price_position_20d'] = (close[-1] - ll) / (hh - ll) if hh > ll else 0.5

        return factors

    def _compute_valuation_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算估值因子"""
        result = pd.DataFrame(index=df['ts_code'])

        def to_float(col):
            return pd.to_numeric(col, errors='coerce').astype(float).values

        total_mv = to_float(df['total_mv'])
        pe_ttm = to_float(df['pe_ttm'])
        pb = to_float(df['pb'])

        result['pe_ttm'] = pe_ttm
        result['pb'] = to_float(df['pb'])
        result['ps_ttm'] = to_float(df['ps_ttm'])
        result['dividend_yield'] = to_float(df['dv_ttm'])
        result['total_mv'] = total_mv * 10000
        result['circ_mv'] = to_float(df['circ_mv']) * 10000
        result['log_mv'] = np.log(np.where(total_mv > 0, total_mv * 10000, np.nan))
        result['ep_ttm'] = 1 / np.where(pe_ttm > 0, pe_ttm, np.nan)
        result['bp'] = 1 / np.where(pb > 0, pb, np.nan)
        result['turnover_rate'] = to_float(df['turnover_rate'])
        result['turnover_rate_f'] = to_float(df['turnover_rate_f'])

        return result

    def _compute_moneyflow_factors(
        self, df: pd.DataFrame, trade_date: datetime
    ) -> pd.DataFrame:
        """计算资金流因子"""
        results = []

        for ts_code in df['ts_code'].unique():
            stock_df = df[df['ts_code'] == ts_code].sort_values('trade_date')

            if stock_df.empty:
                continue

            factors = {'ts_code': ts_code}
            net_inflow = stock_df['buy_lg_amount'] - stock_df['sell_lg_amount']

            factors['main_net_inflow'] = net_inflow.iloc[-1] if len(net_inflow) > 0 else np.nan
            factors['large_order_net_amount'] = net_inflow.iloc[-1] if len(net_inflow) > 0 else np.nan

            if len(net_inflow) >= 5:
                factors['net_inflow_5d'] = net_inflow[-5:].sum()
            if len(net_inflow) >= 20:
                factors['net_inflow_20d'] = net_inflow[-20:].sum()

            results.append(factors)

        return pd.DataFrame(results).set_index('ts_code') if results else pd.DataFrame()

    def _get_stock_pool(self, date: datetime) -> List[str]:
        """获取股票池"""
        date_str = date.strftime('%Y%m%d')

        results = DatabaseManager.fetchall(
            'tushare_biz',
            """
            SELECT ts_code FROM t_stock_basic
            WHERE list_status = 'L'
            AND list_date <= %s
            AND (delist_date IS NULL OR delist_date > %s)
            """,
            (date_str, date_str)
        )

        return [r['ts_code'] for r in results]


class ParallelFastComputer:
    """并行快速计算器"""

    def __init__(self, config: Optional[FastComputeConfig] = None):
        self.config = config or FastComputeConfig()

    def compute_batch(
        self,
        trade_dates: List[datetime],
        stock_pool: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        并行批量计算

        策略：将日期分成多个批次，每个进程处理一批
        """
        if not trade_dates:
            return {}

        # 分批次
        chunk_size = max(1, len(trade_dates) // self.config.workers)
        chunks = [trade_dates[i:i + chunk_size] for i in range(0, len(trade_dates), chunk_size)]

        logger.info(f"Processing {len(trade_dates)} dates in {len(chunks)} chunks with {self.config.workers} workers")

        results = {}

        # 使用进程池
        with ProcessPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {
                executor.submit(self._compute_chunk, chunk, stock_pool): i
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    chunk_results = future.result()
                    results.update(chunk_results)
                    logger.info(f"Chunk {chunk_idx + 1}/{len(chunks)} completed: {len(chunk_results)} dates")
                except Exception as e:
                    logger.error(f"Chunk {chunk_idx + 1} failed: {e}")

        return results

    def _compute_chunk(
        self,
        trade_dates: List[datetime],
        stock_pool: Optional[List[str]]
    ) -> Dict[str, pd.DataFrame]:
        """计算一个批次"""
        computer = FastFactorComputer(self.config)
        return computer.compute_factors_for_dates(trade_dates, stock_pool)


if __name__ == "__main__":
    # 测试
    config = FastComputeConfig(workers=4)
    computer = FastFactorComputer(config)

    # 测试3个日期
    test_dates = [
        datetime(2025, 1, 2),
        datetime(2025, 1, 3),
        datetime(2025, 1, 6),
    ]

    import time
    start = time.time()
    results = computer.compute_factors_for_dates(test_dates)
    elapsed = time.time() - start

    print(f"\nComputed {len(results)} dates in {elapsed:.2f}s")
    for date_str, df in results.items():
        print(f"  {date_str}: {len(df)} stocks, {len(df.columns)} factors")
