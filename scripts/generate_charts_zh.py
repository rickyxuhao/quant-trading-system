"""
生成中文图表 - 回测报告与因子分析
修复中文字体显示问题，重新生成图表到 output/ 目录
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

# ─────────────────────────────────────────
# 0. 中文字体配置
# ─────────────────────────────────────────
def setup_chinese_font() -> str:
    # 直接注册系统中文字体文件（绕过 matplotlib 字体缓存）
    font_paths = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in font_paths:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            font_name = prop.get_name()
            plt.rcParams["font.family"] = font_name
            plt.rcParams["axes.unicode_minus"] = False
            print(f"[INFO] 中文字体已注册: {font_name} ({path})")
            return font_name

    # fallback: 按名称搜索
    candidates = ["STHeiti", "Heiti TC", "Arial Unicode MS", "PingFang HK",
                  "WenQuanYi Micro Hei", "SimHei", "Microsoft YaHei"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            print(f"[INFO] 中文字体已设置: {font}")
            return font
    plt.rcParams["axes.unicode_minus"] = False
    print("[WARN] 未找到中文字体，使用默认字体")
    return "default"


# ─────────────────────────────────────────
# 1. 加载数据
# ─────────────────────────────────────────
ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"

def load_data():
    metrics = pd.read_csv(OUTPUT / "phase3_metrics.csv", index_col=0, header=None)
    metrics.columns = ["value"]
    metrics["value"] = pd.to_numeric(metrics["value"], errors="coerce")

    monthly = pd.read_csv(OUTPUT / "phase3_monthly_returns.csv")
    monthly["month"] = monthly["month"].astype(str)

    perf = pd.read_csv(OUTPUT / "phase3_performance.csv")
    perf["date"] = pd.to_datetime(perf["date"].astype(str), format="%Y%m%d")
    perf = perf.sort_values("date").reset_index(drop=True)
    # 归一化净值
    perf["nav"] = perf["portfolio_value"] / perf["portfolio_value"].iloc[0]

    ic = pd.read_csv(OUTPUT / "phase1_ic_results.csv", index_col=0)

    return metrics, monthly, perf, ic


# ─────────────────────────────────────────
# 2. 生成回测报告图
# ─────────────────────────────────────────
DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
CYAN     = "#00b4d8"
RED_FILL = "#c0392b"
GREEN    = "#2ecc71"
GOLD     = "#f1c40f"
TEXT     = "#e6edf3"
GRID     = "#21262d"


def _apply_dark(ax):
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.5, linestyle="--", alpha=0.7)


def generate_backtest_report(metrics, monthly, perf, ic, font_name):
    fig = plt.figure(figsize=(16, 22), facecolor=DARK_BG)
    fig.patch.set_facecolor(DARK_BG)

    gs = gridspec.GridSpec(
        4, 2, figure=fig,
        height_ratios=[2.5, 2, 2, 2],
        hspace=0.45, wspace=0.3,
        left=0.07, right=0.95, top=0.94, bottom=0.05,
    )

    # 标题
    fig.suptitle(
        "多因子截面选股策略  |  沪深300  |  2025.01 - 2026.03",
        fontsize=18, color=TEXT, fontweight="bold", y=0.97,
    )

    dates = perf["date"].values
    nav   = perf["nav"].values

    # bench_nav 归一化
    bench_start = perf["bench_nav"].iloc[0]
    bench_nav = (perf["bench_nav"] / bench_start).values

    # ── 子图1: 净值曲线 ──────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    _apply_dark(ax1)
    ax1.fill_between(dates, nav, bench_nav, where=(nav >= bench_nav),
                     alpha=0.25, color=CYAN, label="超额收益")
    ax1.fill_between(dates, nav, bench_nav, where=(nav < bench_nav),
                     alpha=0.25, color=RED_FILL)
    ax1.plot(dates, nav, color=CYAN, linewidth=1.8, label="策略 (Multi-Factor)")
    ax1.plot(dates, bench_nav, color="#e67e22", linewidth=1.2,
             linestyle="--", label="沪深300 基准")
    ax1.set_title("净值走势图 (2025.01 - 2026.03)", fontsize=13)
    ax1.set_ylabel("NAV", fontsize=11)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    # 标注终值
    final_nav = nav[-1]
    final_bench = bench_nav[-1]
    ax1.annotate(
        f"策略: {final_nav:.2f}x\n(+{(final_nav-1)*100:.1f}%)",
        xy=(dates[-1], final_nav), xytext=(-90, 10),
        textcoords="offset points", color=CYAN, fontsize=9,
        arrowprops=dict(arrowstyle="->", color=CYAN, lw=0.8),
    )
    ax1.annotate(
        f"HS300: {final_bench:.2f}x\n(+{(final_bench-1)*100:.1f}%)",
        xy=(dates[-1], final_bench), xytext=(-90, -35),
        textcoords="offset points", color="#e67e22", fontsize=9,
        arrowprops=dict(arrowstyle="->", color="#e67e22", lw=0.8),
    )
    ax1.legend(fontsize=9, loc="upper left",
               facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图2: 回撤曲线 ──────────────────────────────
    ax2 = fig.add_subplot(gs[1, :])
    _apply_dark(ax2)
    running_max = np.maximum.accumulate(nav)
    drawdown = (nav - running_max) / running_max * 100
    ax2.fill_between(dates, drawdown, 0, color=RED_FILL, alpha=0.7)
    ax2.plot(dates, drawdown, color=RED_FILL, linewidth=0.8)
    max_dd_idx = np.argmin(drawdown)
    ax2.annotate(
        f"Max DD: {drawdown[max_dd_idx]:.1f}%",
        xy=(dates[max_dd_idx], drawdown[max_dd_idx]),
        xytext=(20, -15), textcoords="offset points",
        color=GOLD, fontsize=9,
        arrowprops=dict(arrowstyle="->", color=GOLD, lw=0.8),
    )
    ax2.axhline(-20, color=GOLD, linewidth=0.8, linestyle="--", alpha=0.7,
                label="-20% 警戒线")
    ax2.set_title("策略回撤", fontsize=13)
    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax2.legend(fontsize=9, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图3: 月度收益热力图 ──────────────────────────
    ax3 = fig.add_subplot(gs[2, :])
    _apply_dark(ax3)

    monthly["year"]  = monthly["month"].str[:4].astype(int)
    monthly["mth"]   = monthly["month"].str[4:6].astype(int)
    years = sorted(monthly["year"].unique())
    months_order = list(range(1, 13))
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec"]

    data_matrix = np.full((len(years), 12), np.nan)
    for _, row in monthly.iterrows():
        yi = years.index(row["year"])
        mi = int(row["mth"]) - 1
        data_matrix[yi, mi] = row["return"] * 100

    norm = TwoSlopeNorm(vmin=-20, vcenter=0, vmax=20)
    im = ax3.imshow(data_matrix, aspect="auto", cmap="RdYlGn", norm=norm)
    ax3.set_xticks(range(12))
    ax3.set_xticklabels(month_labels, fontsize=9, color=TEXT)
    ax3.set_yticks(range(len(years)))
    ax3.set_yticklabels([str(y) for y in years], fontsize=9, color=TEXT)
    for yi in range(len(years)):
        for mi in range(12):
            val = data_matrix[yi, mi]
            if not np.isnan(val):
                ax3.text(mi, yi, f"{val:.1f}%", ha="center", va="center",
                         fontsize=8, color="white" if abs(val) > 10 else "black",
                         fontweight="bold")
    ax3.set_title("月度收益热力图 (%)", fontsize=13)
    cbar = plt.colorbar(im, ax=ax3, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(colors=TEXT, labelsize=8)
    cbar.ax.yaxis.label.set_color(TEXT)
    cbar.set_label("月收益率 (%)", color=TEXT, fontsize=9)

    # ── 子图4: 因子ICIR Top20 ─────────────────────────
    ax4 = fig.add_subplot(gs[3, 0])
    _apply_dark(ax4)
    top20 = ic.nlargest(20, "icir")
    bars = ax4.barh(range(len(top20)), top20["icir"].values,
                    color=[GREEN if v >= 0.5 else "#7f8c8d" for v in top20["icir"].values])
    ax4.set_yticks(range(len(top20)))
    ax4.set_yticklabels(top20.index.tolist(), fontsize=7)
    ax4.axvline(0.5, color=GOLD, linestyle="--", linewidth=0.8, label="ICIR=0.5")
    ax4.set_title("因子 ICIR 排名 Top 20", fontsize=12)
    ax4.set_xlabel("ICIR", fontsize=10)
    ax4.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图5: 绩效指标表格 ──────────────────────────
    ax5 = fig.add_subplot(gs[3, 1])
    _apply_dark(ax5)
    ax5.axis("off")

    m = metrics["value"]
    rows = [
        ("总收益率",    f"+{m['total_return']*100:.1f}%",    f"+{m['bench_total_return']*100:.1f}%"),
        ("年化收益率",   f"+{m['annualized_return']*100:.1f}%", f"+{m['bench_ann_return']*100:.1f}%"),
        ("年化波动率",   f"{m['annualized_vol']*100:.1f}%",   "-"),
        ("夏普比率",    f"{m['sharpe']:.2f}",                "-"),
        ("索提诺比率",   f"{m['sortino']:.2f}",               "-"),
        ("卡玛比率",    f"{m['calmar']:.2f}",                "-"),
        ("信息比率",    f"{m['information_ratio']:.2f}",     "-"),
        ("最大回撤",    f"{m['max_drawdown']*100:.1f}%",     "-"),
        ("胜率",       f"{m['win_rate']*100:.1f}%",         "-"),
        ("Beta",      f"{m['beta']:.2f}",                  "-"),
        ("Alpha(年化)", f"+{m['alpha_ann']*100:.1f}%",       "-"),
    ]

    col_labels = ["指标", "策略", "沪深300"]
    col_widths = [0.45, 0.3, 0.25]
    header_y = 0.97
    row_h = 0.077

    # 表头
    x = 0.0
    for col, w in zip(col_labels, col_widths):
        ax5.text(x + w/2, header_y, col, ha="center", va="top",
                 fontsize=9, color=DARK_BG, fontweight="bold",
                 transform=ax5.transAxes,
                 bbox=dict(boxstyle="round,pad=0.2", fc="#4a9eca", ec="none"))
        x += w

    for i, (label, strat_val, bench_val) in enumerate(rows):
        y = header_y - (i + 1) * row_h
        row_bg = PANEL_BG if i % 2 == 0 else "#1c2333"
        ax5.axhspan(y - row_h * 0.4, y + row_h * 0.5, color=row_bg,
                    transform=ax5.transAxes, zorder=0)
        ax5.text(0.02, y, label, ha="left", va="center",
                 fontsize=8.5, color=TEXT, transform=ax5.transAxes)
        color = GREEN if "+" in strat_val else (RED_FILL if strat_val.startswith("-") and "%" in strat_val else TEXT)
        ax5.text(0.47, y, strat_val, ha="center", va="center",
                 fontsize=8.5, color=color, transform=ax5.transAxes)
        ax5.text(0.85, y, bench_val, ha="center", va="center",
                 fontsize=8.5, color=TEXT, transform=ax5.transAxes)

    ax5.set_title("策略绩效指标", fontsize=12)
    ax5.set_xlim(0, 1)
    ax5.set_ylim(0, 1)

    out_path = OUTPUT / "backtest_report_zh.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"[OK] 已生成: {out_path}")


# ─────────────────────────────────────────
# 3. 生成因子分析图
# ─────────────────────────────────────────
def generate_factor_analysis(metrics, perf, ic, font_name):
    fig = plt.figure(figsize=(18, 12), facecolor=DARK_BG)
    fig.patch.set_facecolor(DARK_BG)

    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        hspace=0.4, wspace=0.35,
        left=0.07, right=0.97, top=0.92, bottom=0.07,
    )

    fig.suptitle(
        "因子分析报告  |  Factor Analysis Dashboard",
        fontsize=17, color=TEXT, fontweight="bold", y=0.96,
    )

    # ── 子图1: Top 30 因子 ICIR ──────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    _apply_dark(ax1)
    top30 = ic.nlargest(30, "icir")
    colors = [GREEN if v >= 0.5 else "#7f8c8d" for v in top30["icir"].values]
    ax1.bar(range(len(top30)), top30["icir"].values, color=colors, width=0.7)
    ax1.set_xticks(range(len(top30)))
    ax1.set_xticklabels(top30.index.tolist(), rotation=45, ha="right", fontsize=7)
    ax1.axhline(0.5, color=GOLD, linestyle="--", linewidth=1.0, label="ICIR=0.5 阈值")
    ax1.set_title("Top 30 Factors ICIR", fontsize=13)
    ax1.set_ylabel("ICIR", fontsize=11)
    ax1.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图2: IC Mean vs Std 散点图 ─────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    _apply_dark(ax2)
    sc = ax2.scatter(ic["ic_std"], ic["ic_mean"], c=ic["icir"],
                     cmap="plasma", s=60, alpha=0.8, zorder=5)
    # 标注 ICIR > 1.5 的因子
    for name, row in ic.iterrows():
        if row["icir"] > 1.5:
            ax2.annotate(name, (row["ic_std"], row["ic_mean"]),
                         fontsize=7, color=TEXT, alpha=0.9,
                         xytext=(3, 3), textcoords="offset points")
    ax2.axhline(0, color=GRID, linewidth=0.8)
    cbar = plt.colorbar(sc, ax=ax2)
    cbar.ax.tick_params(colors=TEXT, labelsize=8)
    cbar.set_label("ICIR", color=TEXT, fontsize=9)
    cbar.ax.yaxis.label.set_color(TEXT)
    ax2.set_title("IC Mean vs Std Scatter", fontsize=13)
    ax2.set_xlabel("IC Std（越小越稳定）", fontsize=10)
    ax2.set_ylabel("IC Mean（越高越有效）", fontsize=10)

    # ── 子图3: 日收益分布 ─────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    _apply_dark(ax3)
    daily_ret = perf["daily_return"].dropna() * 100
    n, bins, patches = ax3.hist(daily_ret, bins=50, color=CYAN, alpha=0.75,
                                edgecolor=DARK_BG, linewidth=0.3)
    # 正态分布拟合曲线
    mu, sigma = daily_ret.mean(), daily_ret.std()
    x_fit = np.linspace(bins[0], bins[-1], 200)
    y_fit = (n.sum() * (bins[1]-bins[0]) *
             np.exp(-0.5*((x_fit-mu)/sigma)**2) / (sigma * np.sqrt(2*np.pi)))
    ax3.plot(x_fit, y_fit, color="white", linewidth=1.5, linestyle="--", label="正态拟合")
    ax3.axvline(mu, color=GOLD, linewidth=1.2, linestyle=":", label=f"均值={mu:.2f}%")
    ax3.set_title("日收益分布", fontsize=13)
    ax3.set_xlabel("Daily Return (%)", fontsize=10)
    ax3.set_ylabel("频次", fontsize=10)
    ax3.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    # ── 子图4: 滚动60日夏普比率 ───────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    _apply_dark(ax4)
    ret = perf["daily_return"].fillna(0)
    rolling_sharpe = (ret.rolling(60).mean() / ret.rolling(60).std()) * np.sqrt(252)
    dates = perf["date"].values
    rs_values = rolling_sharpe.values
    ax4.fill_between(dates, rs_values, 0,
                     where=(rs_values >= 0), color=CYAN, alpha=0.4)
    ax4.fill_between(dates, rs_values, 0,
                     where=(rs_values < 0), color=RED_FILL, alpha=0.4)
    ax4.plot(dates, rs_values, color=CYAN, linewidth=1.2)
    ax4.axhline(1.0, color=GOLD, linewidth=1.0, linestyle="--", label="Sharpe=1.0")
    ax4.axhline(0, color=GRID, linewidth=0.5)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax4.set_title("滚动60日夏普比率", fontsize=13)
    ax4.set_ylabel("Rolling Sharpe", fontsize=10)
    ax4.legend(fontsize=8, facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT)

    out_path = OUTPUT / "factor_analysis_zh.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"[OK] 已生成: {out_path}")


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
if __name__ == "__main__":
    font_name = setup_chinese_font()
    metrics, monthly, perf, ic = load_data()
    generate_backtest_report(metrics, monthly, perf, ic, font_name)
    generate_factor_analysis(metrics, perf, ic, font_name)
    print("[DONE] 两张图表已保存到 output/")
