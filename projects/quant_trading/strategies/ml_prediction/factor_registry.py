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

        # 按数据源分组（只包含SQL和HYBRID类型的因子）
        sql_factors = [f for f in factors if f.factor_type in (FactorType.SQL, FactorType.HYBRID)]
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

    # 盈利收益率 EP = 1/PE (价值因子)
    registry.register_sql_factor(
        name="ep_ttm",
        sql_expr="1/NULLIF(pe_ttm, 0)",
        description="盈利收益率TTM (Earnings Yield)",
        category="valuation",
        data_source="t_stock_daily_basic"
    )

    # 账面市值比 BP = 1/PB (价值因子)
    registry.register_sql_factor(
        name="bp",
        sql_expr="1/NULLIF(pb, 0)",
        description="账面市值比 (Book-to-Market)",
        category="valuation",
        data_source="t_stock_daily_basic"
    )

    # 换手率 (来自 daily_basic)
    registry.register_sql_factor(
        name="turnover_rate",
        sql_expr="turnover_rate",
        description="换手率(%)",
        category="liquidity",
        data_source="t_stock_daily_basic"
    )

    # 换手率自由流通股本
    registry.register_sql_factor(
        name="turnover_rate_f",
        sql_expr="turnover_rate_f",
        description="自由流通股换手率(%)",
        category="liquidity",
        data_source="t_stock_daily_basic"
    )

    # ========== 收益特征因子 ==========
    # 短期反转因子 (5日、10日)
    for period in [5, 10]:
        registry.register_sql_factor(
            name=f"return_{period}d",
            sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER w, 0) - 1)",
            description=f"{period}日收益率（短期反转）",
            category="returns",
            window_days=period
        )

    for period in [20, 60]:
        registry.register_sql_factor(
            name=f"return_{period}d",
            sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER w, 0) - 1)",
            description=f"{period}日收益率",
            category="returns",
            window_days=period
        )

    for period in [5, 10, 20, 60]:
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

    # ========== 流动性因子 (Liquidity) ==========
    # 换手率波动率（基于日频换手率计算）
    registry.register_python_factor(
        name="turnover_volatility_20d",
        compute_fn=lambda df: _calc_turnover_volatility(df, period=20),
        dependencies=["turnover_rate"],
        description="20日换手率波动率",
        category="liquidity"
    )

    # ========== 风险因子 (Risk) ==========
    # 20日最大回撤
    registry.register_python_factor(
        name="max_drawdown_20d",
        compute_fn=lambda df: _calc_max_drawdown(df, period=20),
        dependencies=["close"],
        description="20日最大回撤",
        category="risk"
    )

    # 60日最大回撤
    registry.register_python_factor(
        name="max_drawdown_60d",
        compute_fn=lambda df: _calc_max_drawdown(df, period=60),
        dependencies=["close"],
        description="60日最大回撤",
        category="risk"
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
        ("turnover_rate", "turnover_rate_zscore"),
        ("ep_ttm", "ep_ttm_zscore"),
        ("bp", "bp_zscore"),
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

    # ========== 动量因子（扩展长周期）==========
    for period in [120, 250]:
        registry.register_sql_factor(
            name=f"return_{period}d",
            sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER w, 0) - 1)",
            description=f"{period}日收益率（长期动量）",
            category="momentum",
            window_days=period
        )

    for period in [120, 250]:
        registry.register_sql_factor(
            name=f"volatility_{period}d",
            sql_expr=f"STDDEV(pct_chg) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {period-1} PRECEDING) * SQRT(252)",
            description=f"{period}日年化波动率",
            category="momentum",
            window_days=period
        )

    # 价格位置因子（相对于近期高低点）
    registry.register_sql_factor(
        name="price_position_20d",
        sql_expr="(close - MIN(low) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING)) / NULLIF(MAX(high) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING) - MIN(low) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING), 0)",
        description="20日价格位置（0-1之间，接近1表示接近高点）",
        category="momentum",
        window_days=20
    )

    # ========== 财务因子 (from t_stock_fina_indicator) ==========
    financial_factors = [
        ("roe", "roe", "净资产收益率ROE"),
        ("roa", "roa", "总资产收益率ROA"),
        ("gross_margin", "gross_profit_margin", "销售毛利率"),
        ("net_margin", "net_profit_margin", "销售净利率"),
        ("debt_to_assets", "debt_to_assets", "资产负债率"),
        ("current_ratio", "current_ratio", "流动比率"),
        ("quick_ratio", "quick_ratio", "速动比率"),
        ("asset_turnover", "asset_turnover", "总资产周转率"),
        # Note: inv_turn not available in t_stock_fina_indicator, using ca_turnover instead
        ("ca_turnover", "ca_turnover", "流动资产周转率"),
        ("eps", "basic_eps_yoy", "每股收益同比增长"),
        ("bps", "bps_yoy", "每股净资产同比增长"),
    ]

    for name, expr, desc in financial_factors:
        registry.register_sql_factor(
            name=name,
            sql_expr=expr,
            description=desc,
            category="financial",
            data_source="t_stock_fina_indicator"
        )

    # ========== 波动率因子（ATR、下行波动率）==========
    # 真实波幅（需要使用high/low/close）
    registry.register_sql_factor(
        name="tr",
        sql_expr="GREATEST(high - low, ABS(high - LAG(close, 1) OVER w), ABS(low - LAG(close, 1) OVER w))",
        description="真实波幅TR",
        category="volatility",
        window_days=2
    )

    # ATR (14日)
    registry.register_python_factor(
        name="atr_14d",
        compute_fn=lambda df: _calc_atr(df, period=14),
        dependencies=["tr"],
        description="14日平均真实波幅ATR",
        category="volatility"
    )

    # 下行波动率（只计算负收益的波动）
    registry.register_python_factor(
        name="downside_vol_20d",
        compute_fn=lambda df: _calc_downside_vol(df, period=20),
        dependencies=["return_20d"],
        description="20日下行波动率（只计算亏损部分）",
        category="volatility"
    )

    # ========== 技术因子（RSI、MACD、布林带）==========
    # RSI (14日)
    registry.register_python_factor(
        name="rsi_14d",
        compute_fn=lambda df: _calc_rsi(df, period=14),
        dependencies=["close"],
        description="14日相对强弱指数RSI",
        category="technical"
    )

    # MACD
    registry.register_python_factor(
        name="macd",
        compute_fn=lambda df: _calc_macd(df)["macd"],
        dependencies=["close"],
        description="MACD指标",
        category="technical"
    )

    registry.register_python_factor(
        name="macd_signal",
        compute_fn=lambda df: _calc_macd(df)["signal"],
        dependencies=["close"],
        description="MACD信号线",
        category="technical"
    )

    registry.register_python_factor(
        name="macd_hist",
        compute_fn=lambda df: _calc_macd(df)["hist"],
        dependencies=["close"],
        description="MACD柱状线",
        category="technical"
    )

    # 布林带
    registry.register_python_factor(
        name="bb_upper",
        compute_fn=lambda df: _calc_bollinger(df, period=20, std_dev=2)["upper"],
        dependencies=["close"],
        description="布林带上轨",
        category="technical"
    )

    registry.register_python_factor(
        name="bb_middle",
        compute_fn=lambda df: _calc_bollinger(df, period=20, std_dev=2)["middle"],
        dependencies=["close"],
        description="布林带中轨（20日均线）",
        category="technical"
    )

    registry.register_python_factor(
        name="bb_lower",
        compute_fn=lambda df: _calc_bollinger(df, period=20, std_dev=2)["lower"],
        dependencies=["close"],
        description="布林带下轨",
        category="technical"
    )

    registry.register_python_factor(
        name="bb_width",
        compute_fn=lambda df: _calc_bollinger(df, period=20, std_dev=2)["width"],
        dependencies=["close"],
        description="布林带宽度（(上轨-下轨)/中轨）",
        category="technical"
    )

    registry.register_python_factor(
        name="bb_position",
        compute_fn=lambda df: _calc_bollinger(df, period=20, std_dev=2)["position"],
        dependencies=["close"],
        description="布林带位置（0-1之间）",
        category="technical"
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
