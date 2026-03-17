"""
茅台-五粮液配对交易策略

标的：
- 600519.SH（贵州茅台）
- 000858.SZ（五粮液）

数据区间：2019-2024年
"""

from datetime import datetime

import pandas as pd

from core.logger import get_logger
from projects.quant_trading.strategies.base_strategy import BaseStrategy, StrategyConfig

from .cointegration import CointegrationTester
from .position_sizer import PairPositionSizer, PositionConfig
from .signal_generator import Signal, SignalConfig, SpreadSignalGenerator

logger = get_logger(__name__)


class MaotaiWuliangStrategy(BaseStrategy):
    """
    茅台-五粮液配对交易策略
    """

    params = (
        ("maotai_code", "600519.SH"),
        ("wuliang_code", "000858.SZ"),
        ("lookback", 60),
        ("entry_threshold", 2.0),
        ("exit_threshold", 0.5),
        ("stop_threshold", 3.5),
        ("position_pct", 0.1),
    )

    def __init__(self):
        super().__init__()

        # 信号生成器
        self.signal_config = SignalConfig(
            entry_threshold=self.p.entry_threshold,
            exit_threshold=self.p.exit_threshold,
            stop_threshold=self.p.stop_threshold,
            lookback_window=self.p.lookback,
        )
        self.signal_generator = SpreadSignalGenerator(self.signal_config)

        # 仓位管理器
        self.position_config = PositionConfig(
            max_position_pct=self.p.position_pct,
            use_staged_exit=True,
            use_trailing_stop=True,
        )
        self.position_sizer = PairPositionSizer(self.position_config)

        # 协整检验器
        self.coint_tester = CointegrationTester()

        # 数据引用
        self.maotai = self.datas[0]
        self.wuliang = self.datas[1]

        # 状态变量
        self.spread_history = []
        self.hedge_ratio = None
        self.position_open_price = None
        self.position_high_watermark = 0
        self.days_in_position = 0
        self.current_signal = Signal.NO_SIGNAL

        # 历史价格存储（用于协整检验）
        self.price_history_maotai = []
        self.price_history_wuliang = []

    def next(self):
        """核心交易逻辑"""
        # 更新历史价格
        self.price_history_maotai.append(self.maotai.close[0])
        self.price_history_wuliang.append(self.wuliang.close[0])

        # 数据不足时跳过
        if len(self.price_history_maotai) < self.p.lookback:
            return

        # 保持历史价格在合理长度
        max_history = self.p.lookback * 2
        if len(self.price_history_maotai) > max_history:
            self.price_history_maotai = self.price_history_maotai[-max_history:]
            self.price_history_wuliang = self.price_history_wuliang[-max_history:]

        # 计算协整关系和对冲比例
        if self.hedge_ratio is None or len(self.price_history_maotai) % 20 == 0:
            self._update_hedge_ratio()

        if self.hedge_ratio is None:
            return

        # 计算价差
        spread = self.maotai.close[0] - self.hedge_ratio * self.wuliang.close[0]
        self.spread_history.append(spread)

        # 获取当前持仓状态
        pos_maotai = self.getposition(self.maotai)
        pos_wuliang = self.getposition(self.wuliang)

        has_position = pos_maotai.size != 0 or pos_wuliang.size != 0

        # 计算ADF p值（用于动态监测）
        adf_pvalue = None
        if len(self.spread_history) >= self.p.lookback:
            try:
                _, adf_pvalue, _, _, _, _ = self._quick_adf_test(
                    self.spread_history[-self.p.lookback :]
                )
            except:
                pass

        # 生成交易信号
        signal = self.signal_generator.generate_signal(
            spread, adf_pvalue=adf_pvalue, timestamp=self.maotai.datetime.date(0)
        )

        # 执行交易
        if signal == Signal.LONG_SPREAD and not has_position:
            self._enter_long_spread()
        elif signal == Signal.SHORT_SPREAD and not has_position:
            self._enter_short_spread()
        elif signal == Signal.CLOSE_POSITION and has_position:
            self._close_position("信号平仓")

        # 更新持仓状态
        if has_position:
            self.days_in_position += 1
            self._check_risk_controls()

    def _update_hedge_ratio(self):
        """更新对冲比例"""
        try:
            maotai_series = pd.Series(self.price_history_maotai)
            wuliang_series = pd.Series(self.price_history_wuliang)

            result = self.coint_tester.test_pair(maotai_series, wuliang_series)

            if result.is_cointegrated:
                self.hedge_ratio = result.hedge_ratio
                self.log(f"协整检验通过: β={self.hedge_ratio:.3f}, p={result.adf_pvalue:.4f}")
            else:
                self.hedge_ratio = maotai_series.mean() / wuliang_series.mean()
                self.log(f"协整检验未通过(p={result.adf_pvalue:.4f})，使用均值比作为β")
        except Exception as e:
            logger.error(f"更新对冲比例失败: {e}")
            self.hedge_ratio = 1.0

    def _quick_adf_test(self, series):
        """快速ADF检验"""
        from statsmodels.tsa.stattools import adfuller

        return adfuller(series, autolag="AIC")

    def _enter_long_spread(self):
        """做多价差：买入茅台，卖出五粮液"""
        if not self.is_trading_allowed():
            return

        # 计算仓位
        capital = self.broker.getvalue()
        shares_maotai, shares_wuliang = self.position_sizer.calculate_position_sizes(
            capital=capital,
            price_a=self.maotai.close[0],
            price_b=self.wuliang.close[0],
            hedge_ratio=self.hedge_ratio or 1.0,
        )

        if shares_maotai > 0 and shares_wuliang > 0:
            self.buy(data=self.maotai, size=shares_maotai)
            self.sell(data=self.wuliang, size=shares_wuliang)

            self.position_open_price = (
                self.maotai.close[0] - self.hedge_ratio * self.wuliang.close[0]
            )
            self.position_high_watermark = self.position_open_price
            self.days_in_position = 0
            self.current_signal = Signal.LONG_SPREAD

            self.log(
                f"做多价差: 买入茅台{shares_maotai}股 @ {self.maotai.close[0]:.2f}, "
                f"卖出五粮液{shares_wuliang}股 @ {self.wuliang.close[0]:.2f}"
            )

    def _enter_short_spread(self):
        """做空价差：卖出茅台，买入五粮液"""
        if not self.is_trading_allowed():
            return

        # 计算仓位
        capital = self.broker.getvalue()
        shares_maotai, shares_wuliang = self.position_sizer.calculate_position_sizes(
            capital=capital,
            price_a=self.maotai.close[0],
            price_b=self.wuliang.close[0],
            hedge_ratio=self.hedge_ratio or 1.0,
        )

        if shares_maotai > 0 and shares_wuliang > 0:
            self.sell(data=self.maotai, size=shares_maotai)
            self.buy(data=self.wuliang, size=shares_wuliang)

            self.position_open_price = (
                self.maotai.close[0] - self.hedge_ratio * self.wuliang.close[0]
            )
            self.position_high_watermark = self.position_open_price
            self.days_in_position = 0
            self.current_signal = Signal.SHORT_SPREAD

            self.log(
                f"做空价差: 卖出茅台{shares_maotai}股 @ {self.maotai.close[0]:.2f}, "
                f"买入五粮液{shares_wuliang}股 @ {self.wuliang.close[0]:.2f}"
            )

    def _close_position(self, reason: str = ""):
        """平仓"""
        pos_maotai = self.getposition(self.maotai)
        pos_wuliang = self.getposition(self.wuliang)

        if pos_maotai.size != 0:
            self.close(data=self.maotai)
        if pos_wuliang.size != 0:
            self.close(data=self.wuliang)

        self.position_open_price = None
        self.position_high_watermark = 0
        self.days_in_position = 0
        self.current_signal = Signal.NO_SIGNAL

        self.log(f"平仓: {reason}")

    def _check_risk_controls(self):
        """风险控制检查"""
        if self.position_open_price is None:
            return

        current_spread = self.maotai.close[0] - self.hedge_ratio * self.wuliang.close[0]

        # 计算盈亏
        if self.current_signal == Signal.LONG_SPREAD:
            profit_pct = (current_spread - self.position_open_price) / abs(self.position_open_price)
        else:
            profit_pct = (self.position_open_price - current_spread) / abs(self.position_open_price)

        # 更新最高水位
        if profit_pct > self.position_high_watermark:
            self.position_high_watermark = profit_pct

        # 分级止盈检查
        exit_size, reason = self.position_sizer.check_staged_exit(
            entry_price=self.position_open_price,
            current_price=current_spread,
            position_size=abs(self.getposition(self.maotai).size),
            days_held=self.days_in_position,
        )

        if exit_size:
            self._close_position(f"{reason}")
            return

        # 移动止盈检查
        if profit_pct >= self.position_config.trailing_activation:
            drawdown = self.position_high_watermark - profit_pct
            if drawdown >= self.position_config.trailing_drawdown:
                self._close_position(f"移动止盈: 回撤{drawdown:.1%}")
                return

        # 回撤控制
        self.update_drawdown()
        if not self.is_trading_allowed():
            self._close_position("回撤控制平仓")

    def stop(self):
        """策略结束"""
        # 强制平仓
        self._close_position("策略结束")

        # 输出统计
        total_value = self.broker.getvalue()
        pnl = total_value - self.config.initial_capital
        pnl_pct = pnl / self.config.initial_capital

        self.log(f"策略结束 - 最终资金: {total_value:.2f}, 盈亏: {pnl:.2f} ({pnl_pct:.2%})")


def run_backtest(
    maotai_data,
    wuliang_data,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 1_000_000,
):
    """
    运行回测

    Args:
        maotai_data: 茅台数据DataFeed
        wuliang_data: 五粮液数据DataFeed
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金

    Returns:
        Cerebro回测结果
    """
    from projects.quant_trading.strategies.base_strategy import create_cerebro

    config = StrategyConfig(
        initial_capital=initial_capital,
        commission_rate=0.00025,
        stamp_duty_rate=0.001,
        slippage=0.0005,
        max_drawdown_pct=0.15,
    )

    cerebro = create_cerebro(config)

    # 添加数据
    cerebro.adddata(maotai_data, name="maotai")
    cerebro.adddata(wuliang_data, name="wuliang")

    # 添加策略
    cerebro.addstrategy(MaotaiWuliangStrategy, config=config)

    # 运行回测
    results = cerebro.run()

    return results[0], cerebro


if __name__ == "__main__":
    # 示例运行代码
    print("茅台-五粮液配对交易策略")
    print("使用前请确保已通过Tushare获取数据")
