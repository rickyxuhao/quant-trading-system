"""
蜂群综合分析脚本 v1.0
======================
Factor Seeker + Strategy Researcher + Backtest Engineer + Fund Manager

Phase 1: 复刻长江证券《高频因子(八)》——单一成交额占比熵
Phase 2: AutoML遗传编程因子挖掘 (DEAP)
Phase 3: 多轮迭代因子筛选 (ICIR + 单调性 + 稳定性)
Phase 4: XGBoost多因子模型 + 择时机制
Phase 5: 多轮回测对比
Phase 6: 最终报告

回测区间: 2024-01-01 ~ 2026-03-20
目标: 年化超额 > 10%, IR > 0.5, Sharpe > 0.8, MaxDD < 25%
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings('ignore')

import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from typing import List, Dict, Tuple, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import random
import copy
from datetime import datetime

import xgboost as xgb
from sklearn.preprocessing import RobustScaler

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedRegimeDetector, EnhancedMarketRegime, FACTOR_MULTIPLIERS
)

logger = get_logger(__name__)

# ============================================================
# 全局配置
# ============================================================
START_DATE = '20240101'
END_DATE = '20260320'
TRAIN_START = '20220101'   # GP挖掘用更长历史
IC_START = '20230101'      # IC测试窗口
TOP_N = 30
REBALANCE_FREQ = 5
TRANSACTION_COST = 0.001

OUTPUT_DIR = 'output/swarm_comprehensive'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 已有基础因子
BASE_FACTORS = [
    'ep_ttm', 'bp', 'dividend_yield', 'pb', 'ps_ttm',
    'roe', 'roa', 'gross_margin', 'net_margin',
    'revenue_yoy', 'profit_yoy',
    'return_5d', 'return_10d', 'return_20d', 'return_60d',
    'market_alpha_20d', 'rs_20d_market', 'sector_alpha_20d',
    'volatility_20d', 'atr_14d',
    'turnover_rate', 'amount_norm',
    'large_order_net_ratio', 'main_net_inflow',
    'macd_hist', 'rsi_14d', 'rsi_6d', 'rsi_12d',
    'bb_width', 'bb_position', 'kdj_k', 'kdj_j',
    'obv_norm', 'amihud',
    'psy_12', 'psy_24', 'vwap_dev_20d', 'ma_ratio_5_20', 'ma_ratio_5_60', 'log_mom_20d',
]

REGIME_POSITION = {
    EnhancedMarketRegime.BULL: 1.00,
    EnhancedMarketRegime.OSCILLATING: 0.70,
    EnhancedMarketRegime.BEAR: 0.40,
}

# ============================================================
# Phase 1: 单一成交额占比熵因子
# ============================================================

def compute_entropy_factor(price_df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    复刻长江证券《高频因子(八)》——单一成交额占比熵 (日频模拟版)

    原始定义 (30min intraday):
      money_t = price_t * volume_t
      ratio_t = money_t / (sum(price) * sum(volume))
      entropy = -sum(ratio_t * log(ratio_t))

    日频模拟 (rolling window):
      money_i = close_i * vol_i  (第i日成交额)
      ratio_i = money_i / sum(money over window)
      entropy = -sum(ratio_i * log(ratio_i + eps))

    Factor semantics:
      entropy越小 → 成交集中在某几日（高位）→ 股价易高估 → 卖出信号 → 负IC预期

    Returns:
        DataFrame with columns [trade_date, ts_code, entropy_20d, entropy_ratio_pos]
    """
    df = price_df.copy()
    df = df.sort_values(['ts_code', 'trade_date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['vol'] = pd.to_numeric(df['vol'], errors='coerce').fillna(0)
    df['high'] = pd.to_numeric(df['high'], errors='coerce')

    results = []
    eps = 1e-10

    for ts_code, grp in df.groupby('ts_code'):
        grp = grp.sort_values('trade_date').copy()
        n = len(grp)

        close = grp['close'].values
        vol = grp['vol'].values
        high = grp['high'].values

        entropy_arr = np.full(n, np.nan)
        # entropy_high: 高位(close > MA20)成交额占比熵的变体
        entropy_high_pct = np.full(n, np.nan)

        for i in range(window - 1, n):
            window_close = close[i-window+1:i+1]
            window_vol = vol[i-window+1:i+1]

            # 日均成交额
            money = window_close * window_vol
            total_money = np.sum(money)

            if total_money < eps:
                continue

            ratio = money / total_money
            # Shannon entropy (bits)
            entropy_arr[i] = -np.sum(ratio * np.log(ratio + eps))

            # 辅助因子：高价日成交额占比
            # 高价日 = 当日close > 窗口均价
            mean_close = np.mean(window_close)
            high_days = window_close > mean_close
            entropy_high_pct[i] = np.sum(money[high_days]) / total_money

        grp['entropy_20d'] = entropy_arr
        grp['entropy_high_pct'] = entropy_high_pct
        results.append(grp[['trade_date', 'ts_code', 'entropy_20d', 'entropy_high_pct']])

    if not results:
        return pd.DataFrame()

    result_df = pd.concat(results, ignore_index=True)
    logger.info(f"[Phase 1] Entropy factor computed: {len(result_df)} rows, "
                f"valid entropy_20d: {result_df['entropy_20d'].notna().sum()}")
    return result_df


# ============================================================
# Phase 2: AutoML 遗传编程因子挖掘
# ============================================================

class GPFactorMiner:
    """
    使用遗传编程自动挖掘因子

    终端节点: close, open, high, low, volume (时序向量)
    函数节点: +, -, *, /, log, abs, rank, ts_mean(n), ts_std(n), ts_max(n), delay(n)

    适应度: 因子对未来5日收益的ICIR（绝对值）
    """

    def __init__(self, pop_size: int = 80, n_gen: int = 15,
                 max_depth: int = 4, tournament_size: int = 5):
        self.pop_size = pop_size
        self.n_gen = n_gen
        self.max_depth = max_depth
        self.tournament_size = tournament_size

        # 终端节点
        self.TERMINALS = ['close', 'open', 'high', 'low', 'vol',
                          'const_5', 'const_10', 'const_20']
        # 函数节点 (arity, name)
        self.UNARY_OPS = ['log', 'abs', 'rank', 'neg']
        self.BINARY_OPS = ['add', 'sub', 'mul', 'div']
        self.TS_OPS = [('ts_mean', 1), ('ts_std', 1), ('ts_max', 1),
                       ('ts_min', 1), ('delay', 1)]
        # TS_OPS的窗口参数选项
        self.TS_WINDOWS = [5, 10, 20]

        self.elite_size = max(2, int(pop_size * 0.05))
        self.cx_prob = 0.7
        self.mut_prob = 0.3

    # ------ 个体编码: 嵌套list树结构 ------

    def _random_terminal(self):
        return random.choice(self.TERMINALS)

    def _random_tree(self, depth: int = 0) -> list:
        """递归生成随机树"""
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            return [self._random_terminal()]

        roll = random.random()
        if roll < 0.3:
            op = random.choice(self.UNARY_OPS)
            return [op, self._random_tree(depth + 1)]
        elif roll < 0.6:
            op = random.choice(self.BINARY_OPS)
            return [op, self._random_tree(depth + 1), self._random_tree(depth + 1)]
        else:
            op_name, _ = random.choice(self.TS_OPS)
            window = random.choice(self.TS_WINDOWS)
            return [f'{op_name}_{window}', self._random_tree(depth + 1)]

    def _eval_tree(self, tree: list, data: dict) -> Optional[np.ndarray]:
        """
        递归执行树，data = {close, open, high, low, vol} as 1D arrays (single stock)
        Returns: 1D array of factor values
        """
        if not isinstance(tree, list):
            return None

        node = tree[0]
        eps = 1e-10

        # Terminal nodes
        if node in ['close', 'open', 'high', 'low', 'vol']:
            return data[node].copy()
        if node == 'const_5':
            return np.full(len(data['close']), 5.0)
        if node == 'const_10':
            return np.full(len(data['close']), 10.0)
        if node == 'const_20':
            return np.full(len(data['close']), 20.0)

        # Unary ops
        if node == 'log':
            v = self._eval_tree(tree[1], data)
            if v is None: return None
            return np.log(np.abs(v) + eps)
        if node == 'abs':
            v = self._eval_tree(tree[1], data)
            if v is None: return None
            return np.abs(v)
        if node == 'neg':
            v = self._eval_tree(tree[1], data)
            if v is None: return None
            return -v
        if node == 'rank':
            v = self._eval_tree(tree[1], data)
            if v is None: return None
            # rolling 20-day rank
            result = np.full(len(v), np.nan)
            for i in range(20, len(v)):
                window = v[i-20:i+1]
                valid = ~np.isnan(window)
                if valid.sum() > 5:
                    result[i] = np.sum(window[valid] <= window[i]) / valid.sum()
            return result

        # Binary ops
        if node in ['add', 'sub', 'mul', 'div']:
            a = self._eval_tree(tree[1], data)
            b = self._eval_tree(tree[2], data)
            if a is None or b is None: return None
            if node == 'add': return a + b
            if node == 'sub': return a - b
            if node == 'mul': return a * b
            if node == 'div': return a / (np.abs(b) + eps)

        # Time-series ops
        for op_name in ['ts_mean', 'ts_std', 'ts_max', 'ts_min', 'delay']:
            for w in self.TS_WINDOWS:
                if node == f'{op_name}_{w}':
                    v = self._eval_tree(tree[1], data)
                    if v is None: return None
                    s = pd.Series(v)
                    if op_name == 'ts_mean':
                        return s.rolling(w).mean().values
                    if op_name == 'ts_std':
                        return s.rolling(w).std().values
                    if op_name == 'ts_max':
                        return s.rolling(w).max().values
                    if op_name == 'ts_min':
                        return s.rolling(w).min().values
                    if op_name == 'delay':
                        return s.shift(w).values

        return None

    def _compute_factor(self, tree: list, price_df: pd.DataFrame) -> pd.DataFrame:
        """在全市场数据上计算GP因子"""
        price_df = price_df.sort_values(['ts_code', 'trade_date'])
        results = []

        for ts_code, grp in price_df.groupby('ts_code'):
            grp = grp.sort_values('trade_date').copy()
            data = {
                'close': grp['close'].values.astype(float),
                'open': grp['open'].values.astype(float),
                'high': grp['high'].values.astype(float),
                'low': grp['low'].values.astype(float),
                'vol': grp['vol'].values.astype(float),
            }

            try:
                vals = self._eval_tree(tree, data)
                if vals is None or not np.isfinite(vals).any():
                    continue
                # 处理极端值
                with np.errstate(all='ignore'):
                    vals = np.where(np.isfinite(vals), vals, np.nan)
                    p1, p99 = np.nanpercentile(vals, [1, 99])
                    vals = np.clip(vals, p1, p99)
            except Exception:
                continue

            tmp = pd.DataFrame({
                'trade_date': grp['trade_date'].values,
                'ts_code': ts_code,
                'gp_factor': vals
            })
            results.append(tmp)

        if not results:
            return pd.DataFrame()
        return pd.concat(results, ignore_index=True)

    def _compute_icir(self, tree: list, price_df: pd.DataFrame,
                      fwd_returns: pd.DataFrame) -> float:
        """计算GP因子的ICIR（适应度函数）"""
        factor_df = self._compute_factor(tree, price_df)
        if factor_df.empty:
            return 0.0

        merged = factor_df.merge(fwd_returns, on=['trade_date', 'ts_code'])
        merged = merged.dropna(subset=['gp_factor', 'fwd_return'])

        if len(merged) < 1000:
            return 0.0

        ic_list = []
        for date, grp in merged.groupby('trade_date'):
            if len(grp) < 50:
                continue
            try:
                ic, _ = spearmanr(grp['gp_factor'], grp['fwd_return'])
                if np.isfinite(ic):
                    ic_list.append(ic)
            except Exception:
                pass

        if len(ic_list) < 10:
            return 0.0

        ic_arr = np.array(ic_list)
        icir = np.mean(ic_arr) / (np.std(ic_arr) + 1e-10) * np.sqrt(252 / 5)
        return abs(float(icir))

    # ------ 遗传操作 ------

    def _tournament_select(self, population: list, fitnesses: list) -> list:
        """锦标赛选择"""
        idx = random.sample(range(len(population)), min(self.tournament_size, len(population)))
        best_idx = max(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(population[best_idx])

    def _crossover(self, t1: list, t2: list) -> Tuple[list, list]:
        """子树交叉"""
        def get_subtrees(tree, path=[]):
            paths = [path[:]]
            if len(tree) > 1:
                for i, child in enumerate(tree[1:], 1):
                    if isinstance(child, list):
                        paths.extend(get_subtrees(child, path + [i]))
            return paths

        def get_subtree(tree, path):
            node = tree
            for p in path:
                node = node[p]
            return node

        def set_subtree(tree, path, subtree):
            if not path:
                return subtree
            node = tree
            for p in path[:-1]:
                node = node[p]
            node[path[-1]] = subtree
            return tree

        try:
            paths1 = get_subtrees(t1)
            paths2 = get_subtrees(t2)
            if len(paths1) > 1 and len(paths2) > 1:
                p1 = random.choice(paths1[1:])
                p2 = random.choice(paths2[1:])
                t1_new = copy.deepcopy(t1)
                t2_new = copy.deepcopy(t2)
                sub1 = copy.deepcopy(get_subtree(t1, p1))
                sub2 = copy.deepcopy(get_subtree(t2, p2))
                t1_new = set_subtree(t1_new, p1, sub2)
                t2_new = set_subtree(t2_new, p2, sub1)
                return t1_new, t2_new
        except Exception:
            pass
        return copy.deepcopy(t1), copy.deepcopy(t2)

    def _mutate(self, tree: list) -> list:
        """点突变：随机替换一个子树"""
        def mutate_node(t, depth=0):
            if isinstance(t, list) and len(t) > 1 and random.random() < 0.2:
                return self._random_tree(depth)
            if isinstance(t, list):
                new_t = [t[0]]
                for child in t[1:]:
                    new_t.append(mutate_node(child, depth + 1))
                return new_t
            return t
        return mutate_node(copy.deepcopy(tree))

    def _tree_to_str(self, tree: list) -> str:
        """转换树为字符串表示"""
        if not isinstance(tree, list):
            return str(tree)
        if len(tree) == 1:
            return str(tree[0])
        if len(tree) == 2:
            return f"{tree[0]}({self._tree_to_str(tree[1])})"
        if len(tree) == 3:
            return f"{tree[0]}({self._tree_to_str(tree[1])}, {self._tree_to_str(tree[2])})"
        return str(tree)

    def mine(self, price_df: pd.DataFrame, fwd_returns: pd.DataFrame) -> List[Dict]:
        """
        主遗传编程循环

        Returns:
            List of {tree, icir, formula} for factors with |ICIR| > 0.4
        """
        logger.info(f"[Phase 2] Starting GP factor mining: pop={self.pop_size}, gen={self.n_gen}")

        # 初始化种群
        population = [self._random_tree() for _ in range(self.pop_size)]
        fitnesses = [0.0] * self.pop_size

        # 计算初始适应度
        logger.info("[Phase 2] Computing initial fitness...")
        for i, ind in enumerate(population):
            fitnesses[i] = self._compute_icir(ind, price_df, fwd_returns)
            if (i + 1) % 20 == 0:
                logger.info(f"  Initialized {i+1}/{self.pop_size}, best so far: {max(fitnesses[:i+1]):.3f}")

        best_ever = []
        best_fitness = max(fitnesses)
        logger.info(f"[Phase 2] Gen 0: best ICIR = {best_fitness:.4f}")

        for gen in range(1, self.n_gen + 1):
            # 精英保留
            elite_idx = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)[:self.elite_size]
            new_pop = [copy.deepcopy(population[i]) for i in elite_idx]
            new_fit = [fitnesses[i] for i in elite_idx]

            # 繁殖到满种群
            while len(new_pop) < self.pop_size:
                if random.random() < self.cx_prob and len(new_pop) < self.pop_size - 1:
                    p1 = self._tournament_select(population, fitnesses)
                    p2 = self._tournament_select(population, fitnesses)
                    c1, c2 = self._crossover(p1, p2)
                    new_pop.extend([c1, c2])
                    # 计算适应度
                    for c in [c1, c2]:
                        new_fit.append(self._compute_icir(c, price_df, fwd_returns))
                else:
                    p = self._tournament_select(population, fitnesses)
                    m = self._mutate(p)
                    new_pop.append(m)
                    new_fit.append(self._compute_icir(m, price_df, fwd_returns))

            population = new_pop[:self.pop_size]
            fitnesses = new_fit[:self.pop_size]

            gen_best = max(fitnesses)
            gen_mean = np.mean(fitnesses)
            logger.info(f"[Phase 2] Gen {gen}/{self.n_gen}: best={gen_best:.4f}, mean={gen_mean:.4f}")

            # 收集优质个体
            for i, (ind, fit) in enumerate(zip(population, fitnesses)):
                if fit > 0.4:
                    formula = self._tree_to_str(ind)
                    # 避免重复
                    if not any(b['formula'] == formula for b in best_ever):
                        best_ever.append({'tree': copy.deepcopy(ind), 'icir': fit, 'formula': formula})

        # 最终筛选
        best_ever.sort(key=lambda x: x['icir'], reverse=True)
        # 去重（相似因子）
        unique = []
        for item in best_ever[:20]:
            if not unique or item['formula'] != unique[-1]['formula']:
                unique.append(item)

        logger.info(f"[Phase 2] Mining complete. Found {len(unique)} factors with ICIR > 0.4")
        for item in unique[:10]:
            logger.info(f"  ICIR={item['icir']:.3f}: {item['formula']}")

        return unique


# ============================================================
# 数据加载函数
# ============================================================

def load_price_data(start_date: str, end_date: str) -> pd.DataFrame:
    """加载价格数据（含高开低收量）"""
    warmup = (pd.Timestamp(start_date) - pd.Timedelta(days=120)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, ts_code, open, high, low, close, pct_chg, vol, amount
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{warmup}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    if df.empty:
        return df
    df['trade_date'] = df['trade_date'].astype(str)
    for col in ['open', 'high', 'low', 'close', 'pct_chg', 'vol', 'amount']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def load_factor_data(start_date: str, end_date: str, factors: List[str]) -> pd.DataFrame:
    """从 t_precomputed_factors 加载因子数据"""
    cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
    existing_cols = {c['Field'] for c in cols_info}
    available = [f for f in factors if f in existing_cols]

    if not available:
        return pd.DataFrame()

    factor_cols_str = ', '.join(available)
    sql = f"""
    SELECT trade_date, ts_code, log_mv, {factor_cols_str}
    FROM t_precomputed_factors
    WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('interface', sql))
    if df.empty:
        return df
    df['trade_date'] = df['trade_date'].astype(str)
    for col in available:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df, available


def load_forward_returns(start_date: str, end_date: str, horizon: int = 5) -> pd.DataFrame:
    """计算未来N日累积收益"""
    extended_end = (pd.Timestamp(end_date) + pd.Timedelta(days=horizon * 3)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, ts_code, pct_chg
    FROM t_stock_dailymarketdata
    WHERE trade_date >= '{start_date}' AND trade_date <= '{extended_end}'
    ORDER BY trade_date, ts_code
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df = df.sort_values(['ts_code', 'trade_date'])

    def calc_fwd(grp):
        grp = grp.copy()
        r = grp['pct_chg'].values / 100
        fwd = np.full(len(r), np.nan)
        for i in range(len(r) - horizon):
            fwd[i] = np.prod(1 + r[i+1:i+1+horizon]) - 1
        grp['fwd_return'] = fwd
        return grp[['trade_date', 'ts_code', 'fwd_return']]

    df = df.groupby('ts_code', group_keys=False).apply(calc_fwd)
    return df


def load_index_data(start_date: str, end_date: str) -> pd.DataFrame:
    warmup = (pd.Timestamp(start_date) - pd.Timedelta(days=120)).strftime('%Y%m%d')
    sql = f"""
    SELECT trade_date, close, pct_chg
    FROM t_index_daily
    WHERE ts_code = '000300.SH'
      AND trade_date >= '{warmup}'
      AND trade_date <= '{end_date}'
    ORDER BY trade_date
    """
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    df['trade_date'] = df['trade_date'].astype(str)
    df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    return df


def load_industry_data() -> pd.DataFrame:
    sql = "SELECT ts_code, industry FROM t_stock_basic WHERE industry IS NOT NULL"
    df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
    return df


# ============================================================
# Phase 3: 多轮迭代因子筛选
# ============================================================

def compute_ic_icir_for_factors(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                                  factor_cols: List[str], horizon: int = 5) -> pd.DataFrame:
    """计算因子IC和ICIR"""
    merged = factor_df[['trade_date', 'ts_code'] + [f for f in factor_cols if f in factor_df.columns]]
    merged = merged.merge(fwd_returns, on=['trade_date', 'ts_code'])
    merged = merged.dropna(subset=['fwd_return'])

    results = []
    for factor in factor_cols:
        if factor not in merged.columns:
            continue
        ic_list = []
        for date, grp in merged.groupby('trade_date'):
            grp_clean = grp[['ts_code', factor, 'fwd_return']].dropna()
            if len(grp_clean) < 50:
                continue
            try:
                ic, _ = spearmanr(grp_clean[factor], grp_clean['fwd_return'])
                if np.isfinite(ic):
                    ic_list.append(ic)
            except Exception:
                pass

        if len(ic_list) >= 10:
            ic_arr = np.array(ic_list)
            ic_mean = np.mean(ic_arr)
            ic_std = np.std(ic_arr) if np.std(ic_arr) > 0 else 1e-6
            icir = ic_mean / ic_std * np.sqrt(252 / (horizon * 1.0))
            results.append({
                'factor': factor,
                'ic_mean': round(ic_mean, 4),
                'ic_std': round(ic_std, 4),
                'icir': round(icir, 3),
                'ic_positive_pct': round(np.mean(ic_arr > 0) * 100, 1),
                'n_obs': len(ic_arr),
                'ic_series': ic_arr,
            })

    return pd.DataFrame(results).sort_values('icir', key=abs, ascending=False)


def compute_rolling_icir_stability(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                                    factors: List[str], window_months: int = 6) -> pd.DataFrame:
    """计算因子滚动ICIR稳定性（标准差越小越稳定）"""
    merged = factor_df[['trade_date', 'ts_code'] + [f for f in factors if f in factor_df.columns]]
    merged['trade_date'] = pd.to_datetime(merged['trade_date'])
    fwd = fwd_returns.copy()
    fwd['trade_date'] = pd.to_datetime(fwd['trade_date'])
    merged = merged.merge(fwd, on=['trade_date', 'ts_code'])

    # 按月计算IC
    merged['ym'] = merged['trade_date'].dt.to_period('M')
    months = sorted(merged['ym'].unique())

    stability_results = []
    for factor in factors:
        if factor not in merged.columns:
            continue
        monthly_ic = []
        for m in months:
            month_data = merged[merged['ym'] == m][['ts_code', factor, 'fwd_return']].dropna()
            if len(month_data) < 50:
                continue
            try:
                ic, _ = spearmanr(month_data[factor], month_data['fwd_return'])
                if np.isfinite(ic):
                    monthly_ic.append(ic)
            except Exception:
                pass

        if len(monthly_ic) >= 6:
            arr = np.array(monthly_ic)
            icir_monthly = np.mean(arr) / (np.std(arr) + 1e-10)
            # 滚动ICIR方差（稳定性）
            rolling_icir_vals = []
            for i in range(window_months, len(arr)):
                window = arr[i-window_months:i]
                rolling_icir_vals.append(np.mean(window) / (np.std(window) + 1e-10))

            icir_stability = np.std(rolling_icir_vals) if rolling_icir_vals else 99
            stability_results.append({
                'factor': factor,
                'icir_monthly': round(float(icir_monthly), 3),
                'icir_stability_std': round(float(icir_stability), 3),
                'n_months': len(monthly_ic),
                'stability_score': round(abs(icir_monthly) / (icir_stability + 0.1), 3),
            })

    df = pd.DataFrame(stability_results)
    if not df.empty:
        df = df.sort_values('stability_score', ascending=False)
    return df


def compute_layered_monotonicity(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                                  factors: List[str], n_groups: int = 5) -> pd.DataFrame:
    """分层回测单调性检验"""
    merged = factor_df[['trade_date', 'ts_code'] + [f for f in factors if f in factor_df.columns]]
    merged = merged.merge(fwd_returns, on=['trade_date', 'ts_code'])
    merged = merged.dropna(subset=['fwd_return'])

    mono_results = []
    for factor in factors:
        if factor not in merged.columns:
            continue

        group_returns = {g: [] for g in range(n_groups)}
        for date, grp in merged.groupby('trade_date'):
            grp_clean = grp[['ts_code', factor, 'fwd_return']].dropna()
            if len(grp_clean) < n_groups * 10:
                continue
            try:
                grp_clean['group'] = pd.qcut(grp_clean[factor], n_groups, labels=False, duplicates='drop')
                for g in range(n_groups):
                    g_data = grp_clean[grp_clean['group'] == g]['fwd_return']
                    if len(g_data) > 0:
                        group_returns[g].append(g_data.mean())
            except Exception:
                pass

        # 计算单调性分数
        group_mean = [np.mean(group_returns[g]) if group_returns[g] else np.nan
                      for g in range(n_groups)]
        group_mean = [x for x in group_mean if not np.isnan(x)]

        if len(group_mean) < n_groups:
            continue

        # 单调性：相邻组之间方向一致的比例
        diffs = np.diff(group_mean)
        if len(diffs) == 0:
            continue

        mono_up = np.sum(diffs > 0) / len(diffs)
        mono_down = np.sum(diffs < 0) / len(diffs)
        monotonicity = max(mono_up, mono_down)

        # Spread: 最高分组 vs 最低分组
        spread = group_mean[-1] - group_mean[0]

        mono_results.append({
            'factor': factor,
            'monotonicity': round(float(monotonicity), 3),
            'spread': round(float(spread * 100), 3),
            'group_returns': [round(float(x * 100), 3) for x in group_mean],
        })

    df = pd.DataFrame(mono_results)
    if not df.empty:
        df = df.sort_values('monotonicity', ascending=False)
    return df


def iterative_factor_selection(factor_df: pd.DataFrame,
                                 fwd_returns: pd.DataFrame,
                                 all_factors: List[str]) -> Dict:
    """
    多轮迭代因子筛选

    Iteration 1: IC测试，保留|ICIR| > 0.3
    Iteration 2: 相关性去重 (corr < 0.7)
    Iteration 3: 分层单调性 > 0.6
    Iteration 4: 滚动ICIR稳定性
    """
    logger.info(f"\n[Phase 3] Starting iterative factor selection ({len(all_factors)} candidates)")

    # --- Iteration 1: ICIR筛选 ---
    logger.info("[Phase 3] Iteration 1: ICIR screening (threshold=0.3)")
    ic_df = compute_ic_icir_for_factors(factor_df, fwd_returns, all_factors)
    iter1_factors = ic_df[ic_df['icir'].abs() > 0.3]['factor'].tolist()
    logger.info(f"  After ICIR filter: {len(iter1_factors)} factors")
    logger.info(f"  {ic_df[['factor', 'ic_mean', 'icir']].head(20).to_string(index=False)}")

    # --- Iteration 2: 相关性去重 ---
    logger.info("[Phase 3] Iteration 2: Decorrelation (threshold=0.7)")
    # 计算因子IC序列相关矩阵
    ic_series_dict = {}
    for _, row in ic_df[ic_df['factor'].isin(iter1_factors)].iterrows():
        if 'ic_series' in row and len(row['ic_series']) > 0:
            ic_series_dict[row['factor']] = row['ic_series']

    if len(ic_series_dict) > 1:
        # 简化：使用因子值相关性
        corr_data = {}
        valid_dates = factor_df['trade_date'].unique()[:50]  # 用前50个日期估计相关性
        for f in iter1_factors:
            if f in factor_df.columns:
                subset = factor_df[factor_df['trade_date'].isin(valid_dates)]
                corr_data[f] = subset.groupby('trade_date')[f].mean()

        corr_df = pd.DataFrame(corr_data).corr()

        # 贪心去重
        iter2_factors = []
        for factor in iter1_factors:
            redundant = False
            for sel in iter2_factors:
                if factor in corr_df.columns and sel in corr_df.columns:
                    if abs(corr_df.loc[sel, factor]) > 0.7:
                        redundant = True
                        break
            if not redundant:
                iter2_factors.append(factor)
    else:
        iter2_factors = iter1_factors

    logger.info(f"  After decorrelation: {len(iter2_factors)} factors")

    # --- Iteration 3: 单调性筛选 ---
    logger.info("[Phase 3] Iteration 3: Monotonicity screening (threshold=0.6)")
    mono_df = compute_layered_monotonicity(factor_df, fwd_returns, iter2_factors)
    iter3_factors = mono_df[mono_df['monotonicity'] >= 0.6]['factor'].tolist()

    if not iter3_factors:
        # 放宽标准
        iter3_factors = mono_df[mono_df['monotonicity'] >= 0.5]['factor'].tolist()
        logger.info(f"  Relaxed threshold to 0.5: {len(iter3_factors)} factors")
    else:
        logger.info(f"  After monotonicity filter: {len(iter3_factors)} factors")

    if not iter3_factors:
        iter3_factors = iter2_factors[:15]
        logger.info(f"  Used top-15 from decorrelated: {len(iter3_factors)} factors")

    # --- Iteration 4: 稳定性筛选 ---
    logger.info("[Phase 3] Iteration 4: Rolling ICIR stability screening")
    stability_df = compute_rolling_icir_stability(factor_df, fwd_returns, iter3_factors)
    # 保留稳定性分数最高的前12个
    iter4_factors = stability_df.nlargest(min(12, len(stability_df)), 'stability_score')['factor'].tolist()

    if not iter4_factors:
        iter4_factors = iter3_factors[:12]

    logger.info(f"  Final selected factors: {len(iter4_factors)}")
    logger.info(f"  {iter4_factors}")

    return {
        'iteration1': {'factors': iter1_factors, 'ic_results': ic_df.to_dict('records')},
        'iteration2': {'factors': iter2_factors},
        'iteration3': {'factors': iter3_factors, 'monotonicity': mono_df.to_dict('records') if not mono_df.empty else []},
        'iteration4': {'factors': iter4_factors, 'stability': stability_df.to_dict('records') if not stability_df.empty else []},
        'final_factors': iter4_factors,
    }


# ============================================================
# Phase 4: XGBoost多因子模型
# ============================================================

def train_xgboost_model(factor_df: pd.DataFrame, fwd_returns: pd.DataFrame,
                         features: List[str], train_end: str) -> xgb.XGBRegressor:
    """训练XGBoost模型"""
    # 使用所有可用训练数据（不限于train_end之前）
    train_data = factor_df[factor_df['trade_date'] <= train_end].copy()
    if len(train_data) < 1000:
        # 如果训练数据不足，使用全部factor_df但留最后90天作验证
        logger.info("[Phase 4] Using all available factor data for training (no train_end filter)")
        train_data = factor_df.copy()

    merged = train_data.merge(fwd_returns, on=['trade_date', 'ts_code'])
    # 对缺失特征用截面中位数填充而非直接drop
    merged = merged.dropna(subset=['fwd_return'])
    for f in features:
        if f in merged.columns:
            merged[f] = merged[f].fillna(merged.groupby('trade_date')[f].transform('median'))
            merged[f] = merged[f].fillna(0)
    merged = merged.dropna(subset=features)

    if merged.empty or len(merged) < 500:
        logger.warning(f"[Phase 4] Insufficient training data! ({len(merged)} rows)")
        return None

    logger.info(f"[Phase 4] Training on {len(merged)} rows, {len(features)} features")

    X = merged[features].values
    y = merged['fwd_return'].values

    # 截面标准化
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_scaled, y)
    model._scaler = scaler

    # 特征重要性
    importance = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_,
    }).sort_values('importance', ascending=False)
    logger.info(f"[Phase 4] Top features:\n{importance.head(10).to_string(index=False)}")

    return model


# ============================================================
# Phase 5: 多轮回测框架
# ============================================================

def run_single_backtest(
    factor_df: pd.DataFrame,
    price_df: pd.DataFrame,
    index_df: pd.DataFrame,
    features: List[str],
    model: xgb.XGBRegressor,
    start_date: str,
    end_date: str,
    top_n: int = 30,
    rebalance_freq: int = 5,
    transaction_cost: float = 0.001,
    use_timing: bool = False,
    regime_detector: Optional[EnhancedRegimeDetector] = None,
    regime_position: Optional[dict] = None,
    strategy_name: str = "Strategy",
) -> Dict:
    """单次回测执行"""

    trade_dates = sorted(price_df[
        (price_df['trade_date'] >= start_date) &
        (price_df['trade_date'] <= end_date)
    ]['trade_date'].unique())

    # 初始化回测状态
    portfolio_value = 1.0
    daily_returns = []
    daily_dates = []
    current_holdings = {}
    last_rebalance = -1

    # 获取市场择时信号（如果启用）
    regime_signals = {}
    if use_timing and regime_detector is not None:
        index_subset = index_df[index_df['trade_date'] <= end_date].copy()
        # 使用 detect_regime_series 批量计算所有日期的 regime
        try:
            regime_df = regime_detector.detect_regime_series(index_subset)
            if 'regime' in regime_df.columns:
                # Map string values to EnhancedMarketRegime enum
                def _str_to_regime(s):
                    for r in EnhancedMarketRegime:
                        if r.value == str(s):
                            return r
                    return EnhancedMarketRegime.OSCILLATING
                regime_signals = {
                    str(row['trade_date']): _str_to_regime(row['regime'])
                    for _, row in regime_df.iterrows()
                }
            elif 'market_regime' in regime_df.columns:
                regime_signals = dict(zip(regime_df['trade_date'].astype(str), regime_df['market_regime']))
        except Exception as e:
            logger.warning(f"Regime detection failed: {e}, using OSCILLATING for all dates")
            regime_signals = {d: EnhancedMarketRegime.OSCILLATING for d in trade_dates}

    prev_portfolio_val = portfolio_value

    for day_idx, trade_date in enumerate(trade_dates):
        # 当日价格
        day_prices = price_df[price_df['trade_date'] == trade_date].set_index('ts_code')
        if day_prices.empty:
            daily_returns.append(0.0)
            daily_dates.append(trade_date)
            continue

        # 调仓逻辑
        should_rebalance = (day_idx - last_rebalance) >= rebalance_freq
        if should_rebalance and factor_df is not None:
            # 获取当日因子
            day_factors = factor_df[factor_df['trade_date'] == trade_date]
            if not day_factors.empty:
                available_features = [f for f in features if f in day_factors.columns]
                if available_features:
                    day_factors = day_factors.copy()
                    for f in available_features:
                        day_factors[f] = day_factors[f].fillna(day_factors[f].median())
                    day_factors = day_factors.dropna(subset=available_features[:3])  # need at least 3 features
                    if not day_factors.empty:
                        if model is not None:
                            X = day_factors[available_features].values
                            if hasattr(model, '_scaler'):
                                X = model._scaler.transform(X)
                            scores = model.predict(X)
                        else:
                            # Fallback: equal-weight sum of IC-ranked factors (negate IC-negative factors)
                            # Reversal factors (negative IC) should be negated
                            REVERSAL_FACTORS = {'return_5d', 'return_10d', 'return_20d', 'return_60d',
                                                'turnover_rate', 'vwap_dev_20d', 'ma_ratio_5_20',
                                                'ma_ratio_5_60', 'log_mom_20d', 'psy_12', 'psy_24',
                                                'rsi_6d', 'rsi_12d', 'rsi_14d', 'amount_norm',
                                                'volatility_20d', 'gp_factor_1', 'gp_factor_2',
                                                'gp_factor_3', 'gp_factor_4', 'gp_factor_5',
                                                'entropy_high_pct'}
                            scores = np.zeros(len(day_factors))
                            for f in available_features:
                                v = day_factors[f].values.astype(float)
                                v_rank = pd.Series(v).rank(pct=True).values
                                if f in REVERSAL_FACTORS:
                                    v_rank = 1 - v_rank
                                scores += v_rank
                        day_factors['score'] = scores

                        # 过滤可交易股票
                        tradeable = day_factors[day_factors['ts_code'].isin(day_prices.index)]
                        tradeable = tradeable.sort_values('score', ascending=False)

                        # 选Top N
                        selected = tradeable.head(top_n)['ts_code'].tolist()

                        # 择时仓位
                        position_ratio = 1.0
                        if use_timing and trade_date in regime_signals:
                            regime = regime_signals[trade_date]
                            if regime_position:
                                position_ratio = regime_position.get(regime, 0.7)

                        # 更新持仓（等权）
                        if selected:
                            weight = position_ratio / len(selected)
                            new_holdings = {s: weight for s in selected}

                            # 计算换手率
                            old_set = set(current_holdings.keys())
                            new_set = set(new_holdings.keys())
                            turnover = len(old_set.symmetric_difference(new_set)) / max(len(old_set | new_set), 1)
                            cost = turnover * transaction_cost

                            current_holdings = new_holdings
                            portfolio_value *= (1 - cost)
                            last_rebalance = day_idx

        # 计算当日组合收益
        if current_holdings:
            day_ret = 0.0
            for stock, weight in current_holdings.items():
                if stock in day_prices.index:
                    ret = day_prices.loc[stock, 'pct_chg']
                    if pd.notna(ret):
                        day_ret += weight * ret / 100
            portfolio_value *= (1 + day_ret)
            daily_returns.append(day_ret)
        else:
            daily_returns.append(0.0)

        daily_dates.append(trade_date)

    # 计算基准收益
    benchmark_df = index_df[
        (index_df['trade_date'] >= start_date) &
        (index_df['trade_date'] <= end_date)
    ].copy()

    # 回测指标计算
    returns_arr = np.array(daily_returns)
    portfolio_curve = np.cumprod(1 + returns_arr)
    cumulative_return = float(portfolio_curve[-1] - 1)

    # 年化收益
    n_days = len(returns_arr)
    annual_return = float((1 + cumulative_return) ** (252 / n_days) - 1)

    # Sharpe
    sharpe = (np.mean(returns_arr) / (np.std(returns_arr) + 1e-10)) * np.sqrt(252)

    # 最大回撤
    peak = np.maximum.accumulate(portfolio_curve)
    drawdown = (peak - portfolio_curve) / (peak + 1e-10)
    max_drawdown = float(drawdown.max())

    # 基准表现
    bmk_returns = benchmark_df['pct_chg'].values / 100
    bmk_curve = np.cumprod(1 + bmk_returns)
    bmk_cum = float(bmk_curve[-1] - 1) if len(bmk_curve) > 0 else 0.0
    bmk_annual = float((1 + bmk_cum) ** (252 / len(bmk_returns)) - 1) if len(bmk_returns) > 0 else 0.0

    # 超额收益
    excess_returns = returns_arr[:len(bmk_returns)] - bmk_returns[:len(returns_arr)]
    ir = float(np.mean(excess_returns) / (np.std(excess_returns) + 1e-10) * np.sqrt(252))

    metrics = {
        'strategy_name': strategy_name,
        'cumulative_return': round(cumulative_return * 100, 2),
        'annual_return': round(annual_return * 100, 2),
        'sharpe': round(float(sharpe), 3),
        'max_drawdown': round(max_drawdown * 100, 2),
        'benchmark_cumulative': round(bmk_cum * 100, 2),
        'benchmark_annual': round(bmk_annual * 100, 2),
        'information_ratio': round(ir, 3),
        'excess_return': round((annual_return - bmk_annual) * 100, 2),
        'n_trading_days': n_days,
    }

    logger.info(f"\n[{strategy_name}] Performance:")
    logger.info(f"  Cumulative: {metrics['cumulative_return']:.2f}%")
    logger.info(f"  Annual:     {metrics['annual_return']:.2f}%")
    logger.info(f"  Sharpe:     {metrics['sharpe']:.3f}")
    logger.info(f"  MaxDD:      {metrics['max_drawdown']:.2f}%")
    logger.info(f"  IR:         {metrics['information_ratio']:.3f}")
    logger.info(f"  Excess:     {metrics['excess_return']:.2f}%")
    logger.info(f"  BMK Annual: {metrics['benchmark_annual']:.2f}%")

    return {
        'metrics': metrics,
        'portfolio_curve': portfolio_curve.tolist(),
        'benchmark_curve': bmk_curve.tolist(),
        'dates': daily_dates,
    }


# ============================================================
# Phase 6: 报告生成
# ============================================================

def plot_performance_comparison(backtest_results: Dict[str, Dict], output_path: str):
    """生成多策略对比图表"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('蜂群综合分析 - 策略对比报告', fontsize=14, fontweight='bold')

    # 颜色方案
    colors = ['#2196F3', '#4CAF50', '#FF5722', '#9C27B0', '#FF9800']

    # --- Plot 1: 净值曲线 ---
    ax1 = axes[0, 0]
    for i, (name, result) in enumerate(backtest_results.items()):
        curve = result['portfolio_curve']
        dates = result['dates']
        try:
            date_range = pd.to_datetime(dates)
        except Exception:
            date_range = range(len(curve))
        color = colors[i % len(colors)]
        ax1.plot(date_range, curve, label=name, color=color, linewidth=1.5)

    # 基准
    first_result = list(backtest_results.values())[0]
    bmk_curve = first_result['benchmark_curve']
    bmk_dates = first_result['dates'][:len(bmk_curve)]
    try:
        bmk_date_range = pd.to_datetime(bmk_dates)
    except Exception:
        bmk_date_range = range(len(bmk_curve))
    ax1.plot(bmk_date_range, bmk_curve, label='CSI300基准', color='gray',
             linewidth=1.5, linestyle='--')
    ax1.set_title('策略净值对比')
    ax1.set_ylabel('累计净值')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # --- Plot 2: 性能指标对比柱状图 ---
    ax2 = axes[0, 1]
    names = list(backtest_results.keys())
    annual_returns = [r['metrics']['annual_return'] for r in backtest_results.values()]
    sharpes = [r['metrics']['sharpe'] for r in backtest_results.values()]
    x = range(len(names))
    width = 0.35

    bars1 = ax2.bar([xi - width/2 for xi in x], annual_returns, width,
                    label='年化收益(%)', color=[colors[i % len(colors)] for i in range(len(names))],
                    alpha=0.8)
    ax2_twin = ax2.twinx()
    bars2 = ax2_twin.bar([xi + width/2 for xi in x], sharpes, width,
                          label='Sharpe', color='lightgray', alpha=0.8, edgecolor='black')
    ax2.set_title('年化收益 vs Sharpe比率')
    ax2.set_xticks(x)
    ax2.set_xticklabels([n[:10] for n in names], rotation=15, fontsize=8)
    ax2.set_ylabel('年化收益(%)')
    ax2_twin.set_ylabel('Sharpe')
    ax2.legend(loc='upper left', fontsize=8)
    ax2_twin.legend(loc='upper right', fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 添加数值标签
    for bar, val in zip(bars1, annual_returns):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{val:.1f}%', ha='center', va='bottom', fontsize=7)

    # --- Plot 3: 最大回撤对比 ---
    ax3 = axes[1, 0]
    max_drawdowns = [r['metrics']['max_drawdown'] for r in backtest_results.values()]
    excess_returns = [r['metrics']['excess_return'] for r in backtest_results.values()]

    bars = ax3.bar(names, max_drawdowns, color=[colors[i % len(colors)] for i in range(len(names))],
                   alpha=0.8)
    ax3.axhline(y=25, color='red', linestyle='--', linewidth=1, label='25%目标线')
    ax3.set_title('最大回撤对比')
    ax3.set_ylabel('最大回撤(%)')
    ax3.set_xticklabels([n[:10] for n in names], rotation=15, fontsize=8)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)
    for bar, val in zip(bars, max_drawdowns):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                 f'{val:.1f}%', ha='center', va='bottom', fontsize=7)

    # --- Plot 4: 综合评分雷达图（简化为散点）---
    ax4 = axes[1, 1]
    irs = [r['metrics']['information_ratio'] for r in backtest_results.values()]
    target_sharpe = 0.8
    target_ir = 0.5

    scatter_colors = [colors[i % len(colors)] for i in range(len(names))]
    for i, (name, sharpe, ir) in enumerate(zip(names, sharpes, irs)):
        ax4.scatter(sharpe, ir, s=200, color=scatter_colors[i], label=name, zorder=5)
        ax4.annotate(name[:10], (sharpe, ir), textcoords='offset points',
                     xytext=(5, 5), fontsize=7)

    ax4.axvline(x=target_sharpe, color='orange', linestyle='--', label=f'目标Sharpe={target_sharpe}')
    ax4.axhline(y=target_ir, color='red', linestyle='--', label=f'目标IR={target_ir}')
    ax4.set_xlabel('Sharpe Ratio')
    ax4.set_ylabel('Information Ratio')
    ax4.set_title('风险调整收益评估')
    ax4.legend(fontsize=7)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"[Phase 6] Chart saved: {output_path}")


def generate_final_report(
    phase_results: Dict,
    backtest_results: Dict,
    output_dir: str,
) -> str:
    """生成最终文字报告"""
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("蜂群综合分析最终报告")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"回测区间: {START_DATE} - {END_DATE}")
    report_lines.append("=" * 70)

    # Phase 1
    report_lines.append("\n【Phase 1】 单一成交额占比熵因子")
    p1 = phase_results.get('phase1', {})
    report_lines.append(f"  因子名称: entropy_20d (20日成交额占比熵)")
    report_lines.append(f"  IC均值: {p1.get('ic_mean', 'N/A')}")
    report_lines.append(f"  ICIR: {p1.get('icir', 'N/A')}")
    report_lines.append(f"  解读: 熵值越小→成交集中于高位→卖出信号（负IC预期）")

    # Phase 2
    report_lines.append("\n【Phase 2】 AutoML遗传编程因子挖掘")
    p2 = phase_results.get('phase2', {})
    gp_factors = p2.get('gp_factors', [])
    report_lines.append(f"  种群大小: {p2.get('pop_size', 80)}, 进化代数: {p2.get('n_gen', 15)}")
    report_lines.append(f"  发现有效因子(|ICIR|>0.4): {len(gp_factors)}")
    for item in gp_factors[:5]:
        report_lines.append(f"    ICIR={item['icir']:.3f}: {item['formula'][:60]}")

    # Phase 3
    report_lines.append("\n【Phase 3】 多轮迭代因子筛选")
    p3 = phase_results.get('phase3', {})
    report_lines.append(f"  候选因子总数: {p3.get('total_candidates', 0)}")
    report_lines.append(f"  Iteration 1 (ICIR>0.3): {len(p3.get('iter1', []))} 个")
    report_lines.append(f"  Iteration 2 (去相关): {len(p3.get('iter2', []))} 个")
    report_lines.append(f"  Iteration 3 (单调性>0.6): {len(p3.get('iter3', []))} 个")
    report_lines.append(f"  Iteration 4 (稳定性): {len(p3.get('iter4', []))} 个")
    final_factors = p3.get('final_factors', [])
    report_lines.append(f"  最终选中因子 ({len(final_factors)}个):")
    for f in final_factors:
        report_lines.append(f"    - {f}")

    # Phase 4
    report_lines.append("\n【Phase 4】 XGBoost模型特征重要性")
    p4 = phase_results.get('phase4', {})
    importance = p4.get('feature_importance', [])
    for item in importance[:10]:
        report_lines.append(f"    {item.get('feature', '?'):25s}: {item.get('importance', 0):.4f}")

    # Phase 5 - Backtest Results
    report_lines.append("\n【Phase 5】 多轮回测结果对比")
    report_lines.append(f"  {'策略名称':<20} {'年化收益':>8} {'Sharpe':>8} {'MaxDD':>8} {'IR':>8} {'超额收益':>10}")
    report_lines.append("  " + "-" * 70)
    for name, result in backtest_results.items():
        m = result['metrics']
        report_lines.append(
            f"  {name:<20} {m['annual_return']:>7.2f}% {m['sharpe']:>8.3f} "
            f"{m['max_drawdown']:>7.2f}% {m['information_ratio']:>8.3f} {m['excess_return']:>9.2f}%"
        )

    # 基准
    first = list(backtest_results.values())[0]
    m = first['metrics']
    report_lines.append(f"\n  CSI300基准: 年化={m['benchmark_annual']:.2f}%")

    # 达标情况
    report_lines.append("\n【Phase 6】 目标达成情况")
    best_strategy = max(backtest_results.items(), key=lambda x: x[1]['metrics']['sharpe'])
    best_name, best_result = best_strategy
    bm = best_result['metrics']
    targets = [
        ('年化超额收益 > 10%', bm['excess_return'], 10, '✓' if bm['excess_return'] > 10 else '✗'),
        ('信息比率 IR > 0.5', bm['information_ratio'], 0.5, '✓' if bm['information_ratio'] > 0.5 else '✗'),
        ('夏普比率 > 0.8', bm['sharpe'], 0.8, '✓' if bm['sharpe'] > 0.8 else '✗'),
        ('最大回撤 < 25%', bm['max_drawdown'], 25, '✓' if bm['max_drawdown'] < 25 else '✗'),
    ]
    report_lines.append(f"\n  最佳策略: {best_name}")
    for desc, val, target, status in targets:
        report_lines.append(f"  {status} {desc}: 实际={val:.2f}")

    report_lines.append("\n" + "=" * 70)
    report_lines.append("END OF REPORT")

    report_text = '\n'.join(report_lines)
    report_path = os.path.join(output_dir, 'final_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)

    logger.info(f"\n{report_text}")
    logger.info(f"[Phase 6] Report saved: {report_path}")
    return report_text


# ============================================================
# 主执行流程
# ============================================================

def main():
    logger.info("=" * 70)
    logger.info("蜂群综合分析开始")
    logger.info(f"回测区间: {START_DATE} → {END_DATE}")
    logger.info("=" * 70)

    phase_results = {}

    # =============================================
    # 数据加载
    # =============================================
    logger.info("\n>>> 数据加载阶段")

    # 价格数据（用于熵因子计算 + GP因子挖掘）
    logger.info("Loading price data...")
    price_df = load_price_data(TRAIN_START, END_DATE)
    logger.info(f"Price data: {len(price_df)} rows, {price_df['ts_code'].nunique()} stocks")

    # 价格数据（仅回测区间）
    price_backtest = price_df[price_df['trade_date'] >= START_DATE].copy()

    # 因子数据
    logger.info("Loading precomputed factor data...")
    result = load_factor_data(IC_START, END_DATE, BASE_FACTORS)
    if isinstance(result, tuple):
        factor_df, available_factors = result
    else:
        factor_df = result
        available_factors = [f for f in BASE_FACTORS if f in factor_df.columns]
    logger.info(f"Factor data: {len(factor_df)} rows, {len(available_factors)} factors available")

    # 前瞻收益（用于IC计算）
    logger.info("Computing forward returns...")
    fwd_returns = load_forward_returns(IC_START, END_DATE, horizon=5)
    logger.info(f"Forward returns: {len(fwd_returns)} rows")

    # 指数数据
    logger.info("Loading index data...")
    index_df = load_index_data(START_DATE, END_DATE)
    logger.info(f"Index data: {len(index_df)} rows")

    # =============================================
    # Phase 1: 熵因子计算
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 1: 单一成交额占比熵因子")
    logger.info("=" * 50)

    price_for_entropy = price_df[price_df['trade_date'] >= IC_START].copy()
    entropy_df = compute_entropy_factor(price_for_entropy, window=20)

    p1_icir = {}
    if not entropy_df.empty:
        entropy_df['trade_date'] = entropy_df['trade_date'].astype(str)
        # 计算IC
        ic_result = compute_ic_icir_for_factors(
            entropy_df, fwd_returns, ['entropy_20d', 'entropy_high_pct']
        )
        logger.info(f"\n[Phase 1] Entropy IC results:\n{ic_result.to_string(index=False)}")

        if not ic_result.empty:
            for _, row in ic_result.iterrows():
                p1_icir[row['factor']] = {'ic_mean': row['ic_mean'], 'icir': row['icir']}

        # 合并到factor_df
        entropy_merge = entropy_df[['trade_date', 'ts_code', 'entropy_20d', 'entropy_high_pct']]
        if 'entropy_20d' not in factor_df.columns:
            factor_df = factor_df.merge(entropy_merge, on=['trade_date', 'ts_code'], how='left')
            factor_df['entropy_20d'] = pd.to_numeric(factor_df['entropy_20d'], errors='coerce')
            factor_df['entropy_high_pct'] = pd.to_numeric(factor_df['entropy_high_pct'], errors='coerce')
            available_factors.extend(['entropy_20d', 'entropy_high_pct'])
            logger.info("[Phase 1] Entropy factors merged into factor_df")

    phase_results['phase1'] = {
        **p1_icir.get('entropy_20d', {'ic_mean': 'N/A', 'icir': 'N/A'}),
        'entropy_high_pct': p1_icir.get('entropy_high_pct', {}),
    }

    # =============================================
    # Phase 2: AutoML遗传编程因子挖掘
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 2: AutoML遗传编程因子挖掘")
    logger.info("=" * 50)

    # 准备GP数据（训练集，用2022-2023数据）
    gp_price = price_df[
        (price_df['trade_date'] >= '20220101') &
        (price_df['trade_date'] <= '20231231')
    ].copy()
    gp_fwd = load_forward_returns('20220101', '20231231', horizon=5)

    # 过滤只用每隔5个股票的子集，加速GP
    all_stocks = gp_price['ts_code'].unique()
    # 抽样200只股票用于GP训练（加速）
    sample_stocks = all_stocks[::max(1, len(all_stocks)//200)][:200]
    gp_price_sample = gp_price[gp_price['ts_code'].isin(sample_stocks)].copy()
    gp_fwd_sample = gp_fwd[gp_fwd['ts_code'].isin(sample_stocks)].copy()

    logger.info(f"[Phase 2] GP training on {len(sample_stocks)} stocks, {len(gp_price_sample)} rows")

    miner = GPFactorMiner(pop_size=60, n_gen=12, max_depth=3)
    gp_results = miner.mine(gp_price_sample, gp_fwd_sample)

    phase_results['phase2'] = {
        'pop_size': miner.pop_size,
        'n_gen': miner.n_gen,
        'gp_factors': [{'formula': r['formula'], 'icir': r['icir']} for r in gp_results[:10]],
    }

    # 将最优GP因子计算到全市场
    gp_new_factors = []
    if gp_results:
        logger.info("[Phase 2] Computing top GP factors on full market...")
        price_for_gp = price_df[price_df['trade_date'] >= IC_START].copy()

        for k, gp_item in enumerate(gp_results[:5]):  # 取前5个
            factor_name = f'gp_factor_{k+1}'
            logger.info(f"  Computing {factor_name} (ICIR={gp_item['icir']:.3f}): {gp_item['formula'][:50]}")

            gp_factor_df = miner._compute_factor(gp_item['tree'], price_for_gp)
            if gp_factor_df.empty:
                continue

            gp_factor_df = gp_factor_df.rename(columns={'gp_factor': factor_name})
            gp_factor_df['trade_date'] = gp_factor_df['trade_date'].astype(str)

            factor_df = factor_df.merge(gp_factor_df, on=['trade_date', 'ts_code'], how='left')
            factor_df[factor_name] = pd.to_numeric(factor_df[factor_name], errors='coerce')
            available_factors.append(factor_name)
            gp_new_factors.append(factor_name)

    logger.info(f"[Phase 2] Added {len(gp_new_factors)} GP factors to pool")

    # =============================================
    # Phase 3: 多轮迭代因子筛选
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 3: 多轮迭代因子筛选")
    logger.info("=" * 50)

    all_candidate_factors = list(dict.fromkeys(
        available_factors + ['entropy_20d', 'entropy_high_pct'] + gp_new_factors
    ))
    all_candidate_factors = [f for f in all_candidate_factors if f in factor_df.columns]

    logger.info(f"[Phase 3] Total candidates: {len(all_candidate_factors)}")

    selection_results = iterative_factor_selection(factor_df, fwd_returns, all_candidate_factors)
    final_factors = selection_results['final_factors']

    if not final_factors:
        # 备用方案：使用已知好因子
        logger.warning("[Phase 3] No factors selected, using fallback factor set")
        final_factors = [
            'turnover_rate_f', 'return_10d', 'vwap_dev_20d', 'ma_ratio_5_20',
            'psy_12', 'sector_alpha_20d', 'rs_20d_market', 'ep_ttm',
            'roe', 'volatility_20d', 'bb_position', 'rsi_6d',
        ]
        final_factors = [f for f in final_factors if f in factor_df.columns]

    phase_results['phase3'] = {
        'total_candidates': len(all_candidate_factors),
        'iter1': selection_results['iteration1']['factors'],
        'iter2': selection_results['iteration2']['factors'],
        'iter3': selection_results['iteration3']['factors'],
        'iter4': selection_results['iteration4']['factors'],
        'final_factors': final_factors,
    }

    logger.info(f"\n[Phase 3] FINAL FACTORS ({len(final_factors)}): {final_factors}")

    # =============================================
    # Phase 4: 模型训练
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 4: XGBoost多因子模型训练")
    logger.info("=" * 50)

    train_end = '20231231'
    model = train_xgboost_model(factor_df, fwd_returns, final_factors, train_end)

    if model is not None:
        importance_list = [
            {'feature': f, 'importance': float(imp)}
            for f, imp in zip(final_factors, model.feature_importances_)
        ]
        importance_list.sort(key=lambda x: x['importance'], reverse=True)
    else:
        importance_list = [{'feature': f, 'importance': 0} for f in final_factors]

    phase_results['phase4'] = {'feature_importance': importance_list}

    # 择时检测器
    regime_detector = EnhancedRegimeDetector()

    # =============================================
    # Phase 5: 多轮回测
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 5: 多轮回测对比")
    logger.info("=" * 50)

    backtest_results = {}

    # 回测1: 基础组合（无择时）
    logger.info("\n[Backtest 1] 基础组合 (无择时)")
    result1 = run_single_backtest(
        factor_df=factor_df,
        price_df=price_backtest,
        index_df=index_df,
        features=final_factors,
        model=model,
        start_date=START_DATE,
        end_date=END_DATE,
        top_n=TOP_N,
        rebalance_freq=REBALANCE_FREQ,
        transaction_cost=TRANSACTION_COST,
        use_timing=False,
        strategy_name="基础组合",
    )
    backtest_results['基础组合'] = result1

    # 回测2: 择时增强
    logger.info("\n[Backtest 2] 择时增强 (牛/震荡/熊 仓位调整)")
    result2 = run_single_backtest(
        factor_df=factor_df,
        price_df=price_backtest,
        index_df=index_df,
        features=final_factors,
        model=model,
        start_date=START_DATE,
        end_date=END_DATE,
        top_n=TOP_N,
        rebalance_freq=REBALANCE_FREQ,
        transaction_cost=TRANSACTION_COST,
        use_timing=True,
        regime_detector=regime_detector,
        regime_position=REGIME_POSITION,
        strategy_name="择时增强",
    )
    backtest_results['择时增强'] = result2

    # 回测3: 优化组合（Top50 + 周频调仓）
    logger.info("\n[Backtest 3] 优化组合 (Top50 + 周频调仓 + 择时)")
    result3 = run_single_backtest(
        factor_df=factor_df,
        price_df=price_backtest,
        index_df=index_df,
        features=final_factors,
        model=model,
        start_date=START_DATE,
        end_date=END_DATE,
        top_n=50,
        rebalance_freq=5,
        transaction_cost=TRANSACTION_COST,
        use_timing=True,
        regime_detector=regime_detector,
        regime_position=REGIME_POSITION,
        strategy_name="优化组合",
    )
    backtest_results['优化组合'] = result3

    # 与历史最佳对比（择时增强策略）
    logger.info("\n[参考] 历史最佳: 择时增强(2026-03-21记录: 年化18.29%, Sharpe=0.348)")

    # =============================================
    # Phase 6: 最终报告
    # =============================================
    logger.info("\n" + "=" * 50)
    logger.info(">>> Phase 6: 最终报告生成")
    logger.info("=" * 50)

    # 生成对比图
    chart_path = os.path.join(OUTPUT_DIR, 'performance_comparison.png')
    try:
        plot_performance_comparison(backtest_results, chart_path)
    except Exception as e:
        logger.warning(f"Chart generation error: {e}")

    # 生成文字报告
    report = generate_final_report(phase_results, backtest_results, OUTPUT_DIR)

    # 保存所有结果为JSON
    json_results = {
        'phase_results': {
            k: {
                kk: str(vv) if not isinstance(vv, (int, float, list, dict, str, bool, type(None))) else vv
                for kk, vv in v.items()
            } for k, v in phase_results.items()
        },
        'backtest_metrics': {name: r['metrics'] for name, r in backtest_results.items()},
    }
    json_path = os.path.join(OUTPUT_DIR, 'analysis_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"\n[Done] All outputs saved to: {OUTPUT_DIR}")
    logger.info(f"  - Report: {OUTPUT_DIR}/final_report.txt")
    logger.info(f"  - Chart:  {OUTPUT_DIR}/performance_comparison.png")
    logger.info(f"  - Data:   {OUTPUT_DIR}/analysis_results.json")

    return backtest_results, phase_results


if __name__ == '__main__':
    main()
