"""
Cross-Sectional ML Strategy Backtest Runner

统一入口脚本，整合所有组件：
- 数据完整性检查
- 股票池选择
- 特征工程
- 市场状态识别
- 横截面预测
- 组合优化
- 风险模型
- 绩效验证

Usage:
    python run_cross_sectional_backtest.py --start-date 20190101 --end-date 20241231
    python run_cross_sectional_backtest.py --check-data
    python run_cross_sectional_backtest.py --analyze-features
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
import yaml

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger
from core.storage.relational.connection import DatabaseManager
from projects.quant_trading.strategies.ml_prediction.cross_sectional_features import (
    CrossSectionalFeatureEngineer,
    create_standard_pipeline,
    create_rank_pipeline,
)
from projects.quant_trading.strategies.ml_prediction.universe_selector import (
    DynamicUniverseSelector,
    IndexUniverseSelector,
    create_csi300_universe,
    create_csi500_universe,
)
from projects.quant_trading.strategies.ml_prediction.regime_detector import (
    MarketRegimeDetector,
    MarketRegime,
)
from projects.quant_trading.strategies.ml_prediction.cross_sectional_strategy import (
    CrossSectionalMLStrategy,
    RegimeSpecificModel,
)
from projects.quant_trading.backtest.multi_stock_engine import (
    MultiStockBacktestEngine,
    RebalanceFrequency,
)
from projects.quant_trading.backtest.risk_model import create_factor_risk_model
from projects.quant_trading.backtest.portfolio_optimizer import (
    create_default_optimizer,
    create_risk_parity_optimizer,
    OptimizationObjective,
)
from projects.quant_trading.evaluation.ic_analysis import (
    ICAnalyzer,
    QuantileAnalyzer,
    ICType,
    analyze_factor_performance,
)
from projects.quant_trading.evaluation.bootstrap_validator import (
    BootstrapValidator,
    bootstrap_backtest_metrics,
)
from scripts.check_data_integrity import DataIntegrityChecker

logger = get_logger(__name__)


class CrossSectionalBacktestPipeline:
    """
    横截面策略回测流水线

    整合所有组件，提供一站式回测体验
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        universe_selector: Optional[Any] = None,
        feature_engineer: Optional[CrossSectionalFeatureEngineer] = None,
        strategy: Optional[CrossSectionalMLStrategy] = None,
        initial_capital: float = 1_000_000,
        rebalancing_freq: str = "weekly",
        rebalance_day: int = 1,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.rebalancing_freq = rebalancing_freq
        self.rebalance_day = rebalance_day

        # 初始化组件（使用默认配置或自定义配置）
        self.universe_selector = universe_selector or create_csi300_universe()
        self.feature_engineer = feature_engineer or self._create_default_feature_engineer()
        self.strategy = strategy or self._create_default_strategy()

        # 初始化回测引擎
        from projects.quant_trading.backtest.multi_stock_engine import MultiStockBacktestConfig
        import pandas as pd

        backtest_config = MultiStockBacktestConfig(
            start_date=pd.Timestamp(start_date),
            end_date=pd.Timestamp(end_date),
            initial_capital=initial_capital,
            rebalance_freq=RebalanceFrequency(rebalancing_freq),
            rebalance_day=rebalance_day,
            max_positions=top_n if 'top_n' in locals() else 30,
        )
        self.backtest_engine = MultiStockBacktestEngine(
            config=backtest_config,
            strategy=self.strategy,
        )

        # 结果存储
        self.results: Dict[str, Any] = {}

    def _create_default_feature_engineer(self) -> CrossSectionalFeatureEngineer:
        """创建默认特征工程器"""
        from projects.quant_trading.strategies.ml_prediction.cross_sectional_features import (
            CrossSectionalFeatureConfig,
            NeutralizationMethod,
        )
        config = CrossSectionalFeatureConfig(
            neutralization=NeutralizationMethod.INDUSTRY_ZSCORE,
        )
        return CrossSectionalFeatureEngineer(config=config)

    def _create_default_strategy(self) -> CrossSectionalMLStrategy:
        """创建默认策略"""
        from projects.quant_trading.strategies.ml_prediction.cross_sectional_strategy import (
            CrossSectionalConfig,
        )
        config = CrossSectionalConfig(
            top_n_stocks=30,
            use_xgboost=True,
            use_lstm=False,
            use_regime_switching=True,
            prediction_horizons=[1, 5, 10],
            horizon_weights=[0.5, 0.3, 0.2],
        )
        return CrossSectionalMLStrategy(config=config)

    def run_data_integrity_check(self) -> bool:
        """运行数据完整性检查"""
        logger.info("=" * 60)
        logger.info("Step 1: Data Integrity Check")
        logger.info("=" * 60)

        checker = DataIntegrityChecker()

        start_year = int(self.start_date[:4])
        end_year = int(self.end_date[:4])

        results = checker.run_all_checks(start_year, end_year)

        # 检查关键数据是否可用
        has_daily = (
            "daily_market" in results
            and not results["daily_market"].empty
        )
        has_valuation = (
            "valuation" in results
            and not results["valuation"].empty
        )

        if not has_daily:
            logger.error("Daily market data not available!")
            return False

        logger.info("Data integrity check passed")
        return True

    def analyze_features(self) -> Dict[str, Any]:
        """分析特征有效性（IC分析）"""
        logger.info("=" * 60)
        logger.info("Step 2: Feature IC Analysis")
        logger.info("=" * 60)

        # 获取股票池
        dates = pd.date_range(
            start=pd.Timestamp(self.start_date),
            end=pd.Timestamp(self.end_date),
            freq="W",
        )

        sample_dates = dates[:10]  # 取前10周作为样本
        universe = self.universe_selector.get_universe(sample_dates[0])

        logger.info(f"Sample universe size: {len(universe)}")

        # 生成特征
        logger.info("Generating features for IC analysis...")
        features_list = []
        returns_list = []

        for date in sample_dates[:-1]:
            try:
                features = self.feature_engineer.create_features_for_universe(
                    date, universe
                )
                if features.empty:
                    continue

                # 获取未来5日收益
                future_date = date + pd.Timedelta(days=5)
                forward_returns = self._get_forward_returns(
                    universe, date, future_date
                )

                if not forward_returns.empty:
                    features_list.append(features)
                    returns_list.append(forward_returns)

            except Exception as e:
                logger.warning(f"Feature generation failed for {date}: {e}")
                continue

        if not features_list:
            logger.warning("No valid features generated for IC analysis")
            return {}

        # 合并数据
        combined_features = pd.concat(features_list, ignore_index=True)
        combined_returns = pd.concat(returns_list, ignore_index=True)

        # 分析每个因子的IC
        results = {}
        ic_analyzer = ICAnalyzer(ic_type=ICType.SPEARMAN)

        for col in combined_features.columns:
            if col in ["ts_code", "trade_date", "industry"]:
                continue

            factor_series = combined_features[col]
            valid_idx = factor_series.notna() & combined_returns.notna()

            if valid_idx.sum() < 30:
                continue

            ic_series = []
            for i in range(len(factor_series)):
                if valid_idx.iloc[i]:
                    # 简化为直接计算相关性
                    ic = np.corrcoef(
                        factor_series[valid_idx].values,
                        combined_returns[valid_idx].values,
                    )[0, 1]
                    if not np.isnan(ic):
                        ic_series.append(ic)

            if ic_series:
                mean_ic = np.mean(ic_series)
                std_ic = np.std(ic_series)
                ir = mean_ic / std_ic if std_ic > 0 else 0

                results[col] = {
                    "mean_ic": mean_ic,
                    "std_ic": std_ic,
                    "ir": ir,
                }

                logger.info(f"{col}: IC={mean_ic:.4f}, IR={ir:.4f}")

        self.results["feature_ic"] = results
        return results

    def _get_forward_returns(
        self,
        universe: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.Series:
        """获取未来收益"""
        from projects.quant_trading.backtest.data_manager import DataManager

        data_manager = DataManager()
        returns = pd.Series(index=universe, dtype=float)

        for ts_code in universe:
            try:
                df = data_manager.get_stock_data(ts_code, start_date, end_date)
                if not df.empty and len(df) >= 2:
                    total_return = df["adj_close"].iloc[-1] / df["adj_close"].iloc[0] - 1
                    returns[ts_code] = total_return
            except Exception:
                continue

        return returns.dropna()

    def run_backtest(self) -> Dict[str, Any]:
        """运行回测"""
        logger.info("=" * 60)
        logger.info("Step 3: Running Backtest")
        logger.info("=" * 60)
        logger.info(f"Period: {self.start_date} to {self.end_date}")
        logger.info(f"Initial Capital: {self.initial_capital:,.0f}")
        logger.info(f"Rebalancing: {self.rebalancing_freq}")

        # 运行回测
        results = self.backtest_engine.run()

        self.results["backtest"] = results

        # 打印关键指标
        if "metrics" in results:
            metrics = results["metrics"]
            logger.info("\nBacktest Results:")
            logger.info(f"  Total Return: {metrics.get('total_return', 0)*100:.2f}%")
            logger.info(f"  Annual Return: {metrics.get('annual_return', 0)*100:.2f}%")
            logger.info(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            logger.info(f"  Max Drawdown: {metrics.get('max_drawdown', 0)*100:.2f}%")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0)*100:.2f}%")

        return results

    def run_bootstrap_validation(self) -> Dict[str, Any]:
        """运行Bootstrap验证"""
        logger.info("=" * 60)
        logger.info("Step 4: Bootstrap Validation")
        logger.info("=" * 60)

        if "backtest" not in self.results:
            logger.error("Please run backtest first")
            return {}

        backtest_results = self.results["backtest"]

        if "returns" not in backtest_results or "nav" not in backtest_results:
            logger.error("Backtest results missing returns or NAV data")
            return {}

        returns = pd.Series(backtest_results["returns"])
        nav = pd.Series(backtest_results["nav"])

        logger.info(f"Running bootstrap with {len(returns)} observations...")

        # 计算关键指标的Bootstrap置信区间
        bootstrap_results = bootstrap_backtest_metrics(
            returns, nav, n_bootstrap=1000
        )

        logger.info("\nBootstrap Results:")
        for metric_name, result in bootstrap_results.items():
            logger.info(f"\n{metric_name}:")
            logger.info(f"  Original: {result.original_value:.4f}")
            logger.info(f"  95% CI: [{result.ci_lower:.4f}, {result.ci_upper:.4f}]")
            logger.info(f"  p-value: {result.pvalue_two_sided:.4f}")

        self.results["bootstrap"] = bootstrap_results
        return bootstrap_results

    def generate_report(self) -> str:
        """生成完整报告"""
        lines = [
            "=" * 80,
            "Cross-Sectional ML Strategy Backtest Report",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Period: {self.start_date} to {self.end_date}",
            f"Initial Capital: {self.initial_capital:,.0f} RMB",
            f"Rebalancing: {self.rebalancing_freq} (day {self.rebalance_day})",
            "",
        ]

        # 特征IC分析结果
        if "feature_ic" in self.results:
            lines.extend([
                "-" * 80,
                "Feature IC Analysis",
                "-" * 80,
                f"{'Factor':<30} {'Mean IC':<12} {'IR':<10}",
                "-" * 80,
            ])

            for factor, stats in sorted(
                self.results["feature_ic"].items(),
                key=lambda x: abs(x[1]["ir"]),
                reverse=True,
            ):
                lines.append(
                    f"{factor:<30} {stats['mean_ic']:>10.4f}  {stats['ir']:>8.4f}"
                )

            lines.append("")

        # 回测结果
        if "backtest" in self.results:
            backtest = self.results["backtest"]
            lines.extend([
                "-" * 80,
                "Backtest Performance",
                "-" * 80,
            ])

            if "metrics" in backtest:
                m = backtest["metrics"]
                lines.extend([
                    f"Total Return:        {m.get('total_return', 0)*100:>10.2f}%",
                    f"Annual Return:       {m.get('annual_return', 0)*100:>10.2f}%",
                    f"Annual Volatility:   {m.get('annual_volatility', 0)*100:>10.2f}%",
                    f"Sharpe Ratio:        {m.get('sharpe_ratio', 0):>10.2f}",
                    f"Max Drawdown:        {m.get('max_drawdown', 0)*100:>10.2f}%",
                    f"Calmar Ratio:        {m.get('calmar_ratio', 0):>10.2f}",
                    f"Win Rate:            {m.get('win_rate', 0)*100:>10.2f}%",
                    f"Profit Factor:       {m.get('profit_factor', 0):>10.2f}",
                    f"Turnover (Annual):   {m.get('turnover_rate', 0)*100:>10.2f}%",
                    "",
                ])

            if "trade_count" in backtest:
                lines.append(f"Total Trades:        {backtest['trade_count']:>10}")
            if "position_count" in backtest:
                lines.append(f"Avg Positions:       {backtest['position_count']:>10.1f}")

            lines.append("")

        # Bootstrap验证结果
        if "bootstrap" in self.results:
            lines.extend([
                "-" * 80,
                "Bootstrap Validation (95% Confidence Intervals)",
                "-" * 80,
            ])

            for metric_name, result in self.results["bootstrap"].items():
                lines.append(f"\n{metric_name}:")
                lines.append(f"  Point Estimate: {result.original_value:>10.4f}")
                lines.append(
                    f"  95% CI:         [{result.ci_lower:>10.4f}, {result.ci_upper:>10.4f}]"
                )
                lines.append(f"  Bias:           {result.bias:>10.4f}")
                lines.append(f"  Std Error:      {result.se:>10.4f}")

            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def save_report(self, output_path: str = "backtest_report.txt") -> None:
        """保存报告到文件"""
        report = self.generate_report()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(report)

        logger.info(f"Report saved to {output_path}")

    def run_full_pipeline(self) -> Dict[str, Any]:
        """运行完整流水线"""
        logger.info("=" * 80)
        logger.info("Cross-Sectional ML Strategy - Full Pipeline")
        logger.info("=" * 80)

        # 1. 数据完整性检查
        if not self.run_data_integrity_check():
            logger.error("Data integrity check failed. Aborting.")
            return {}

        # 2. 特征分析（可选，仅样本期内）
        # self.analyze_features()

        # 3. 运行回测
        self.run_backtest()

        # 4. Bootstrap验证
        self.run_bootstrap_validation()

        # 5. 生成报告
        self.save_report()

        logger.info("=" * 80)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 80)

        return self.results

    @classmethod
    def from_config(cls, config_path: str) -> "CrossSectionalBacktestPipeline":
        """从YAML配置文件创建流水线"""
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 数据配置
        data_cfg = config.get("data", {})
        start_date = data_cfg.get("database", {}).get("start_date", "20190101")
        end_date = data_cfg.get("database", {}).get("end_date", "20241231")

        # 股票池配置
        universe_cfg = config.get("universe", {})
        universe_type = universe_cfg.get("type", "csi300")

        if universe_type == "csi300":
            universe_selector = create_csi300_universe()
        elif universe_type == "csi500":
            universe_selector = create_csi500_universe()
        else:
            universe_selector = create_csi300_universe()  # 默认

        # 特征工程配置
        features_cfg = config.get("features", {})
        from projects.quant_trading.strategies.ml_prediction.cross_sectional_features import (
            CrossSectionalFeatureConfig,
            NeutralizationMethod,
        )
        # 将字符串转换为枚举
        neutralization_str = features_cfg.get("neutralize_method", "INDUSTRY_ZSCORE")
        neutralization_map = {
            "NONE": NeutralizationMethod.NONE,
            "INDUSTRY_MEAN": NeutralizationMethod.INDUSTRY_MEAN,
            "INDUSTRY_ZSCORE": NeutralizationMethod.INDUSTRY_ZSCORE,
            "MARKET_CAP": NeutralizationMethod.MARKET_CAP,
            "INDUSTRY_CAP": NeutralizationMethod.INDUSTRY_CAP,
        }
        feature_config = CrossSectionalFeatureConfig(
            neutralization=neutralization_map.get(neutralization_str, NeutralizationMethod.INDUSTRY_ZSCORE),
        )
        feature_engineer = CrossSectionalFeatureEngineer(config=feature_config)

        # 模型配置
        model_cfg = config.get("model", {})
        regime_cfg = config.get("regime_detection", {})

        strategy = CrossSectionalMLStrategy(
            lookback_days=model_cfg.get("rolling_train", {}).get("lookback_days", 252),
            prediction_horizon=5,
            top_n=config.get("portfolio", {}).get("top_n", 30),
            model_type=model_cfg.get("default_type", "xgboost"),
            use_regime_detection=regime_cfg.get("enabled", True),
            multi_horizon_weights=model_cfg.get("multi_horizon", {}).get("weights", {1: 0.5, 5: 0.3, 10: 0.2}),
        )

        # 回测配置
        backtest_cfg = config.get("backtest", {})
        initial_capital = backtest_cfg.get("initial_capital", 1_000_000)

        # 再平衡配置
        rebalancing_cfg = config.get("rebalancing", {})
        rebalancing_freq = rebalancing_cfg.get("frequency", "weekly")
        rebalance_day = rebalancing_cfg.get("day", 1)

        return cls(
            start_date=start_date,
            end_date=end_date,
            universe_selector=universe_selector,
            feature_engineer=feature_engineer,
            strategy=strategy,
            initial_capital=initial_capital,
            rebalancing_freq=rebalancing_freq,
            rebalance_day=rebalance_day,
        )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Cross-Sectional ML Strategy Backtest"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="20190101",
        help="Backtest start date (YYYYMMDD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="20241231",
        help="Backtest end date (YYYYMMDD)",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=1_000_000,
        help="Initial capital in RMB (default: 1,000,000)",
    )
    parser.add_argument(
        "--universe",
        type=str,
        default="csi300",
        choices=["csi300", "csi500", "csi1000", "all"],
        help="Stock universe (default: csi300)",
    )
    parser.add_argument(
        "--rebalancing",
        type=str,
        default="weekly",
        choices=["daily", "weekly", "monthly"],
        help="Rebalancing frequency (default: weekly)",
    )
    parser.add_argument(
        "--rebalance-day",
        type=int,
        default=1,
        help="Rebalance day (weekday for weekly, day of month for monthly)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of stocks to select (default: 30)",
    )
    parser.add_argument(
        "--check-data",
        action="store_true",
        help="Run data integrity check only",
    )
    parser.add_argument(
        "--analyze-features",
        action="store_true",
        help="Run feature IC analysis only",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backtest_report.txt",
        help="Output report path",
    )

    args = parser.parse_args()

    # 从配置文件或命令行参数创建流水线
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        pipeline = CrossSectionalBacktestPipeline.from_config(args.config)
    else:
        # 创建股票池选择器
        if args.universe == "csi300":
            universe_selector = create_csi300_universe()
        elif args.universe == "csi500":
            universe_selector = create_csi500_universe()
        elif args.universe == "csi1000":
            from projects.quant_trading.strategies.ml_prediction.universe_selector import create_csi1000_universe
            universe_selector = create_csi1000_universe()
        else:
            from projects.quant_trading.strategies.ml_prediction.universe_selector import create_all_a_share_universe
            universe_selector = create_all_a_share_universe()

        # 创建策略配置
        from projects.quant_trading.strategies.ml_prediction.cross_sectional_strategy import (
            CrossSectionalConfig,
        )

        strategy_config = CrossSectionalConfig(
            top_n_stocks=args.top_n,
            use_xgboost=True,
            use_lstm=False,
            use_regime_switching=True,
            prediction_horizons=[1, 5, 10],
            horizon_weights=[0.5, 0.3, 0.2],
        )
        strategy = CrossSectionalMLStrategy(config=strategy_config)

        # 创建流水线
        pipeline = CrossSectionalBacktestPipeline(
            start_date=args.start_date,
            end_date=args.end_date,
            universe_selector=universe_selector,
            strategy=strategy,
            initial_capital=args.initial_capital,
            rebalancing_freq=args.rebalancing,
            rebalance_day=args.rebalance_day,
        )

    # 执行命令
    if args.check_data:
        pipeline.run_data_integrity_check()
    elif args.analyze_features:
        pipeline.analyze_features()
    else:
        # 运行完整流水线
        results = pipeline.run_full_pipeline()
        pipeline.save_report(args.output)


if __name__ == "__main__":
    main()
