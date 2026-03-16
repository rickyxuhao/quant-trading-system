"""
自定义Backtrader分析器

扩展Backtrader的分析能力，提供：
- Calmar比率
- Sortino比率
- 交易明细分析
- 模型预测分析
- 收益归因

参考：
- Calmar Ratio: https://en.wikipedia.org/wiki/Calmar_ratio
- Sortino Ratio: https://en.wikipedia.org/wiki/Sortino_ratio
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import defaultdict

import pandas as pd
import numpy as np
import backtrader as bt

from core.logger import get_logger

logger = get_logger(__name__)


class CalmarRatio(bt.Analyzer):
    """
    Calmar比率分析器

    Calmar比率 = 年化收益率 / 最大回撤

    用于评估风险调整后的收益，与Sharpe比率类似但使用最大回撤而非波动率作为风险度量。

    Attributes:
        calmar_ratio: Calmar比率值
        annual_return: 年化收益率
        max_drawdown: 最大回撤

    Example:
        >>> cerebro.addanalyzer(CalmarRatio, _name='calmar')
        >>> results = cerebro.run()
        >>> calmar = results[0].analyzers.calmar.get_analysis()
    """

    params = (
        ('timeframe', bt.TimeFrame.Days),
        ('compression', 1),
        ('period', None),  # None表示使用全部数据
        ('risk_free_rate', 0.02),  # 无风险利率
    )

    def __init__(self):
        super().__init__()
        self._returns: List[float] = []
        self._values: List[float] = []
        self._dates: List[datetime] = []
        self._max_drawdown: float = 0.0
        self._peak: float = 0.0

    def start(self):
        """开始分析"""
        super().start()
        self._returns = []
        self._values = [self.strategy.broker.getvalue()]
        self._dates = [self.strategy.datetime.datetime()]
        self._peak = self._values[0]
        self._max_drawdown = 0.0

    def next(self):
        """每个bar调用"""
        current_value = self.strategy.broker.getvalue()
        current_date = self.strategy.datetime.datetime()

        # 计算收益
        if self._values:
            ret = (current_value - self._values[-1]) / self._values[-1] \
                  if self._values[-1] != 0 else 0
            self._returns.append(ret)

        self._values.append(current_value)
        self._dates.append(current_date)

        # 更新最大回撤
        if current_value > self._peak:
            self._peak = current_value

        if self._peak > 0:
            drawdown = (self._peak - current_value) / self._peak
            self._max_drawdown = max(self._max_drawdown, drawdown)

    def stop(self):
        """分析结束"""
        super().stop()
        self.rets._calmar_ratio = self._calculate_calmar()
        self.rets._annual_return = self._calculate_annual_return()
        self.rets._max_drawdown = self._max_drawdown

    def _calculate_annual_return(self) -> float:
        """计算年化收益率"""
        if len(self._values) < 2:
            return 0.0

        total_return = (self._values[-1] - self._values[0]) / self._values[0]
        days = (self._dates[-1] - self._dates[0]).days

        if days <= 0:
            return 0.0

        # 年化
        annual_return = (1 + total_return) ** (365 / days) - 1
        return annual_return

    def _calculate_calmar(self) -> float:
        """计算Calmar比率"""
        annual_return = self._calculate_annual_return()

        if self._max_drawdown <= 0:
            return float('inf') if annual_return > 0 else 0.0

        return annual_return / self._max_drawdown

    def get_analysis(self) -> Dict[str, float]:
        """获取分析结果"""
        return {
            'calmar_ratio': self.rets._calmar_ratio,
            'annual_return': self.rets._annual_return,
            'max_drawdown': self.rets._max_drawdown,
        }


class SortinoRatio(bt.Analyzer):
    """
    Sortino比率分析器

    Sortino比率 = (年化收益率 - 目标收益率) / 下行标准差

    与Sharpe比率类似，但只考虑下行风险（负收益），更适合评估有偏分布的收益。

    Attributes:
        sortino_ratio: Sortino比率值
        annual_return: 年化收益率
        downside_std: 下行标准差（年化）

    Example:
        >>> cerebro.addanalyzer(SortinoRatio, _name='sortino', target_return=0.02)
        >>> results = cerebro.run()
        >>> sortino = results[0].analyzers.sortino.get_analysis()
    """

    params = (
        ('timeframe', bt.TimeFrame.Days),
        ('compression', 1),
        ('target_return', 0.0),  # 目标/最低可接受收益率
        ('risk_free_rate', 0.02),
    )

    def __init__(self):
        super().__init__()
        self._returns: List[float] = []
        self._dates: List[datetime] = []

    def start(self):
        """开始分析"""
        super().start()
        self._returns = []
        self._dates = []

    def next(self):
        """每个bar调用"""
        current_value = self.strategy.broker.getvalue()
        current_date = self.strategy.datetime.datetime()

        if len(self._returns) == 0:
            # 第一个值，记录但不计算收益
            pass
        else:
            # 计算收益率
            prev_value = self.strategy.broker.getvalue() / (1 + 0)  # 简化处理
            ret = (current_value - prev_value) / prev_value if prev_value != 0 else 0
            self._returns.append(ret)

        self._dates.append(current_date)

    def stop(self):
        """分析结束"""
        super().stop()

        # 从策略获取收益率数据（更准确）
        if hasattr(self.strategy, '_rets'):
            self._returns = list(self.strategy._rets)

        self.rets._sortino_ratio = self._calculate_sortino()
        self.rets._annual_return = self._calculate_annual_return()
        self.rets._downside_std = self._calculate_downside_std()

    def _calculate_downside_std(self) -> float:
        """计算下行标准差（年化）"""
        if not self._returns:
            return 0.0

        # 只考虑低于目标收益的收益率
        downside_returns = [r for r in self._returns if r < self.p.target_return]

        if not downside_returns:
            return 0.0

        # 计算下行标准差
        downside_variance = sum((r - self.p.target_return) ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = np.sqrt(downside_variance)

        # 年化（假设日收益，乘以sqrt(252)）
        annual_downside_std = downside_std * np.sqrt(252)

        return annual_downside_std

    def _calculate_annual_return(self) -> float:
        """计算年化收益率"""
        if not self._returns:
            return 0.0

        # 累积收益率
        total_return = np.prod([1 + r for r in self._returns]) - 1
        n_periods = len(self._returns)

        # 年化
        if n_periods > 0:
            annual_return = (1 + total_return) ** (252 / n_periods) - 1
        else:
            annual_return = 0.0

        return annual_return

    def _calculate_sortino(self) -> float:
        """计算Sortino比率"""
        annual_return = self._calculate_annual_return()
        downside_std = self._calculate_downside_std()

        if downside_std <= 0:
            return float('inf') if annual_return > self.p.target_return else 0.0

        return (annual_return - self.p.target_return) / downside_std

    def get_analysis(self) -> Dict[str, float]:
        """获取分析结果"""
        return {
            'sortino_ratio': self.rets._sortino_ratio,
            'annual_return': self.rets._annual_return,
            'downside_std': self.rets._downside_std,
            'target_return': self.p.target_return,
        }


class TradeDetailAnalyzer(bt.Analyzer):
    """
    交易明细分析器

    记录每笔交易的详细信息，支持后续分析。

    记录字段：
    - entry_date: 入场日期
    - exit_date: 出场日期
    - entry_price: 入场价格
    - exit_price: 出场价格
    - size: 交易数量
    - pnl: 盈亏金额
    - pnl_pct: 盈亏比例
    - holding_days: 持仓天数
    - exit_reason: 出场原因

    Example:
        >>> cerebro.addanalyzer(TradeDetailAnalyzer, _name='trade_details')
        >>> results = cerebro.run()
        >>> trades = results[0].analyzers.trade_details.get_analysis()
    """

    def __init__(self):
        super().__init__()
        self._trades: List[Dict[str, Any]] = []
        self._open_trades: Dict[Any, Dict[str, Any]] = {}

    def notify_trade(self, trade):
        """交易通知"""
        if trade.justopened:
            # 新开仓
            self._open_trades[trade.ref] = {
                'entry_date': self.strategy.datetime.datetime(),
                'entry_price': trade.price,
                'size': trade.size,
                'data_name': trade.data._name,
            }

        elif trade.isclosed:
            # 平仓
            open_trade = self._open_trades.pop(trade.ref, {})

            if open_trade:
                entry_date = open_trade.get('entry_date')
                exit_date = self.strategy.datetime.datetime()

                holding_days = (exit_date - entry_date).days if entry_date else 0

                pnl = trade.pnlcomm
                entry_price = open_trade.get('entry_price', 0)
                pnl_pct = (pnl / (entry_price * abs(open_trade.get('size', 0)))) \
                          if entry_price and open_trade.get('size') else 0

                trade_detail = {
                    'entry_date': entry_date,
                    'exit_date': exit_date,
                    'entry_price': entry_price,
                    'exit_price': trade.price,
                    'size': open_trade.get('size', 0),
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'data_name': open_trade.get('data_name', ''),
                    'exit_reason': getattr(trade, 'exit_reason', 'unknown'),
                }

                self._trades.append(trade_detail)

    def stop(self):
        """分析结束"""
        super().stop()
        self.rets._trades = self._trades

    def get_analysis(self) -> pd.DataFrame:
        """获取分析结果（DataFrame格式）"""
        if not self._trades:
            return pd.DataFrame()

        return pd.DataFrame(self._trades)

    def get_summary(self) -> Dict[str, Any]:
        """获取交易摘要统计"""
        if not self._trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'avg_holding_days': 0.0,
            }

        df = self.get_analysis()

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        return {
            'total_trades': len(df),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(df) if len(df) > 0 else 0.0,
            'avg_pnl': df['pnl'].mean(),
            'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0.0,
            'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0.0,
            'total_pnl': df['pnl'].sum(),
            'avg_holding_days': df['holding_days'].mean(),
            'max_holding_days': df['holding_days'].max(),
            'min_holding_days': df['holding_days'].min(),
        }


class ModelPredictionAnalyzer(bt.Analyzer):
    """
    模型预测分析器

    记录模型预测值与实际值的对比，用于评估模型性能。

    记录字段：
    - date: 日期
    - predicted: 预测值
    - actual: 实际值
    - signal: 交易信号
    - confidence: 置信度

    Example:
        >>> cerebro.addanalyzer(ModelPredictionAnalyzer, _name='predictions')
        >>> # 在策略中调用记录
        >>> self.analyzers.predictions.record_prediction(predicted=1.05, actual=1.03, signal='BUY')
        >>> results = cerebro.run()
        >>> predictions = results[0].analyzers.predictions.get_analysis()
    """

    def __init__(self):
        super().__init__()
        self._predictions: List[Dict[str, Any]] = []

    def start(self):
        """开始分析"""
        super().start()
        self._predictions = []

    def record_prediction(
        self,
        predicted: float,
        actual: Optional[float] = None,
        signal: str = '',
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录预测

        在策略中调用此方法记录预测。

        Args:
            predicted: 预测值
            actual: 实际值（如果已知）
            signal: 交易信号
            confidence: 置信度
            metadata: 额外元数据
        """
        prediction = {
            'date': self.strategy.datetime.datetime(),
            'predicted': predicted,
            'actual': actual,
            'signal': signal,
            'confidence': confidence,
            'metadata': metadata or {},
        }
        self._predictions.append(prediction)

    def stop(self):
        """分析结束"""
        super().stop()
        self.rets._predictions = self._predictions
        self.rets._accuracy = self._calculate_accuracy()
        self.rets._directional_accuracy = self._calculate_directional_accuracy()

    def _calculate_accuracy(self) -> float:
        """计算预测准确度（MSE归一化）"""
        if not self._predictions:
            return 0.0

        valid_predictions = [p for p in self._predictions if p['actual'] is not None]

        if not valid_predictions:
            return 0.0

        # 计算均方误差
        mse = sum((p['predicted'] - p['actual']) ** 2 for p in valid_predictions) / len(valid_predictions)

        # 归一化（简化处理）
        return 1 / (1 + mse)  # 越接近1表示越准确

    def _calculate_directional_accuracy(self) -> float:
        """计算方向预测准确度"""
        if not self._predictions:
            return 0.0

        valid_predictions = [p for p in self._predictions if p['actual'] is not None]

        if len(valid_predictions) < 2:
            return 0.0

        correct = 0
        total = 0

        for i in range(1, len(valid_predictions)):
            pred_direction = 1 if valid_predictions[i]['predicted'] > valid_predictions[i-1]['predicted'] else -1
            actual_direction = 1 if valid_predictions[i]['actual'] > valid_predictions[i-1]['actual'] else -1

            if pred_direction == actual_direction:
                correct += 1
            total += 1

        return correct / total if total > 0 else 0.0

    def get_analysis(self) -> pd.DataFrame:
        """获取分析结果（DataFrame格式）"""
        if not self._predictions:
            return pd.DataFrame()

        return pd.DataFrame(self._predictions)

    def get_summary(self) -> Dict[str, Any]:
        """获取预测摘要"""
        return {
            'total_predictions': len(self._predictions),
            'accuracy': self.rets._accuracy,
            'directional_accuracy': self.rets._directional_accuracy,
        }


class ReturnAttribution(bt.Analyzer):
    """
    收益归因分析器

    分析各因子/资产对组合收益的贡献度。

    Example:
        >>> cerebro.addanalyzer(ReturnAttribution, _name='attribution')
        >>> results = cerebro.run()
        >>> attribution = results[0].analyzers.attribution.get_analysis()
    """

    params = (
        ('factors', []),  # 因子名称列表
    )

    def __init__(self):
        super().__init__()
        self._returns: Dict[str, List[float]] = defaultdict(list)
        self._dates: List[datetime] = []
        self._factor_exposures: Dict[str, List[float]] = defaultdict(list)

    def start(self):
        """开始分析"""
        super().start()
        self._returns = defaultdict(list)
        self._dates = []
        self._factor_exposures = defaultdict(list)

    def record_factor_exposure(self, factor: str, exposure: float):
        """
        记录因子暴露

        Args:
            factor: 因子名称
            exposure: 暴露值
        """
        self._factor_exposures[factor].append(exposure)

    def record_return(self, source: str, ret: float):
        """
        记录收益来源

        Args:
            source: 收益来源（如资产名称、因子名称）
            ret: 收益贡献
        """
        self._returns[source].append(ret)

    def next(self):
        """每个bar调用"""
        self._dates.append(self.strategy.datetime.datetime())

    def stop(self):
        """分析结束"""
        super().stop()
        self.rets._attribution = self._calculate_attribution()

    def _calculate_attribution(self) -> Dict[str, Dict[str, float]]:
        """计算收益归因"""
        attribution = {}

        for source, returns in self._returns.items():
            total_return = sum(returns)
            avg_return = np.mean(returns) if returns else 0.0
            std_return = np.std(returns) if returns else 0.0

            attribution[source] = {
                'total_return': total_return,
                'avg_return': avg_return,
                'std_return': std_return,
                'contribution_pct': 0.0,  # 将在后续计算
            }

        # 计算贡献比例
        total = sum(a['total_return'] for a in attribution.values())
        if total != 0:
            for source in attribution:
                attribution[source]['contribution_pct'] = attribution[source]['total_return'] / total

        return attribution

    def get_analysis(self) -> pd.DataFrame:
        """获取归因分析结果"""
        if not self.rets._attribution:
            return pd.DataFrame()

        return pd.DataFrame.from_dict(self.rets._attribution, orient='index')


class EnhancedTradeAnalyzer(bt.Analyzer):
    """
    增强版交易分析器

    扩展Backtrader内置的TradeAnalyzer，提供更多指标。

    新增指标：
    - 盈亏比 (Profit Factor)
    - 期望值 (Expected Value)
    - 连续盈亏次数
    - 最大单笔盈亏
    """

    def __init__(self):
        super().__init__()
        self._pnls: List[float] = []
        self._win_streak: int = 0
        self._loss_streak: int = 0
        self._max_win_streak: int = 0
        self._max_loss_streak: int = 0

    def notify_trade(self, trade):
        """交易通知"""
        if trade.isclosed:
            pnl = trade.pnlcomm
            self._pnls.append(pnl)

            # 更新连赢/连输
            if pnl > 0:
                self._win_streak += 1
                self._loss_streak = 0
                self._max_win_streak = max(self._max_win_streak, self._win_streak)
            else:
                self._loss_streak += 1
                self._win_streak = 0
                self._max_loss_streak = max(self._max_loss_streak, self._loss_streak)

    def stop(self):
        """分析结束"""
        super().stop()

        wins = [p for p in self._pnls if p > 0]
        losses = [p for p in self._pnls if p <= 0]

        # 盈亏比
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # 期望值
        win_rate = len(wins) / len(self._pnls) if self._pnls else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        expected_value = win_rate * avg_win + (1 - win_rate) * avg_loss

        self.rets._profit_factor = profit_factor
        self.rets._expected_value = expected_value
        self.rets._max_win_streak = self._max_win_streak
        self.rets._max_loss_streak = self._max_loss_streak
        self.rets._max_single_win = max(wins) if wins else 0
        self.rets._max_single_loss = min(losses) if losses else 0

    def get_analysis(self) -> Dict[str, Any]:
        """获取分析结果"""
        return {
            'profit_factor': getattr(self.rets, '_profit_factor', 0),
            'expected_value': getattr(self.rets, '_expected_value', 0),
            'max_win_streak': getattr(self.rets, '_max_win_streak', 0),
            'max_loss_streak': getattr(self.rets, '_max_loss_streak', 0),
            'max_single_win': getattr(self.rets, '_max_single_win', 0),
            'max_single_loss': getattr(self.rets, '_max_single_loss', 0),
        }


# 便捷函数
def add_all_analyzers(cerebro: bt.Cerebro):
    """
    添加所有自定义分析器到Cerebro

    Args:
        cerebro: Backtrader Cerebro实例
    """
    # 标准分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 自定义分析器
    cerebro.addanalyzer(CalmarRatio, _name='calmar')
    cerebro.addanalyzer(SortinoRatio, _name='sortino')
    cerebro.addanalyzer(TradeDetailAnalyzer, _name='trade_details')
    cerebro.addanalyzer(ModelPredictionAnalyzer, _name='predictions')
    cerebro.addanalyzer(EnhancedTradeAnalyzer, _name='enhanced_trades')

    logger.info("[add_all_analyzers] 已添加所有分析器")


def get_analyzer_results(result) -> Dict[str, Any]:
    """
    获取所有分析器结果

    Args:
        result: Backtrader回测结果

    Returns:
        分析结果字典
    """
    results = {}

    # 标准分析器
    if hasattr(result.analyzers, 'sharpe'):
        results['sharpe'] = result.analyzers.sharpe.get_analysis()
    if hasattr(result.analyzers, 'drawdown'):
        results['drawdown'] = result.analyzers.drawdown.get_analysis()
    if hasattr(result.analyzers, 'returns'):
        results['returns'] = result.analyzers.returns.get_analysis()
    if hasattr(result.analyzers, 'trades'):
        results['trades'] = result.analyzers.trades.get_analysis()

    # 自定义分析器
    if hasattr(result.analyzers, 'calmar'):
        results['calmar'] = result.analyzers.calmar.get_analysis()
    if hasattr(result.analyzers, 'sortino'):
        results['sortino'] = result.analyzers.sortino.get_analysis()
    if hasattr(result.analyzers, 'trade_details'):
        results['trade_details'] = result.analyzers.trade_details.get_analysis()
    if hasattr(result.analyzers, 'predictions'):
        results['predictions'] = result.analyzers.predictions.get_analysis()
    if hasattr(result.analyzers, 'enhanced_trades'):
        results['enhanced_trades'] = result.analyzers.enhanced_trades.get_analysis()

    return results


if __name__ == "__main__":
    print("=== 自定义分析器模块 ===\n")
    print("可用分析器：")
    print("  - CalmarRatio: Calmar比率")
    print("  - SortinoRatio: Sortino比率")
    print("  - TradeDetailAnalyzer: 交易明细")
    print("  - ModelPredictionAnalyzer: 模型预测")
    print("  - ReturnAttribution: 收益归因")
    print("  - EnhancedTradeAnalyzer: 增强版交易分析")
