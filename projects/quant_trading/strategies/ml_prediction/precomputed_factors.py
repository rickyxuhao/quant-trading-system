"""
预计算因子模块 - 每日批量计算并存储

存储策略:
1. 基本面因子: PE/PB/ROE等 - 每日收盘后预计算
2. 资金流因子: 大单净流入等 - 每日收盘后预计算
3. 技术指标: RSI/MACD等 - 回测时实时计算(变化快)

表设计: t_precomputed_factors
- trade_date (日期索引)
- ts_code (股票代码索引)
- factor_xxx (40个预计算因子)

优点:
- 回测速度提升10倍以上
- 因子一致性保证
- 支持并行回测
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager

logger = get_logger(__name__)


# 预计算因子列表 (存储在数据库中)
PRECOMPUTED_FACTOR_SCHEMA = {
    # 估值因子 (8个)
    "pe_ttm": "FLOAT",
    "pb": "FLOAT",
    "ps_ttm": "FLOAT",
    "pcf": "FLOAT",
    "dividend_yield": "FLOAT",
    "total_mv": "FLOAT",  # 总市值
    "circ_mv": "FLOAT",   # 流通市值
    "log_mv": "FLOAT",    # 对数市值

    # 盈利能力因子 (5个)
    "roe": "FLOAT",
    "roa": "FLOAT",
    "gross_margin": "FLOAT",
    "net_margin": "FLOAT",
    "operating_margin": "FLOAT",

    # 成长因子 (4个)
    "revenue_yoy": "FLOAT",
    "profit_yoy": "FLOAT",
    "roe_yoy": "FLOAT",
    "asset_growth": "FLOAT",

    # 资金流向因子 (6个)
    "large_order_net_ratio": "FLOAT",
    "main_net_inflow": "FLOAT",
    "retail_net_inflow": "FLOAT",
    "net_inflow_5d": "FLOAT",
    "net_inflow_20d": "FLOAT",

    # 收益特征 (6个)
    "return_20d": "FLOAT",
    "return_60d": "FLOAT",
    "volatility_20d": "FLOAT",
    "volatility_60d": "FLOAT",
    "volume_ratio": "FLOAT",
    "turnover_20d": "FLOAT",

    # 行业相对 (4个)
    "sector_alpha_20d": "FLOAT",
    "sector_alpha_60d": "FLOAT",
    "sector_rank_20d": "FLOAT",
    "sector_rank_60d": "FLOAT",

    # 市场相对 (4个)
    "market_alpha_20d": "FLOAT",
    "market_alpha_60d": "FLOAT",
    "rs_20d_market": "FLOAT",
    "rs_60d_market": "FLOAT",

    # 横截面Z-score (7个核心因子的Z-score)
    "pe_ttm_zscore": "FLOAT",
    "pb_zscore": "FLOAT",
    "roe_zscore": "FLOAT",
    "profit_yoy_zscore": "FLOAT",
    "return_20d_zscore": "FLOAT",
    "volatility_20d_zscore": "FLOAT",
    "market_alpha_20d_zscore": "FLOAT",
}


@dataclass
class PrecomputeConfig:
    """预计算配置"""
    batch_size: int = 500  # 每批处理股票数
    workers: int = 4       # 并行工作数
    lookback_days: int = 60  # 计算收益需要的历史天数


class FactorPrecomputer:
    """
    因子预计算器

    每日收盘后运行，为全市场股票计算因子并入库
    """

    TABLE_NAME = "t_precomputed_factors"
    DB_NAME = "interface"  # 加工数据存入interface库

    def __init__(self, config: Optional[PrecomputeConfig] = None):
        self.config = config or PrecomputeConfig()
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """确保预计算表存在"""
        columns_def = [f"{name} {dtype}" for name, dtype in PRECOMPUTED_FACTOR_SCHEMA.items()]

        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
            trade_date VARCHAR(8) NOT NULL,
            ts_code VARCHAR(16) NOT NULL,
            {', '.join(columns_def)},
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (trade_date, ts_code),
            INDEX idx_trade_date (trade_date),
            INDEX idx_ts_code (ts_code),
            INDEX idx_pe_zscore (trade_date, pe_ttm_zscore),
            INDEX idx_roe_zscore (trade_date, roe_zscore)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """

        try:
            DatabaseManager.execute(self.DB_NAME, create_sql)
            logger.info(f"Table {self.TABLE_NAME} ready")
        except Exception as e:
            logger.error(f"Error creating table: {e}")

    def precompute_for_date(
        self,
        trade_date: datetime,
        stock_pool: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        为指定日期预计算所有因子

        Args:
            trade_date: 交易日
            stock_pool: 股票池(默认全市场)

        Returns:
            统计信息
        """
        from .cross_sectional_features import CrossSectionalFeatureEngineer
        from projects.quant_trading.backtest.data_manager import DataManager

        logger.info(f"Precomputing factors for {trade_date.strftime('%Y%m%d')}")

        # 获取股票池
        if stock_pool is None:
            stock_pool = self._get_all_stocks(trade_date)

        logger.info(f"Stock pool size: {len(stock_pool)}")

        # 分批处理避免内存溢出
        all_results = []
        batch_size = self.config.batch_size
        total_batches = (len(stock_pool) + batch_size - 1) // batch_size

        for i in range(total_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, len(stock_pool))
            batch_stocks = stock_pool[start_idx:end_idx]

            logger.info(f"Processing batch {i+1}/{total_batches}: {len(batch_stocks)} stocks")

            # 计算这批股票的因子
            engineer = CrossSectionalFeatureEngineer(data_manager=DataManager())
            features_df = engineer.create_features_for_universe(
                date=trade_date,
                stock_pool=batch_stocks
            )

            if not features_df.empty:
                # 只保留预计算因子列
                available_cols = set(features_df.columns)
                keep_cols = [c for c in PRECOMPUTED_FACTOR_SCHEMA.keys() if c in available_cols]

                batch_result = features_df[keep_cols].copy()
                batch_result['trade_date'] = trade_date.strftime('%Y%m%d')
                batch_result['ts_code'] = features_df.index

                all_results.append(batch_result)

        if not all_results:
            logger.warning("No factors computed")
            return {"status": "empty", "rows": 0}

        # 合并所有批次
        final_df = pd.concat(all_results, ignore_index=True)

        # 写入数据库
        rows_inserted = self._save_to_db(final_df)

        return {
            "status": "success",
            "trade_date": trade_date.strftime('%Y%m%d'),
            "stocks_processed": len(stock_pool),
            "rows_inserted": rows_inserted
        }

    def _get_all_stocks(self, date: datetime) -> List[str]:
        """获取全市场上市股票"""
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

    def _save_to_db(self, df: pd.DataFrame) -> int:
        """保存到数据库，使用批量插入"""
        if df.empty:
            return 0

        # 构造INSERT ... ON DUPLICATE KEY UPDATE语句
        columns = list(PRECOMPUTED_FACTOR_SCHEMA.keys()) + ['trade_date', 'ts_code']
        columns = [c for c in columns if c in df.columns]

        update_columns = [c for c in columns if c not in ['trade_date', 'ts_code']]

        values_list = []
        for _, row in df.iterrows():
            values = []
            for c in columns:
                val = row.get(c, None)
                # Convert NaN/inf to None for MySQL compatibility
                if val is None:
                    values.append(None)
                elif isinstance(val, float):
                    if np.isnan(val) or np.isinf(val):
                        values.append(None)
                    else:
                        values.append(val)
                else:
                    values.append(val)
            values_list.append(tuple(values))

        # 批量插入
        placeholders = ', '.join(['%s'] * len(columns))
        update_clause = ', '.join([f"{c}=VALUES({c})" for c in update_columns])

        sql = f"""
        INSERT INTO {self.TABLE_NAME} ({', '.join(columns)})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
        """

        try:
            # 分批插入避免SQL过长
            batch_size = 1000
            total_inserted = 0

            for i in range(0, len(values_list), batch_size):
                batch = values_list[i:i+batch_size]
                DatabaseManager.executemany(self.DB_NAME, sql, batch)
                total_inserted += len(batch)

            logger.info(f"Saved {total_inserted} rows to {self.TABLE_NAME}")
            return total_inserted

        except Exception as e:
            logger.error(f"Error saving to DB: {e}")
            return 0

    def get_precomputed_factors(
        self,
        trade_date: datetime,
        stock_pool: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        读取预计算因子

        这是回测时的主要入口，替代实时计算
        """
        date_str = trade_date.strftime('%Y%m%d')

        if stock_pool:
            placeholders = ', '.join(['%s'] * len(stock_pool))
            sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE trade_date = %s AND ts_code IN ({placeholders})
            """
            params = (date_str,) + tuple(stock_pool)
        else:
            sql = f"SELECT * FROM {self.TABLE_NAME} WHERE trade_date = %s"
            params = (date_str,)

        results = DatabaseManager.fetchall(self.DB_NAME, sql, params)

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df.set_index('ts_code', inplace=True)

        # 删除元数据列
        for col in ['updated_at']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        return df

    def batch_precompute(
        self,
        start_date: datetime,
        end_date: datetime,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        批量预计算一段日期范围的因子

        用于历史数据回填，通常在首次部署时运行
        """
        # 获取交易日历
        from projects.quant_trading.backtest.data_manager import DataManager

        trade_dates = DataManager().get_trade_dates(start_date, end_date)

        logger.info(f"Batch precompute: {len(trade_dates)} trading days")

        results = {
            "total_dates": len(trade_dates),
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }

        for date in trade_dates:
            date_str = date.strftime('%Y%m%d')

            # 检查是否已存在
            if skip_existing:
                existing = DatabaseManager.fetchone(
                    self.DB_NAME,
                    f"SELECT COUNT(*) as cnt FROM {self.TABLE_NAME} WHERE trade_date = %s",
                    (date_str,)
                )
                if existing and existing['cnt'] > 3000:  # 假设>3000只股票已计算
                    logger.info(f"Skipping {date_str}, already computed")
                    results["skipped"] += 1
                    continue

            try:
                result = self.precompute_for_date(date)
                if result.get("status") == "success":
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({"date": date_str, **result})

            except Exception as e:
                logger.error(f"Failed to precompute {date_str}: {e}")
                results["failed"] += 1
                results["details"].append({"date": date_str, "status": "error", "error": str(e)})

        logger.info(f"Batch complete: {results['success']} success, {results['skipped']} skipped, {results['failed']} failed")
        return results


def create_precompute_table_ddl() -> str:
    """生成建表SQL，用于数据库迁移"""
    columns = [f"    {name} {dtype}" for name, dtype in PRECOMPUTED_FACTOR_SCHEMA.items()]

    ddl = f"""
-- 预计算因子表
CREATE TABLE IF NOT EXISTS t_precomputed_factors (
    trade_date VARCHAR(8) NOT NULL COMMENT '交易日期YYYYMMDD',
    ts_code VARCHAR(16) NOT NULL COMMENT '股票代码',
{','.join(columns)},
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (trade_date, ts_code),
    KEY idx_trade_date (trade_date),
    KEY idx_ts_code (ts_code),
    KEY idx_pe_zscore (trade_date, pe_ttm_zscore),
    KEY idx_roe_zscore (trade_date, roe_zscore),
    KEY idx_return_zscore (trade_date, return_20d_zscore)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预计算因子表';

-- 估算存储: 4500只股票 × 250天 × 40因子 ≈ 180MB/年
"""
    return ddl


# 使用示例
if __name__ == "__main__":
    # 初始化
    precomputer = FactorPrecomputer()

    # 单日预计算
    # result = precomputer.precompute_for_date(datetime(2024, 1, 15))
    # print(result)

    # 批量预计算 (首次部署)
    # results = precomputer.batch_precompute(
    #     start_date=datetime(2020, 1, 1),
    #     end_date=datetime(2024, 12, 31)
    # )

    # 读取预计算因子
    factors = precomputer.get_precomputed_factors(datetime(2024, 1, 15))
    print(factors.head())
