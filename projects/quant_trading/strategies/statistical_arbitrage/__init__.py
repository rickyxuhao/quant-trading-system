"""
统计套利策略包 - 配对交易策略实现

包含模块：
- pair_selection: 配对筛选
- cointegration: 协整检验
- signal_generator: 信号生成
- position_sizer: 仓位管理
- maotai_wuliang_pair: 茅台-五粮液配对策略
"""

from .pair_selection import PairSelector, SelectionCriteria
from .cointegration import CointegrationTester
from .signal_generator import SpreadSignalGenerator
from .position_sizer import PairPositionSizer
from .maotai_wuliang_pair import MaotaiWuliangStrategy

__all__ = [
    "PairSelector",
    "SelectionCriteria",
    "CointegrationTester",
    "SpreadSignalGenerator",
    "PairPositionSizer",
    "MaotaiWuliangStrategy",
]
