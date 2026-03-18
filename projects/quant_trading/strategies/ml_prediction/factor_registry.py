"""
因子注册表 - 插件化因子框架

解决现有框架扩展性问题：
1. 声明式因子定义（无需修改核心代码）
2. 自动 SQL 生成
3. 动态因子发现
4. 支持自定义计算逻辑
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

logger = get_logger(__name__)


class FactorType(Enum):
    """因子类型"""
    SQL = auto()      # 纯 SQL 计算
    PYTHON = auto()   # Python 后处理
    HYBRID = auto()   # SQL + Python 组合


@dataclass
class FactorDefinition:
    """因子定义"""
    name: str                           # 因子名称
    description: str                    # 描述
    factor_type: FactorType             # 类型

    # SQL 相关
    sql_expr: Optional[str] = None      # SQL 表达式
    sql_cte: Optional[str] = None       # 自定义 CTE（可选）

    # Python 相关
    compute_fn: Optional[Callable] = None  # Python 计算函数

    # 通用
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他因子
    data_source: str = "t_stock_dailymarketdata"          # 默认数据源
    category: str = "misc"              # 分类: valuation/returns/momentum/etc

    # 元数据
    default_value: float = 0.0          # 缺失值填充
    winsorize: bool = True              # 是否缩尾处理
    zscore: bool = False                # 是否自动计算 Z-score

    # 扩展元数据（可选）
    window_days: Optional[int] = None   # 计算窗口天数
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展字段


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
            factor_type=FactorType.SQL,
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
            factor_type=FactorType.PYTHON,
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
            factor_type=FactorType.HYBRID,
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
        sql_factors = [f for f in factors if f.factor_type in (FactorType.SQL, FactorType.HYBRID)]
        python_factors = [f for f in factors if f.factor_type in (FactorType.PYTHON, FactorType.HYBRID)]

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

        # 按数据源分组
        price_factors = [f for f in factors if f.data_source == "t_stock_dailymarketdata"]
        valuation_factors = [f for f in factors if f.data_source == "t_stock_daily_basic"]
        moneyflow_factors = [f for f in factors if f.data_source == "t_stock_moneyflow"]

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
            price_exprs = ["ts_code", "trade_date", "close", "vol", "amount", "pct_chg"]
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

        # 构建最终查询
        select_list = ["COALESCE(p.ts_code, v.ts_code, m.ts_code) as ts_code"]
        from_clause = ""

        # 确定主表
        if price_factors:
            from_clause = "price_data p"
            if valuation_factors:
                from_clause += " LEFT JOIN valuation_data v ON p.ts_code = v.ts_code AND p.trade_date = v.trade_date"
            if moneyflow_factors:
                from_clause += " LEFT JOIN moneyflow_data m ON p.ts_code = m.ts_code AND p.trade_date = m.trade_date"
            where_clause = f"WHERE p.trade_date = %s AND p.ts_code IN ({placeholders})"
        elif valuation_factors:
            from_clause = "valuation_data v"
            if moneyflow_factors:
                from_clause += " LEFT JOIN moneyflow_data m ON v.ts_code = m.ts_code AND v.trade_date = m.trade_date"
            where_clause = f"WHERE v.trade_date = %s AND v.ts_code IN ({placeholders})"
        else:
            from_clause = "moneyflow_data m"
            where_clause = f"WHERE m.trade_date = %s AND m.ts_code IN ({placeholders})"

        # 添加所有因子列
        all_factors = price_factors + valuation_factors + moneyflow_factors
        for f in all_factors:
            # 确定表别名
            if f.data_source == "t_stock_dailymarketdata":
                alias = "p"
            elif f.data_source == "t_stock_daily_basic":
                alias = "v"
            else:
                alias = "m"
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
        params.extend([date_str] + stock_pool)

        return sql, tuple(params)

    def _process_sql_expr(self, expr: str) -> str:
        """处理 SQL 表达式，确保兼容性"""
        return expr


# ==================== 完整因子库定义 ====================

def create_full_registry() -> FactorRegistry:
    """创建完整因子注册表（包含所有预计算因子）"""
    registry = FactorRegistry()

    # ========== 估值因子 (from t_stock_daily_basic) ==========
    valuation_factors = [
        ("pe_ttm", "pe_ttm", "市盈率TTM"),
        ("pb", "pb", "市净率"),
        ("ps_ttm", "ps_ttm", "市销率TTM"),
        ("dividend_yield", "dv_ttm", "股息率"),
        ("total_mv", "total_mv * 10000", "总市值"),
        ("circ_mv", "circ_mv * 10000", "流通市值"),
    ]

    for name, expr, desc in valuation_factors:
        registry.register_sql_factor(
            name=name,
            sql_expr=expr,
            description=desc,
            category="valuation",
            data_source="t_stock_daily_basic"
        )

    # 对数市值（基于 total_mv）
    registry.register_sql_factor(
        name="log_mv",
        sql_expr="LN(NULLIF(total_mv, 0))",
        description="对数市值",
        category="valuation",
        data_source="t_stock_daily_basic"
    )

    # ========== 收益特征因子 ==========
    for period in [20, 60]:
        registry.register_sql_factor(
            name=f"return_{period}d",
            sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER w, 0) - 1)",
            description=f"{period}日收益率",
            category="returns",
            window_days=period
        )

    for period in [20, 60]:
        registry.register_sql_factor(
            name=f"volatility_{period}d",
            sql_expr=f"STDDEV(pct_chg) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {period-1} PRECEDING) * SQRT(252)",
            description=f"{period}日年化波动率",
            category="returns",
            window_days=period
        )

    # 成交量比率
    registry.register_sql_factor(
        name="volume_ratio",
        sql_expr="AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 4 PRECEDING) / NULLIF(AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING), 0)",
        description="5日/20日成交量比率",
        category="returns",
        window_days=20
    )

    # 20日平均成交量
    registry.register_sql_factor(
        name="turnover_20d",
        sql_expr="AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING)",
        description="20日平均成交量",
        category="returns",
        window_days=20
    )

    # ========== 资金流向因子 ==========
    registry.register_sql_factor(
        name="main_net_inflow",
        sql_expr="buy_lg_amount - sell_lg_amount",
        description="主力净流入（大单）",
        category="moneyflow",
        data_source="t_stock_moneyflow"
    )

    for period in [5, 20]:
        registry.register_sql_factor(
            name=f"net_inflow_{period}d",
            sql_expr=f"SUM(buy_lg_amount - sell_lg_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {period-1} PRECEDING)",
            description=f"{period}日累计净流入",
            category="moneyflow",
            data_source="t_stock_moneyflow",
            window_days=period
        )

    # 大单净流入（金额，不是占比）
    registry.register_sql_factor(
        name="large_order_net_amount",
        sql_expr="buy_lg_amount - sell_lg_amount",
        description="大单净流入金额",
        category="moneyflow",
        data_source="t_stock_moneyflow"
    )

    # ========== 横截面 Z-Score (Python 计算) ==========
    zscore_factors = [
        ("pe_ttm", "pe_ttm_zscore"),
        ("pb", "pb_zscore"),
        ("return_20d", "return_20d_zscore"),
        ("volatility_20d", "volatility_20d_zscore"),
    ]

    for base_col, zscore_name in zscore_factors:
        registry.register_python_factor(
            name=zscore_name,
            compute_fn=lambda df, col=base_col: _calc_zscore(df.get(col)),
            dependencies=[base_col],
            description=f"{base_col} 横截面Z-score",
            category="zscore"
        )

    # ========== 市场相对因子 (Python 计算) ==========
    def _calc_market_alpha(df, col):
        """计算市场超额收益"""
        series = df.get(col)
        if series is None or not isinstance(series, pd.Series):
            return pd.Series(0, index=df.index)
        # 转换为 float 避免 Decimal 类型问题
        series = pd.to_numeric(series, errors='coerce')
        return series - series.mean()

    registry.register_python_factor(
        name="market_alpha_20d",
        compute_fn=lambda df, col='return_20d': _calc_market_alpha(df, col),
        dependencies=["return_20d"],
        description="20日市场超额收益",
        category="relative"
    )

    registry.register_python_factor(
        name="market_alpha_60d",
        compute_fn=lambda df, col='return_60d': _calc_market_alpha(df, col),
        dependencies=["return_60d"],
        description="60日市场超额收益",
        category="relative"
    )

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


# 单例实例
_full_registry: Optional[FactorRegistry] = None


def get_full_registry() -> FactorRegistry:
    """获取完整因子注册表"""
    global _full_registry
    if _full_registry is None:
        _full_registry = create_full_registry()
    return _full_registry
