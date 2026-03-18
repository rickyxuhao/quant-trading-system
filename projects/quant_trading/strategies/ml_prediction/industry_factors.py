"""
行业因子构建模块

基于《A股因子挖掘库构建指南》最佳实践实现：
- 行业指数收益率因子
- 行业内聚合因子（市值加权平均）
- 行业相对因子（行业vs市场）
- 行业轮动信号

用于捕捉行业层面的alpha和构建行业轮动策略。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from collections import defaultdict

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager
from projects.quant_trading.backtest.data_manager import DataManager
from projects.quant_trading.strategies.ml_prediction.precomputed_factors import (
    get_factor_precomputer
)

logger = get_logger(__name__)


@dataclass
class IndustryFactorResult:
    """行业因子计算结果"""
    industry_code: str
    industry_name: str
    trade_date: str

    # 行业收益特征
    industry_return_1d: float
    industry_return_5d: float
    industry_return_20d: float

    # 行业相对强弱
    rs_vs_market_1d: float
    rs_vs_market_5d: float
    rs_vs_market_20d: float

    # 行业动量排名
    rank_5d: int
    rank_20d: int

    # 行业内聚合因子（市值加权）
    aggregated_factors: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'industry_code': self.industry_code,
            'industry_name': self.industry_name,
            'trade_date': self.trade_date,
            'industry_return_1d': self.industry_return_1d,
            'industry_return_5d': self.industry_return_5d,
            'industry_return_20d': self.industry_return_20d,
            'rs_vs_market_1d': self.rs_vs_market_1d,
            'rs_vs_market_5d': self.rs_vs_market_5d,
            'rs_vs_market_20d': self.rs_vs_market_20d,
            'rank_5d': self.rank_5d,
            'rank_20d': self.rank_20d,
        }
        result.update(self.aggregated_factors)
        return result


@dataclass
class IndustryRotationSignal:
    """行业轮动信号"""
    trade_date: str
    top_industries: List[Tuple[str, str, float]]  # (code, name, score)
    bottom_industries: List[Tuple[str, str, float]]
    rotation_strength: float  # 轮动强度（行业分化程度）
    momentum_score: pd.Series  # 各行业动量得分


class IndustryFactorBuilder:
    """
    行业因子构建器

    主要功能：
    1. 行业指数收益计算（1d/5d/20d收益率）
    2. 行业内聚合因子（行业内个股因子的市值加权平均）
    3. 行业相对强弱（行业vs沪深300）
    4. 行业轮动信号生成
    """

    # 主要申万行业列表（一级行业）
    SW_INDUSTRIES = [
        '801010', '801020', '801030', '801040', '801050',  # 农林牧渔、采掘、化工、钢铁、有色
        '801080', '801110', '801120', '801130', '801140',  # 电子、家用电器、食品饮料、纺织服装、轻工制造
        '801150', '801160', '801170', '801180', '801200',  # 医药生物、公用事业、交通运输、房地产、商业贸易
        '801210', '801230', '801710', '801720', '801730',  # 休闲服务、综合、建筑材料、建筑装饰、电气设备
        '801740', '801750', '801760', '801770', '801780',  # 国防军工、计算机、传媒、通信、银行
        '801790', '801880', '801890',  # 非银金融、汽车、机械设备
    ]

    def __init__(self, db_name: str = "tushare_biz"):
        """
        初始化行业因子构建器

        Args:
            db_name: 数据库名称
        """
        self.db_name = db_name
        self.data_manager = DataManager()
        self.precomputer = get_factor_precomputer()

        # 缓存
        self._industry_mapping: Optional[pd.DataFrame] = None
        self._market_index_cache: Dict[str, pd.Series] = {}

    def _get_industry_mapping(self, trade_date: datetime, level: str = 'L1') -> pd.DataFrame:
        """
        获取股票行业映射

        Args:
            trade_date: 交易日期
            level: 行业级别 (L1=一级, L2=二级, L3=三级)

        Returns:
            DataFrame: columns=[ts_code, industry_code, industry_name]
        """
        date_str = trade_date.strftime('%Y%m%d')

        # 优先从 t_sw_member 表获取申万行业分类
        results = DatabaseManager.fetchall(
            self.db_name,
            """
            SELECT con_code as ts_code, index_code as industry_code, index_name as industry_name
            FROM t_sw_member
            WHERE is_new = 1
            AND level = %s
            """,
            (level,)
        )

        if results:
            return pd.DataFrame(results)

        # 如果没有新数据，回退到 t_stock_basic 的 industry 字段
        logger.warning("t_sw_member is empty, falling back to t_stock_basic.industry")
        results = DatabaseManager.fetchall(
            self.db_name,
            """
            SELECT ts_code, industry as industry_name
            FROM t_stock_basic
            WHERE list_status = 'L'
            AND (delist_date IS NULL OR delist_date > %s)
            AND industry IS NOT NULL
            """,
            (date_str,)
        )

        if not results:
            return pd.DataFrame(columns=['ts_code', 'industry_code', 'industry_name'])

        df = pd.DataFrame(results)
        df['industry_code'] = df['industry_name'].apply(self._map_industry_name_to_code)

        return df

    def _map_industry_name_to_code(self, industry_name: str) -> Optional[str]:
        """
        将行业名称映射到行业代码

        简化版本，实际应该使用标准映射表
        """
        if not industry_name:
            return None

        # 常见行业名称映射
        mapping = {
            '银行': '801780', '非银金融': '801790', '房地产': '801180',
            '医药生物': '801150', '电子': '801080', '计算机': '801750',
            '传媒': '801760', '通信': '801770', '食品饮料': '801120',
            '家用电器': '801110', '汽车': '801880', '机械设备': '801890',
            '电气设备': '801730', '化工': '801030', '有色金属': '801050',
            '钢铁': '801040', '采掘': '801020', '农林牧渔': '801010',
            '建筑装饰': '801720', '建筑材料': '801710', '交通运输': '801170',
            '公用事业': '801160', '商业贸易': '801200', '休闲服务': '801210',
            '轻工制造': '801140', '纺织服装': '801130', '国防军工': '801740',
            '综合': '801230',
        }

        # 尝试直接匹配
        if industry_name in mapping:
            return mapping[industry_name]

        # 尝试部分匹配
        for name, code in mapping.items():
            if name in industry_name or industry_name in name:
                return code

        return None

    def _get_market_index_returns(
        self,
        start_date: datetime,
        end_date: datetime,
        index_code: str = '000300.SH'  # 沪深300
    ) -> pd.DataFrame:
        """
        获取市场指数收益

        Args:
            start_date: 开始日期
            end_date: 结束日期
            index_code: 指数代码

        Returns:
            DataFrame: columns=[trade_date, pct_chg, close]
        """
        results = DatabaseManager.fetchall(
            self.db_name,
            """
            SELECT trade_date, pct_chg, close
            FROM t_index_daily
            WHERE ts_code = %s
            AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date
            """,
            (index_code, start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'))
        )

        if not results:
            return pd.DataFrame(columns=['trade_date', 'pct_chg', 'close'])

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)

        return df

    def build_industry_index_factors(
        self,
        trade_date: datetime,
        lookback_days: int = 60
    ) -> pd.DataFrame:
        """
        构建行业指数收益因子

        数据来源: t_sw_daily (申万行业指数日行情表)

        Args:
            trade_date: 交易日期
            lookback_days: 回看天数

        Returns:
            DataFrame: index=industry_code, columns=[return_1d, return_5d, return_20d, ...]
        """
        start_date = trade_date - timedelta(days=lookback_days + 20)
        end_date = trade_date

        # 从 t_sw_daily 获取申万行业指数数据
        # 申万行业指数代码格式如：801010.SWI
        industry_index_codes = [f"{code}.SWI" for code in self.SW_INDUSTRIES]

        results = DatabaseManager.fetchall(
            self.db_name,
            """
            SELECT ts_code, trade_date, close, pct_chg, name
            FROM t_sw_daily
            WHERE ts_code IN %s
            AND trade_date BETWEEN %s AND %s
            ORDER BY ts_code, trade_date
            """,
            (tuple(industry_index_codes), start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'))
        )

        if not results:
            logger.warning("No industry index data found")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        # 计算各行业收益
        industry_factors = []

        for code in industry_index_codes:
            industry_data = df[df['ts_code'] == code].sort_values('trade_date')

            if len(industry_data) < 20:
                continue

            industry_code = code.replace('.SWI', '')

            # 计算不同周期的收益率
            close_prices = industry_data['close'].values

            return_1d = close_prices[-1] / close_prices[-2] - 1 if len(close_prices) >= 2 else 0
            return_5d = close_prices[-1] / close_prices[-6] - 1 if len(close_prices) >= 6 else 0
            return_20d = close_prices[-1] / close_prices[-21] - 1 if len(close_prices) >= 21 else 0

            # 计算波动率
            pct_changes = industry_data['pct_chg'].dropna()
            volatility_20d = pct_changes.tail(20).std() * np.sqrt(252) if len(pct_changes) >= 20 else 0

            industry_factors.append({
                'industry_code': industry_code,
                'return_1d': return_1d,
                'return_5d': return_5d,
                'return_20d': return_20d,
                'volatility_20d': volatility_20d,
            })

        return pd.DataFrame(industry_factors).set_index('industry_code')

    def build_industry_aggregated_factors(
        self,
        trade_date: datetime,
        factor_names: Optional[List[str]] = None,
        min_stocks_per_industry: int = 5
    ) -> pd.DataFrame:
        """
        构建行业内聚合因子

        对行业内个股的因子进行市值加权平均，得到行业层面的因子值。

        Args:
            trade_date: 交易日期
            factor_names: 要聚合的因子列表（默认全部）
            min_stocks_per_industry: 每个行业最少股票数

        Returns:
            DataFrame: index=industry_code, columns=[aggregated_factors]
        """
        # 获取行业映射（使用一级行业）
        industry_mapping = self._get_industry_mapping(trade_date, level='L1')

        if industry_mapping.empty:
            logger.warning("No industry mapping data")
            return pd.DataFrame()

        # 获取个股因子数据
        stock_factors = self.precomputer.get_precomputed_factors(trade_date=trade_date)

        if stock_factors.empty:
            logger.warning("No precomputed factors available")
            return pd.DataFrame()

        # 确定要聚合的因子
        if factor_names is None:
            # 排除非因子列
            exclude_cols = ['trade_date']
            factor_names = [c for c in stock_factors.columns if c not in exclude_cols]

        # 添加行业信息
        stock_factors = stock_factors.reset_index()
        stock_factors = stock_factors.merge(
            industry_mapping[['ts_code', 'industry_code']],
            on='ts_code',
            how='left'
        )

        # 删除没有行业分类的股票
        stock_factors = stock_factors.dropna(subset=['industry_code'])

        if stock_factors.empty:
            return pd.DataFrame()

        # 获取市值数据用于加权
        date_str = trade_date.strftime('%Y%m%d')
        market_values = self._get_market_values(trade_date)

        if not market_values.empty:
            stock_factors = stock_factors.merge(
                market_values,
                left_on='ts_code',
                right_index=True,
                how='left'
            )
            stock_factors['weight'] = stock_factors['total_mv'].fillna(0)
        else:
            # 等权
            stock_factors['weight'] = 1.0

        # 按行业聚合
        aggregated = []

        for industry_code, group in stock_factors.groupby('industry_code'):
            if len(group) < min_stocks_per_industry:
                continue

            row = {'industry_code': industry_code}

            # 市值加权平均
            total_weight = group['weight'].sum()

            if total_weight > 0:
                for factor in factor_names:
                    if factor in group.columns:
                        weighted_avg = (group[factor] * group['weight']).sum() / total_weight
                        row[f'ind_{factor}'] = weighted_avg

            # 行业内统计
            row['ind_stock_count'] = len(group)
            row['ind_total_mv'] = total_weight

            aggregated.append(row)

        if not aggregated:
            return pd.DataFrame()

        return pd.DataFrame(aggregated).set_index('industry_code')

    def _get_market_values(self, trade_date: datetime) -> pd.Series:
        """获取市值数据"""
        date_str = trade_date.strftime('%Y%m%d')

        results = DatabaseManager.fetchall(
            self.db_name,
            """
            SELECT ts_code, total_mv
            FROM t_stock_daily_basic
            WHERE trade_date = %s
            """,
            (date_str,)
        )

        if not results:
            return pd.Series(dtype=float)

        df = pd.DataFrame(results)
        df.set_index('ts_code', inplace=True)

        return df['total_mv']

    def build_industry_relative_factors(
        self,
        trade_date: datetime,
        lookback_days: int = 60
    ) -> pd.DataFrame:
        """
        构建行业相对因子（行业vs市场）

        Args:
            trade_date: 交易日期
            lookback_days: 回看天数

        Returns:
            DataFrame: index=industry_code, columns=[relative factors]
        """
        # 获取行业指数因子
        industry_factors = self.build_industry_index_factors(trade_date, lookback_days)

        if industry_factors.empty:
            return pd.DataFrame()

        # 获取市场指数收益
        start_date = trade_date - timedelta(days=lookback_days + 20)
        market_data = self._get_market_index_returns(start_date, trade_date)

        if market_data.empty:
            logger.warning("No market index data available")
            return industry_factors

        # 计算市场收益
        close_prices = market_data['close'].values
        market_return_1d = close_prices[-1] / close_prices[-2] - 1 if len(close_prices) >= 2 else 0
        market_return_5d = close_prices[-1] / close_prices[-6] - 1 if len(close_prices) >= 6 else 0
        market_return_20d = close_prices[-1] / close_prices[-21] - 1 if len(close_prices) >= 21 else 0

        # 计算相对因子
        relative = industry_factors.copy()
        relative['rs_1d'] = relative['return_1d'] - market_return_1d
        relative['rs_5d'] = relative['return_5d'] - market_return_5d
        relative['rs_20d'] = relative['return_20d'] - market_return_20d

        # 计算排名
        relative['rank_1d'] = relative['return_1d'].rank(ascending=False)
        relative['rank_5d'] = relative['return_5d'].rank(ascending=False)
        relative['rank_20d'] = relative['return_20d'].rank(ascending=False)

        # 计算RS排名
        relative['rs_rank_5d'] = relative['rs_5d'].rank(ascending=False)
        relative['rs_rank_20d'] = relative['rs_20d'].rank(ascending=False)

        return relative

    def build_industry_rotation_signals(
        self,
        trade_date: datetime,
        top_n: int = 5,
        lookback_days: int = 60
    ) -> IndustryRotationSignal:
        """
        构建行业轮动信号

        综合多维度指标生成行业轮动建议。

        Args:
            trade_date: 交易日期
            top_n: 选出前N个行业
            lookback_days: 回看天数

        Returns:
            IndustryRotationSignal: 行业轮动信号
        """
        # 获取行业相对因子
        relative_factors = self.build_industry_relative_factors(trade_date, lookback_days)

        if relative_factors.empty:
            logger.warning("No data for industry rotation")
            return IndustryRotationSignal(
                trade_date=trade_date.strftime('%Y%m%d'),
                top_industries=[],
                bottom_industries=[],
                rotation_strength=0.0,
                momentum_score=pd.Series(dtype=float)
            )

        # 获取行业名称映射
        industry_names = self._get_industry_names()

        # 计算综合动量得分
        # 结合短期、中期收益和相对强弱
        momentum_score = (
            relative_factors['return_5d'] * 0.4 +
            relative_factors['return_20d'] * 0.3 +
            relative_factors['rs_5d'] * 0.2 +
            relative_factors['rs_20d'] * 0.1
        )

        momentum_score = momentum_score.dropna().sort_values(ascending=False)

        # 选取得分最高和最低的行业
        top = momentum_score.head(top_n)
        bottom = momentum_score.tail(top_n)

        top_industries = [
            (code, industry_names.get(code, code), score)
            for code, score in top.items()
        ]

        bottom_industries = [
            (code, industry_names.get(code, code), score)
            for code, score in bottom.items()
        ]

        # 计算轮动强度（行业分化程度）
        # 使用得分分布的标准差
        rotation_strength = momentum_score.std()

        return IndustryRotationSignal(
            trade_date=trade_date.strftime('%Y%m%d'),
            top_industries=top_industries,
            bottom_industries=bottom_industries,
            rotation_strength=rotation_strength,
            momentum_score=momentum_score
        )

    def _get_industry_names(self) -> Dict[str, str]:
        """获取行业代码到名称的映射"""
        # 优先从 t_sw_classify 表获取
        results = DatabaseManager.fetchall(
            self.db_name,
            "SELECT ts_code, name FROM t_sw_classify WHERE level = 1"
        )

        if results:
            return {r['ts_code']: r['name'] for r in results}

        # 如果数据库为空，返回硬编码映射
        return {
            '801010': '农林牧渔', '801020': '采掘', '801030': '化工',
            '801040': '钢铁', '801050': '有色金属', '801080': '电子',
            '801110': '家用电器', '801120': '食品饮料', '801130': '纺织服装',
            '801140': '轻工制造', '801150': '医药生物', '801160': '公用事业',
            '801170': '交通运输', '801180': '房地产', '801200': '商业贸易',
            '801210': '休闲服务', '801230': '综合', '801710': '建筑材料',
            '801720': '建筑装饰', '801730': '电气设备', '801740': '国防军工',
            '801750': '计算机', '801760': '传媒', '801770': '通信',
            '801780': '银行', '801790': '非银金融', '801880': '汽车',
            '801890': '机械设备',
        }

    def batch_build_factors(
        self,
        start_date: datetime,
        end_date: datetime,
        build_index_factors: bool = True,
        build_aggregated_factors: bool = True,
        build_relative_factors: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        批量构建行业因子

        Args:
            start_date: 开始日期
            end_date: 结束日期
            build_index_factors: 是否构建行业指数因子
            build_aggregated_factors: 是否构建行业内聚合因子
            build_relative_factors: 是否构建行业相对因子

        Returns:
            Dict[str, pd.DataFrame]: 各类因子的DataFrame
        """
        from projects.quant_trading.backtest.data_manager import DataManager

        trade_dates = self.data_manager.get_trade_dates(start_date, end_date)

        logger.info(f"Batch building industry factors for {len(trade_dates)} dates...")

        results = {
            'index_factors': [],
            'aggregated_factors': [],
            'relative_factors': [],
        }

        for i, date in enumerate(trade_dates):
            if i % 50 == 0:
                logger.info(f"Processing [{i+1}/{len(trade_dates)}] {date.strftime('%Y%m%d')}")

            try:
                if build_index_factors:
                    idx_factors = self.build_industry_index_factors(date)
                    if not idx_factors.empty:
                        idx_factors['trade_date'] = date.strftime('%Y%m%d')
                        results['index_factors'].append(idx_factors.reset_index())

                if build_aggregated_factors:
                    agg_factors = self.build_industry_aggregated_factors(date)
                    if not agg_factors.empty:
                        agg_factors['trade_date'] = date.strftime('%Y%m%d')
                        results['aggregated_factors'].append(agg_factors.reset_index())

                if build_relative_factors:
                    rel_factors = self.build_industry_relative_factors(date)
                    if not rel_factors.empty:
                        rel_factors['trade_date'] = date.strftime('%Y%m%d')
                        results['relative_factors'].append(rel_factors.reset_index())

            except Exception as e:
                logger.warning(f"Failed to build factors for {date}: {e}")
                continue

        # 合并结果
        output = {}
        for key, data_list in results.items():
            if data_list:
                output[key] = pd.concat(data_list, ignore_index=True)
            else:
                output[key] = pd.DataFrame()

        return output


def get_industry_exposure(
    portfolio: Dict[str, float],
    trade_date: datetime
) -> pd.Series:
    """
    计算组合的行业暴露

    Args:
        portfolio: 组合权重 {stock_code: weight}
        trade_date: 交易日期

    Returns:
        Series: 各行业暴露权重
    """
    builder = IndustryFactorBuilder()
    industry_mapping = builder._get_industry_mapping(trade_date)

    if industry_mapping.empty:
        return pd.Series(dtype=float)

    # 构建股票到行业的映射
    stock_to_industry = dict(zip(
        industry_mapping['ts_code'],
        industry_mapping['industry_code']
    ))

    # 计算行业暴露
    industry_exposure = defaultdict(float)

    for stock, weight in portfolio.items():
        industry = stock_to_industry.get(stock)
        if industry:
            industry_exposure[industry] += weight

    return pd.Series(industry_exposure)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--rotation":
        # 行业轮动信号示例
        date = datetime.now() - timedelta(days=1)
        builder = IndustryFactorBuilder()

        print(f"Building industry rotation signals for {date.strftime('%Y%m%d')}...")
        signal = builder.build_industry_rotation_signals(date, top_n=5)

        print(f"\nTop 5 Industries:")
        for code, name, score in signal.top_industries:
            print(f"  {code} {name}: {score:.4f}")

        print(f"\nBottom 5 Industries:")
        for code, name, score in signal.bottom_industries:
            print(f"  {code} {name}: {score:.4f}")

        print(f"\nRotation Strength: {signal.rotation_strength:.4f}")

    elif len(sys.argv) > 1 and sys.argv[1] == "--relative":
        # 行业相对因子示例
        date = datetime.now() - timedelta(days=1)
        builder = IndustryFactorBuilder()

        print(f"Building industry relative factors for {date.strftime('%Y%m%d')}...")
        factors = builder.build_industry_relative_factors(date)

        print(f"\nTop 5 by 20-day Return:")
        top = factors.nlargest(5, 'return_20d')[['return_20d', 'rs_20d', 'rank_20d']]
        print(top.to_string())

        print(f"\nBottom 5 by 20-day Return:")
        bottom = factors.nsmallest(5, 'return_20d')[['return_20d', 'rs_20d', 'rank_20d']]
        print(bottom.to_string())

    else:
        print("Usage:")
        print("  python industry_factors.py --rotation")
        print("  python industry_factors.py --relative")
