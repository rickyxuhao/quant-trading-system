"""
统一因子定义清单

作为所有因子的"唯一真相源"(Single Source of Truth)，本文件定义了系统中所有可用的因子。
每个因子包含完整的元数据：名称、描述、分类、数据来源、计算方式等。

使用方式:
    from factor_definitions import FACTOR_DEFINITIONS, get_factor_lineage

    # 获取因子定义
    pe_def = FACTOR_DEFINITIONS["pe_ttm"]

    # 获取数据血缘
    lineage = get_factor_lineage("return_20d")

作者: Claude
创建日期: 2026-03-19
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto


class CalculationType(Enum):
    """因子计算类型"""
    DIRECT = auto()      # 直接取自数据库字段
    SQL = auto()         # SQL 窗口函数计算
    PYTHON = auto()      # Python 计算（如 TA-Lib）
    HYBRID = auto()      # SQL + Python 组合
    DERIVED = auto()     # 基于其他因子计算


@dataclass
class FactorDefinition:
    """
    因子定义数据类

    Attributes:
        name: 因子名称（唯一标识）
        description: 因子中文描述
        category: 分类（valuation/returns/momentum/volatility/moneyflow/financial/liquidity/technical/zscore/relative/risk）
        calculation: 计算类型
        data_source: 数据源表名
        source_field: 源字段名
        sql_expr: SQL 表达式（SQL/HYBRID类型需要）
        window_days: 计算窗口天数（时序因子需要）
        dependencies: 依赖的其他因子列表
        default_value: 缺失值填充默认值
        winsorize: 是否进行缩尾处理（1%-99%）
        valid_range: 有效值范围元组 (min, max)，None表示无限制
        extra: 扩展字段
    """
    name: str
    description: str
    category: str
    calculation: CalculationType

    # 数据源信息
    data_source: Optional[str] = None
    source_field: Optional[str] = None

    # SQL 相关
    sql_expr: Optional[str] = None
    window_days: Optional[int] = None

    # Python 相关
    dependencies: List[str] = field(default_factory=list)

    # 数据处理
    default_value: Optional[float] = None
    winsorize: bool = False
    valid_range: Optional[tuple] = None

    # 扩展
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "calculation": self.calculation.name,
            "data_source": self.data_source,
            "source_field": self.source_field,
            "sql_expr": self.sql_expr,
            "window_days": self.window_days,
            "dependencies": self.dependencies,
            "default_value": self.default_value,
            "winsorize": self.winsorize,
            "valid_range": self.valid_range,
        }


# ============================================================================
# 因子定义清单
# ============================================================================

FACTOR_DEFINITIONS: Dict[str, FactorDefinition] = {}


def _register_factor(factor: FactorDefinition):
    """注册因子定义"""
    FACTOR_DEFINITIONS[factor.name] = factor


# =============================================================================
# 1. 估值因子 (Valuation Factors) - 来自 t_stock_daily_basic
# =============================================================================

_register_factor(FactorDefinition(
    name="pe_ttm",
    description="市盈率TTM (Price-to-Earnings Ratio TTM)",
    category="valuation",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="pe_ttm",
    sql_expr="pe_ttm",
    winsorize=True,
    valid_range=(0, 1000),
))

_register_factor(FactorDefinition(
    name="pb",
    description="市净率 (Price-to-Book Ratio)",
    category="valuation",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="pb",
    sql_expr="pb",
    winsorize=True,
    valid_range=(0, 100),
))

_register_factor(FactorDefinition(
    name="ps_ttm",
    description="市销率TTM (Price-to-Sales Ratio TTM)",
    category="valuation",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="ps_ttm",
    sql_expr="ps_ttm",
    winsorize=True,
))

# Note: pcf_ncf_ttm column does not exist in t_stock_daily_basic, removed
# _register_factor(FactorDefinition(
#     name="pcf",
#     description="市现率 (Price-to-Cash-Flow)",
#     category="valuation",
#     calculation=CalculationType.DIRECT,
#     data_source="t_stock_daily_basic",
#     source_field="pcf_ncf_ttm",
#     sql_expr="pcf_ncf_ttm",
#     winsorize=True,
# ))

_register_factor(FactorDefinition(
    name="dividend_yield",
    description="股息率TTM (Dividend Yield)",
    category="valuation",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="dv_ttm",
    sql_expr="dv_ttm",
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="total_mv",
    description="总市值 (元)",
    category="valuation",
    calculation=CalculationType.SQL,
    data_source="t_stock_daily_basic",
    source_field="total_mv",
    sql_expr="total_mv * 10000",  # 转换为元
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="circ_mv",
    description="流通市值 (元)",
    category="valuation",
    calculation=CalculationType.SQL,
    data_source="t_stock_daily_basic",
    source_field="circ_mv",
    sql_expr="circ_mv * 10000",  # 转换为元
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="log_mv",
    description="对数总市值",
    category="valuation",
    calculation=CalculationType.SQL,
    data_source="t_stock_daily_basic",
    source_field="total_mv",
    sql_expr="LN(NULLIF(total_mv, 0))",
    dependencies=["total_mv"],
))

_register_factor(FactorDefinition(
    name="ep_ttm",
    description="盈利收益率TTM (Earnings Yield = 1/PE)",
    category="valuation",
    calculation=CalculationType.SQL,
    data_source="t_stock_daily_basic",
    source_field="pe_ttm",
    sql_expr="1/NULLIF(pe_ttm, 0)",
    dependencies=["pe_ttm"],
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="bp",
    description="账面市值比 (Book-to-Market = 1/PB)",
    category="valuation",
    calculation=CalculationType.SQL,
    data_source="t_stock_daily_basic",
    source_field="pb",
    sql_expr="1/NULLIF(pb, 0)",
    dependencies=["pb"],
    winsorize=True,
))


# =============================================================================
# 2. 收益特征因子 (Return Characteristics) - 来自 t_stock_dailymarketdata
# =============================================================================

for period in [5, 10, 20, 60, 120, 250]:
    _register_factor(FactorDefinition(
        name=f"return_{period}d",
        description=f"{period}日收益率",
        category="returns" if period <= 60 else "momentum",
        calculation=CalculationType.SQL,
        data_source="t_stock_dailymarketdata",
        source_field="close",
        sql_expr=f"(close / NULLIF(LAG(close, {period}) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1)",
        window_days=period,
        default_value=0.0,
        winsorize=True,
        valid_range=(-0.5, 0.5),
    ))

for period in [5, 10, 20, 60, 120, 250]:
    _register_factor(FactorDefinition(
        name=f"volatility_{period}d",
        description=f"{period}日年化波动率",
        category="returns" if period <= 60 else "momentum",
        calculation=CalculationType.SQL,
        data_source="t_stock_dailymarketdata",
        source_field="pct_chg",
        sql_expr=f"STDDEV(pct_chg) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {period-1} PRECEDING) * SQRT(252)",
        window_days=period,
        default_value=0.0,
        winsorize=True,
    ))

_register_factor(FactorDefinition(
    name="volume_ratio",
    description="5日/20日成交量比率 (Volume Ratio)",
    category="returns",
    calculation=CalculationType.SQL,
    data_source="t_stock_dailymarketdata",
    source_field="vol",
    sql_expr="AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 4 PRECEDING) / NULLIF(AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING), 0)",
    window_days=20,
    default_value=1.0,
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="turnover_20d",
    description="20日平均成交量",
    category="returns",
    calculation=CalculationType.SQL,
    data_source="t_stock_dailymarketdata",
    source_field="vol",
    sql_expr="AVG(vol) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING)",
    window_days=20,
))


# =============================================================================
# 3. 流动性因子 (Liquidity) - 来自 t_stock_daily_basic
# =============================================================================

_register_factor(FactorDefinition(
    name="turnover_rate",
    description="换手率(%)",
    category="liquidity",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="turnover_rate",
    sql_expr="turnover_rate",
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="turnover_rate_f",
    description="自由流通股换手率(%)",
    category="liquidity",
    calculation=CalculationType.DIRECT,
    data_source="t_stock_daily_basic",
    source_field="turnover_rate_f",
    sql_expr="turnover_rate_f",
    winsorize=True,
))

_register_factor(FactorDefinition(
    name="turnover_volatility_20d",
    description="20日换手率波动率 (变异系数)",
    category="liquidity",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_daily_basic",
    source_field="turnover_rate",
    dependencies=["turnover_rate"],
    window_days=20,
))


# =============================================================================
# 4. 资金流向因子 (Money Flow) - 来自 t_stock_moneyflow
# =============================================================================

_register_factor(FactorDefinition(
    name="main_net_inflow",
    description="主力净流入（大单买入-卖出，元）",
    category="moneyflow",
    calculation=CalculationType.SQL,
    data_source="t_stock_moneyflow",
    source_field="buy_lg_amount, sell_lg_amount",
    sql_expr="buy_lg_amount - sell_lg_amount",
))

_register_factor(FactorDefinition(
    name="large_order_net_amount",
    description="大单净流入金额（元）",
    category="moneyflow",
    calculation=CalculationType.SQL,
    data_source="t_stock_moneyflow",
    source_field="buy_lg_amount, sell_lg_amount",
    sql_expr="buy_lg_amount - sell_lg_amount",
))

for period in [5, 20]:
    _register_factor(FactorDefinition(
        name=f"net_inflow_{period}d",
        description=f"{period}日累计净流入（元）",
        category="moneyflow",
        calculation=CalculationType.SQL,
        data_source="t_stock_moneyflow",
        source_field="buy_lg_amount, sell_lg_amount",
        sql_expr=f"SUM(buy_lg_amount - sell_lg_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS {period-1} PRECEDING)",
        window_days=period,
        default_value=0.0,
    ))

_register_factor(FactorDefinition(
    name="large_order_net_ratio",
    description="大单净流入占比",
    category="moneyflow",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_moneyflow",
    source_field="buy_lg_amount, sell_lg_amount, amount",
    dependencies=["large_order_net_amount"],
))


# =============================================================================
# 5. 财务质量因子 (Financial Quality) - 来自 t_stock_fina_indicator
# =============================================================================

FINANCIAL_FACTORS = [
    ("roe", "roe", "净资产收益率ROE (%)"),
    ("roa", "roa", "总资产收益率ROA (%)"),
    ("gross_margin", "gross_profit_margin", "销售毛利率 (%)"),
    ("net_margin", "net_profit_margin", "销售净利率 (%)"),
    ("debt_to_assets", "debt_to_assets", "资产负债率 (%)"),
    ("current_ratio", "current_ratio", "流动比率"),
    ("quick_ratio", "quick_ratio", "速动比率"),
    ("asset_turnover", "asset_turnover", "总资产周转率"),
    ("ca_turnover", "ca_turnover", "流动资产周转率"),
    ("eps", "basic_eps_yoy", "每股收益同比增长率 (%)"),
    ("bps", "bps_yoy", "每股净资产同比增长率 (%)"),
]

for name, field, desc in FINANCIAL_FACTORS:
    # Note: t_stock_fina_indicator does not have trade_date column
    # It uses end_date instead. These factors need special handling.
    _register_factor(FactorDefinition(
        name=name,
        description=desc,
        category="financial",
        calculation=CalculationType.PYTHON,  # Changed from DIRECT due to no trade_date
        data_source="t_stock_fina_indicator",
        source_field=field,
        # sql_expr is not used for PYTHON type, but we keep it for reference
        sql_expr=f"(SELECT {field} FROM t_stock_fina_indicator fi WHERE fi.ts_code = ts_code AND fi.end_date <= trade_date ORDER BY fi.end_date DESC LIMIT 1)",
        winsorize=True,
    ))


# =============================================================================
# 6. 技术因子 (Technical Indicators) - Python 计算
# =============================================================================

_register_factor(FactorDefinition(
    name="rsi_14d",
    description="14日相对强弱指数 RSI",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=14,
    default_value=50.0,
    valid_range=(0, 100),
))

_register_factor(FactorDefinition(
    name="macd",
    description="MACD 指标",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
))

_register_factor(FactorDefinition(
    name="macd_signal",
    description="MACD 信号线",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
))

_register_factor(FactorDefinition(
    name="macd_hist",
    description="MACD 柱状线",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
))

_register_factor(FactorDefinition(
    name="bb_upper",
    description="布林带上轨 (Bollinger Upper)",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=20,
))

_register_factor(FactorDefinition(
    name="bb_middle",
    description="布林带中轨 (20日均线)",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=20,
))

_register_factor(FactorDefinition(
    name="bb_lower",
    description="布林带下轨 (Bollinger Lower)",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=20,
))

_register_factor(FactorDefinition(
    name="bb_width",
    description="布林带宽度 (Upper-Lower)/Middle",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=20,
))

_register_factor(FactorDefinition(
    name="bb_position",
    description="布林带位置 (0-1之间，接近1表示接近上轨)",
    category="technical",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="close",
    dependencies=["close"],
    window_days=20,
    default_value=0.5,
    valid_range=(0, 1),
))


# =============================================================================
# 7. 波动率因子 (Volatility)
# =============================================================================

_register_factor(FactorDefinition(
    name="tr",
    description="真实波幅 True Range",
    category="volatility",
    calculation=CalculationType.SQL,
    data_source="t_stock_dailymarketdata",
    source_field="high, low, close",
    sql_expr="GREATEST(high - low, ABS(high - LAG(close, 1) OVER (PARTITION BY ts_code ORDER BY trade_date)), ABS(low - LAG(close, 1) OVER (PARTITION BY ts_code ORDER BY trade_date)))",
    window_days=2,
))

_register_factor(FactorDefinition(
    name="atr_14d",
    description="14日平均真实波幅 ATR",
    category="volatility",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="high, low, close",
    dependencies=["tr"],
    window_days=14,
))

_register_factor(FactorDefinition(
    name="downside_vol_20d",
    description="20日下行波动率（只计算负收益部分）",
    category="volatility",
    calculation=CalculationType.PYTHON,
    data_source="t_stock_dailymarketdata",
    source_field="pct_chg",
    dependencies=["pct_chg"],
    window_days=20,
))

_register_factor(FactorDefinition(
    name="price_position_20d",
    description="20日价格位置 (0-1之间，接近1表示接近高点)",
    category="volatility",
    calculation=CalculationType.SQL,
    data_source="t_stock_dailymarketdata",
    source_field="high, low, close",
    sql_expr="(close - MIN(low) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING)) / NULLIF(MAX(high) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING) - MIN(low) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING), 0)",
    window_days=20,
    default_value=0.5,
    valid_range=(0, 1),
))


# =============================================================================
# 8. 风险因子 (Risk)
# =============================================================================

for period in [20, 60]:
    _register_factor(FactorDefinition(
        name=f"max_drawdown_{period}d",
        description=f"{period}日最大回撤",
        category="risk",
        calculation=CalculationType.PYTHON,
        data_source="t_stock_dailymarketdata",
        source_field="close",
        dependencies=["close"],
        window_days=period,
        default_value=0.0,
        valid_range=(0, 1),
    ))


# =============================================================================
# 9. 横截面标准化因子 (Z-Score)
# =============================================================================

ZSCORE_BASE_FACTORS = [
    ("pe_ttm", "pe_ttm_zscore"),
    ("pb", "pb_zscore"),
    ("ps_ttm", "ps_ttm_zscore"),
    ("return_20d", "return_20d_zscore"),
    ("volatility_20d", "volatility_20d_zscore"),
    ("turnover_rate", "turnover_rate_zscore"),
    ("ep_ttm", "ep_ttm_zscore"),
    ("bp", "bp_zscore"),
]

for base_col, zscore_name in ZSCORE_BASE_FACTORS:
    _register_factor(FactorDefinition(
        name=zscore_name,
        description=f"{base_col} 横截面Z-score",
        category="zscore",
        calculation=CalculationType.PYTHON,
        data_source="derived",
        dependencies=[base_col],
        default_value=0.0,
        valid_range=(-5, 5),
    ))


# =============================================================================
# 10. 相对市场/行业因子 (Relative)
# =============================================================================

for period in [20, 60]:
    _register_factor(FactorDefinition(
        name=f"market_alpha_{period}d",
        description=f"{period}日市场超额收益",
        category="relative",
        calculation=CalculationType.PYTHON,
        data_source="derived",
        dependencies=[f"return_{period}d"],
        default_value=0.0,
    ))

for period in [20, 60]:
    _register_factor(FactorDefinition(
        name=f"sector_alpha_{period}d",
        description=f"{period}日行业超额收益",
        category="relative",
        calculation=CalculationType.PYTHON,
        data_source="derived",
        dependencies=[f"return_{period}d", "industry"],
        default_value=0.0,
    ))

_register_factor(FactorDefinition(
    name="sector_rank_20d",
    description="20日行业内收益率排名 (0-1)",
    category="relative",
    calculation=CalculationType.PYTHON,
    data_source="derived",
    dependencies=["return_20d", "industry"],
    default_value=0.5,
    valid_range=(0, 1),
))


# =============================================================================
# 辅助函数
# =============================================================================

def get_factor_lineage(factor_name: str) -> Dict[str, Any]:
    """
    获取因子的数据血缘信息

    Args:
        factor_name: 因子名称

    Returns:
        包含血缘信息的字典，包括：
        - factor: 因子定义
        - source_table: 源数据表
        - source_fields: 源字段列表
        - dependencies: 依赖因子
        - calculation_path: 计算路径
    """
    factor = FACTOR_DEFINITIONS.get(factor_name)
    if not factor:
        return {"error": f"Factor '{factor_name}' not found"}

    # 解析 source_field（可能包含多个字段）
    source_fields = []
    if factor.source_field:
        source_fields = [f.strip() for f in factor.source_field.split(",")]

    return {
        "factor_name": factor.name,
        "description": factor.description,
        "category": factor.category,
        "source_table": factor.data_source,
        "source_fields": source_fields,
        "calculation_type": factor.calculation.name,
        "sql_expression": factor.sql_expr,
        "dependencies": factor.dependencies,
        "calculation_path": _build_calculation_path(factor),
    }


def _build_calculation_path(factor: FactorDefinition, depth: int = 0) -> List[str]:
    """递归构建计算路径"""
    if depth > 5:  # 防止循环依赖
        return ["... (max depth reached)"]

    path = [f"{factor.name} ({factor.calculation.name})"]

    for dep_name in factor.dependencies:
        dep_factor = FACTOR_DEFINITIONS.get(dep_name)
        if dep_factor:
            dep_path = _build_calculation_path(dep_factor, depth + 1)
            for dp in dep_path:
                path.append("  " + dp)

    return path


def get_factors_by_category(category: str) -> List[FactorDefinition]:
    """按分类获取因子列表"""
    return [f for f in FACTOR_DEFINITIONS.values() if f.category == category]


def get_factors_by_data_source(data_source: str) -> List[FactorDefinition]:
    """按数据源获取因子列表"""
    return [f for f in FACTOR_DEFINITIONS.values() if f.data_source == data_source]


def get_factors_by_calculation_type(calc_type: CalculationType) -> List[FactorDefinition]:
    """按计算类型获取因子列表"""
    return [f for f in FACTOR_DEFINITIONS.values() if f.calculation == calc_type]


def list_all_factors() -> List[str]:
    """列出所有因子名称"""
    return list(FACTOR_DEFINITIONS.keys())


def get_factor_statistics() -> Dict[str, Any]:
    """获取因子统计信息"""
    stats = {
        "total_count": len(FACTOR_DEFINITIONS),
        "by_category": {},
        "by_data_source": {},
        "by_calculation_type": {},
    }

    for factor in FACTOR_DEFINITIONS.values():
        # 按分类统计
        stats["by_category"][factor.category] = stats["by_category"].get(factor.category, 0) + 1

        # 按数据源统计
        ds = factor.data_source or "unknown"
        stats["by_data_source"][ds] = stats["by_data_source"].get(ds, 0) + 1

        # 按计算类型统计
        ct = factor.calculation.name
        stats["by_calculation_type"][ct] = stats["by_calculation_type"].get(ct, 0) + 1

    return stats


def print_factor_lineage(factor_name: str):
    """打印因子的数据血缘信息（用于调试）"""
    lineage = get_factor_lineage(factor_name)

    if "error" in lineage:
        print(f"Error: {lineage['error']}")
        return

    print(f"\n因子: {lineage['factor_name']}")
    print(f"描述: {lineage['description']}")
    print(f"分类: {lineage['category']}")
    print(f"\n数据源表: {lineage['source_table']}")
    print(f"源字段: {', '.join(lineage['source_fields'])}")
    print(f"计算类型: {lineage['calculation_type']}")

    if lineage['sql_expression']:
        print(f"\nSQL表达式:")
        print(f"  {lineage['sql_expression']}")

    if lineage['dependencies']:
        print(f"\n依赖因子: {', '.join(lineage['dependencies'])}")

    print(f"\n计算路径:")
    for line in lineage['calculation_path']:
        print(f"  {line}")


def print_all_factors_summary():
    """打印所有因子的汇总信息"""
    stats = get_factor_statistics()

    print("=" * 60)
    print(f"因子定义清单汇总 (共 {stats['total_count']} 个因子)")
    print("=" * 60)

    print("\n按分类统计:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"  {cat:20s}: {count:3d} 个")

    print("\n按数据源统计:")
    for ds, count in sorted(stats["by_data_source"].items()):
        print(f"  {ds:30s}: {count:3d} 个")

    print("\n按计算类型统计:")
    for ct, count in sorted(stats["by_calculation_type"].items()):
        print(f"  {ct:15s}: {count:3d} 个")


# =============================================================================
# 主程序入口（用于测试）
# =============================================================================

if __name__ == "__main__":
    # 打印汇总信息
    print_all_factors_summary()

    # 示例：打印几个因子的血缘
    print("\n" + "=" * 60)
    print("示例因子血缘")
    print("=" * 60)

    for factor_name in ["pe_ttm", "return_20d", "ep_ttm", "atr_14d"]:
        print_factor_lineage(factor_name)
        print()
