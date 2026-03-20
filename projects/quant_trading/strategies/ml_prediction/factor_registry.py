"""
因子注册表 - 插件化因子框架

解决现有框架扩展性问题：
1. 声明式因子定义（无需修改核心代码）
2. 自动 SQL 生成
3. 动态因子发现
4. 支持自定义计算逻辑

版本历史：
- 2026-03-19: 重构为从 factor_definitions.py 读取因子定义，移除硬编码
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set, Union
from datetime import datetime
from enum import Enum, auto
import logging

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager

# 导入统一因子定义
from .factor_definitions import (
    FACTOR_DEFINITIONS,
    FactorDefinition,
    CalculationType,
    get_factor_lineage,
    get_factors_by_category,
    get_factors_by_data_source,
)

logger = get_logger(__name__)


class FactorType(Enum):
    """因子类型 (向后兼容)"""
    SQL = auto()      # 纯 SQL 计算
    PYTHON = auto()   # Python 后处理
    HYBRID = auto()   # SQL + Python 组合

    @classmethod
    def from_calculation_type(cls, calc_type: CalculationType) -> "FactorType":
        """从 CalculationType 转换"""
        mapping = {
            CalculationType.DIRECT: cls.SQL,
            CalculationType.SQL: cls.SQL,
            CalculationType.PYTHON: cls.PYTHON,
            CalculationType.HYBRID: cls.HYBRID,
            CalculationType.DERIVED: cls.PYTHON,
        }
        return mapping.get(calc_type, cls.PYTHON)


class FactorRegistry:
    """
    因子注册表

    管理所有因子定义，支持：
    - 声明式因子注册
    - 依赖自动解析
    - SQL 自动生成
    - 自定义计算逻辑
    """

    def __init__(self):
        self._factors: Dict[str, FactorDefinition] = {}
        self._sql_builder = SQLFactorBuilder()

    def register_sql_factor(
        self,
        name: str,
        sql_expr: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        category: str = "misc",
        **kwargs
    ) -> "FactorRegistry":
        """注册 SQL 因子"""
        factor = FactorDefinition(
            name=name,
            description=description,
            calculation=CalculationType.SQL,
            sql_expr=sql_expr,
            dependencies=dependencies or [],
            category=category,
            **kwargs
        )
        self._factors[name] = factor
        logger.debug(f"Registered SQL factor: {name}")
        return self

    def register_python_factor(
        self,
        name: str,
        compute_fn: Callable[[pd.DataFrame], pd.Series],
        dependencies: List[str],
        description: str = "",
        category: str = "misc",
        **kwargs
    ) -> "FactorRegistry":
        """注册 Python 计算因子"""
        factor = FactorDefinition(
            name=name,
            description=description,
            calculation=CalculationType.PYTHON,
            compute_fn=compute_fn,
            dependencies=dependencies,
            category=category,
            **kwargs
        )
        self._factors[name] = factor
        logger.debug(f"Registered Python factor: {name}")
        return self

    def register_hybrid_factor(
        self,
        name: str,
        sql_expr: str,
        compute_fn: Callable[[pd.DataFrame], pd.Series],
        dependencies: List[str],
        description: str = "",
        category: str = "misc",
        **kwargs
    ) -> "FactorRegistry":
        """注册混合因子（SQL 初算 + Python 精修）"""
        factor = FactorDefinition(
            name=name,
            description=description,
            calculation=CalculationType.HYBRID,
            sql_expr=sql_expr,
            compute_fn=compute_fn,
            dependencies=dependencies,
            category=category,
            **kwargs
        )
        self._factors[name] = factor
        logger.debug(f"Registered hybrid factor: {name}")
        return self

    def get_factor(self, name: str) -> Optional[FactorDefinition]:
        """获取因子定义"""
        return self._factors.get(name)

    def list_factors(self, category: Optional[str] = None) -> List[str]:
        """列出所有因子，可按分类过滤"""
        if category:
            return [f.name for f in self._factors.values() if f.category == category]
        return list(self._factors.keys())

    def get_all_factors(self) -> Dict[str, FactorDefinition]:
        """获取所有因子定义"""
        return self._factors.copy()

    def compute_factors(
        self,
        trade_date: datetime,
        stock_pool: List[str],
        factor_names: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        计算指定因子

        Args:
            trade_date: 交易日期
            stock_pool: 股票池
            factor_names: 要计算的因子（默认全部）

        Returns:
            DataFrame with factors
        """
        # 确定要计算的因子
        names = factor_names or list(self._factors.keys())
        factors = [self._factors[n] for n in names if n in self._factors]

        if not factors:
            logger.warning("No factors to compute")
            return pd.DataFrame()

        date_str = trade_date.strftime("%Y%m%d")

        # 分离 SQL 和 Python 因子
        sql_factors = [f for f in factors if FactorType.from_calculation_type(f.calculation) in (FactorType.SQL, FactorType.HYBRID)]
        python_factors = [f for f in factors if FactorType.from_calculation_type(f.calculation) in (FactorType.PYTHON, FactorType.HYBRID)]

        # 1. 执行 SQL 查询获取基础因子
        if sql_factors:
            sql, params = self._sql_builder.build(sql_factors, date_str, stock_pool)
            try:
                results = DatabaseManager.fetchall("tushare_biz", sql, params)
                df = pd.DataFrame(results)
                if not df.empty:
                    df.set_index("ts_code", inplace=True)
            except Exception as e:
                logger.error(f"SQL query failed: {e}")
                logger.debug(f"SQL: {sql[:500]}...")
                df = pd.DataFrame()
        else:
            df = pd.DataFrame(index=stock_pool)

        # 2. 执行 Python 计算
        for factor in python_factors:
            try:
                if factor.compute_fn:
                    df[factor.name] = factor.compute_fn(df)
            except Exception as e:
                logger.error(f"Failed to compute {factor.name}: {e}")
                df[factor.name] = factor.default_value

        return df

    def compute_single_factor(
        self,
        factor_name: str,
        trade_date: datetime,
        stock_pool: List[str]
    ) -> pd.Series:
        """计算单个因子"""
        df = self.compute_factors(trade_date, stock_pool, [factor_name])
        if factor_name in df.columns:
            return df[factor_name]
        return pd.Series(index=stock_pool, name=factor_name)


class SQLFactorBuilder:
    """SQL 查询构建器 - 支持多表 JOIN 和窗口函数"""

    def build(
        self,
        factors: List[FactorDefinition],
        date_str: str,
        stock_pool: List[str]
    ) -> tuple[str, tuple]:
        """构建 SQL 查询"""

        placeholders = ','.join(['%s'] * len(stock_pool))

        # 按数据源分组（只包含SQL和HYBRID类型的因子）
        sql_factors = [f for f in factors if FactorType.from_calculation_type(f.calculation) in (FactorType.SQL, FactorType.HYBRID)]
        price_factors = [f for f in sql_factors if f.data_source == "t_stock_dailymarketdata"]
        valuation_factors = [f for f in sql_factors if f.data_source == "t_stock_daily_basic"]
        moneyflow_factors = [f for f in sql_factors if f.data_source == "t_stock_moneyflow"]
        financial_factors = [f for f in sql_factors if f.data_source == "t_stock_fina_indicator"]

        # 计算最大窗口需求
        max_window = 0
        for f in price_factors:
            if f.window_days:
                max_window = max(max_window, f.window_days)

        # 计算起始日期
        from datetime import datetime, timedelta
        end_date = datetime.strptime(date_str, '%Y%m%d')
        start_date = end_date - timedelta(days=max_window + 10) if max_window > 0 else end_date
        start_str = start_date.strftime('%Y%m%d')

        # 构建价格数据 CTE（需要窗口函数的历史数据）
        ctes = []
        if price_factors:
            price_exprs = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pct_chg"]
            for f in price_factors:
                if f.sql_expr:
                    expr = self._process_sql_expr(f.sql_expr)
                    price_exprs.append(f"{expr} as {f.name}")

            ctes.append(f"""
price_data AS (
    SELECT {', '.join(price_exprs)}
    FROM t_stock_dailymarketdata
    WHERE trade_date BETWEEN %s AND %s
      AND ts_code IN ({placeholders})
    WINDOW w AS (PARTITION BY ts_code ORDER BY trade_date)
)
            """.strip())

        # 构建估值数据 CTE（单日数据）
        if valuation_factors:
            val_exprs = ["ts_code", "trade_date"]
            for f in valuation_factors:
                if f.sql_expr:
                    val_exprs.append(f"{f.sql_expr} as {f.name}")

            ctes.append(f"""
valuation_data AS (
    SELECT {', '.join(val_exprs)}
    FROM t_stock_daily_basic
    WHERE trade_date = %s
      AND ts_code IN ({placeholders})
)
            """.strip())

        # 构建资金流 CTE（需要历史数据）
        mf_window = max([f.window_days for f in moneyflow_factors if f.window_days], default=0)
        if moneyflow_factors:
            mf_exprs = ["ts_code", "trade_date", "buy_lg_amount", "sell_lg_amount"]
            for f in moneyflow_factors:
                if f.sql_expr:
                    expr = self._process_sql_expr(f.sql_expr)
                    mf_exprs.append(f"{expr} as {f.name}")

            mf_start = (end_date - timedelta(days=mf_window + 10)).strftime('%Y%m%d') if mf_window > 0 else date_str
            ctes.append(f"""
moneyflow_data AS (
    SELECT {', '.join(mf_exprs)}
    FROM t_stock_moneyflow
    WHERE trade_date BETWEEN %s AND %s
      AND ts_code IN ({placeholders})
    WINDOW w AS (PARTITION BY ts_code ORDER BY trade_date)
)
            """.strip())

        # 构建财务数据 CTE（最新财报数据）
        if financial_factors:
            fina_exprs = ["ts_code"]
            for f in financial_factors:
                if f.sql_expr:
                    fina_exprs.append(f"{f.sql_expr} as {f.name}")

            ctes.append(f"""
financial_data AS (
    SELECT {', '.join(fina_exprs)}
    FROM t_stock_fina_indicator
    WHERE (ts_code, end_date) IN (
        SELECT ts_code, MAX(end_date)
        FROM t_stock_fina_indicator
        WHERE end_date <= %s
        GROUP BY ts_code
    )
      AND ts_code IN ({placeholders})
)
            """.strip())

        # 构建最终查询
        # 确定所有数据源
        has_price = bool(price_factors)
        has_val = bool(valuation_factors)
        has_mf = bool(moneyflow_factors)
        has_fin = bool(financial_factors)

        # 确定主表（优先顺序：price > valuation > moneyflow）
        if has_price:
            primary_table = "p"
            primary_alias = "p"
        elif has_val:
            primary_table = "v"
            primary_alias = "v"
        elif has_mf:
            primary_table = "m"
            primary_alias = "m"
        else:
            primary_table = "f"
            primary_alias = "f"

        select_list = [f"COALESCE({primary_alias}.ts_code" +
                       (", v.ts_code" if has_val and primary_alias != "v" else "") +
                       (", m.ts_code" if has_mf and primary_alias != "m" else "") +
                       (", f.ts_code" if has_fin and primary_alias != "f" else "") +
                       ") as ts_code"]

        # 构建 FROM 子句
        from_parts = []
        join_conditions = []

        if has_price:
            from_parts.append("price_data p")
        if has_val:
            if not from_parts:
                from_parts.append("valuation_data v")
            else:
                join_conditions.append("LEFT JOIN valuation_data v ON p.ts_code = v.ts_code AND p.trade_date = v.trade_date")
        if has_mf:
            if not from_parts:
                from_parts.append("moneyflow_data m")
            else:
                if has_price:
                    join_conditions.append("LEFT JOIN moneyflow_data m ON p.ts_code = m.ts_code AND p.trade_date = m.trade_date")
                else:
                    join_conditions.append("LEFT JOIN moneyflow_data m ON v.ts_code = m.ts_code AND v.trade_date = m.trade_date")
        if has_fin:
            if not from_parts:
                from_parts.append("financial_data f")
            else:
                if has_price:
                    join_conditions.append("LEFT JOIN financial_data f ON p.ts_code = f.ts_code")
                elif has_val:
                    join_conditions.append("LEFT JOIN financial_data f ON v.ts_code = f.ts_code")
                else:
                    join_conditions.append("LEFT JOIN financial_data f ON m.ts_code = f.ts_code")

        from_clause = " ".join(from_parts + join_conditions)

        # WHERE 子句
        if has_price:
            where_clause = f"WHERE p.trade_date = %s AND p.ts_code IN ({placeholders})"
        elif has_val:
            where_clause = f"WHERE v.trade_date = %s AND v.ts_code IN ({placeholders})"
        elif has_mf:
            where_clause = f"WHERE m.trade_date = %s AND m.ts_code IN ({placeholders})"
        else:
            where_clause = f"WHERE f.ts_code IN ({placeholders})"

        # 添加所有因子列
        all_factors = price_factors + valuation_factors + moneyflow_factors + financial_factors
        for f in all_factors:
            # 确定表别名
            if f.data_source == "t_stock_dailymarketdata":
                alias = "p"
            elif f.data_source == "t_stock_daily_basic":
                alias = "v"
            elif f.data_source == "t_stock_moneyflow":
                alias = "m"
            elif f.data_source == "t_stock_fina_indicator":
                alias = "f"
            else:
                alias = "p"  # default
            select_list.append(f"{alias}.{f.name}")

        sql = f"WITH {', '.join(ctes)}\nSELECT {', '.join(select_list)}\nFROM {from_clause}\n{where_clause}"

        # 构建参数
        params = []
        if price_factors:
            params.extend([start_str, date_str] + stock_pool)
        if valuation_factors:
            params.extend([date_str] + stock_pool)
        if moneyflow_factors:
            mf_start = (end_date - timedelta(days=mf_window + 10)).strftime('%Y%m%d') if mf_window > 0 else date_str
            params.extend([mf_start, date_str] + stock_pool)
        if financial_factors:
            params.extend([date_str] + stock_pool)

        # 最后添加主表的日期和股票池参数
        if price_factors or valuation_factors or moneyflow_factors:
            params.extend([date_str] + stock_pool)
        else:
            params.extend(stock_pool)

        return sql, tuple(params)

    def _process_sql_expr(self, expr: str) -> str:
        """处理 SQL 表达式，确保兼容性"""
        return expr


# ==================== 完整因子库定义 ====================

def _convert_factor_def_to_registry(
    registry: "FactorRegistry",
    factor_def: FactorDefinition
) -> None:
    """
    将 FactorDefinition 转换为 FactorRegistry 中的注册

    Args:
        registry: FactorRegistry 实例
        factor_def: 统一因子定义
    """
    calc_type = factor_def.calculation

    if calc_type in (CalculationType.DIRECT, CalculationType.SQL):
        # SQL 类型因子
        registry.register_sql_factor(
            name=factor_def.name,
            sql_expr=factor_def.sql_expr or factor_def.source_field or factor_def.name,
            description=factor_def.description,
            category=factor_def.category,
            data_source=factor_def.data_source,
            window_days=factor_def.window_days,
            default_value=factor_def.default_value,
        )
    elif calc_type == CalculationType.PYTHON:
        # Python 类型因子 - 需要根据因子名称映射到对应的计算函数
        compute_fn = _get_python_compute_fn(factor_def.name)
        if compute_fn:
            registry.register_python_factor(
                name=factor_def.name,
                compute_fn=compute_fn,
                dependencies=factor_def.dependencies,
                description=factor_def.description,
                category=factor_def.category,
                default_value=factor_def.default_value,
            )
        else:
            # 如果找不到计算函数，作为占位符注册
            logger.debug(f"No Python compute function found for {factor_def.name}, registering as placeholder")
            registry.register_python_factor(
                name=factor_def.name,
                compute_fn=lambda df: pd.Series(factor_def.default_value or 0, index=df.index),
                dependencies=factor_def.dependencies,
                description=factor_def.description,
                category=factor_def.category,
                default_value=factor_def.default_value,
            )
    elif calc_type == CalculationType.HYBRID:
        # HYBRID 类型因子
        compute_fn = _get_python_compute_fn(factor_def.name)
        registry.register_hybrid_factor(
            name=factor_def.name,
            sql_expr=factor_def.sql_expr or "",
            compute_fn=compute_fn or (lambda df: pd.Series(factor_def.default_value or 0, index=df.index)),
            dependencies=factor_def.dependencies,
            description=factor_def.description,
            category=factor_def.category,
        )


def _get_python_compute_fn(factor_name: str) -> Optional[Callable]:
    """
    根据因子名称获取对应的 Python 计算函数

    这是从旧代码迁移过来的计算函数映射
    """
    compute_fn_map = {
        # Z-score 因子
        "pe_ttm_zscore": lambda df: _calc_zscore(df.get("pe_ttm")),
        "pb_zscore": lambda df: _calc_zscore(df.get("pb")),
        "ps_ttm_zscore": lambda df: _calc_zscore(df.get("ps_ttm")),
        "return_20d_zscore": lambda df: _calc_zscore(df.get("return_20d")),
        "volatility_20d_zscore": lambda df: _calc_zscore(df.get("volatility_20d")),
        "turnover_rate_zscore": lambda df: _calc_zscore(df.get("turnover_rate")),
        "ep_ttm_zscore": lambda df: _calc_zscore(df.get("ep_ttm")),
        "bp_zscore": lambda df: _calc_zscore(df.get("bp")),

        # 流动性因子
        "turnover_volatility_20d": lambda df: _calc_turnover_volatility(df, period=20),

        # 风险因子
        "max_drawdown_20d": lambda df: _calc_max_drawdown(df, period=20),
        "max_drawdown_60d": lambda df: _calc_max_drawdown(df, period=60),

        # 市场相对因子
        "market_alpha_20d": lambda df: _calc_market_alpha(df, "return_20d"),
        "market_alpha_60d": lambda df: _calc_market_alpha(df, "return_60d"),

        # 行业相对因子
        "sector_alpha_20d": lambda df: _calc_sector_alpha(df, "return_20d"),
        "sector_alpha_60d": lambda df: _calc_sector_alpha(df, "return_60d"),
        "sector_rank_20d": lambda df: _calc_sector_rank(df, "return_20d"),

        # 波动率因子
        "atr_14d": lambda df: _calc_atr(df, period=14),
        "downside_vol_20d": lambda df: _calc_downside_vol(df, period=20),

        # 技术因子
        "rsi_14d": lambda df: _calc_rsi(df, period=14),
        "macd": lambda df: _calc_macd_cached(df)["macd"],
        "macd_signal": lambda df: _calc_macd_cached(df)["signal"],
        "macd_hist": lambda df: _calc_macd_cached(df)["hist"],
        "bb_upper": lambda df: _calc_bollinger_cached(df, period=20, std_dev=2)["upper"],
        "bb_middle": lambda df: _calc_bollinger_cached(df, period=20, std_dev=2)["middle"],
        "bb_lower": lambda df: _calc_bollinger_cached(df, period=20, std_dev=2)["lower"],
        "bb_width": lambda df: _calc_bollinger_cached(df, period=20, std_dev=2)["width"],
        "bb_position": lambda df: _calc_bollinger_cached(df, period=20, std_dev=2)["position"],
    }

    return compute_fn_map.get(factor_name)


def _calc_market_alpha(df: pd.DataFrame, col: str) -> pd.Series:
    """计算市场超额收益"""
    series = df.get(col)
    if series is None or not isinstance(series, pd.Series):
        return pd.Series(0, index=df.index)
    series = pd.to_numeric(series, errors='coerce')
    return series - series.mean()


def _calc_sector_alpha(df: pd.DataFrame, col: str) -> pd.Series:
    """计算行业超额收益（需要 industry 列）"""
    series = df.get(col)
    industry = df.get("industry")
    if series is None or industry is None:
        return pd.Series(0, index=df.index)

    series = pd.to_numeric(series, errors='coerce')
    # groupby().transform() 替代 Python for loop，向量化执行
    tmp = pd.DataFrame({"v": series, "ind": industry})
    sector_mean = tmp.groupby("ind")["v"].transform("mean")
    return (series - sector_mean).fillna(0)


def _calc_sector_rank(df: pd.DataFrame, col: str) -> pd.Series:
    """计算行业内排名（百分位）"""
    series = df.get(col)
    industry = df.get("industry")
    if series is None or industry is None:
        return pd.Series(0.5, index=df.index)

    series = pd.to_numeric(series, errors='coerce')
    tmp = pd.DataFrame({"v": series, "ind": industry})
    result = tmp.groupby("ind")["v"].transform(lambda x: x.rank(pct=True) if len(x) > 1 else pd.Series(0.5, index=x.index))
    return result.fillna(0.5)


def create_full_registry() -> FactorRegistry:
    """
    创建完整因子注册表（包含所有预计算因子）

    现在从 factor_definitions.py 读取所有因子定义
    """
    registry = FactorRegistry()

    # 从统一清单导入所有因子定义
    for factor_name, factor_def in FACTOR_DEFINITIONS.items():
        try:
            _convert_factor_def_to_registry(registry, factor_def)
        except Exception as e:
            logger.warning(f"Failed to register factor {factor_name}: {e}")

    logger.info(f"Created registry with {len(registry._factors)} factors from unified definitions")
    return registry


def _calc_zscore(series: pd.Series) -> pd.Series:
    """计算 Z-score"""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    # 转换为 float 避免 Decimal 类型问题
    series = pd.to_numeric(series, errors='coerce')
    mean = series.mean()
    std = series.std()
    if std > 0:
        return (series - mean) / std
    return pd.Series(0, index=series.index)


def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算平均真实波幅 ATR"""
    if 'tr' not in df.columns:
        return pd.Series(0, index=df.index)
    tr = pd.to_numeric(df['tr'], errors='coerce')
    # 使用指数移动平均
    atr = tr.ewm(span=period, adjust=False).mean()
    return atr


def _calc_downside_vol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """计算下行波动率（只计算负收益的波动）"""
    # 获取日收益率数据
    if 'pct_chg' in df.columns:
        returns = pd.to_numeric(df['pct_chg'], errors='coerce')
    elif 'return_1d' in df.columns:
        returns = pd.to_numeric(df['return_1d'], errors='coerce')
    else:
        # 如果没有日收益，使用close计算
        if 'close' in df.columns:
            close = pd.to_numeric(df['close'], errors='coerce')
            returns = close.pct_change()
        else:
            return pd.Series(0, index=df.index)

    # 只保留负收益
    downside_returns = returns[returns < 0]
    if len(downside_returns) == 0:
        return pd.Series(0, index=df.index)

    # 计算下行标准差
    downside_std = downside_returns.rolling(window=period, min_periods=5).std() * np.sqrt(252)
    return downside_std.fillna(0)


def _calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算 RSI 相对强弱指数"""
    if 'close' not in df.columns:
        return pd.Series(50, index=df.index)

    close = pd.to_numeric(df['close'], errors='coerce')
    # 计算价格变化
    delta = close.diff()

    # 分离上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    # 计算平均涨跌
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    # 计算 RS 和 RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


def _calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """计算 MACD 指标"""
    if 'close' not in df.columns:
        empty = pd.Series(0, index=df.index)
        return {"macd": empty, "signal": empty, "hist": empty}

    close = pd.to_numeric(df['close'], errors='coerce')

    # 计算EMA
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    # MACD线
    macd_line = ema_fast - ema_slow

    # 信号线
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    # MACD柱状线
    hist = macd_line - signal_line

    return {
        "macd": macd_line.fillna(0),
        "signal": signal_line.fillna(0),
        "hist": hist.fillna(0)
    }


def _calc_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> dict:
    """计算布林带指标"""
    if 'close' not in df.columns:
        empty = pd.Series(0, index=df.index)
        return {"upper": empty, "middle": empty, "lower": empty, "width": empty, "position": empty}

    close = pd.to_numeric(df['close'], errors='coerce')

    # 中轨（移动平均线）
    middle = close.rolling(window=period, min_periods=5).mean()

    # 标准差
    std = close.rolling(window=period, min_periods=5).std()

    # 上轨和下轨
    upper = middle + std_dev * std
    lower = middle - std_dev * std

    # 布林带宽度
    width = (upper - lower) / middle.replace(0, np.nan)

    # 价格在布林带中的位置（0-1之间）
    position = (close - lower) / (upper - lower).replace(0, np.nan)
    position = position.clip(0, 1)  # 限制在0-1之间

    return {
        "upper": upper.fillna(method='ffill').fillna(close),
        "middle": middle.fillna(method='ffill').fillna(close),
        "lower": lower.fillna(method='ffill').fillna(close),
        "width": width.fillna(0),
        "position": position.fillna(0.5)
    }


# ---------------------------------------------------------------------------
# 带DataFrame级别缓存的 macd / bollinger 包装器
# 每次 compute_factors 调用时，同一个 df 对象只计算一次
# ---------------------------------------------------------------------------
_MACD_CACHE: dict = {}   # id(df) -> result
_BB_CACHE: dict = {}     # (id(df), period, std_dev) -> result


def _calc_macd_cached(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    key = id(df)
    if key not in _MACD_CACHE:
        _MACD_CACHE.clear()          # 每次新 df 进来时清旧缓存，避免内存泄漏
        _MACD_CACHE[key] = _calc_macd(df, fast, slow, signal)
    return _MACD_CACHE[key]


def _calc_bollinger_cached(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> dict:
    key = (id(df), period, std_dev)
    if key not in _BB_CACHE:
        if not any(k[0] == id(df) for k in _BB_CACHE):
            _BB_CACHE.clear()        # 每次新 df 进来时清旧缓存
        _BB_CACHE[key] = _calc_bollinger(df, period, std_dev)
    return _BB_CACHE[key]


def _calc_turnover_volatility(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """计算换手率波动率"""
    if 'turnover_rate' not in df.columns:
        return pd.Series(0, index=df.index)

    turnover = pd.to_numeric(df['turnover_rate'], errors='coerce')
    # 计算换手率的变异系数（标准差/均值）
    rolling_std = turnover.rolling(window=period, min_periods=5).std()
    rolling_mean = turnover.rolling(window=period, min_periods=5).mean().replace(0, np.nan)

    cv = rolling_std / rolling_mean
    return cv.fillna(0)


def _calc_max_drawdown(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """计算最大回撤

    最大回撤 = (历史最高 - 当前) / 历史最高
    返回值范围: 0 到 1（0表示没有回撤，1表示全部亏损）
    """
    if 'close' not in df.columns:
        return pd.Series(0, index=df.index)

    close = pd.to_numeric(df['close'], errors='coerce')

    # 计算滚动窗口内的累计最大值
    rolling_max = close.rolling(window=period, min_periods=5).max()

    # 计算回撤
    drawdown = (rolling_max - close) / rolling_max.replace(0, np.nan)

    return drawdown.fillna(0).clip(0, 1)


# 单例实例
_full_registry: Optional[FactorRegistry] = None


def get_full_registry() -> FactorRegistry:
    """获取完整因子注册表"""
    global _full_registry
    if _full_registry is None:
        _full_registry = create_full_registry()
    return _full_registry
