"""
Phase 5: 市场环境感知多因子策略
- 使用 EnhancedRegimeDetector 识别市场环境（牛/熊/震荡）
- 不同市场环境使用不同因子权重
- XGBoost整合多类因子
- 行业中性约束
- 生成每日Top 30选股信号
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
import xgboost as xgb

from core.storage.relational.connection import DatabaseManager
from core.logger import get_logger
from projects.quant_trading.strategies.ml_prediction.enhanced_regime_detector import (
    EnhancedRegimeDetector, EnhancedMarketRegime, REGIME_FACTOR_WEIGHTS, FACTOR_MULTIPLIERS
)

logger = get_logger(__name__)


# ===== 因子分组（与ICIR分析脚本保持一致）=====
FACTOR_GROUPS = {
    'value': ['ep_ttm', 'bp', 'dividend_yield', 'pb', 'ps_ttm'],
    'quality': ['roe', 'roa', 'gross_margin', 'net_margin', 'debt_to_assets', 'current_ratio'],
    'growth': ['revenue_yoy', 'profit_yoy', 'roe_yoy'],
    'momentum': ['return_5d', 'return_10d', 'return_20d', 'return_60d',
                 'market_alpha_20d', 'rs_20d_market', 'sector_alpha_20d'],
    'volatility': ['volatility_20d', 'volatility_60d', 'downside_vol_20d',
                   'max_drawdown_20d', 'atr_14d'],
    'liquidity': ['turnover_rate', 'turnover_20d', 'volume_ratio', 'amount_norm'],
    'moneyflow': ['large_order_net_ratio', 'main_net_inflow', 'net_inflow_5d'],
    'technical': ['macd_hist', 'rsi_14d', 'rsi_6d', 'rsi_12d',
                  'bb_width', 'bb_position', 'kdj_k', 'kdj_j', 'obv_norm', 'amihud'],
}

ALL_FACTORS = [f for factors in FACTOR_GROUPS.values() for f in factors]

# 行业中性化所需的分类信息
INDUSTRY_COL = 'industry'


@dataclass
class RegimeAwareConfig:
    """市场环境感知策略配置"""
    top_n: int = 30                     # 每日选股数量
    train_lookback: int = 252           # 训练回看天数（1年）
    min_train_samples: int = 5000       # 最少训练样本数
    retrain_freq: int = 21              # 重训练频率（约月度）
    prediction_horizon: int = 5         # 预测horizon（5日收益）
    min_stocks_per_date: int = 200      # 每日最少有效股票数
    industry_neutral: bool = True       # 是否行业中性化
    use_regime_weights: bool = True     # 是否使用环境权重
    max_factor_pct_nan: float = 0.5     # 因子最大缺失率（超过则剔除）


class RegimeAwareStrategy:
    """
    市场环境感知多因子策略

    核心流程：
    1. 加载预计算因子 + 收益率数据
    2. 检测当日市场环境（牛/熊/震荡）
    3. 根据环境调整因子权重
    4. 训练XGBoost（滚动重训练）
    5. 生成Top 30选股信号
    """

    def __init__(self, config: Optional[RegimeAwareConfig] = None):
        self.config = config or RegimeAwareConfig()
        self.regime_detector = EnhancedRegimeDetector()
        self._models: Dict[str, xgb.XGBRegressor] = {}  # date -> model
        self._last_train_date: Optional[str] = None
        self._regime_series: Optional[pd.DataFrame] = None
        self._scaler = RobustScaler()

    def load_factor_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """加载因子数据"""
        # 确认哪些因子列存在
        cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
        existing_cols = {c['Field'] for c in cols_info}

        available_factors = [f for f in ALL_FACTORS if f in existing_cols]
        factor_cols = ', '.join(available_factors)

        sql = f"""
        SELECT trade_date, ts_code, log_mv, {factor_cols}
        FROM t_precomputed_factors
        WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date, ts_code
        """
        df = pd.DataFrame(DatabaseManager.fetchall('interface', sql))
        if df.empty:
            return df

        df['trade_date'] = df['trade_date'].astype(str)
        for f in available_factors:
            if f in df.columns:
                df[f] = pd.to_numeric(df[f], errors='coerce')

        return df

    def load_forward_returns(self, start_date: str, end_date: str,
                              horizon: int = 5) -> pd.DataFrame:
        """加载未来N日收益率"""
        # 需要加载到 end_date + horizon 个交易日后
        extended_end = pd.Timestamp(end_date) + pd.Timedelta(days=horizon * 3)
        sql = f"""
        SELECT trade_date, ts_code, pct_chg
        FROM t_stock_dailymarketdata
        WHERE trade_date >= '{start_date}'
          AND trade_date <= '{extended_end.strftime("%Y%m%d")}'
        ORDER BY trade_date, ts_code
        """
        df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
        if df.empty:
            return df

        df['trade_date'] = df['trade_date'].astype(str)
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce').fillna(0)

        # 计算累积前瞻收益
        df = df.sort_values(['ts_code', 'trade_date'])

        def calc_fwd(grp):
            grp = grp.copy()
            r = grp['pct_chg'].values / 100
            fwd = np.full(len(r), np.nan)
            for i in range(len(r) - horizon):
                fwd[i] = np.prod(1 + r[i+1:i+1+horizon]) - 1
            grp['fwd_return'] = fwd
            return grp

        df = df.groupby('ts_code', group_keys=False).apply(calc_fwd)
        return df[['trade_date', 'ts_code', 'fwd_return']]

    def load_industry_data(self) -> pd.DataFrame:
        """加载行业分类数据"""
        sql = """
        SELECT ts_code, industry
        FROM t_stock_basic
        WHERE list_status = 'L'
        """
        try:
            df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
            return df[['ts_code', 'industry']].dropna()
        except Exception:
            return pd.DataFrame()

    def load_regime_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """加载并计算市场环境序列"""
        if self._regime_series is not None:
            return self._regime_series

        warmup_start = (pd.Timestamp(start_date) - pd.Timedelta(days=90)).strftime('%Y%m%d')
        sql = f"""
        SELECT trade_date, pct_chg
        FROM t_index_daily
        WHERE ts_code = '000300.SH'
          AND trade_date >= '{warmup_start}'
          AND trade_date <= '{end_date}'
        ORDER BY trade_date
        """
        df = pd.DataFrame(DatabaseManager.fetchall('tushare_biz', sql))
        if df.empty:
            logger.warning("No CSI300 data, using oscillating for all dates")
            return pd.DataFrame()

        regime_df = self.regime_detector.detect_regime_series(df)
        self._regime_series = regime_df
        return regime_df

    def industry_neutralize(self, factor_df: pd.DataFrame, factor_cols: List[str],
                             industry_df: pd.DataFrame) -> pd.DataFrame:
        """行业中性化：减去行业均值"""
        if industry_df.empty or not factor_cols:
            return factor_df

        merged = factor_df.merge(industry_df, on='ts_code', how='left')
        merged['industry'] = merged['industry'].fillna('未知')

        for f in factor_cols:
            if f not in merged.columns:
                continue
            try:
                ind_mean = merged.groupby('industry')[f].transform('mean')
                merged[f] = merged[f] - ind_mean
            except Exception:
                pass

        return merged.drop(columns=['industry'], errors='ignore')

    def compute_regime_adjusted_score(self, factor_df: pd.DataFrame,
                                       regime: EnhancedMarketRegime,
                                       factor_cols: List[str]) -> pd.Series:
        """基于市场环境计算加权因子综合分"""
        weights = self.regime_detector.get_factor_weights(
            regime, factor_cols, FACTOR_GROUPS
        )

        score = pd.Series(0.0, index=factor_df.index)
        for f in factor_cols:
            if f not in factor_df.columns or f not in weights:
                continue
            vals = factor_df[f].copy()
            # 截面标准化
            vals_std = vals.std()
            if vals_std > 1e-10:
                vals = (vals - vals.mean()) / vals_std
            # Winsorize
            vals = vals.clip(-3, 3)
            score += weights[f] * vals

        return score

    def prepare_features(self, factor_df: pd.DataFrame,
                          regime: EnhancedMarketRegime,
                          factor_cols: List[str]) -> pd.DataFrame:
        """
        准备模型输入特征：
        1. 截面标准化
        2. 应用环境权重乘数
        3. 填充缺失值
        """
        X = factor_df[factor_cols].copy()
        multipliers = FACTOR_MULTIPLIERS.get(regime, {})

        # 截面标准化
        for f in factor_cols:
            if f not in X.columns:
                continue
            vals = X[f]
            mean = vals.mean()
            std = vals.std()
            if std > 1e-10:
                X[f] = ((vals - mean) / std).clip(-3, 3)
            # 应用环境权重乘数
            if f in multipliers:
                X[f] *= multipliers[f]

        # 填充剩余缺失值（均值填充）
        X = X.fillna(0)
        return X

    def train_model(self, factor_df: pd.DataFrame, returns_df: pd.DataFrame,
                     regime: EnhancedMarketRegime, factor_cols: List[str]) -> Optional[xgb.XGBRegressor]:
        """训练XGBoost模型"""
        # 合并特征和标签
        merged = factor_df.merge(returns_df, on=['trade_date', 'ts_code'])
        merged = merged.dropna(subset=['fwd_return'])

        if len(merged) < self.config.min_train_samples:
            logger.warning(f"Insufficient samples: {len(merged)} < {self.config.min_train_samples}")
            return None

        X = self.prepare_features(merged, regime, factor_cols)
        y = merged['fwd_return']

        # 时序分割
        split = int(len(merged) * 0.85)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]

        model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.7,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            tree_method='hist',
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=20,
            eval_metric='rmse',
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        logger.info(f"Model trained on {len(merged)} samples, regime={regime.value}")
        return model

    def generate_signals(self, trade_date: str, factor_df: pd.DataFrame,
                          model: Optional[xgb.XGBRegressor],
                          regime: EnhancedMarketRegime,
                          industry_df: pd.DataFrame,
                          factor_cols: List[str]) -> pd.DataFrame:
        """
        生成选股信号

        Returns:
            DataFrame with ts_code, score, rank, regime columns
        """
        date_df = factor_df[factor_df['trade_date'] == trade_date].copy()
        if len(date_df) < self.config.min_stocks_per_date:
            return pd.DataFrame()

        # 行业中性化
        if self.config.industry_neutral and not industry_df.empty:
            date_df = self.industry_neutralize(date_df, factor_cols, industry_df)

        # 计算综合分（环境加权）
        regime_score = self.compute_regime_adjusted_score(date_df, regime, factor_cols)

        if model is not None:
            # 用模型预测
            X = self.prepare_features(date_df, regime, factor_cols)
            try:
                ml_pred = model.predict(X)
                # 混合：50% 模型 + 50% 规则加权
                final_score = 0.5 * pd.Series(ml_pred, index=date_df.index) + 0.5 * regime_score
            except Exception as e:
                logger.warning(f"Model prediction failed: {e}, using regime score")
                final_score = regime_score
        else:
            final_score = regime_score

        date_df['score'] = final_score.values
        date_df['regime'] = regime.value
        date_df = date_df.sort_values('score', ascending=False)
        date_df['rank'] = range(1, len(date_df) + 1)

        return date_df[['trade_date', 'ts_code', 'score', 'rank', 'regime']].head(self.config.top_n * 3)

    def run_backtest_preparation(self, start_date: str, end_date: str) -> Dict:
        """
        准备回测所需的所有数据和信号

        Returns:
            dict with keys: signals, regime_stats, factor_importance
        """
        logger.info(f"Loading data {start_date} -> {end_date}")

        # 确认可用因子列
        cols_info = DatabaseManager.fetchall('interface', 'DESCRIBE t_precomputed_factors')
        existing_cols = {c['Field'] for c in cols_info}
        factor_cols = [f for f in ALL_FACTORS if f in existing_cols]
        logger.info(f"Available factors: {len(factor_cols)}")

        # 加载数据（需要更早数据用于训练）
        train_start = (pd.Timestamp(start_date) - pd.Timedelta(days=self.config.train_lookback + 30)).strftime('%Y%m%d')

        factor_df = self.load_factor_data(train_start, end_date)
        logger.info(f"Factor data: {len(factor_df)} rows")

        returns_df = self.load_forward_returns(train_start, end_date, self.config.prediction_horizon)
        logger.info(f"Returns data: {len(returns_df)} rows")

        industry_df = self.load_industry_data()
        logger.info(f"Industry data: {len(industry_df)} stocks")

        regime_df = self.load_regime_data(start_date, end_date)
        logger.info(f"Regime data: {len(regime_df)} days")

        # 获取回测期内的交易日
        backtest_dates = sorted(factor_df[
            (factor_df['trade_date'] >= start_date) &
            (factor_df['trade_date'] <= end_date)
        ]['trade_date'].unique())
        logger.info(f"Backtest dates: {len(backtest_dates)}")

        all_signals = []
        current_model = None
        last_regime = EnhancedMarketRegime.OSCILLATING

        for i, date in enumerate(backtest_dates):
            # 获取当日市场环境
            if not regime_df.empty:
                date_regime_row = regime_df[regime_df['trade_date'].astype(str) == date]
                if not date_regime_row.empty:
                    regime_str = date_regime_row.iloc[0]['regime']
                    last_regime = EnhancedMarketRegime(regime_str)
            regime = last_regime

            # 是否需要重训练
            need_retrain = (
                current_model is None or
                self._last_train_date is None or
                i % self.config.retrain_freq == 0
            )

            if need_retrain:
                # 准备训练数据（使用到date前的历史数据）
                train_factor = factor_df[factor_df['trade_date'] < date].copy()
                train_returns = returns_df[returns_df['trade_date'] < date].copy()

                if len(train_factor) >= self.config.min_train_samples:
                    current_model = self.train_model(
                        train_factor, train_returns, regime, factor_cols
                    )
                    self._last_train_date = date
                    if current_model:
                        logger.info(f"[{date}] Retrained model (regime={regime.value})")

            # 生成当日选股信号
            signals = self.generate_signals(
                date, factor_df, current_model, regime, industry_df, factor_cols
            )

            if not signals.empty:
                all_signals.append(signals.head(self.config.top_n))

            if i % 20 == 0:
                logger.info(f"Progress: {i+1}/{len(backtest_dates)} [{date}] "
                           f"regime={regime.value}, stocks={len(signals) if not signals.empty else 0}")

        if not all_signals:
            return {'signals': pd.DataFrame(), 'regime_stats': {}}

        signals_df = pd.concat(all_signals, ignore_index=True)

        # 计算regime统计
        regime_stats = {}
        if not regime_df.empty:
            stats = regime_df['regime'].value_counts()
            for r in ['bull', 'bear', 'oscillating']:
                count = stats.get(r, 0)
                regime_stats[r] = {'days': int(count), 'pct': round(count / len(regime_df) * 100, 1)}

        # 因子重要性
        factor_importance = {}
        if current_model is not None and hasattr(current_model, 'feature_importances_'):
            importance = current_model.feature_importances_
            factor_importance = dict(zip(factor_cols, importance.tolist()))
            factor_importance = dict(sorted(factor_importance.items(),
                                            key=lambda x: x[1], reverse=True))

        return {
            'signals': signals_df,
            'regime_stats': regime_stats,
            'factor_importance': factor_importance,
            'factor_cols': factor_cols,
        }


if __name__ == '__main__':
    import json

    os.makedirs('output', exist_ok=True)

    strategy = RegimeAwareStrategy()
    result = strategy.run_backtest_preparation('20240101', '20260320')

    signals = result['signals']
    print(f"\nTotal signals generated: {len(signals)}")
    if not signals.empty:
        print(signals.head(10))

    print("\nRegime stats:")
    print(json.dumps(result['regime_stats'], indent=2))

    if result.get('factor_importance'):
        print("\nTop 10 factors:")
        for f, imp in list(result['factor_importance'].items())[:10]:
            print(f"  {f}: {imp:.4f}")

    # Save signals
    if not signals.empty:
        signals.to_csv('output/regime_aware_signals.csv', index=False)
        print("\nSignals saved to output/regime_aware_signals.csv")
