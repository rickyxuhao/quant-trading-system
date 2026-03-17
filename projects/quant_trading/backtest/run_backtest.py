"""
回测框架 - 入口脚本

命令行入口，执行回测并输出结果。
支持多种策略类型、自定义参数配置、结果保存和可视化。

Usage:
    # 运行动量策略回测（默认配置）
    python run_backtest.py --strategy momentum

    # 运行周频调仓回测
    python run_backtest.py --strategy momentum --freq weekly --start 20240101 --end 20241231

    # 自定义参数
    python run_backtest.py --strategy dual_momentum --initial-cash 500000 --max-positions 15

Example:
    $ python run_backtest.py --strategy momentum --start 20240101 --end 20241231
    $ python run_backtest.py --strategy mean_reversion --freq weekly --lookback 30
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    pass

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from projects.quant_trading.backtest.engine import BacktestConfig, BacktestEngine
    from projects.quant_trading.backtest.risk_manager import RiskConfig
    from projects.quant_trading.backtest.strategy import BuyAndHoldStrategy
    from projects.quant_trading.backtest.visualizer import BacktestVisualizer
    from projects.quant_trading.backtest.example_strategy import (
        DualMomentumStrategy,
        MeanReversionStrategy,
        MomentumStrategy,
        RSIStrategy,
    )
except ImportError as e:
    print(f"[Error] Failed to import required modules: {e}")
    print(f"Please run this script from the project root directory")
    sys.exit(1)


class StrategyType(Enum):
    """策略类型枚举"""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    DUAL_MOMENTUM = "dual_momentum"
    BUY_HOLD = "buy_hold"
    RSI = "rsi"


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """设置日志

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Logger实例

    Example:
        >>> logger = setup_logging("DEBUG")
        >>> logger.info("Test message")
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime:
    """解析日期字符串

    Args:
        date_str: 日期字符串，格式YYYYMMDD

    Returns:
        datetime对象

    Raises:
        ValueError: 当日期格式无效时

    Example:
        >>> parse_date("20240101")
        datetime(2024, 1, 1, 0, 0)
    """
    try:
        return datetime.strptime(date_str, "%Y%m%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYYMMDD") from e


def parse_args() -> argparse.Namespace:
    """解析命令行参数

    Returns:
        解析后的参数命名空间
    """
    parser = argparse.ArgumentParser(
        description="Stock Backtest System - Quantitative Strategy Backtest Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration:
  --initial-cash: Initial capital, default 200000 (200k CNY)
  --commission: Commission rate, default 0.00015 (0.015%)
  --slippage: Slippage rate, default 0.0002 (0.02%)
  --min-positions: Minimum positions, default 3
  --max-positions: Maximum positions, default 10
  --freq: Rebalance frequency, daily or weekly
  --lookback: Strategy lookback period in trading days, default 20

Strategies:
  momentum:        Momentum strategy - select stocks with highest returns
  mean_reversion:  Mean reversion - select stocks with largest declines
  dual_momentum:   Dual momentum - absolute + relative momentum filter
  buy_hold:        Buy and hold - baseline strategy
  rsi:             RSI strategy - based on RSI overbought/oversold signals

Examples:
  # Run momentum strategy backtest (default config)
  python run_backtest.py --strategy momentum

  # Run weekly rebalance backtest
  python run_backtest.py --strategy momentum --freq weekly --start 20240101 --end 20241231

  # Custom parameters
  python run_backtest.py --strategy dual_momentum --initial-cash 500000 --max-positions 15

  # Disable risk control
  python run_backtest.py --strategy momentum --no-risk
        """,
    )

    # Strategy selection
    parser.add_argument(
        "--strategy",
        type=str,
        default="momentum",
        choices=[s.value for s in StrategyType],
        help="Strategy type (default: momentum)",
    )

    # Date range
    parser.add_argument(
        "--start",
        type=str,
        default="20240101",
        help="Start date, format YYYYMMDD (default: 20240101)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date, format YYYYMMDD (default: today)",
    )

    # Capital and positions
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=200000.0,
        help="Initial capital in CNY (default: 200000)",
    )
    parser.add_argument(
        "--min-positions",
        type=int,
        default=3,
        help="Minimum positions (default: 3)",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=10,
        help="Maximum positions (default: 10)",
    )

    # Transaction costs
    parser.add_argument(
        "--commission",
        type=float,
        default=0.00015,
        help="Commission rate (default: 0.00015, i.e., 0.015%)",
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0002,
        help="Slippage rate (default: 0.0002, i.e., 0.02%)",
    )

    # Rebalance and strategy parameters
    parser.add_argument(
        "--freq",
        type=str,
        default="weekly",
        choices=["daily", "weekly", "monthly"],
        help="Rebalance frequency (default: weekly)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=20,
        help="Strategy lookback period in trading days (default: 20)",
    )

    # Output configuration
    parser.add_argument(
        "--output",
        type=str,
        default="./backtest_results",
        help="Output directory (default: ./backtest_results)",
    )
    parser.add_argument(
        "--no-visualize",
        action="store_true",
        help="Disable visualization chart generation",
    )

    # Risk control configuration
    parser.add_argument(
        "--no-risk",
        action="store_true",
        help="Disable risk control module",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=0.15,
        help="Maximum drawdown limit (default: 0.15, i.e., 15%)",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=0.08,
        help="Individual stock stop loss (default: 0.08, i.e., 8%)",
    )

    # Logging configuration
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )

    return parser.parse_args()


def create_strategy_instance(
    strategy_name: str,
    lookback: int,
    top_n: int,
) -> Any:
    """创建策略实例

    Args:
        strategy_name: 策略名称
        lookback: 回看周期
        top_n: 选股数量

    Returns:
        策略实例

    Raises:
        ValueError: 当策略名称未知时

    Example:
        >>> strategy = create_strategy_instance("momentum", 20, 10)
        >>> print(strategy.get_name())
        MomentumStrategy
    """
    strategy_map = {
        "momentum": lambda: MomentumStrategy(lookback_period=lookback, top_n=top_n),
        "mean_reversion": lambda: MeanReversionStrategy(lookback_period=lookback, top_n=top_n),
        "dual_momentum": lambda: DualMomentumStrategy(lookback_period=lookback, top_n=top_n),
        "buy_hold": lambda: BuyAndHoldStrategy(),
        "rsi": lambda: RSIStrategy(rsi_period=lookback, top_n=top_n),
    }

    if strategy_name not in strategy_map:
        available = ", ".join(strategy_map.keys())
        raise ValueError(f"Unknown strategy: '{strategy_name}'. Available: [{available}]")

    return strategy_map[strategy_name]()


def print_banner(logger: logging.Logger) -> None:
    """打印程序横幅

    Args:
        logger: 日志器实例
    """
    banner = [
        "=" * 60,
        "Stock Backtest System",
        "=" * 60,
    ]
    for line in banner:
        logger.info(line)


def print_config(
    logger: logging.Logger,
    args: argparse.Namespace,
    start_date: datetime,
    end_date: datetime,
) -> None:
    """打印配置信息

    Args:
        logger: 日志器实例
        args: 命令行参数
        start_date: 开始日期
        end_date: 结束日期
    """
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"Period: {start_date.strftime('%Y%m%d')} ~ {end_date.strftime('%Y%m%d')}")
    logger.info(f"Initial Capital: ¥{args.initial_cash:,.2f}")
    logger.info(f"Positions: {args.min_positions} ~ {args.max_positions}")
    logger.info(f"Rebalance Frequency: {args.freq}")
    logger.info(
        f"Transaction Costs: commission {args.commission*10000:.0f}bp + slippage {args.slippage*10000:.0f}bp"
    )
    logger.info(f"Risk Control: {'Disabled' if args.no_risk else 'Enabled'}")
    logger.info("=" * 60)


def run_backtest(
    args: argparse.Namespace,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """执行回测

    Args:
        args: 命令行参数
        logger: 日志器实例

    Returns:
        回测结果字典

    Raises:
        Exception: 当回测执行失败时
    """
    # Parse dates
    start_date = parse_date(args.start)
    if args.end:
        end_date = parse_date(args.end)
    else:
        end_date = datetime.now()

    print_banner(logger)
    print_config(logger, args, start_date, end_date)

    # Create risk configuration
    risk_config: Optional[RiskConfig] = None
    if not args.no_risk:
        risk_config = RiskConfig(
            max_drawdown_limit=args.max_drawdown,
            stop_loss_pct=args.stop_loss,
        )

    # Create backtest configuration
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash=args.initial_cash,
        min_positions=args.min_positions,
        max_positions=args.max_positions,
        rebalance_freq=args.freq,
        commission_rate=args.commission,
        slippage_rate=args.slippage,
        enable_risk_control=not args.no_risk,
        risk_config=risk_config,
        log_level=args.log_level,
    )

    # Create strategy
    try:
        strategy = create_strategy_instance(
            args.strategy,
            args.lookback,
            args.max_positions,
        )
        logger.info(f"Strategy created: {strategy.get_name()}")
    except ValueError as e:
        logger.error(f"Strategy creation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating strategy: {e}")
        raise

    # Create backtest engine
    try:
        engine = BacktestEngine(config, strategy)
        logger.info("Backtest engine initialized")
    except Exception as e:
        logger.error(f"Engine initialization failed: {e}")
        raise

    # Run backtest
    try:
        results = engine.run()
        return results
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        raise


def print_results(
    logger: logging.Logger,
    results: Dict[str, Any],
) -> None:
    """打印回测结果

    Args:
        logger: 日志器实例
        results: 回测结果字典
    """
    logger.info("\n" + "=" * 60)
    logger.info("Backtest Results")
    logger.info("=" * 60)

    metrics = results.get("metrics")
    if metrics:
        logger.info(f"\nTotal Return: {metrics.total_return*100:+.2f}%")
        logger.info(f"Annual Return: {metrics.annual_return*100:+.2f}%")
        logger.info(f"Max Drawdown: {metrics.max_drawdown*100:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        logger.info(f"Total Trades: {metrics.total_trades}")
        logger.info(f"Win Rate: {metrics.win_rate*100:.2f}%")
    else:
        logger.warning("No performance metrics available")

    summary = results.get("summary", {})
    final_nav = summary.get("nav", 0)
    final_value = summary.get("total_value", 0)
    logger.info(f"\nFinal NAV: {final_nav:.4f}")
    logger.info(f"Final Equity: ¥{final_value:,.2f}")


def save_results(
    results: Dict[str, Any],
    output_path: Path,
    logger: logging.Logger,
) -> bool:
    """保存回测结果

    Args:
        results: 回测结果
        output_path: 输出目录路径
        logger: 日志器实例

    Returns:
        是否保存成功
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required for saving results")
        return False

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create output directory: {e}")
        return False

    try:
        # Save NAV history
        nav_history = results.get("nav_history", [])
        if nav_history:
            nav_df = pd.DataFrame(nav_history, columns=["date", "nav"])
            nav_file = output_path / "nav_history.csv"
            nav_df.to_csv(nav_file, index=False)
            logger.info(f"NAV history saved: {nav_file}")

        # Save trades
        trades_df = results.get("trades")
        if trades_df is not None and not trades_df.empty:
            trades_file = output_path / "trades.csv"
            trades_df.to_csv(trades_file, index=False)
            logger.info(f"Trade records saved: {trades_file}")

        # Save metrics
        metrics = results.get("metrics")
        if metrics:
            metrics_dict = metrics.to_dict()
            metrics_file = output_path / "metrics.csv"
            pd.Series(metrics_dict).to_csv(metrics_file, header=["value"])
            logger.info(f"Performance metrics saved: {metrics_file}")

        logger.info(f"\nResults saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save results: {e}")
        return False


def generate_visualization(
    results: Dict[str, Any],
    output_path: Path,
    strategy_name: str,
    logger: logging.Logger,
) -> bool:
    """生成可视化图表

    Args:
        results: 回测结果
        output_path: 输出目录路径
        strategy_name: 策略名称
        logger: 日志器实例

    Returns:
        是否生成成功
    """
    try:
        visualizer = BacktestVisualizer()
        save_path = str(output_path / "backtest_report.png")
        visualizer.plot_report(
            nav_history=results.get("nav_history", []),
            benchmark_nav=None,  # TODO: Load benchmark data
            trades_df=results.get("trades"),
            title=f"Backtest Result - {strategy_name}",
            save_path=save_path,
        )
        logger.info(f"Visualization saved: {save_path}")
        return True
    except Exception as e:
        logger.warning(f"Visualization failed: {e}")
        return False


def save_and_visualize(
    results: Dict[str, Any],
    args: argparse.Namespace,
    logger: logging.Logger,
) -> None:
    """保存结果并生成可视化

    Args:
        results: 回测结果
        args: 命令行参数
        logger: 日志器实例
    """
    output_path = Path(args.output)

    # Save results
    save_results(results, output_path, logger)

    # Generate visualization
    if not args.no_visualize:
        generate_visualization(results, output_path, args.strategy, logger)


def main() -> int:
    """主函数

    Returns:
        退出码 (0=成功, 1=失败, 130=用户中断)
    """
    args = parse_args()
    logger = setup_logging(args.log_level)

    try:
        # Run backtest
        results = run_backtest(args, logger)

        # Print results
        print_results(logger, results)

        # Save and visualize
        save_and_visualize(results, args, logger)

        logger.info("\nBacktest completed!")
        return 0

    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
        return 130
    except ValueError as e:
        logger.error(f"\nValidation error: {e}")
        return 1
    except Exception as e:
        logger.error(f"\nBacktest failed: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
