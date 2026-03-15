"""
Tushare 同步任务

使用注册模式管理所有同步任务类型
"""
from typing import Type, Dict
from core.data_sync.task import SyncTask
from core.data_sync.tasks.base import BaseTushareTask
from core.data_sync.tasks.rate_limiter import RateLimiter
from core.data_sync.tasks.tushare_stock_basic import TushareStockBasicTask
from core.data_sync.tasks.tushare_trade_date import TushareTradeDateTask
from core.data_sync.tasks.tushare_stock_st_list import TushareStockStListTask
from core.data_sync.tasks.tushare_stock_dailymarketdata import TushareStockDailyMarketDataTask
from core.data_sync.tasks.tushare_stock_adjfactor import TushareStockAdjFactorTask


class TaskRegistry:
    """任务注册中心 - 使用注册模式管理任务类型"""

    _registry: Dict[str, Type[SyncTask]] = {}

    @classmethod
    def register(cls, task_type: str, task_class: Type[SyncTask]):
        """
        注册任务类型

        Args:
            task_type: 任务类型标识符
            task_class: 任务类
        """
        cls._registry[task_type] = task_class

    @classmethod
    def get(cls, task_type: str) -> Type[SyncTask]:
        """
        获取任务类

        Args:
            task_type: 任务类型标识符

        Returns:
            任务类

        Raises:
            ValueError: 如果任务类型未注册
        """
        if task_type not in cls._registry:
            raise ValueError(f"未注册的任务类型: {task_type}")
        return cls._registry[task_type]

    @classmethod
    def create(cls, task_type: str, config: dict) -> SyncTask:
        """
        创建任务实例

        Args:
            task_type: 任务类型标识符
            config: 任务配置

        Returns:
            任务实例
        """
        task_class = cls.get(task_type)

        # 提取通用参数
        batch_size = config.get('batch_size', 0)
        max_requests_per_minute = config.get('max_requests_per_minute', 500)
        check_after_sync = config.get('check_after_sync', True)
        name = config['name']

        # 创建任务实例
        return task_class(
            name=name,
            check_after_sync=check_after_sync,
            batch_size=batch_size,
            max_requests_per_minute=max_requests_per_minute
        )

    @classmethod
    def list_registered(cls) -> list:
        """列出所有已注册的任务类型"""
        return list(cls._registry.keys())


# 装饰器形式的注册函数
def register_task(task_type: str):
    """
    任务注册装饰器

    用法:
        @register_task('my_task')
        class MyTask(SyncTask):
            ...
    """
    def decorator(task_class: Type[SyncTask]) -> Type[SyncTask]:
        TaskRegistry.register(task_type, task_class)
        return task_class
    return decorator


# 自动注册所有内置任务
TaskRegistry.register('tushare_stock_basic', TushareStockBasicTask)
TaskRegistry.register('tushare_trade_date', TushareTradeDateTask)
TaskRegistry.register('tushare_stock_st_list', TushareStockStListTask)
TaskRegistry.register('tushare_stock_dailymarketdata', TushareStockDailyMarketDataTask)
TaskRegistry.register('tushare_stock_adjfactor', TushareStockAdjFactorTask)


__all__ = [
    # 注册相关
    'TaskRegistry',
    'register_task',
    # 基类
    'BaseTushareTask',
    # 限流器
    'RateLimiter',
    # 具体任务类
    'TushareStockBasicTask',
    'TushareTradeDateTask',
    'TushareStockStListTask',
    'TushareStockDailyMarketDataTask',
    'TushareStockAdjFactorTask',
]
