"""
量化交易回测框架 - 第三阶段增强版

提供完善的回测引擎、精细化风险管理和成本建模能力。

主要模块:
- risk_config: 风控配置类
- enhanced_risk_manager: 增强版风险管理器
- position_sizing: 仓位管理模块（Kelly、风险平价、波动率目标）
- transaction_cost: 多资产交易成本模型
- slippage: 滑点模型
- comminfo: Backtrader佣金方案集成
- data_feed: MySQL数据源
- analyzers: 自定义分析器（Calmar、Sortino等）
- multi_strategy: 多策略并行回测

Example:
    >>> from projects.quant_trading.backtest import (
    ...     EnhancedRiskManager, EnhancedRiskConfig,
    ...     KellyPositionSizer, RiskParityPositionSizer,
    ...     StockCostModel, PercentageSlippage,
    ...     MySQLDataFeed, run_multiple_strategies
    ... )
"""

# 风险配置
from projects.quant_trading.backtest.risk_config import (
    EnhancedRiskConfig,
    ExitType,
    create_conservative_risk_config,
    create_aggressive_risk_config,
    create_trend_following_config,
    create_mean_reversion_config,
)

# 增强版风险管理
from projects.quant_trading.backtest.enhanced_risk_manager import (
    EnhancedRiskManager,
    ExitSignal,
    PositionTracker,
    SubPosition,
)

# 仓位管理
from projects.quant_trading.backtest.position_sizing import (
    # 基类
    BasePositionSizer,
    SizingResult,
    PositionSizingMethod,
    # 具体实现
    FixedPositionSizer,
    KellyPositionSizer,
    RiskParityPositionSizer,
    VolatilityTargetSizer,
    DrawdownController,
    CompositePositionSizer,
    # 便捷函数
    create_kelly_vol_composite,
    create_full_risk_controlled_sizer,
)

# 交易成本模型
from projects.quant_trading.backtest.transaction_cost import (
    # 基类
    CostModel,
    CostBreakdown,
    AssetType,
    TradeDirection,
    # 具体实现
    StockCostModel,
    ETFCostModel,
    FundCostModel,
    FuturesCostModel,
    OptionsCostModel,
    CryptocurrencyCostModel,
    CompositeCostModel,
    # 便捷函数
    create_stock_cost_model,
    create_etf_cost_model,
    create_fund_cost_model,
    create_futures_cost_model,
)

# 滑点模型
from projects.quant_trading.backtest.slippage import (
    # 基类
    SlippageModel,
    # 具体实现
    FixedSlippage,
    PercentageSlippage,
    VolatilitySlippage,
    VolumeImpactSlippage,
    SpreadBasedSlippage,
    TimeBasedSlippage,
    CompositeSlippage,
    AdaptiveSlippage,
    # 便捷函数
    create_default_slippage_model,
    create_conservative_slippage_model,
    create_aggressive_slippage_model,
    create_adaptive_slippage_model,
)

# Backtrader佣金方案
from projects.quant_trading.backtest.comminfo import (
    EnhancedChinaCommInfo,
    CostModelCommInfo,
    SlippageCommissionInfo,
    MultiAssetCommInfo,
    # 便捷函数
    create_stock_commission,
    create_etf_commission,
    setup_china_stock_commission,
)

# 数据源
from projects.quant_trading.backtest.data_feed import (
    MySQLDataFeed,
    MultiSymbolDataFeed,
    PandasDataFeed,
    # 便捷函数
    create_data_feed,
    load_stock_data,
)

# 分析器
from projects.quant_trading.backtest.analyzers import (
    CalmarRatio,
    SortinoRatio,
    TradeDetailAnalyzer,
    ModelPredictionAnalyzer,
    ReturnAttribution,
    EnhancedTradeAnalyzer,
    # 便捷函数
    add_all_analyzers,
    get_analyzer_results,
)

# 多策略回测
from projects.quant_trading.backtest.multi_strategy import (
    BacktestResult,
    BacktestConfig,
    run_multiple_strategies,
    compare_strategies,
    plot_comparison,
    save_results_to_csv,
    save_results_to_database,
    quick_backtest_comparison,
)

# 保留原有导出
from projects.quant_trading.backtest.risk_manager import (
    RiskConfig,
    RiskManager,
    RiskAlert,
    RiskSeverity,
    RiskAlertType,
    create_conservative_config,
    create_aggressive_config,
)

from projects.quant_trading.backtest.engine import (
    BacktestEngine,
    BacktestConfig as EngineConfig,
    BacktestStats,
    BacktestEvent,
)

from projects.quant_trading.backtest.data_manager import (
    DataManager,
    StockData,
    IndexData,
    MissingDataError,
)

__version__ = "3.0.0"
__all__ = [
    # 风控配置
    "EnhancedRiskConfig",
    "ExitType",
    "create_conservative_risk_config",
    "create_aggressive_risk_config",
    "create_trend_following_config",
    "create_mean_reversion_config",

    # 风险管理
    "EnhancedRiskManager",
    "ExitSignal",
    "PositionTracker",
    "SubPosition",

    # 仓位管理
    "BasePositionSizer",
    "SizingResult",
    "PositionSizingMethod",
    "FixedPositionSizer",
    "KellyPositionSizer",
    "RiskParityPositionSizer",
    "VolatilityTargetSizer",
    "DrawdownController",
    "CompositePositionSizer",

    # 交易成本
    "CostModel",
    "CostBreakdown",
    "AssetType",
    "TradeDirection",
    "StockCostModel",
    "ETFCostModel",
    "FundCostModel",
    "FuturesCostModel",
    "OptionsCostModel",
    "CryptocurrencyCostModel",
    "CompositeCostModel",

    # 滑点
    "SlippageModel",
    "FixedSlippage",
    "PercentageSlippage",
    "VolatilitySlippage",
    "VolumeImpactSlippage",
    "SpreadBasedSlippage",
    "TimeBasedSlippage",
    "CompositeSlippage",
    "AdaptiveSlippage",

    # Backtrader集成
    "EnhancedChinaCommInfo",
    "CostModelCommInfo",
    "SlippageCommissionInfo",
    "MultiAssetCommInfo",

    # 数据源
    "MySQLDataFeed",
    "MultiSymbolDataFeed",
    "PandasDataFeed",

    # 分析器
    "CalmarRatio",
    "SortinoRatio",
    "TradeDetailAnalyzer",
    "ModelPredictionAnalyzer",
    "ReturnAttribution",
    "EnhancedTradeAnalyzer",

    # 多策略回测
    "BacktestResult",
    "BacktestConfig",
    "run_multiple_strategies",
    "compare_strategies",
    "plot_comparison",
    "save_results_to_csv",
    "save_results_to_database",
    "quick_backtest_comparison",

    # 原有导出
    "RiskConfig",
    "RiskManager",
    "RiskAlert",
    "RiskSeverity",
    "RiskAlertType",
    "BacktestEngine",
    "EngineConfig",
    "BacktestStats",
    "BacktestEvent",
    "DataManager",
    "StockData",
    "IndexData",
    "MissingDataError",
]
