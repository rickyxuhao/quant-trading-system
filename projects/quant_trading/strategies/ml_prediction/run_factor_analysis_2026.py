"""
因子有效性分析脚本 - 2026年沪深300成分股

分析时间范围: 2025-01-01 至 2026-03-19
分析标的: 沪深300 (HS300) 成分股
分析因子: 估值、质量、动量、波动率、流动性、技术类因子

用法:
    python run_factor_analysis_2026.py
"""

import os
import sys
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import matplotlib
matplotlib.use('Agg')  # 非交互式后端，必须在 pyplot 导入前设置
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使脚本可以独立运行
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[4]  # ml_prediction -> strategies -> quant_trading -> projects -> root
sys.path.insert(0, str(_PROJECT_ROOT))
# Also add current working directory if running from project root
if Path('.').resolve() != _PROJECT_ROOT and (Path('.') / 'core').exists():
    sys.path.insert(0, str(Path('.').resolve()))

# ---------------------------------------------------------------------------
# 项目内部导入
# ---------------------------------------------------------------------------
from core.storage.relational.connection import DatabaseManager
from projects.quant_trading.strategies.ml_prediction.factor_analysis import (
    FactorAnalyzer,
    industry_neutral_quantile_analysis,
)

# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------
# 总分析区间
ANALYSIS_START = datetime(2025, 1, 1)
ANALYSIS_END = datetime(2026, 3, 19)

# 样本内：因子IC分析和权重训练
IN_SAMPLE_START = datetime(2025, 1, 1)
IN_SAMPLE_END = datetime(2025, 10, 31)

# 样本外：泛化能力验证
OUT_SAMPLE_START = datetime(2025, 11, 1)
OUT_SAMPLE_END = datetime(2026, 3, 19)

# 兼容旧代码引用
START_DATE = ANALYSIS_START
END_DATE = ANALYSIS_END

# 要测试的因子列表（对应 t_precomputed_factors 表的列名）
TARGET_FACTORS = [
    # 估值类
    "pe_ttm",
    "pb",
    "ep_ttm",
    # 质量类
    "roe",
    "roa",
    # 动量类
    "return_20d",
    "return_60d",
    # 波动率类
    "volatility_20d",
    # 流动性类
    "turnover_rate",
    # 技术/Qlib 类
    "KMID",
    "ROC20",
    "MA20",
    "CORR20",
]

# 输出目录
OUTPUT_DIR = _SCRIPT_DIR / "output" / "factor_analysis_2026"

# 同步脚本路径
_SYNC_SCRIPT = _PROJECT_ROOT / "scripts" / "sync" / "sync_t_index_weight.py"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _setup_chinese_font() -> bool:
    """尝试配置中文字体，返回是否成功。"""
    chinese_fonts = [
        "SimHei", "Microsoft YaHei", "PingFang SC", "Heiti SC",
        "WenQuanYi Micro Hei", "Noto Sans CJK SC",
    ]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font in chinese_fonts:
        if font in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            print(f"[INFO] 中文字体已设置: {font}")
            return True
    print("[WARN] 未找到中文字体，使用英文标签")
    return False


def _get_trade_dates_from_db(start_date: datetime, end_date: datetime) -> List[str]:
    """从数据库获取交易日列表（格式：YYYYMMDD）。"""
    try:
        results = DatabaseManager.fetchall(
            "tushare_biz",
            "SELECT cal_date FROM t_stock_tradedate WHERE is_open = 1 AND cal_date >= %s AND cal_date <= %s ORDER BY cal_date",
            (start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")),
        )
        return [r["cal_date"] for r in results]
    except Exception as e:
        print(f"  [WARN] 无法从t_stock_tradedate获取交易日: {e}")
        return []


def check_and_sync_hs300_data(start_date: datetime, end_date: datetime) -> bool:
    """
    检查HS300数据完整性，如缺失则触发同步。

    Returns:
        True表示数据完整或同步成功，False表示同步失败。
    """
    print("[STEP 1a] 检查HS300数据完整性...")

    # 获取需要的交易日列表
    required_dates = _get_trade_dates_from_db(start_date, end_date)
    if not required_dates:
        print("  [WARN] 无法获取交易日历，跳过完整性检查")
        return True

    print(f"  [INFO] 目标区间交易日: {len(required_dates)} 天 ({required_dates[0]} ~ {required_dates[-1]})")

    # 查询已存在的HS300数据日期
    try:
        existing = DatabaseManager.fetchall(
            "tushare_biz",
            "SELECT DISTINCT trade_date FROM t_index_weight WHERE index_code = %s AND trade_date >= %s AND trade_date <= %s",
            ("000300.SH", required_dates[0], required_dates[-1]),
        )
        existing_dates = {r["trade_date"] for r in existing}
    except Exception as e:
        print(f"  [WARN] 无法查询已存在数据: {e}")
        existing_dates = set()

    missing = [d for d in required_dates if d not in existing_dates]

    if not missing:
        print(f"  [OK] HS300数据完整，共 {len(existing_dates)} 个交易日有数据")
        return True

    coverage = len(existing_dates) / len(required_dates) * 100 if required_dates else 0
    print(f"  [WARN] 数据不完整: 已有 {len(existing_dates)} 天，缺失 {len(missing)} 天 (覆盖率 {coverage:.1f}%)")
    print(f"  [INFO] 缺失示例: {missing[:5]}")

    # 触发同步
    if not _SYNC_SCRIPT.exists():
        print(f"  [ERROR] 同步脚本不存在: {_SYNC_SCRIPT}")
        return False

    print(f"  [INFO] 触发数据同步: {_SYNC_SCRIPT.name}")
    sync_start = start_date.strftime("%Y%m%d")
    sync_end = end_date.strftime("%Y%m%d")

    try:
        result = subprocess.run(
            [sys.executable, str(_SYNC_SCRIPT),
             "--mode", "incremental",
             "--start-date", sync_start,
             "--end-date", sync_end],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            print("  [OK] 同步完成")
        else:
            print(f"  [ERROR] 同步失败 (returncode={result.returncode})")
            print(f"  stdout: {result.stdout[-500:] if result.stdout else ''}")
            print(f"  stderr: {result.stderr[-500:] if result.stderr else ''}")
            return False
    except subprocess.TimeoutExpired:
        print("  [ERROR] 同步超时（5分钟）")
        return False
    except Exception as e:
        print(f"  [ERROR] 同步异常: {e}")
        return False

    # 同步后再次验证
    try:
        existing2 = DatabaseManager.fetchall(
            "tushare_biz",
            "SELECT DISTINCT trade_date FROM t_index_weight WHERE index_code = %s AND trade_date >= %s AND trade_date <= %s",
            ("000300.SH", required_dates[0], required_dates[-1]),
        )
        still_missing = len(required_dates) - len(existing2)
        if still_missing > len(required_dates) * 0.2:  # 允许20%缺失（假期等原因）
            print(f"  [ERROR] 同步后仍缺失 {still_missing} 个交易日数据，超过20%阈值，退出")
            return False
        print(f"  [OK] 同步验证通过，覆盖 {len(existing2)}/{len(required_dates)} 天")
    except Exception as e:
        print(f"  [WARN] 同步后验证失败: {e}")

    return True


def _get_hs300_stocks() -> List[str]:
    """
    从数据库获取沪深300成分股列表。

    先检查数据完整性并触发同步（如需），
    然后从 t_index_weight 获取成分股。
    如数据缺失，报错退出（不兜底）。
    """
    print("[STEP 1] 获取沪深300成分股...")

    # 检查并同步数据
    sync_ok = check_and_sync_hs300_data(ANALYSIS_START, ANALYSIS_END)
    if not sync_ok:
        print("[ERROR] HS300数据不完整且同步失败，请手动运行:")
        print(f"  python {_SYNC_SCRIPT} --mode incremental --start-date 20250101 --end-date 20260319")
        sys.exit(1)

    # 从 t_index_weight 获取成分股（使用 con_code 字段）
    try:
        results = DatabaseManager.fetchall(
            "tushare_biz",
            "SELECT DISTINCT con_code FROM t_index_weight WHERE index_code = %s",
            ("000300.SH",),
        )
        if results:
            stocks = [r["con_code"] for r in results]
            print(f"  [OK] 从 t_index_weight 获取到 {len(stocks)} 只成分股")
            return stocks
        else:
            print("[ERROR] t_index_weight 中 HS300 数据为空，请检查同步状态")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] t_index_weight 查询失败: {e}")
        sys.exit(1)


def diagnose_factor_availability(
    factor_names: List[str],
    start_date: datetime,
    end_date: datetime,
    stock_pool: List[str],
    report_path: Optional[Path] = None,
) -> Tuple[List[str], str]:
    """
    详细诊断因子可用性，返回可用因子列表及诊断报告字符串。

    Returns:
        (available_factors, diagnosis_report_text)
    """
    print("[STEP 2] 因子可用性详细诊断...")

    lines = ["=" * 70, "  因子可用性诊断报告", "=" * 70, ""]

    # 1. 检查表结构：哪些列存在
    try:
        col_results = DatabaseManager.fetchall(
            "interface",
            (
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s"
            ),
            ("t_precomputed_factors",),
        )
        existing_cols = {r["COLUMN_NAME"] for r in col_results}
        lines.append(f"表结构检查: t_precomputed_factors 共 {len(existing_cols)} 列")
    except Exception as e:
        lines.append(f"[WARN] 无法查询表结构: {e}")
        existing_cols = set()

    # 2. 获取数据统计（日期范围、每因子非NULL数量）
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    available_factors = []
    missing_factors = []

    lines.append("")
    for factor in factor_names:
        if factor not in existing_cols:
            missing_factors.append((factor, "列不存在", "检查factor_definitions.py，运行run_factor_backfill.py注册并计算此因子"))
            continue

        # 检查数据覆盖情况
        try:
            count_result = DatabaseManager.fetchone(
                "interface",
                f"SELECT COUNT(*) as cnt, COUNT({factor}) as non_null_cnt, "
                f"MIN(trade_date) as min_date, MAX(trade_date) as max_date "
                f"FROM t_precomputed_factors "
                f"WHERE trade_date >= %s AND trade_date <= %s",
                (start_str, end_str),
            )
            total = count_result["cnt"] if count_result else 0
            non_null = count_result["non_null_cnt"] if count_result else 0
            min_date = count_result["min_date"] if count_result else None
            max_date = count_result["max_date"] if count_result else None

            if non_null == 0:
                missing_factors.append((
                    factor,
                    "列存在但数据为NULL（可能源数据缺失或未计算）",
                    "检查日线数据同步状态，然后运行run_factor_backfill.py重新计算"
                ))
            else:
                coverage_pct = non_null / total * 100 if total > 0 else 0
                available_factors.append(factor)
                lines.append(
                    f"  [OK] {factor:<20}: {min_date} ~ {max_date}, "
                    f"非空 {non_null}/{total} 行 ({coverage_pct:.1f}%)"
                )
        except Exception as e:
            missing_factors.append((factor, f"数据查询异常: {e}", "检查数据库连接和表结构"))

    lines.append("")
    lines.append(f"可用因子 ({len(available_factors)}/{len(factor_names)}):")
    for f in available_factors:
        lines.append(f"  ✓ {f}")

    lines.append("")
    lines.append(f"缺失因子 ({len(missing_factors)}/{len(factor_names)}):")
    for f, reason, suggestion in missing_factors:
        lines.append(f"  ✗ {f:<20}: {reason}")
        lines.append(f"      建议: {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    report_text = "\n".join(lines)
    print(report_text)

    # 保存诊断报告
    if report_path:
        report_path.write_text(report_text, encoding="utf-8")
        print(f"  [SAVED] {report_path.name}")

    print(f"  [SUMMARY] 可用因子: {len(available_factors)}/{len(factor_names)}")
    return available_factors, report_text


# ---------------------------------------------------------------------------
# IC 分析
# ---------------------------------------------------------------------------

def run_ic_analysis(
    analyzer: FactorAnalyzer,
    factors: List[str],
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """
    对所有因子分别计算 5d 和 20d IC。

    Returns:
        (ic_results_5d, ic_results_20d): 两个字典，key=factor_name，value=ICResult
    """
    print("\n[STEP 3] IC 分析 (5d & 20d)...")
    ic_results_5d: Dict[str, object] = {}
    ic_results_20d: Dict[str, object] = {}

    for factor in factors:
        # 5d IC
        try:
            result = analyzer.calculate_ic(factor, forward_period=5)
            ic_results_5d[factor] = result
            print(
                f"  {factor:20s} | IC_5d mean={result.ic_mean:+.4f}  "
                f"ICIR={result.icir:+.4f}  t={result.t_statistic:+.3f}"
            )
        except Exception as e:
            print(f"  [WARN] {factor} 5d IC 计算失败: {e}")

        # 20d IC
        try:
            result = analyzer.calculate_ic(factor, forward_period=20)
            ic_results_20d[factor] = result
            print(
                f"  {factor:20s} | IC_20d mean={result.ic_mean:+.4f}  "
                f"ICIR={result.icir:+.4f}  t={result.t_statistic:+.3f}"
            )
        except Exception as e:
            print(f"  [WARN] {factor} 20d IC 计算失败: {e}")

    return ic_results_5d, ic_results_20d


# ---------------------------------------------------------------------------
# 分层回测
# ---------------------------------------------------------------------------

def run_quantile_backtest(
    analyzer: FactorAnalyzer,
    factors: List[str],
    n_quantiles: int = 10,
    forward_period: int = 20,
) -> Dict[str, object]:
    """分层回测，返回 {factor: QuantileBacktestResult}。"""
    print(f"\n[STEP 4] 分层回测 (n_quantiles={n_quantiles}, forward={forward_period}d)...")
    qb_results: Dict[str, object] = {}

    for factor in factors:
        try:
            result = analyzer.quantile_backtest(
                factor, n_quantiles=n_quantiles, forward_period=forward_period
            )
            qb_results[factor] = result
            print(
                f"  {factor:20s} | LS_Sharpe={result.long_short_sharpe:+.4f}  "
                f"Monotonicity={result.monotonicity_score:+.4f}"
            )
        except Exception as e:
            print(f"  [WARN] {factor} 分层回测失败: {e}")

    return qb_results


# ---------------------------------------------------------------------------
# 行业中性检验
# ---------------------------------------------------------------------------

def run_industry_neutral(
    top_factors: List[str],
    stock_pool: List[str],
) -> Dict[str, object]:
    """对 Top 因子进行行业中性检验。"""
    print(f"\n[STEP 5] 行业中性检验 (top factors: {top_factors})...")
    neutral_results: Dict[str, object] = {}

    for factor in top_factors:
        try:
            result = industry_neutral_quantile_analysis(
                factor_name=factor,
                industry_field="industry",
                n_quantiles=5,
                forward_period=20,
                start_date=IN_SAMPLE_START,
                end_date=IN_SAMPLE_END,
            )
            neutral_results[factor] = result
            print(
                f"  {factor:20s} | neutral_IC={result.industry_neutral_ic:+.4f}  "
                f"cross_industry_IC={result.ic_cross_industry:+.4f}"
            )
        except Exception as e:
            print(f"  [WARN] {factor} 行业中性检验失败: {e}")

    return neutral_results


# ---------------------------------------------------------------------------
# 多因子投资组合策略
# ---------------------------------------------------------------------------

class MultiFactorPortfolioStrategy:
    """
    多因子组合策略（兼容 MultiStockBacktestEngine 接口）

    基于样本内IC分析确定因子方向和权重，
    横截面Z-score标准化后合成因子得分，
    选择Top-N股票等权配置。
    """

    def __init__(
        self,
        ic_results_20d: Dict[str, object],
        stock_pool: List[str],
        top_n: int = 30,
        min_icir_threshold: float = 0.1,
    ):
        """
        Args:
            ic_results_20d: 样本内20d IC分析结果 {factor: ICResult}
            stock_pool: 股票池（HS300成分股）
            top_n: 每次调仓选择的最大股票数
            min_icir_threshold: ICIR绝对值阈值，低于此值的因子不参与合成
        """
        self.stock_pool = stock_pool
        self.top_n = top_n
        self.min_icir_threshold = min_icir_threshold

        # 计算因子权重（基于ICIR，正负代表方向）
        self.factor_weights = self._compute_factor_weights(ic_results_20d)
        self._retrain_dates: set = set()

        if self.factor_weights:
            print(f"  [MultiFactorStrategy] 参与合成因子 ({len(self.factor_weights)}):")
            for f, w in sorted(self.factor_weights.items(), key=lambda x: abs(x[1]), reverse=True):
                print(f"    {f:<20}: ICIR权重={w:+.4f}")
        else:
            print("  [WARN] 没有因子满足ICIR阈值，将使用等权随机选股")

    def _compute_factor_weights(
        self, ic_results: Dict[str, object]
    ) -> Dict[str, float]:
        """基于ICIR计算因子权重（正负代表方向）。"""
        weights = {}
        for factor, result in ic_results.items():
            icir = result.icir
            if abs(icir) >= self.min_icir_threshold:
                weights[factor] = icir

        if not weights:
            return weights

        # 对权重绝对值归一化（保留方向符号）
        total_abs = sum(abs(w) for w in weights.values())
        if total_abs > 0:
            weights = {f: w / total_abs for f, w in weights.items()}

        return weights

    def train(self, train_start: datetime, train_end: datetime) -> None:
        """兼容引擎接口：本策略不需要ML训练。"""
        pass

    def should_retrain(self, date: datetime) -> bool:
        """兼容引擎接口：不需要重训练。"""
        return False

    def predict(self, trade_date: datetime) -> pd.DataFrame:
        """
        生成当日股票预测得分，返回按得分降序排列的DataFrame。

        Returns:
            DataFrame with columns: ts_code, predicted_return, confidence
        """
        from core.storage.relational.connection import DatabaseManager

        if not self.factor_weights:
            # 无因子权重：随机选股（用于对照）
            import random
            selected = random.sample(self.stock_pool, min(self.top_n, len(self.stock_pool)))
            return pd.DataFrame({
                "ts_code": selected,
                "predicted_return": [0.0] * len(selected),
                "confidence": [0.0] * len(selected),
            })

        trade_date_str = trade_date.strftime("%Y%m%d")
        factor_cols = list(self.factor_weights.keys())
        cols_sql = ", ".join(factor_cols)

        try:
            rows = DatabaseManager.fetchall(
                "interface",
                f"SELECT ts_code, {cols_sql} FROM t_precomputed_factors "
                f"WHERE trade_date = %s AND ts_code IN ({','.join(['%s']*len(self.stock_pool))})",
                (trade_date_str, *self.stock_pool),
            )
        except Exception as e:
            return pd.DataFrame(columns=["ts_code", "predicted_return", "confidence"])

        if not rows:
            return pd.DataFrame(columns=["ts_code", "predicted_return", "confidence"])

        df = pd.DataFrame(rows)
        df = df.set_index("ts_code")

        # 计算横截面Z-score合成得分
        scores = pd.Series(0.0, index=df.index)
        valid_factors = 0

        for factor, weight in self.factor_weights.items():
            if factor not in df.columns:
                continue
            col = df[factor].dropna()
            if len(col) < 10:
                continue
            zscore = (col - col.mean()) / (col.std() + 1e-8)
            scores = scores.add(zscore * weight, fill_value=0)
            valid_factors += 1

        if valid_factors == 0:
            return pd.DataFrame(columns=["ts_code", "predicted_return", "confidence"])

        scores = scores.dropna()
        scores_sorted = scores.sort_values(ascending=False)

        result_df = pd.DataFrame({
            "ts_code": scores_sorted.index,
            "predicted_return": scores_sorted.values,
            "confidence": (scores_sorted.rank(pct=True).values),
        })

        return result_df.head(self.top_n)

    def generate_portfolio_weights(
        self,
        trade_date: datetime,
        selected_stocks: List[str],
        method: str = "equal",
    ) -> Dict[str, float]:
        """生成等权投资组合权重。"""
        n = len(selected_stocks)
        if n == 0:
            return {}
        weight = 1.0 / n
        return {ts_code: weight for ts_code in selected_stocks}


# ---------------------------------------------------------------------------
# 投资组合回测
# ---------------------------------------------------------------------------

def run_portfolio_backtest(
    strategy: MultiFactorPortfolioStrategy,
    start_date: datetime,
    end_date: datetime,
    label: str = "回测",
) -> Optional[object]:
    """
    使用 MultiStockBacktestEngine 运行投资组合回测。

    Returns:
        BacktestResult 或 None（如失败）
    """
    print(f"\n[STEP] 运行{label}: {start_date.date()} ~ {end_date.date()}")

    try:
        from projects.quant_trading.backtest.multi_stock_engine import (
            MultiStockBacktestEngine,
            MultiStockBacktestConfig,
            RebalanceFrequency,
        )
    except ImportError as e:
        print(f"  [ERROR] 无法导入 MultiStockBacktestEngine: {e}")
        return None

    config = MultiStockBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=1_000_000.0,
        max_positions=strategy.top_n,
        min_positions=5,
        rebalance_freq=RebalanceFrequency.WEEKLY,
        position_size_method="equal",
        benchmark="000300.SH",
    )

    try:
        engine = MultiStockBacktestEngine(config, strategy)
        result = engine.run()

        m = result.metrics
        print(f"  [RESULT] {label}:")
        print(f"    总收益率:   {m.total_return*100:+.2f}%")
        print(f"    年化收益:   {m.annual_return*100:+.2f}%")
        print(f"    夏普比率:   {m.sharpe_ratio:.3f}")
        print(f"    最大回撤:   {m.max_drawdown*100:.2f}%")
        print(f"    信息比率:   {m.information_ratio:.3f}")
        print(f"    胜率:       {m.win_rate*100:.2f}%")

        return result

    except Exception as e:
        print(f"  [ERROR] {label}失败: {e}")
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# 可视化
# ---------------------------------------------------------------------------

def _use_chinese(has_cn: bool) -> callable:
    """返回标签选择器：有中文字体返回中文字符串，否则返回英文。"""
    def _label(cn: str, en: str) -> str:
        return cn if has_cn else en
    return _label


def plot_ic_bar(
    ic_results_20d: Dict[str, object],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """1. IC 均值柱状图（20d）。"""
    label = _use_chinese(has_chinese)
    factors = list(ic_results_20d.keys())
    ic_means = [ic_results_20d[f].ic_mean for f in factors]

    colors = ["#d62728" if v >= 0 else "#1f77b4" for v in ic_means]

    fig, ax = plt.subplots(figsize=(max(10, len(factors) * 0.8), 6))
    bars = ax.bar(factors, ic_means, color=colors, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, ic_means):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + (0.002 if val >= 0 else -0.004),
            f"{val:+.4f}",
            ha="center",
            va="bottom" if val >= 0 else "top",
            fontsize=8,
        )

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_title(label("各因子 IC 均值 (20日前瞻)", "Factor IC Mean (20d Forward)"), fontsize=14)
    ax.set_xlabel(label("因子", "Factor"), fontsize=12)
    ax.set_ylabel(label("IC 均值", "IC Mean"), fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_ic_timeseries(
    ic_results_20d: Dict[str, object],
    top_factors: List[str],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """2. Top 3 因子的 IC 时序图（20d）。"""
    label = _use_chinese(has_chinese)
    fig, axes = plt.subplots(
        len(top_factors), 1,
        figsize=(14, 4 * len(top_factors)),
        sharex=False,
    )
    if len(top_factors) == 1:
        axes = [axes]

    for ax, factor in zip(axes, top_factors):
        if factor not in ic_results_20d:
            ax.set_title(f"{factor} - no data")
            continue
        result = ic_results_20d[factor]
        ic_series = result.ic_series
        dates = ic_series.index if hasattr(ic_series.index, '__iter__') else result.dates

        ax.bar(range(len(ic_series)), ic_series.values, color=[
            "#d62728" if v >= 0 else "#1f77b4" for v in ic_series.values
        ], alpha=0.7)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.axhline(ic_series.mean(), color="orange", linewidth=1.5,
                   linestyle="--", label=f"Mean={ic_series.mean():+.4f}")

        title = label(
            f"{factor} | IC均值={result.ic_mean:+.4f}  ICIR={result.icir:+.4f}",
            f"{factor} | IC Mean={result.ic_mean:+.4f}  ICIR={result.icir:+.4f}",
        )
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(label("IC值", "IC"), fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    fig.suptitle(
        label("Top 因子 IC 时序 (20日前瞻)", "Top Factor IC Time Series (20d)"),
        fontsize=14, y=1.01,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_quantile_heatmap(
    qb_results: Dict[str, object],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """3. 分组平均收益热力图。"""
    label = _use_chinese(has_chinese)
    if not qb_results:
        print("  [SKIP] 无分层回测结果，跳过热力图")
        return

    factors = list(qb_results.keys())
    n_quantiles = next(iter(qb_results.values())).n_quantiles
    data = np.zeros((len(factors), n_quantiles))

    for i, factor in enumerate(factors):
        result = qb_results[factor]
        for q in range(1, n_quantiles + 1):
            data[i, q - 1] = result.quantile_stats[q]["mean_return"]

    fig, ax = plt.subplots(figsize=(max(12, n_quantiles), max(6, len(factors) * 0.6)))
    vmax = np.nanpercentile(np.abs(data), 95)
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(n_quantiles))
    ax.set_xticklabels([f"Q{q}" for q in range(1, n_quantiles + 1)], fontsize=9)
    ax.set_yticks(range(len(factors)))
    ax.set_yticklabels(factors, fontsize=9)

    for i in range(len(factors)):
        for j in range(n_quantiles):
            ax.text(j, i, f"{data[i, j]:.3%}", ha="center", va="center", fontsize=7)

    plt.colorbar(im, ax=ax, label=label("平均收益率", "Avg Return"))
    ax.set_title(
        label("各因子分位数组合平均收益热力图", "Factor Quantile Average Return Heatmap"),
        fontsize=13,
    )
    ax.set_xlabel(label("分位数组", "Quantile Group"), fontsize=11)
    ax.set_ylabel(label("因子", "Factor"), fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_long_short_cumulative(
    qb_results: Dict[str, object],
    top_factors: List[str],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """4. Top 3 因子多空累计收益曲线。"""
    label = _use_chinese(has_chinese)
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = plt.cm.tab10.colors  # type: ignore[attr-defined]

    has_any = False
    for idx, factor in enumerate(top_factors):
        if factor not in qb_results:
            continue
        result = qb_results[factor]
        cum = result.long_short_cumulative
        ax.plot(
            range(len(cum)),
            cum.values,
            label=f"{factor} (Sharpe={result.long_short_sharpe:.2f})",
            color=colors[idx % len(colors)],
            linewidth=2,
        )
        has_any = True

    if not has_any:
        print("  [SKIP] 无多空回测结果，跳过累计收益图")
        plt.close(fig)
        return

    ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_title(
        label("Top 因子多空组合累计收益", "Top Factor Long-Short Cumulative Return"),
        fontsize=14,
    )
    ax.set_xlabel(label("交易日序号", "Trading Day Index"), fontsize=12)
    ax.set_ylabel(label("累计收益 (1=起点)", "Cumulative Return (base=1)"), fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_factor_correlation(
    analyzer: FactorAnalyzer,
    factors: List[str],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """5. 因子相关性矩阵热力图。"""
    label = _use_chinese(has_chinese)
    print("  计算因子相关性矩阵...")

    try:
        factors_df = analyzer.precomputer.get_precomputed_factors(
            trade_date=IN_SAMPLE_END,
            stock_pool=analyzer.stock_pool,
        )
    except Exception as e:
        print(f"  [WARN] 无法获取因子数据计算相关性: {e}")
        return

    available_cols = [f for f in factors if f in factors_df.columns]
    if len(available_cols) < 2:
        print("  [SKIP] 可用因子列不足，跳过相关性图")
        return

    corr = factors_df[available_cols].corr(method="spearman")

    fig, ax = plt.subplots(figsize=(max(10, len(available_cols)), max(8, len(available_cols))))
    im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(len(available_cols)))
    ax.set_yticks(range(len(available_cols)))
    ax.set_xticklabels(available_cols, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(available_cols, fontsize=9)

    for i in range(len(available_cols)):
        for j in range(len(available_cols)):
            ax.text(
                j, i, f"{corr.values[i, j]:.2f}",
                ha="center", va="center", fontsize=7,
                color="black" if abs(corr.values[i, j]) < 0.7 else "white",
            )

    plt.colorbar(im, ax=ax, label=label("Spearman 相关系数", "Spearman Correlation"))
    ax.set_title(
        label("因子相关性矩阵 (Spearman)", "Factor Correlation Matrix (Spearman)"),
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_portfolio_nav(
    result_in: object,
    result_out: Optional[object],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """6. 投资组合净值曲线（样本内+样本外合并展示）。"""
    label = _use_chinese(has_chinese)
    fig, ax = plt.subplots(figsize=(16, 7))

    # 样本内
    nav_in = result_in.nav_history
    if not nav_in.empty:
        nav_norm_in = nav_in["nav"] / nav_in["nav"].iloc[0]
        ax.plot(
            nav_in.index,
            nav_norm_in.values,
            color="#1f77b4",
            linewidth=2,
            label=label(
                f"样本内 ({IN_SAMPLE_START.date()}~{IN_SAMPLE_END.date()})",
                f"In-Sample ({IN_SAMPLE_START.date()}~{IN_SAMPLE_END.date()})"
            ),
        )

    # 样本外
    if result_out is not None:
        nav_out = result_out.nav_history
        if not nav_out.empty:
            nav_norm_out = nav_out["nav"] / nav_out["nav"].iloc[0]
            ax.plot(
                nav_out.index,
                nav_norm_out.values,
                color="#d62728",
                linewidth=2,
                linestyle="--",
                label=label(
                    f"样本外 ({OUT_SAMPLE_START.date()}~{OUT_SAMPLE_END.date()})",
                    f"Out-of-Sample ({OUT_SAMPLE_START.date()}~{OUT_SAMPLE_END.date()})"
                ),
            )

    # 样本内外分界线
    ax.axvline(
        x=pd.Timestamp(OUT_SAMPLE_START),
        color="gray",
        linewidth=1.5,
        linestyle=":",
        alpha=0.8,
        label=label("样本内/外分界", "Train/Test Split"),
    )

    ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--", alpha=0.3)
    ax.set_title(
        label("多因子投资组合净值曲线", "Multi-Factor Portfolio NAV Curve"),
        fontsize=14,
    )
    ax.set_xlabel(label("日期", "Date"), fontsize=12)
    ax.set_ylabel(label("归一化净值", "Normalized NAV"), fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


def plot_performance_comparison(
    result_in: object,
    result_out: Optional[object],
    output_path: Path,
    has_chinese: bool,
) -> None:
    """7. 样本内/外绩效对比表图。"""
    label = _use_chinese(has_chinese)

    metrics_labels = {
        "total_return": label("总收益率", "Total Return"),
        "annual_return": label("年化收益", "Annual Return"),
        "sharpe_ratio": label("夏普比率", "Sharpe Ratio"),
        "max_drawdown": label("最大回撤", "Max Drawdown"),
        "information_ratio": label("信息比率", "Info Ratio"),
        "win_rate": label("胜率", "Win Rate"),
        "volatility": label("波动率", "Volatility"),
    }

    m_in = result_in.metrics
    m_out = result_out.metrics if result_out else None

    rows = []
    for key, lbl in metrics_labels.items():
        val_in = getattr(m_in, key, None)
        val_out = getattr(m_out, key, None) if m_out else None

        # 格式化为百分比或数值
        pct_keys = {"total_return", "annual_return", "max_drawdown", "win_rate", "volatility"}
        fmt = lambda v: f"{v*100:+.2f}%" if v is not None and key in pct_keys else (f"{v:.3f}" if v is not None else "N/A")
        rows.append({
            label("指标", "Metric"): lbl,
            label("样本内", "In-Sample"): fmt(val_in),
            label("样本外", "Out-of-Sample"): fmt(val_out),
        })

    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(10, max(4, len(rows) * 0.5 + 2)))
    ax.axis("off")
    col_labels = list(df.columns)
    table = ax.table(
        cellText=df.values,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    # 标题行底色
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#2196F3")
        table[0, j].set_text_props(color="white", fontweight="bold")

    ax.set_title(
        label("样本内/外绩效对比", "In-Sample vs Out-of-Sample Performance"),
        fontsize=14, pad=20,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {output_path.name}")


# ---------------------------------------------------------------------------
# 汇总报告
# ---------------------------------------------------------------------------

def build_summary_report(
    factors: List[str],
    ic_results_5d: Dict[str, object],
    ic_results_20d: Dict[str, object],
    qb_results: Dict[str, object],
) -> pd.DataFrame:
    """构建汇总 DataFrame，并按 |ICIR(20d)| 降序排列。"""
    rows = []
    for factor in factors:
        row = {"factor": factor}

        if factor in ic_results_5d:
            r5 = ic_results_5d[factor]
            row["ic_mean_5d"] = round(r5.ic_mean, 6)
            row["icir_5d"] = round(r5.icir, 6)
            row["t_stat_5d"] = round(r5.t_statistic, 4)
            row["p_value_5d"] = round(r5.p_value, 4)
        else:
            row.update({"ic_mean_5d": np.nan, "icir_5d": np.nan,
                        "t_stat_5d": np.nan, "p_value_5d": np.nan})

        if factor in ic_results_20d:
            r20 = ic_results_20d[factor]
            row["ic_mean_20d"] = round(r20.ic_mean, 6)
            row["icir_20d"] = round(r20.icir, 6)
            row["t_stat_20d"] = round(r20.t_statistic, 4)
            row["p_value_20d"] = round(r20.p_value, 4)
        else:
            row.update({"ic_mean_20d": np.nan, "icir_20d": np.nan,
                        "t_stat_20d": np.nan, "p_value_20d": np.nan})

        if factor in qb_results:
            qb = qb_results[factor]
            row["long_short_sharpe"] = round(qb.long_short_sharpe, 4)
            row["monotonicity"] = round(qb.monotonicity_score, 4)
        else:
            row.update({"long_short_sharpe": np.nan, "monotonicity": np.nan})

        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("icir_20d", key=lambda s: s.abs(), ascending=False, na_position="last")
    df = df.reset_index(drop=True)
    return df


def build_performance_comparison_csv(
    result_in: object,
    result_out: Optional[object],
    output_path: Path,
) -> None:
    """将绩效对比保存为CSV。"""
    metric_keys = [
        "total_return", "annual_return", "sharpe_ratio", "max_drawdown",
        "information_ratio", "win_rate", "volatility", "total_trades",
        "calmar_ratio", "sortino_ratio",
    ]

    m_in = result_in.metrics
    m_out = result_out.metrics if result_out else None

    rows = []
    for key in metric_keys:
        val_in = getattr(m_in, key, None)
        val_out = getattr(m_out, key, None) if m_out else None
        rows.append({
            "metric": key,
            "in_sample": val_in,
            "out_of_sample": val_out,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  [SAVED] {output_path.name}")


def print_summary_table(df: pd.DataFrame) -> None:
    """格式化打印汇总表。"""
    print("\n" + "=" * 90)
    print("  因子有效性分析汇总 (按 |ICIR 20d| 降序)")
    print("=" * 90)
    header = (
        f"{'Factor':<20} {'IC_5d':>8} {'IC_20d':>8} "
        f"{'ICIR_20d':>9} {'T-stat':>8} {'LS_Sharpe':>10} {'Mono':>7}"
    )
    print(header)
    print("-" * 90)
    for _, row in df.iterrows():
        def _fmt(v):
            return f"{v:+.4f}" if pd.notna(v) else "   N/A"

        print(
            f"{str(row['factor']):<20} "
            f"{_fmt(row['ic_mean_5d']):>8} "
            f"{_fmt(row['ic_mean_20d']):>8} "
            f"{_fmt(row['icir_20d']):>9} "
            f"{_fmt(row['t_stat_20d']):>8} "
            f"{_fmt(row['long_short_sharpe']):>10} "
            f"{_fmt(row['monotonicity']):>7}"
        )
    print("=" * 90)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  沪深300 因子有效性分析 + 多因子投资组合回测")
    print(f"  总分析区间: {ANALYSIS_START.date()} ~ {ANALYSIS_END.date()}")
    print(f"  样本内:     {IN_SAMPLE_START.date()} ~ {IN_SAMPLE_END.date()}")
    print(f"  样本外:     {OUT_SAMPLE_START.date()} ~ {OUT_SAMPLE_END.date()}")
    print("=" * 70)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")

    # 配置中文字体
    has_chinese = _setup_chinese_font()

    # Step 1: 获取沪深300成分股（含数据完整性检查和同步）
    stock_pool = _get_hs300_stocks()
    print(f"[INFO] 股票池规模: {len(stock_pool)} 只")

    # Step 2: 因子可用性详细诊断
    available_factors, _ = diagnose_factor_availability(
        TARGET_FACTORS,
        start_date=IN_SAMPLE_START,
        end_date=IN_SAMPLE_END,
        stock_pool=stock_pool,
        report_path=OUTPUT_DIR / "data_diagnosis_report.txt",
    )

    if not available_factors:
        print("[ERROR] 没有可用因子，退出")
        sys.exit(1)

    # Step 3~4: IC 分析 & 分层回测（基于样本内数据）
    print(f"\n[INFO] 初始化 FactorAnalyzer (样本内: {IN_SAMPLE_START.date()} ~ {IN_SAMPLE_END.date()}, "
          f"stock_pool={len(stock_pool)} 只)...")
    analyzer = FactorAnalyzer(
        start_date=IN_SAMPLE_START,
        end_date=IN_SAMPLE_END,
        stock_pool=stock_pool,
        min_stocks_per_day=10,
    )

    ic_results_5d, ic_results_20d = run_ic_analysis(analyzer, available_factors)

    qb_results = run_quantile_backtest(
        analyzer, available_factors, n_quantiles=10, forward_period=20
    )

    # Step 5: 选出 Top 3 因子（按 |ICIR 20d|）并进行行业中性检验
    icir_ranked = sorted(
        [f for f in available_factors if f in ic_results_20d],
        key=lambda f: abs(ic_results_20d[f].icir),
        reverse=True,
    )
    top3_factors = icir_ranked[:3]
    print(f"\n[INFO] Top 3 因子 (|ICIR 20d|): {top3_factors}")

    neutral_results = run_industry_neutral(top3_factors, stock_pool)

    # Step 6: 构建多因子组合策略
    print("\n[STEP 6] 构建多因子投资组合策略...")
    strategy = MultiFactorPortfolioStrategy(
        ic_results_20d=ic_results_20d,
        stock_pool=stock_pool,
        top_n=30,
        min_icir_threshold=0.1,
    )

    # Step 7: 样本内回测
    result_in = run_portfolio_backtest(
        strategy=strategy,
        start_date=IN_SAMPLE_START,
        end_date=IN_SAMPLE_END,
        label="样本内回测",
    )

    # Step 8: 样本外回测（使用相同因子权重）
    result_out = run_portfolio_backtest(
        strategy=strategy,
        start_date=OUT_SAMPLE_START,
        end_date=OUT_SAMPLE_END,
        label="样本外验证",
    )

    # Step 9: 可视化
    print(f"\n[STEP 9] 生成可视化图表...")

    if ic_results_20d:
        plot_ic_bar(ic_results_20d, OUTPUT_DIR / "ic_bar.png", has_chinese)

    if ic_results_20d and top3_factors:
        plot_ic_timeseries(ic_results_20d, top3_factors, OUTPUT_DIR / "ic_timeseries.png", has_chinese)

    if qb_results:
        plot_quantile_heatmap(qb_results, OUTPUT_DIR / "quantile_heatmap.png", has_chinese)
        plot_long_short_cumulative(qb_results, top3_factors, OUTPUT_DIR / "long_short_cumulative.png", has_chinese)

    plot_factor_correlation(analyzer, available_factors, OUTPUT_DIR / "factor_correlation.png", has_chinese)

    if result_in is not None:
        plot_portfolio_nav(result_in, result_out, OUTPUT_DIR / "portfolio_nav.png", has_chinese)
        plot_performance_comparison(result_in, result_out, OUTPUT_DIR / "performance_comparison.png", has_chinese)
        build_performance_comparison_csv(result_in, result_out, OUTPUT_DIR / "performance_comparison.csv")

    # Step 10: 汇总报告
    print("\n[STEP 10] 生成汇总报告...")
    summary_df = build_summary_report(available_factors, ic_results_5d, ic_results_20d, qb_results)

    csv_path = OUTPUT_DIR / "summary_report.csv"
    summary_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  [SAVED] {csv_path.name}")

    print_summary_table(summary_df)

    # 打印过拟合风险评估
    if result_in is not None and result_out is not None:
        print("\n" + "=" * 70)
        print("  样本内/外对比（过拟合风险评估）")
        print("=" * 70)
        m_in = result_in.metrics
        m_out = result_out.metrics
        print(f"  {'指标':<20} {'样本内':>12} {'样本外':>12} {'变化':>12}")
        print("-" * 70)
        for label_cn, key, is_pct in [
            ("总收益率", "total_return", True),
            ("夏普比率", "sharpe_ratio", False),
            ("最大回撤", "max_drawdown", True),
            ("信息比率", "information_ratio", False),
            ("胜率", "win_rate", True),
        ]:
            v_in = getattr(m_in, key, None)
            v_out = getattr(m_out, key, None)
            if v_in is None or v_out is None:
                continue
            fmt = lambda v: f"{v*100:+.2f}%" if is_pct else f"{v:+.3f}"
            delta = v_out - v_in
            delta_str = fmt(delta)
            flag = " ⚠" if abs(delta) > abs(v_in) * 0.5 else ""
            print(f"  {label_cn:<20} {fmt(v_in):>12} {fmt(v_out):>12} {delta_str:>12}{flag}")
        print("=" * 70)

    print(f"\n[DONE] 所有输出已保存至: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
