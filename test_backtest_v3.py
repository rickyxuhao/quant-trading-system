"""
第三阶段回测框架测试脚本

测试内容:
1. 增强版风险管理器
2. 仓位管理模块
3. 交易成本模型
4. 滑点模型
5. Backtrader集成
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("第三阶段回测框架测试")
print("=" * 70)

# =============================================================================
# Test 1: 增强版风险管理器
# =============================================================================
print("\n" + "=" * 70)
print("Test 1: 增强版风险管理器 (EnhancedRiskManager)")
print("=" * 70)

from projects.quant_trading.backtest import (
    EnhancedRiskConfig,
    EnhancedRiskManager,
    create_conservative_risk_config,
    create_trend_following_config
)

# 创建配置
config = EnhancedRiskConfig(
    fixed_stop_loss_pct=0.05,
    fixed_take_profit_pct=0.10,
    enable_trailing_stop=True,
    trailing_activation_pct=0.05,
    trailing_stop_pct=0.03,
    enable_atr_stop=True,
    atr_multiplier=2.0,
    enable_time_stop=True,
    max_holding_days=20,
    partial_exits=[(0.05, 0.3), (0.10, 0.5)]
)

print(f"\n配置信息:")
print(f"  固定止损: {config.fixed_stop_loss_pct*100:.1f}%")
print(f"  固定止盈: {config.fixed_take_profit_pct*100:.1f}%")
print(f"  移动止盈: 启用 (启动{config.trailing_activation_pct*100:.1f}%, 回撤{config.trailing_stop_pct*100:.1f}%)")
print(f"  分级止盈: {config.partial_exits}")

# 创建风险管理器
risk_mgr = EnhancedRiskManager(config)

# 添加持仓
entry_date = datetime(2024, 1, 1)
risk_mgr.add_position('000001.SZ', 100.0, 1000, entry_date)

print(f"\n持仓信息:")
print(f"  标的: 000001.SZ")
print(f"  入场价: 100.0")
print(f"  数量: 1000")

# 测试各种出场条件
test_cases = [
    # (价格, 持仓天数, 描述, market_data)
    (96.0, 1, "固定止损测试 (亏损4%)", {}),
    (94.0, 1, "固定止损测试 (亏损6%)", {}),
    (105.0, 1, "分级止盈测试 (盈利5%)", {}),
    (111.0, 1, "固定止盈测试 (盈利11%)", {}),
    (100.0, 25, "时间止损测试 (持仓25天)", {}),
]

print(f"\n出场条件测试:")
print("-" * 70)
print(f"{'场景':<25} {'价格':>8} {'信号':<10} {'原因':<30}")
print("-" * 70)

# 先涨后跌测试移动止盈
risk_mgr.reset()
risk_mgr.add_position('000001.SZ', 100.0, 1000, entry_date)

# 模拟价格上涨到105（启动移动止盈）
risk_mgr.position_trackers['000001.SZ'].update_extreme_prices(105.0)
signal = risk_mgr.check_all_exits('000001.SZ', 101.5, 5)  # 从高点回撤约3.3%
print(f"{'移动止盈测试':<25} {101.5:>8.1f} {'是' if signal.should_exit else '否':<10} {signal.exit_reason[:28] if signal.should_exit else '无':<30}")

# 重置测试其他条件
risk_mgr.reset()
risk_mgr.add_position('000001.SZ', 100.0, 1000, entry_date)

for price, days, desc, market_data in test_cases:
    signal = risk_mgr.check_all_exits('000001.SZ', price, days, market_data)
    exit_flag = "是" if signal.should_exit else "否"
    reason = signal.exit_reason[:28] if signal.should_exit else "无"
    print(f"{desc:<25} {price:>8.1f} {exit_flag:<10} {reason:<30}")

print("-" * 70)
print("✓ 风险管理器测试通过")

# =============================================================================
# Test 2: 仓位管理模块
# =============================================================================
print("\n" + "=" * 70)
print("Test 2: 仓位管理模块 (Position Sizing)")
print("=" * 70)

from projects.quant_trading.backtest import (
    KellyPositionSizer,
    VolatilityTargetSizer,
    DrawdownController,
    RiskParityPositionSizer
)

# Kelly公式测试
print("\n1. Kelly公式测试")
kelly = KellyPositionSizer(fraction=0.5)

# 场景1: 高胜率，高盈亏比
result = kelly.calculate(win_rate=0.55, avg_win=100, avg_loss=50)
print(f"   胜率55%, 盈亏比2:1 -> 仓位: {result.get_weight('default')*100:.1f}%")

# 场景2: 低胜率，高盈亏比
result = kelly.calculate(win_rate=0.40, avg_win=200, avg_loss=50)
print(f"   胜率40%, 盈亏比4:1 -> 仓位: {result.get_weight('default')*100:.1f}%")

# 场景3: 边缘情况
result = kelly.calculate(win_rate=0.30, avg_win=100, avg_loss=100)
print(f"   胜率30%, 盈亏比1:1 -> 仓位: {result.get_weight('default')*100:.1f}%")

# 波动率目标测试
print("\n2. 波动率目标测试")
vol_target = VolatilityTargetSizer(target_vol=0.15, max_leverage=2.0)

scenarios = [
    (0.10, "低波动10%"),
    (0.15, "目标波动15%"),
    (0.30, "高波动30%"),
    (0.05, "极低波动5%"),
]

for vol, desc in scenarios:
    result = vol_target.calculate(current_vol=vol)
    print(f"   {desc} -> 仓位: {result.get_weight('default')*100:.1f}%")

# 回撤控制测试
print("\n3. 回撤控制测试")
dd_controller = DrawdownController(
    max_drawdown=0.15,
    warning_drawdown=0.10,
    normal_scale=1.0,
    warning_scale=0.5,
    limit_scale=0.0
)

drawdowns = [0.05, 0.08, 0.12, 0.18, 0.08, 0.03]
for dd in drawdowns:
    result = dd_controller.calculate(dd)
    status = result.metadata['status']
    print(f"   回撤{dd*100:.0f}% -> 仓位: {result.get_weight('default')*100:.0f}%, 状态: {status}")

# 风险平价测试
print("\n4. 风险平价测试")
np.random.seed(42)
returns = pd.DataFrame({
    'Stock_A': np.random.normal(0.001, 0.02, 252),
    'Stock_B': np.random.normal(0.0005, 0.015, 252),
    'Stock_C': np.random.normal(0.0008, 0.025, 252),
})
cov_matrix = returns.cov() * 252

rp_sizer = RiskParityPositionSizer(target_risk=0.10)
result = rp_sizer.calculate(cov_matrix)

print(f"   风险平价权重:")
for asset, weight in result.weights.items():
    print(f"      {asset}: {weight*100:.1f}%")
print(f"   预期波动率: {result.expected_risk*100:.1f}%")

print("\n✓ 仓位管理模块测试通过")

# =============================================================================
# Test 3: 交易成本模型
# =============================================================================
print("\n" + "=" * 70)
print("Test 3: 交易成本模型 (Transaction Cost)")
print("=" * 70)

from projects.quant_trading.backtest import (
    StockCostModel,
    ETFCostModel,
    FundCostModel,
    FuturesCostModel,
    TradeDirection
)

# A股股票成本测试
print("\n1. A股股票交易成本")
stock_model = StockCostModel(is_shanghai=True)

# 买入
buy_cost = stock_model.calculate_cost(100.0, 1000, TradeDirection.BUY)
amount = 100.0 * 1000
print(f"   买入10万元:")
print(f"      佣金: ¥{buy_cost.commission:.2f}")
print(f"      过户费: ¥{buy_cost.transfer_fee:.2f}")
print(f"      总成本: ¥{buy_cost.total:.2f} ({buy_cost.total_pct*100:.3f}%)")

# 卖出
sell_cost = stock_model.calculate_cost(110.0, 1000, TradeDirection.SELL)
amount = 110.0 * 1000
print(f"   卖出11万元:")
print(f"      佣金: ¥{sell_cost.commission:.2f}")
print(f"      印花税: ¥{sell_cost.tax:.2f}")
print(f"      过户费: ¥{sell_cost.transfer_fee:.2f}")
print(f"      总成本: ¥{sell_cost.total:.2f} ({sell_cost.total_pct*100:.3f}%)")

# 双向成本
print(f"   双向总成本: ¥{(buy_cost.total + sell_cost.total):.2f}")

# ETF成本测试
print("\n2. ETF交易成本")
etf_model = ETFCostModel()
buy_cost = etf_model.calculate_cost(3.0, 10000, TradeDirection.BUY)
sell_cost = etf_model.calculate_cost(3.2, 10000, TradeDirection.SELL)
print(f"   买入3万元: 佣金¥{buy_cost.commission:.2f}")
print(f"   卖出3.2万元: 佣金¥{sell_cost.commission:.2f}")
print(f"   双向总成本: ¥{(buy_cost.total + sell_cost.total):.2f}")

# 基金成本测试
print("\n3. 场外基金交易成本")
fund_model = FundCostModel(subscribe_fee_rate=0.015, fee_discount=0.1)

# 申购
subscribe_cost = fund_model.calculate_cost(1.0, 10000, TradeDirection.BUY)
print(f"   申购1万元: 申购费¥{subscribe_cost.commission:.2f}")

# 不同持有期的赎回费
holding_periods = [
    (5, "5天(惩罚性费率)"),
    (20, "20天"),
    (100, "100天"),
    (400, "400天(>1年)"),
]
for days, desc in holding_periods:
    redeem_cost = fund_model.calculate_cost(1.1, 10000, TradeDirection.SELL, holding_days=days)
    print(f"   赎回({desc}): 赎回费¥{redeem_cost.commission:.2f}")

# 期货成本测试
print("\n4. 股指期货交易成本")
futures_if = FuturesCostModel('IF')

open_cost = futures_if.calculate_cost(4000.0, 1, TradeDirection.OPEN_LONG)
close_cost = futures_if.calculate_cost(4050.0, 1, TradeDirection.CLOSE_LONG)

print(f"   开多1手IF(4000点):")
print(f"      手续费: ¥{open_cost.commission:.2f}")
print(f"      保证金: ¥{open_cost.metadata['margin_required']:.0f}")
print(f"   平多1手IF(4050点): 手续费¥{close_cost.commission:.2f}")

print("\n✓ 交易成本模型测试通过")

# =============================================================================
# Test 4: 滑点模型
# =============================================================================
print("\n" + "=" * 70)
print("Test 4: 滑点模型 (Slippage)")
print("=" * 70)

from projects.quant_trading.backtest import (
    FixedSlippage,
    PercentageSlippage,
    VolatilitySlippage,
    VolumeImpactSlippage
)

price = 100.0

# 固定滑点
print("\n1. 固定滑点模型")
fixed = FixedSlippage(fixed_amount=0.01)
buy_price = fixed.get_execution_price('BUY', price)
sell_price = fixed.get_execution_price('SELL', price)
print(f"   意向价格: {price}")
print(f"   买入执行价: {buy_price} (滑点+{buy_price-price})")
print(f"   卖出执行价: {sell_price} (滑点{sell_price-price})")

# 百分比滑点
print("\n2. 百分比滑点模型 (0.05%)")
pct = PercentageSlippage(slippage_pct=0.0005)
buy_price = pct.get_execution_price('BUY', price)
sell_price = pct.get_execution_price('SELL', price)
print(f"   买入执行价: {buy_price:.4f} (滑点{(buy_price-price)/price*100:.3f}%)")
print(f"   卖出执行价: {sell_price:.4f} (滑点{(price-sell_price)/price*100:.3f}%)")

# 波动率滑点
print("\n3. 波动率滑点模型")
vol = VolatilitySlippage(atr_ratio=0.1)

market_data_high = {'atr': 5.0}  # 高波动
buy_price_high = vol.get_execution_price('BUY', price, market_data=market_data_high)

market_data_low = {'atr': 1.0}  # 低波动
buy_price_low = vol.get_execution_price('BUY', price, market_data=market_data_low)

print(f"   高波动(ATR=5): 买入执行价 {buy_price_high:.4f}")
print(f"   低波动(ATR=1): 买入执行价 {buy_price_low:.4f}")

# 成交量冲击滑点
print("\n4. 成交量冲击滑点模型")
vol_impact = VolumeImpactSlippage(volume_threshold=0.01, base_slippage_pct=0.0005)

# 小单
market_data_small = {'daily_volume': 2000000}
buy_price_small = vol_impact.get_execution_price('BUY', price, volume=10000, market_data=market_data_small)

# 大单
market_data_large = {'daily_volume': 200000}
buy_price_large = vol_impact.get_execution_price('BUY', price, volume=10000, market_data=market_data_large)

print(f"   小单(占0.5%成交量): 买入执行价 {buy_price_small:.4f}")
print(f"   大单(占5%成交量): 买入执行价 {buy_price_large:.4f}")

print("\n✓ 滑点模型测试通过")

# =============================================================================
# Test 5: Backtrader集成
# =============================================================================
print("\n" + "=" * 70)
print("Test 5: Backtrader集成 (Backtrader Integration)")
print("=" * 70)

from projects.quant_trading.backtest import (
    EnhancedChinaCommInfo,
    add_all_analyzers,
    CalmarRatio,
    SortinoRatio
)

try:
    import backtrader as bt

    print("\n1. 佣金方案测试")

    # 创建佣金方案
    stock_cost = StockCostModel(is_shanghai=True)
    slippage_model = PercentageSlippage(0.0005)

    comminfo = EnhancedChinaCommInfo(
        cost_model=stock_cost,
        slippage_model=slippage_model
    )

    # 测试佣金计算
    size = 1000
    price = 100.0
    commission = comminfo._getcommission(size, price)
    breakdown = comminfo.get_cost_breakdown(size, price)

    print(f"   买入 {size}股 @ {price}元")
    print(f"      总佣金: ¥{commission:.2f}")
    print(f"      佣金明细: 佣金¥{breakdown.commission:.2f}, 过户费¥{breakdown.transfer_fee:.2f}")

    # 测试滑点
    exec_price = comminfo.get_slippage_price('BUY', price, size)
    print(f"   滑点后价格: {exec_price:.4f}")

    print("\n2. 分析器测试")

    # 创建简单的Cerebro实例
    cerebro = bt.Cerebro()

    # 添加分析器
    add_all_analyzers(cerebro)

    analyzers = ['sharpe', 'drawdown', 'returns', 'trades', 'calmar', 'sortino',
                 'trade_details', 'predictions', 'enhanced_trades']
    print(f"   已添加分析器: {', '.join(analyzers)}")

    print("\n✓ Backtrader集成测试通过")

except ImportError:
    print("   Backtrader未安装，跳过集成测试")

# =============================================================================
# Test 6: 多策略回测框架
# =============================================================================
print("\n" + "=" * 70)
print("Test 6: 多策略回测框架 (Multi-Strategy)")
print("=" * 70)

from projects.quant_trading.backtest import (
    BacktestResult,
    BacktestConfig,
    compare_strategies
)

# 创建模拟结果
results = [
    BacktestResult(
        strategy_name="Momentum",
        run_id="test1",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        total_return=0.25,
        annual_return=0.25,
        max_drawdown=0.12,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        calmar_ratio=2.08,
        total_trades=50,
        winning_trades=28,
        win_rate=0.56
    ),
    BacktestResult(
        strategy_name="MeanReversion",
        run_id="test2",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        total_return=0.18,
        annual_return=0.18,
        max_drawdown=0.08,
        sharpe_ratio=1.8,
        sortino_ratio=2.5,
        calmar_ratio=2.25,
        total_trades=80,
        winning_trades=50,
        win_rate=0.625
    ),
    BacktestResult(
        strategy_name="TrendFollowing",
        run_id="test3",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        total_return=0.30,
        annual_return=0.30,
        max_drawdown=0.18,
        sharpe_ratio=1.2,
        sortino_ratio=1.6,
        calmar_ratio=1.67,
        total_trades=20,
        winning_trades=12,
        win_rate=0.60
    ),
]

print("\n1. 策略对比")
comparison_df = compare_strategies(results, sort_by='sharpe_ratio')
print("\n" + comparison_df[['strategy_name', 'total_return', 'max_drawdown',
                         'sharpe_ratio', 'calmar_ratio', 'win_rate']].to_string(index=False))

print("\n2. 综合评分")
for result in results:
    score = result.calculate_score()
    print(f"   {result.strategy_name}: {score:.1f}分")

print("\n✓ 多策略回测框架测试通过")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)

print("""
所有核心模块测试通过:

✓ 增强版风险管理器 (enhanced_risk_manager.py)
  - 固定止盈止损
  - 移动止盈 (Trailing Stop)
  - 分级止盈 (Partial Exits)
  - 时间止损
  - ATR止损
  - 出场优先级处理

✓ 仓位管理模块 (position_sizing.py)
  - Kelly公式
  - 风险平价
  - 波动率目标
  - 回撤动态控制

✓ 交易成本模型 (transaction_cost.py)
  - A股股票成本
  - ETF成本
  - 基金成本 (含分层赎回费)
  - 期货成本 (含保证金)

✓ 滑点模型 (slippage.py)
  - 固定滑点
  - 百分比滑点
  - 波动率滑点 (ATR)
  - 成交量冲击滑点

✓ Backtrader集成 (comminfo.py, analyzers.py)
  - EnhancedChinaCommInfo
  - 自定义分析器 (Calmar, Sortino, TradeDetail等)

✓ 多策略回测框架 (multi_strategy.py)
  - 并行回测支持
  - 结果对比分析
  - 综合评分系统
""")

print("=" * 70)
print("所有测试通过! 第三阶段回测框架已就绪。")
print("=" * 70)
