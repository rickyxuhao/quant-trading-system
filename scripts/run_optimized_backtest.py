#!/usr/bin/env python3
"""
优化后回测验证脚本 - Phase 5

对比优化前(Phase3)与优化后执行逻辑的回测表现

优化点：
  1. T+1日 (high+low)/2 成交价
  2. 涨跌停过滤（涨停不买，跌停不强平）
  3. 0.1% 固定滑点 + 量化冲击 (sqrt(size_ratio))
  4. 印花税 0.1% (单向卖出) + 佣金 0.025%（双向，最低5元）
  5. 因子 IC 改为 63日滚动 ICIR 加权
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

# ─── 路径 ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.storage.relational.connection import DatabaseManager

# ─── 常量 ─────────────────────────────────────────────────────────────────────
START_DATE   = "20250101"
END_DATE     = "20260320"
INITIAL_CAP  = 2_000_000.0
TOP_N        = 30           # 每期持仓只数
REBAL_FREQ   = "weekly"     # 每周调仓（周一）
OUTPUT       = ROOT / "output"

# 交易成本参数
COMMISSION_RATE     = 0.00025    # 佣金 0.025%
MIN_COMMISSION      = 5.0        # 最低佣金 5元
STAMP_DUTY          = 0.001      # 印花税 0.1%（仅卖出）
FIXED_SLIPPAGE      = 0.001      # 固定滑点 0.1%
MARKET_IMPACT_COEF  = 0.001      # 量化冲击系数（HS300大盘股冲击极小）
REF_AMOUNT          = 100_000_000  # 参考日均成交额（沪深300 ~1亿均量）

# ─── 字体 ─────────────────────────────────────────────────────────────────────
DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
CYAN     = "#00b4d8"
RED_FILL = "#c0392b"
GREEN    = "#2ecc71"
GOLD     = "#f1c40f"
TEXT     = "#e6edf3"
GRID     = "#21262d"
ORANGE   = "#e67e22"
PURPLE   = "#9b59b6"


def setup_chinese_font() -> str:
    font_paths = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    for path in font_paths:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            font_name = prop.get_name()
            plt.rcParams["font.family"] = font_name
            plt.rcParams["axes.unicode_minus"] = False
            return font_name
    plt.rcParams["axes.unicode_minus"] = False
    return "default"


def _apply_dark(ax):
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.5, linestyle="--", alpha=0.7)


# ─── 1. 数据加载 ─────────────────────────────────────────────────────────────

def get_hs300_stocks(trade_date: str) -> List[str]:
    """获取沪深300成分股列表"""
    rows = DatabaseManager.fetchall(
        "tushare_biz",
        """SELECT DISTINCT con_code FROM t_index_weight
           WHERE index_code = '000300.SH'
           AND trade_date = (
               SELECT MAX(trade_date) FROM t_index_weight
               WHERE index_code = '000300.SH' AND trade_date <= %s
           )""",
        (trade_date,)
    )
    return [r["con_code"] for r in rows]


def get_trade_dates(start_date: str, end_date: str) -> List[str]:
    """获取交易日列表"""
    rows = DatabaseManager.fetchall(
        "tushare_biz",
        """SELECT cal_date FROM t_stock_tradedate
           WHERE is_open = 1 AND cal_date >= %s AND cal_date <= %s
           ORDER BY cal_date""",
        (start_date, end_date)
    )
    return [r["cal_date"] for r in rows]


def get_daily_data_batch(ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """批量获取日线数据（open/high/low/close/pct_chg）"""
    if not ts_codes:
        return pd.DataFrame()
    batch_size = 300
    all_rows = []
    for i in range(0, len(ts_codes), batch_size):
        batch = ts_codes[i:i+batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        rows = DatabaseManager.fetchall(
            "tushare_biz",
            f"""SELECT ts_code, trade_date, open, high, low, close, pct_chg
                FROM t_stock_dailymarketdata
                WHERE ts_code IN ({placeholders})
                AND trade_date >= %s AND trade_date <= %s""",
            tuple(batch) + (start_date, end_date)
        )
        all_rows.extend(rows)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["trade_date"] = df["trade_date"].astype(str)
    return df


def get_factors_batch(ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """批量获取预计算因子"""
    factor_cols = [
        "return_5d", "return_20d", "return_60d", "return_120d",
        "price_position_20d", "volatility_20d", "volatility_60d",
        "turnover_rate", "turnover_rate_f",
        "large_order_net_amount", "main_net_inflow", "net_inflow_5d",
        "market_alpha_20d", "market_alpha_60d", "tr", "volume_ratio",
        "return_10d", "volatility_10d", "volatility_5d",
        "pe_ttm", "pb", "ep_ttm", "roe",
        "turnover_rate_zscore", "return_20d_zscore",
    ]
    cols_str = ", ".join(["trade_date", "ts_code"] + factor_cols)

    batch_size = 300
    all_rows = []
    for i in range(0, len(ts_codes), batch_size):
        batch = ts_codes[i:i+batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        rows = DatabaseManager.fetchall(
            "interface",
            f"""SELECT {cols_str} FROM t_precomputed_factors
                WHERE ts_code IN ({placeholders})
                AND trade_date >= %s AND trade_date <= %s""",
            tuple(batch) + (start_date, end_date)
        )
        all_rows.extend(rows)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["trade_date"] = df["trade_date"].astype(str)
    return df


def get_hs300_daily(start_date: str, end_date: str) -> pd.DataFrame:
    """获取沪深300指数日线"""
    rows = DatabaseManager.fetchall(
        "tushare_biz",
        """SELECT trade_date, close, pct_chg
           FROM t_index_daily
           WHERE ts_code = '000300.SH'
           AND trade_date >= %s AND trade_date <= %s
           ORDER BY trade_date""",
        (start_date, end_date)
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["trade_date"] = df["trade_date"].astype(str)
    return df.sort_values("trade_date").reset_index(drop=True)


# ─── 2. 因子IC分析（滚动ICIR） ────────────────────────────────────────────────

def compute_rolling_icir(factors_df: pd.DataFrame, price_df: pd.DataFrame,
                          trade_dates: List[str],
                          forward_days: int = 5,
                          rolling_window: int = 63) -> Dict[str, float]:
    """
    计算各因子的 63日滚动 ICIR（季度窗口）
    返回: {factor_name: final_rolling_icir}
    """
    factor_cols = [c for c in factors_df.columns if c not in ("trade_date", "ts_code")]

    # Build forward returns
    price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
    date_idx = {d: i for i, d in enumerate(sorted(price_pivot.index))}
    all_dates = sorted(price_pivot.index)

    ic_dict: Dict[str, List[float]] = {c: [] for c in factor_cols}
    ic_dates: List[str] = []

    for date in trade_dates:
        idx = date_idx.get(date)
        if idx is None:
            continue
        future_idx = idx + forward_days
        if future_idx >= len(all_dates):
            continue
        future_date = all_dates[future_idx]

        cur_prices = price_pivot.loc[date].dropna()
        fut_prices = price_pivot.loc[future_date].dropna()
        common = cur_prices.index.intersection(fut_prices.index)
        if len(common) < 30:
            continue

        fwd_ret = (fut_prices[common] / cur_prices[common] - 1)

        day_factors = factors_df[factors_df["trade_date"] == date].set_index("ts_code")
        day_factors = day_factors.loc[day_factors.index.intersection(common)]

        if len(day_factors) < 30:
            continue

        ic_dates.append(date)
        for col in factor_cols:
            if col not in day_factors.columns:
                ic_dict[col].append(np.nan)
                continue
            fv = day_factors[col].dropna()
            rv = fwd_ret.reindex(fv.index).dropna()
            if len(rv) < 10:
                ic_dict[col].append(np.nan)
                continue
            from scipy.stats import spearmanr
            ic_val, _ = spearmanr(fv.loc[rv.index], rv)
            ic_dict[col].append(np.nan if np.isnan(ic_val) else ic_val)

    # rolling ICIR
    result = {}
    for col in factor_cols:
        s = pd.Series(ic_dict[col], index=ic_dates, dtype=float).dropna()
        if len(s) < 10:
            result[col] = 0.0
            continue
        # full-period ICIR
        ic_mean = s.mean()
        ic_std = s.std()
        icir = ic_mean / ic_std if ic_std > 0 else 0.0
        # rolling 63d ICIR (use last available value)
        roll_mean = s.rolling(rolling_window, min_periods=max(10, rolling_window // 3)).mean()
        roll_std = s.rolling(rolling_window, min_periods=max(10, rolling_window // 3)).std()
        roll_icir = (roll_mean / roll_std.replace(0, np.nan)).dropna()
        final_rolling = float(roll_icir.iloc[-1]) if len(roll_icir) > 0 else icir
        result[col] = final_rolling

    return result


# ─── 3. 信号生成 ─────────────────────────────────────────────────────────────

def generate_signals(factors_df: pd.DataFrame, ic_weights: Dict[str, float],
                     trade_dates: List[str], top_n: int = 30) -> pd.DataFrame:
    """
    使用 IC 加权复合得分生成横截面信号
    先对各因子做截面zscore，再IC加权合成
    """
    factor_cols = [c for c in ic_weights if c in factors_df.columns and abs(ic_weights[c]) > 0.1]
    if not factor_cols:
        # 回退：使用所有因子
        factor_cols = [c for c in factors_df.columns if c not in ("trade_date", "ts_code")]

    results = []
    for date in trade_dates:
        day = factors_df[factors_df["trade_date"] == date].copy()
        if len(day) < 10:
            continue

        day = day.set_index("ts_code")
        scores = pd.Series(0.0, index=day.index)

        for col in factor_cols:
            if col not in day.columns:
                continue
            v = day[col].astype(float)
            # clip extremes
            v = v.clip(lower=v.quantile(0.01), upper=v.quantile(0.99))
            std = v.std()
            if std > 0:
                z = (v - v.mean()) / std
                # factor direction sign from ic_weight
                w = ic_weights.get(col, 0.0)
                scores += z * abs(w) * (1 if w >= 0 else -1)

        scores = scores.dropna()
        scores = scores.sort_values(ascending=False)

        for rank_i, (ts_code, score) in enumerate(scores.items(), 1):
            results.append({
                "trade_date": date,
                "ts_code": ts_code,
                "composite_score": score,
                "rank": rank_i,
            })

    return pd.DataFrame(results)


# ─── 4. 交易成本计算（优化版） ────────────────────────────────────────────────

def calc_cost(amount: float, is_sell: bool) -> float:
    """
    计算单笔交易总成本（含滑点）

    成本项：
    - 佣金: 0.025%（双向，最低5元）
    - 印花税: 0.1%（仅卖出）
    - 固定滑点: 0.1%
    - 量化冲击: 0.1 * sqrt(amount / 1M)
    """
    if amount <= 0:
        return 0.0

    # 佣金
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    # 印花税（仅卖出）
    stamp = amount * STAMP_DUTY if is_sell else 0.0
    # 滑点 = 固定 + 量化冲击
    fixed_slip = amount * FIXED_SLIPPAGE
    size_ratio = amount / REF_AMOUNT
    market_impact = amount * MARKET_IMPACT_COEF * math.sqrt(size_ratio)
    slippage = fixed_slip + market_impact

    return commission + stamp + slippage


# ─── 5. 组合模拟（优化执行逻辑） ─────────────────────────────────────────────

class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}   # ts_code -> shares
        self.cost_basis: Dict[str, float] = {}  # ts_code -> avg cost
        self.total_cost_paid = 0.0

    @property
    def total_value(self) -> float:
        return self.cash + sum(
            shares * self._mark_prices.get(ts, 0.0)
            for ts, shares in self.positions.items()
        )

    def mark_to_market(self, prices: Dict[str, float]) -> None:
        self._mark_prices = prices

    def rebalance(
        self,
        target_stocks: List[str],
        exec_prices: Dict[str, float],   # T+1日 (high+low)/2
        mark_prices: Dict[str, float],   # T日收盘价（用于估值）
        limit_up_stocks: set,
        limit_down_stocks: set,
        date: str,
    ) -> List[dict]:
        """执行调仓（T+1价，涨跌停过滤）"""
        self._mark_prices = mark_prices

        # 过滤涨停（无法买入）
        buyable = [s for s in target_stocks if s not in limit_up_stocks]
        if not buyable:
            return []

        total_val = self.total_value
        if total_val <= 0:
            return []

        target_weight = 1.0 / len(buyable)
        trades = []

        # 先卖出不在目标中的持仓（跌停的不强平）
        for ts_code in list(self.positions.keys()):
            if ts_code not in buyable:
                if ts_code in limit_down_stocks:
                    continue  # 跌停，保留
                ep = exec_prices.get(ts_code)
                if ep is None or ep <= 0:
                    continue
                shares = self.positions[ts_code]
                amount = shares * ep
                cost = calc_cost(amount, is_sell=True)
                self.cash += amount - cost
                self.total_cost_paid += cost
                del self.positions[ts_code]
                if ts_code in self.cost_basis:
                    del self.cost_basis[ts_code]
                trades.append({"date": date, "ts_code": ts_code, "action": "sell",
                               "shares": shares, "price": ep, "amount": amount, "cost": cost})

        # 再买入目标股票（调整权重）
        total_val = self.total_value
        for ts_code in buyable:
            ep = exec_prices.get(ts_code)
            if ep is None or ep <= 0:
                continue
            target_amount = total_val * target_weight
            current_shares = self.positions.get(ts_code, 0.0)
            current_amount = current_shares * ep
            delta = target_amount - current_amount

            if abs(delta) < 1000:  # 小于1000元忽略
                continue

            if delta > 0:  # 买入
                # 手数取整（100股为单位）
                shares_to_buy = (delta / ep // 100) * 100
                if shares_to_buy < 100:
                    continue
                buy_amount = shares_to_buy * ep
                cost = calc_cost(buy_amount, is_sell=False)
                if self.cash < buy_amount + cost:
                    shares_to_buy = ((self.cash * 0.95 / ep) // 100) * 100
                    if shares_to_buy < 100:
                        continue
                    buy_amount = shares_to_buy * ep
                    cost = calc_cost(buy_amount, is_sell=False)
                self.cash -= (buy_amount + cost)
                self.total_cost_paid += cost
                self.positions[ts_code] = current_shares + shares_to_buy
                self.cost_basis[ts_code] = (
                    (current_amount + buy_amount) / (current_shares + shares_to_buy)
                    if current_shares + shares_to_buy > 0 else ep
                )
                trades.append({"date": date, "ts_code": ts_code, "action": "buy",
                               "shares": shares_to_buy, "price": ep,
                               "amount": buy_amount, "cost": cost})
            else:  # 部分减仓
                shares_to_sell = (-delta / ep // 100) * 100
                if shares_to_sell < 100 or shares_to_sell > current_shares:
                    continue
                sell_amount = shares_to_sell * ep
                cost = calc_cost(sell_amount, is_sell=True)
                self.cash += sell_amount - cost
                self.total_cost_paid += cost
                self.positions[ts_code] -= shares_to_sell
                if self.positions[ts_code] <= 0:
                    del self.positions[ts_code]
                    if ts_code in self.cost_basis:
                        del self.cost_basis[ts_code]
                trades.append({"date": date, "ts_code": ts_code, "action": "sell",
                               "shares": shares_to_sell, "price": ep,
                               "amount": sell_amount, "cost": cost})

        return trades


# ─── 6. 主回测流程 ────────────────────────────────────────────────────────────

def run_backtest(signals_df: pd.DataFrame, price_df: pd.DataFrame,
                 trade_dates: List[str], bench_df: pd.DataFrame) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    """
    运行优化执行逻辑的回测

    Returns:
        (performance_df, metrics_dict, trade_log_df)
    """
    # 建立价格索引
    price_pivot = price_df.pivot_table(index="trade_date", columns="ts_code", values="close")
    high_pivot  = price_df.pivot_table(index="trade_date", columns="ts_code", values="high")
    low_pivot   = price_df.pivot_table(index="trade_date", columns="ts_code", values="low")
    pct_pivot   = price_df.pivot_table(index="trade_date", columns="ts_code", values="pct_chg")

    # 基准
    bench_dict = dict(zip(bench_df["trade_date"], bench_df["pct_chg"].astype(float) / 100))

    portfolio = Portfolio(INITIAL_CAP)
    portfolio._mark_prices = {}

    performance = []
    all_trades = []

    bench_nav = INITIAL_CAP
    prev_value = INITIAL_CAP

    signals_by_date = {}
    for _, row in signals_df.iterrows():
        dt = str(row["trade_date"])
        if dt not in signals_by_date:
            signals_by_date[dt] = []
        signals_by_date[dt].append(row["ts_code"])

    # 调仓日 = 信号日期中每周仅取首日（避免过度调仓）
    # 原始回测逻辑：每周只调仓一次，取当周第一个有信号的交易日
    raw_signal_dates = sorted(signals_by_date.keys())
    signal_dates_set = set()
    last_rebal = None
    MIN_REBAL_INTERVAL = 4  # 至少间隔4个交易日才能再次调仓
    trade_date_set = set(trade_dates)
    trade_date_list = sorted(trade_date_set)
    date_to_idx = {d: i for i, d in enumerate(trade_date_list)}
    for sd in raw_signal_dates:
        if last_rebal is None:
            signal_dates_set.add(sd)
            last_rebal = sd
        else:
            last_idx = date_to_idx.get(last_rebal, 0)
            curr_idx = date_to_idx.get(sd, 0)
            if curr_idx - last_idx >= MIN_REBAL_INTERVAL:
                signal_dates_set.add(sd)
                last_rebal = sd

    for i, date in enumerate(trade_dates):
        # 当日收盘价（估值用）
        mark_prices = {}
        if date in price_pivot.index:
            row = price_pivot.loc[date].dropna()
            mark_prices = row.to_dict()

        # 更新持仓估值
        portfolio.mark_to_market(mark_prices)

        # 调仓日 = 有信号的日期（不限于周一）
        if date in signal_dates_set:
            # 获取T+1执行价格
            next_date = trade_dates[i+1] if i+1 < len(trade_dates) else date
            exec_prices = {}
            if next_date in high_pivot.index and next_date in low_pivot.index:
                h = high_pivot.loc[next_date].dropna()
                l = low_pivot.loc[next_date].dropna()
                common = h.index.intersection(l.index)
                for ts in common:
                    exec_prices[ts] = (float(h[ts]) + float(l[ts])) / 2
            else:
                exec_prices = mark_prices.copy()

            # 涨跌停检测（当日）
            limit_up_stocks = set()
            limit_down_stocks = set()
            if date in pct_pivot.index:
                pct_row = pct_pivot.loc[date].dropna()
                for ts, pct in pct_row.items():
                    if float(pct) >= 9.9:
                        limit_up_stocks.add(ts)
                    elif float(pct) <= -9.9:
                        limit_down_stocks.add(ts)

            # 获取信号（当日排名前TOP_N）
            target_stocks = signals_by_date.get(date, [])[:TOP_N]

            if target_stocks and exec_prices:
                trades = portfolio.rebalance(
                    target_stocks=target_stocks,
                    exec_prices=exec_prices,
                    mark_prices=mark_prices,
                    limit_up_stocks=limit_up_stocks,
                    limit_down_stocks=limit_down_stocks,
                    date=date,
                )
                all_trades.extend(trades)

                limit_msg = ""
                if limit_up_stocks:
                    limit_msg = f" [涨停过滤: {len(limit_up_stocks & set(target_stocks))}只]"
                print(f"  [{date}] 调仓 → {len(target_stocks)}只信号, {len(trades)}笔成交{limit_msg}")

        curr_value = portfolio.total_value
        daily_ret = (curr_value - prev_value) / prev_value if prev_value > 0 else 0.0
        bench_ret = bench_dict.get(date, 0.0)
        bench_nav *= (1 + bench_ret)

        performance.append({
            "date": date,
            "portfolio_value": curr_value,
            "cash": portfolio.cash,
            "daily_return": daily_ret,
            "trade_date": date,
            "bench_return": bench_ret,
            "bench_nav": bench_nav,
            "month": date[:6],
        })

        prev_value = curr_value

    perf_df = pd.DataFrame(performance)
    perf_df["date"] = pd.to_datetime(perf_df["date"])
    perf_df["nav"] = perf_df["portfolio_value"] / INITIAL_CAP

    # 计算绩效指标
    returns = perf_df["daily_return"].values
    nav_arr = perf_df["nav"].values

    total_return = nav_arr[-1] - 1
    n_days = len(returns)
    n_years = n_days / 252
    ann_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

    valid_ret = pd.Series(returns).dropna()
    ann_vol = float(valid_ret.std() * np.sqrt(252))
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0

    downside = valid_ret[valid_ret < 0]
    downside_std = float(downside.std() * np.sqrt(252))
    sortino = ann_return / downside_std if downside_std > 0 else 0

    running_max = np.maximum.accumulate(nav_arr)
    dd_arr = (nav_arr - running_max) / running_max
    max_dd = float(dd_arr.min())
    calmar = ann_return / abs(max_dd) if max_dd < 0 else 0

    bench_total = perf_df["bench_nav"].iloc[-1] / INITIAL_CAP - 1
    bench_ann = (1 + bench_total) ** (1 / n_years) - 1 if n_years > 0 else 0

    # Beta & Alpha
    bench_rets = perf_df["bench_return"].values
    cov_mat = np.cov(returns[1:], bench_rets[1:])
    beta = cov_mat[0, 1] / cov_mat[1, 1] if cov_mat[1, 1] > 0 else 1.0
    alpha_ann = ann_return - beta * bench_ann

    # IR
    excess = valid_ret - pd.Series(perf_df["bench_return"].values)
    ir = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0

    win_rate = float((valid_ret > 0).mean())

    # Monthly returns
    monthly = perf_df.groupby("month").apply(
        lambda g: (1 + g["daily_return"]).prod() - 1
    ).reset_index()
    monthly.columns = ["month", "return"]

    metrics = {
        "total_return": total_return,
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "information_ratio": ir,
        "beta": beta,
        "alpha_ann": alpha_ann,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "best_month": float(monthly["return"].max()),
        "worst_month": float(monthly["return"].min()),
        "monthly_win_rate": float((monthly["return"] > 0).mean()),
        "bench_total_return": bench_total,
        "bench_ann_return": bench_ann,
        "final_value": float(perf_df["portfolio_value"].iloc[-1]),
        "initial_capital": INITIAL_CAP,
        "total_cost_paid": portfolio.total_cost_paid,
    }

    trade_log_df = pd.DataFrame(all_trades)
    return perf_df, metrics, monthly, trade_log_df


# ─── 7. 图表生成 ─────────────────────────────────────────────────────────────

def generate_comparison_chart(
    old_perf: pd.DataFrame,
    new_perf: pd.DataFrame,
    old_metrics: pd.Series,
    new_metrics: dict,
    old_monthly: pd.DataFrame,
    new_monthly: pd.DataFrame,
    ic_df: pd.DataFrame,
    font_name: str,
):
    """生成优化前后对比图"""
    fig = plt.figure(figsize=(18, 26), facecolor=DARK_BG)
    fig.patch.set_facecolor(DARK_BG)

    gs = gridspec.GridSpec(
        5, 2, figure=fig,
        height_ratios=[2.5, 2, 2, 2, 1.8],
        hspace=0.48, wspace=0.3,
        left=0.07, right=0.95, top=0.94, bottom=0.04,
    )

    fig.suptitle(
        "优化前后回测对比  |  沪深300  |  2025.01 - 2026.03",
        fontsize=18, color=TEXT, fontweight="bold", y=0.97,
    )

    dates_old = pd.to_datetime(old_perf["date"])
    nav_old   = old_perf["nav"].values
    dates_new = pd.to_datetime(new_perf["date"])
    nav_new   = new_perf["nav"].values

    bench_old = old_perf["bench_nav"].values / old_perf["bench_nav"].iloc[0]
    bench_new = new_perf["bench_nav"].values / INITIAL_CAP

    # ── 子图1: 净值对比 ─────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    _apply_dark(ax1)
    ax1.plot(dates_old, nav_old, color=ORANGE, linewidth=2, alpha=0.7, label="优化前 (Phase3)")
    ax1.plot(dates_new, nav_new, color=CYAN, linewidth=2, label="优化后 (Phase5)")
    ax1.plot(dates_new, bench_new, color="#7f8c8d", linewidth=1.2, linestyle="--", label="沪深300 基准")
    ax1.set_title("净值走势对比", fontsize=13)
    ax1.set_ylabel("NAV", fontsize=11)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # 终值标注
    ax1.annotate(f"优化前: {nav_old[-1]:.2f}x\n(+{(nav_old[-1]-1)*100:.1f}%)",
        xy=(dates_old.iloc[-1], nav_old[-1]), xytext=(-110, -30),
        textcoords="offset points", color=ORANGE, fontsize=9,
        arrowprops=dict(arrowstyle="->", color=ORANGE, lw=0.8))
    ax1.annotate(f"优化后: {nav_new[-1]:.2f}x\n(+{(nav_new[-1]-1)*100:.1f}%)",
        xy=(dates_new.iloc[-1], nav_new[-1]), xytext=(-110, 10),
        textcoords="offset points", color=CYAN, fontsize=9,
        arrowprops=dict(arrowstyle="->", color=CYAN, lw=0.8))
    ax1.annotate(f"HS300: {bench_new[-1]:.2f}x\n(+{(bench_new[-1]-1)*100:.1f}%)",
        xy=(dates_new.iloc[-1], bench_new[-1]), xytext=(-110, 10),
        textcoords="offset points", color="#7f8c8d", fontsize=9,
        arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=0.8))
    ax1.legend(fontsize=9, loc="upper left", facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图2: 回撤对比 ──────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, :])
    _apply_dark(ax2)
    dd_old = (nav_old - np.maximum.accumulate(nav_old)) / np.maximum.accumulate(nav_old) * 100
    dd_new = (nav_new - np.maximum.accumulate(nav_new)) / np.maximum.accumulate(nav_new) * 100
    ax2.fill_between(dates_old, dd_old, 0, alpha=0.35, color=ORANGE, label="优化前")
    ax2.fill_between(dates_new, dd_new, 0, alpha=0.5, color=RED_FILL, label="优化后")
    ax2.plot(dates_old, dd_old, color=ORANGE, linewidth=0.8)
    ax2.plot(dates_new, dd_new, color=RED_FILL, linewidth=0.8)
    max_dd_old_idx = np.argmin(dd_old)
    max_dd_new_idx = np.argmin(dd_new)
    ax2.annotate(f"旧MaxDD: {dd_old[max_dd_old_idx]:.1f}%",
        xy=(dates_old.iloc[max_dd_old_idx], dd_old[max_dd_old_idx]),
        xytext=(20, -15), textcoords="offset points",
        color=ORANGE, fontsize=8, arrowprops=dict(arrowstyle="->", color=ORANGE, lw=0.8))
    ax2.annotate(f"新MaxDD: {dd_new[max_dd_new_idx]:.1f}%",
        xy=(dates_new.iloc[max_dd_new_idx], dd_new[max_dd_new_idx]),
        xytext=(20, -28), textcoords="offset points",
        color=RED_FILL, fontsize=8, arrowprops=dict(arrowstyle="->", color=RED_FILL, lw=0.8))
    ax2.axhline(-20, color=GOLD, linewidth=0.8, linestyle="--", alpha=0.7, label="-20% 警戒线")
    ax2.set_title("策略回撤对比", fontsize=13)
    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax2.legend(fontsize=9, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图3a: 优化前月度收益热力图 ──────────────────────────────────────────
    for ax_idx, (monthly_df, title, subplot) in enumerate([
        (old_monthly, "优化前月度收益 (%)", gs[2, 0]),
        (new_monthly, "优化后月度收益 (%)", gs[2, 1]),
    ]):
        ax = fig.add_subplot(subplot)
        _apply_dark(ax)
        monthly_df = monthly_df.copy()
        monthly_df["year"] = monthly_df["month"].astype(str).str[:4].astype(int)
        monthly_df["mth"]  = monthly_df["month"].astype(str).str[4:6].astype(int)
        years = sorted(monthly_df["year"].unique())
        data_mat = np.full((len(years), 12), np.nan)
        for _, row in monthly_df.iterrows():
            yi = years.index(row["year"])
            mi = int(row["mth"]) - 1
            data_mat[yi, mi] = row["return"] * 100
        norm = TwoSlopeNorm(vmin=-15, vcenter=0, vmax=20)
        im = ax.imshow(data_mat, aspect="auto", cmap="RdYlGn", norm=norm)
        ax.set_xticks(range(12))
        ax.set_xticklabels(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
                           fontsize=7, color=TEXT)
        ax.set_yticks(range(len(years)))
        ax.set_yticklabels([str(y) for y in years], fontsize=8, color=TEXT)
        for yi in range(len(years)):
            for mi in range(12):
                val = data_mat[yi, mi]
                if not np.isnan(val):
                    ax.text(mi, yi, f"{val:.1f}%", ha="center", va="center",
                           fontsize=7, color="white" if abs(val) > 8 else "black", fontweight="bold")
        ax.set_title(title, fontsize=11)
        cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.ax.tick_params(colors=TEXT, labelsize=7)

    # ── 子图4a: 因子ICIR Top15 ────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[3, 0])
    _apply_dark(ax4)
    if not ic_df.empty:
        top15 = ic_df.nlargest(15, "icir")
        colors = [GREEN if v >= 0.5 else ("#e67e22" if v >= 0.2 else "#7f8c8d")
                  for v in top15["icir"].values]
        ax4.barh(range(len(top15)), top15["icir"].values, color=colors)
        ax4.set_yticks(range(len(top15)))
        ax4.set_yticklabels(top15.index.tolist(), fontsize=7)
        ax4.axvline(0.5, color=GOLD, linestyle="--", linewidth=0.8, label="ICIR=0.5")
        ax4.set_title("因子滚动ICIR (Top15)", fontsize=11)
        ax4.set_xlabel("Rolling ICIR", fontsize=9)
        ax4.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图4b: 绩效指标对比表 ─────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[3, 1])
    _apply_dark(ax5)
    ax5.axis("off")

    nm = new_metrics
    om = old_metrics

    def fmt_pct(v):
        return f"{v*100:+.1f}%"
    def fmt_f(v):
        return f"{v:.2f}"

    rows_data = [
        ("总收益率",   fmt_pct(nm["total_return"]),    fmt_pct(float(om.get("total_return",0))),   False),
        ("年化收益率",  fmt_pct(nm["annualized_return"]), fmt_pct(float(om.get("annualized_return",0))), False),
        ("年化波动率",  f'{nm["annualized_vol"]*100:.1f}%', f'{float(om.get("annualized_vol",0))*100:.1f}%', True),
        ("夏普比率",   fmt_f(nm["sharpe"]),             fmt_f(float(om.get("sharpe",0))),           False),
        ("索提诺比率",  fmt_f(nm["sortino"]),            fmt_f(float(om.get("sortino",0))),          False),
        ("最大回撤",   fmt_pct(nm["max_drawdown"]),     fmt_pct(float(om.get("max_drawdown",0))),   True),
        ("信息比率",   fmt_f(nm["information_ratio"]),  fmt_f(float(om.get("information_ratio",0))), False),
        ("卡玛比率",   fmt_f(nm["calmar"]),             fmt_f(float(om.get("calmar",0))),           False),
        ("胜率",      f'{nm["win_rate"]*100:.1f}%',    f'{float(om.get("win_rate",0))*100:.1f}%',   False),
        ("Alpha(年化)",fmt_pct(nm["alpha_ann"]),        fmt_pct(float(om.get("alpha_ann",0))),      False),
    ]

    col_labels = ["指标", "优化后", "优化前"]
    col_widths = [0.45, 0.275, 0.275]
    header_y = 0.97
    row_h = 0.085

    x = 0.0
    for col, w in zip(col_labels, col_widths):
        ax5.text(x + w/2, header_y, col, ha="center", va="top",
                fontsize=9, color=DARK_BG, fontweight="bold",
                transform=ax5.transAxes,
                bbox=dict(boxstyle="round,pad=0.2", fc="#4a9eca", ec="none"))
        x += w

    for i, (label, new_val, old_val, lower_better) in enumerate(rows_data):
        y = header_y - (i + 1) * row_h
        bg = PANEL_BG if i % 2 == 0 else "#1c2333"
        ax5.axhspan(y - row_h * 0.45, y + row_h * 0.5, color=bg, transform=ax5.transAxes, zorder=0)
        ax5.text(0.02, y, label, ha="left", va="center", fontsize=8.5, color=TEXT, transform=ax5.transAxes)

        try:
            new_num = float(new_val.replace("%","").replace("+",""))
            old_num = float(old_val.replace("%","").replace("+",""))
            if lower_better:
                new_color = GREEN if new_num < old_num else RED_FILL
            else:
                new_color = GREEN if new_num > old_num else RED_FILL
        except:
            new_color = TEXT

        ax5.text(0.50, y, new_val, ha="center", va="center", fontsize=8.5, color=new_color, transform=ax5.transAxes)
        ax5.text(0.85, y, old_val, ha="center", va="center", fontsize=8.5, color=TEXT, transform=ax5.transAxes)

    ax5.set_title("绩效指标对比（优化前 vs 优化后）", fontsize=11)
    ax5.set_xlim(0, 1)
    ax5.set_ylim(0, 1)

    # ── 子图5: 关键指标变化总结 ───────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[4, :])
    _apply_dark(ax6)
    ax6.axis("off")

    summary_text = (
        f"【优化内容】  "
        f"① T+1日(高+低)/2成交价    "
        f"② 涨跌停过滤    "
        f"③ 滑点0.1% + 量化冲击    "
        f"④ 印花税0.1% + 佣金0.025%    "
        f"⑤ 因子 63日滚动ICIR加权\n"
        f"【关键变化】  "
        f"总收益: {float(om.get('total_return',0))*100:.1f}% → {nm['total_return']*100:.1f}%  |  "
        f"夏普: {float(om.get('sharpe',0)):.2f} → {nm['sharpe']:.2f}  |  "
        f"最大回撤: {float(om.get('max_drawdown',0))*100:.1f}% → {nm['max_drawdown']*100:.1f}%  |  "
        f"年化Alpha: {float(om.get('alpha_ann',0))*100:.1f}% → {nm['alpha_ann']*100:.1f}%"
    )
    ax6.text(0.5, 0.6, summary_text, ha="center", va="center",
             fontsize=10, color=TEXT, transform=ax6.transAxes,
             bbox=dict(boxstyle="round,pad=0.5", fc=PANEL_BG, ec=GOLD, alpha=0.9))
    ax6.set_title("优化效果总结", fontsize=12)

    out_path = OUTPUT / "phase5_backtest_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"[OK] 对比图已生成: {out_path}")


def generate_factor_analysis_chart(ic_df: pd.DataFrame, rolling_icir_df: pd.DataFrame,
                                    font_name: str):
    """生成因子分析专项图"""
    fig = plt.figure(figsize=(18, 12), facecolor=DARK_BG)
    fig.patch.set_facecolor(DARK_BG)

    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35,
                           left=0.08, right=0.97, top=0.92, bottom=0.07)
    fig.suptitle("因子有效性分析（滚动ICIR）| 2025.01 - 2026.03",
                fontsize=16, color=TEXT, fontweight="bold", y=0.97)

    # 1. 全因子 ICIR 排名
    ax1 = fig.add_subplot(gs[0, 0])
    _apply_dark(ax1)
    top20 = ic_df.nlargest(20, "icir")
    bar_colors = [GREEN if v >= 0.5 else ("#e67e22" if v >= 0.2 else "#7f8c8d")
                  for v in top20["icir"].values]
    ax1.barh(range(len(top20)), top20["icir"].values, color=bar_colors)
    ax1.set_yticks(range(len(top20)))
    ax1.set_yticklabels(top20.index.tolist(), fontsize=7)
    ax1.axvline(0.5, color=GOLD, linestyle="--", linewidth=0.8, label="ICIR=0.5")
    ax1.set_title("全因子滚动ICIR排名 (Top20)", fontsize=12)
    ax1.set_xlabel("63日滚动ICIR", fontsize=10)
    ax1.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # 2. Top因子 IC 时序（滚动）
    ax2 = fig.add_subplot(gs[0, 1])
    _apply_dark(ax2)
    if not rolling_icir_df.empty:
        top5_factors = ic_df.nlargest(5, "icir").index.tolist()
        colors_used = [CYAN, ORANGE, GREEN, GOLD, PURPLE]
        for fi, (factor, color) in enumerate(zip(top5_factors, colors_used)):
            if factor in rolling_icir_df.columns:
                s = rolling_icir_df[factor].dropna()
                if len(s) > 0:
                    ax2.plot(s.index, s.values, color=color, linewidth=1.2, label=factor)
        ax2.axhline(0.5, color=GOLD, linestyle="--", linewidth=0.8, alpha=0.7)
        ax2.axhline(0, color="#7f8c8d", linewidth=0.5, alpha=0.5)
        ax2.set_title("Top5因子 63日滚动ICIR时序", fontsize=12)
        ax2.set_ylabel("Rolling ICIR", fontsize=10)
        ax2.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # 3. IC均值 vs ICIR 散点图
    ax3 = fig.add_subplot(gs[1, 0])
    _apply_dark(ax3)
    if "ic_mean" in ic_df.columns and "icir" in ic_df.columns:
        ic_mean_vals = ic_df["ic_mean"].values
        icir_vals = ic_df["icir"].values
        scatter = ax3.scatter(ic_mean_vals, icir_vals, c=icir_vals, cmap="RdYlGn",
                             vmin=-1, vmax=2, alpha=0.7, s=50)
        ax3.axhline(0.5, color=GOLD, linestyle="--", linewidth=0.8, alpha=0.7)
        ax3.axvline(0, color="#7f8c8d", linewidth=0.5, alpha=0.5)
        # 标注Top5
        for f in ic_df.nlargest(5, "icir").index:
            if f in ic_df.index:
                row = ic_df.loc[f]
                ax3.annotate(f, (row["ic_mean"], row["icir"]), fontsize=6,
                            color=TEXT, textcoords="offset points", xytext=(3, 3))
        ax3.set_title("IC均值 vs 滚动ICIR", fontsize=12)
        ax3.set_xlabel("IC均值", fontsize=10)
        ax3.set_ylabel("滚动ICIR", fontsize=10)
        plt.colorbar(scatter, ax=ax3, fraction=0.03).ax.tick_params(colors=TEXT, labelsize=7)

    # 4. 有效因子统计
    ax4 = fig.add_subplot(gs[1, 1])
    _apply_dark(ax4)
    ax4.axis("off")
    valid_05 = (ic_df["icir"] >= 0.5).sum()
    valid_02 = ((ic_df["icir"] >= 0.2) & (ic_df["icir"] < 0.5)).sum()
    invalid  = (ic_df["icir"] < 0.2).sum()
    negative = (ic_df["icir"] < 0).sum()

    stats_text = "\n".join([
        f"因子总数:  {len(ic_df)}",
        f"  ICIR≥0.5 (强有效): {valid_05}",
        f"  0.2≤ICIR<0.5 (弱有效): {valid_02}",
        f"  ICIR<0.2 (无效): {invalid - negative}",
        f"  ICIR<0 (负向): {negative}",
        f"",
        f"Top3因子 (滚动ICIR):",
    ])
    for f in ic_df.nlargest(3, "icir").index:
        row = ic_df.loc[f]
        stats_text += f"\n  {f}: ICIR={row['icir']:.3f}"

    ax4.text(0.5, 0.5, stats_text, ha="center", va="center",
            fontsize=10, color=TEXT, transform=ax4.transAxes,
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.6", fc=PANEL_BG, ec=CYAN, alpha=0.9))
    ax4.set_title("因子有效性统计（63日滚动ICIR）", fontsize=12)

    out_path = OUTPUT / "phase5_factor_analysis.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"[OK] 因子分析图已生成: {out_path}")


# ─── 8. 主入口 ────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Phase 5: 优化执行逻辑回测验证")
    print("=" * 70)

    font_name = setup_chinese_font()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # ── Step 1: 加载旧回测数据（Phase3对比基线） ──────────────────────────────
    print("\n[1/6] 加载旧回测数据（Phase3对比基线）...")
    old_perf = pd.read_csv(OUTPUT / "phase3_performance.csv")
    old_perf["date"] = pd.to_datetime(old_perf["date"].astype(str), format="%Y%m%d")
    old_perf["nav"] = old_perf["portfolio_value"] / old_perf["portfolio_value"].iloc[0]
    old_metrics = pd.read_csv(OUTPUT / "phase3_metrics.csv", index_col=0, header=None)
    old_metrics.columns = ["value"]
    old_metrics["value"] = pd.to_numeric(old_metrics["value"], errors="coerce")
    old_monthly = pd.read_csv(OUTPUT / "phase3_monthly_returns.csv")
    old_monthly["month"] = old_monthly["month"].astype(str)

    # ── Step 2: 获取交易日和HS300成分股 ──────────────────────────────────────
    print("\n[2/6] 获取交易日和HS300成分股...")
    trade_dates = get_trade_dates(START_DATE, END_DATE)
    print(f"  交易日: {len(trade_dates)} 天 ({trade_dates[0]} ~ {trade_dates[-1]})")

    hs300_stocks = get_hs300_stocks(trade_dates[0])
    print(f"  HS300成分股: {len(hs300_stocks)} 只")

    # ── Step 3: 加载市场数据 ──────────────────────────────────────────────────
    print("\n[3/6] 加载市场数据（OHLC + 涨跌幅）...")
    price_df = get_daily_data_batch(hs300_stocks, START_DATE, END_DATE)
    print(f"  日线数据: {len(price_df)} 条")

    bench_df = get_hs300_daily(START_DATE, END_DATE)
    print(f"  HS300基准: {len(bench_df)} 天")

    # ── Step 4: 因子IC分析（63日滚动ICIR） ────────────────────────────────────
    print("\n[4/6] 因子IC分析（63日滚动ICIR）...")
    factors_df = get_factors_batch(hs300_stocks, START_DATE, END_DATE)
    print(f"  预计算因子: {len(factors_df)} 条, {len(factors_df.columns)-2} 个因子")

    rolling_icir_dict = compute_rolling_icir(
        factors_df, price_df, trade_dates, forward_days=5, rolling_window=63
    )
    ic_df = pd.DataFrame.from_dict(rolling_icir_dict, orient="index", columns=["icir"])

    # 也计算 ic_mean 供散点图使用
    ic_mean_dict = {}
    price_pivot_tmp = price_df.pivot_table(index="trade_date", columns="ts_code", values="close")
    date_idx_tmp = {d: i for i, d in enumerate(sorted(price_pivot_tmp.index))}
    all_dates_tmp = sorted(price_pivot_tmp.index)
    factor_cols_tmp = [c for c in factors_df.columns if c not in ("trade_date", "ts_code")]
    sample_dates = [d for d in trade_dates[:100] if d in price_pivot_tmp.index]  # 快速估算
    from scipy.stats import spearmanr as _spearmanr
    for col in factor_cols_tmp:
        ic_vals = []
        for date in sample_dates:
            idx = date_idx_tmp.get(date)
            if idx is None or idx + 5 >= len(all_dates_tmp):
                continue
            fut_date = all_dates_tmp[idx + 5]
            cp = price_pivot_tmp.loc[date].dropna()
            fp = price_pivot_tmp.loc[fut_date].dropna()
            common = cp.index.intersection(fp.index)
            if len(common) < 30:
                continue
            fwd = fp[common] / cp[common] - 1
            day_f = factors_df[(factors_df["trade_date"] == date)].set_index("ts_code")
            if col not in day_f.columns:
                continue
            fv = day_f[col].dropna().reindex(common).dropna()
            rv = fwd.reindex(fv.index).dropna()
            if len(rv) < 10:
                continue
            ic_val, _ = _spearmanr(fv.loc[rv.index], rv)
            if not np.isnan(ic_val):
                ic_vals.append(ic_val)
        ic_mean_dict[col] = np.mean(ic_vals) if ic_vals else 0.0

    ic_df["ic_mean"] = pd.Series(ic_mean_dict)
    ic_df = ic_df.sort_values("icir", ascending=False)

    # 保存IC分析结果
    ic_df.to_csv(OUTPUT / "phase5_ic_results.csv")
    print(f"  有效因子 (ICIR≥0.5): {(ic_df['icir'] >= 0.5).sum()} 个")
    print(f"  Top3 因子: {ic_df.head(3).index.tolist()}")

    # 滚动ICIR时序（用于图表）
    rolling_icir_series_dict: Dict[str, pd.Series] = {}
    price_pivot_r = price_df.pivot_table(index="trade_date", columns="ts_code", values="close")
    all_dates_r = sorted(price_pivot_r.index)
    date_idx_r = {d: i for i, d in enumerate(all_dates_r)}
    ic_by_date_all: Dict[str, List] = {c: [] for c in factor_cols_tmp}
    ic_date_list: List[str] = []
    for date in trade_dates:
        idx = date_idx_r.get(date)
        if idx is None or idx + 5 >= len(all_dates_r):
            continue
        fut_date = all_dates_r[idx + 5]
        cp = price_pivot_r.loc[date].dropna()
        fp = price_pivot_r.loc[fut_date].dropna()
        common = cp.index.intersection(fp.index)
        if len(common) < 30:
            continue
        fwd = fp[common] / cp[common] - 1
        day_f = factors_df[factors_df["trade_date"] == date].set_index("ts_code")
        ic_date_list.append(date)
        for col in factor_cols_tmp:
            if col not in day_f.columns:
                ic_by_date_all[col].append(np.nan)
                continue
            fv = day_f[col].dropna().reindex(common).dropna()
            rv = fwd.reindex(fv.index).dropna()
            if len(rv) < 10:
                ic_by_date_all[col].append(np.nan)
                continue
            ic_val, _ = _spearmanr(fv.loc[rv.index], rv)
            ic_by_date_all[col].append(np.nan if np.isnan(ic_val) else ic_val)

    ic_dates_idx = pd.to_datetime(ic_date_list, format="%Y%m%d")
    for col in ic_df.head(10).index.tolist():
        s = pd.Series(ic_by_date_all.get(col, []), index=ic_dates_idx, dtype=float)
        roll = s.rolling(63, min_periods=20).mean() / s.rolling(63, min_periods=20).std().replace(0, np.nan)
        rolling_icir_series_dict[col] = roll.dropna()
    rolling_icir_df = pd.DataFrame(rolling_icir_series_dict)

    # ── Step 5: 信号生成 & 新回测 ─────────────────────────────────────────────
    print("\n[5/6] 信号生成 & 优化回测执行...")

    # 优先使用已有phase2信号，若无则重新生成
    phase2_path = OUTPUT / "phase2_signals.csv"
    if phase2_path.exists():
        print("  加载现有 phase2 信号...")
        signals_df = pd.read_csv(phase2_path)
        signals_df["trade_date"] = signals_df["trade_date"].astype(str)
    else:
        print("  重新生成信号（使用滚动ICIR加权）...")
        valid_factors = {k: v for k, v in rolling_icir_dict.items() if abs(v) >= 0.2}
        signals_df = generate_signals(factors_df, valid_factors, trade_dates, top_n=TOP_N)
        signals_df.to_csv(OUTPUT / "phase5_signals.csv", index=False)

    new_perf, new_metrics, new_monthly, trade_log = run_backtest(
        signals_df, price_df, trade_dates, bench_df
    )

    # 保存结果
    new_perf_out = new_perf.copy()
    new_perf_out["date"] = new_perf_out["date"].dt.strftime("%Y%m%d")
    new_perf_out.to_csv(OUTPUT / "phase5_performance.csv", index=False)

    metrics_series = pd.Series(new_metrics)
    metrics_series.to_csv(OUTPUT / "phase5_metrics.csv", header=False)

    new_monthly.to_csv(OUTPUT / "phase5_monthly_returns.csv", index=False)

    if not trade_log.empty:
        trade_log.to_csv(OUTPUT / "phase5_trade_log.csv", index=False)

    print(f"\n  [结果] 总收益: {new_metrics['total_return']*100:.1f}%")
    print(f"  [结果] 年化: {new_metrics['annualized_return']*100:.1f}%")
    print(f"  [结果] 夏普: {new_metrics['sharpe']:.2f}")
    print(f"  [结果] 最大回撤: {new_metrics['max_drawdown']*100:.1f}%")
    print(f"  [结果] 总交易成本: {new_metrics['total_cost_paid']:,.0f} 元")

    # ── Step 6: 生成图表 ──────────────────────────────────────────────────────
    print("\n[6/6] 生成对比图表...")

    generate_comparison_chart(
        old_perf=old_perf,
        new_perf=new_perf,
        old_metrics=old_metrics["value"],
        new_metrics=new_metrics,
        old_monthly=old_monthly,
        new_monthly=new_monthly,
        ic_df=ic_df,
        font_name=font_name,
    )

    generate_factor_analysis_chart(
        ic_df=ic_df,
        rolling_icir_df=rolling_icir_df,
        font_name=font_name,
    )

    # ── 打印对比摘要 ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("关键指标对比 (Phase3 旧版 vs Phase5 优化版)")
    print("=" * 70)
    om = old_metrics["value"]
    metrics_to_compare = [
        ("总收益率",       "total_return",       True,  "%"),
        ("年化收益率",     "annualized_return",   True,  "%"),
        ("年化波动率",     "annualized_vol",      False, "%"),
        ("夏普比率",       "sharpe",              True,  "x"),
        ("最大回撤",       "max_drawdown",        False, "%"),
        ("卡玛比率",       "calmar",              True,  "x"),
        ("信息比率",       "information_ratio",   True,  "x"),
        ("胜率",           "win_rate",            True,  "%"),
        ("Alpha(年化)",    "alpha_ann",           True,  "%"),
    ]
    for label, key, higher_better, unit in metrics_to_compare:
        old_v = float(om.get(key, 0))
        new_v = new_metrics.get(key, 0)
        if unit == "%":
            old_s = f"{old_v*100:+.1f}%"
            new_s = f"{new_v*100:+.1f}%"
        else:
            old_s = f"{old_v:.2f}"
            new_s = f"{new_v:.2f}"
        improved = (new_v > old_v) == higher_better or (new_v > old_v and higher_better) or (new_v < old_v and not higher_better)
        arrow = "↑" if (new_v > old_v and higher_better) or (new_v < old_v and not higher_better) else "↓"
        print(f"  {label:<12} {old_s:>10} → {new_s:>10}  {arrow}")

    print("=" * 70)
    print("\n[完成] 所有输出文件已保存到 output/ 目录")


if __name__ == "__main__":
    main()
