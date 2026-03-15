"""
数据同步引擎
整合调度器、任务管理和执行
使用注册模式管理任务类型
"""
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path

from core.data_sync.scheduler import TaskScheduler
from core.data_sync.task import SyncTask
from core.data_sync.logger import SyncLogger
from core.data_sync.tasks import TaskRegistry


class DataSyncEngine:
    """数据同步引擎"""

    def __init__(self, config_path: str = None):
        self.scheduler = TaskScheduler()
        self.config_path = config_path
        self.tasks_config = []

        if config_path:
            self._load_config(config_path)

    def _load_config(self, path: str):
        """加载配置文件"""
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self.tasks_config = config.get('tasks', [])
        self._register_tasks_from_config()

    def _register_tasks_from_config(self):
        """从配置注册任务"""
        for task_config in self.tasks_config:
            task = self._create_task_from_config(task_config)
            if task:
                deps = task_config.get('depends_on', [])
                self.scheduler.register_task(task, deps)

    def _create_task_from_config(self, config: Dict) -> Optional[SyncTask]:
        """
        从配置创建任务
        使用注册模式替代硬编码 if-elif 链
        """
        task_type = config.get('task_type', 'custom')

        # 使用注册中心创建任务
        try:
            return TaskRegistry.create(task_type, config)
        except ValueError as e:
            if task_type == 'custom':
                print(f"警告: 任务 {config['name']} 是自定义类型，需要手动注册")
            else:
                print(f"错误: 无法创建任务 {config['name']}: {e}")
            return None

    def register_task_type(self, task_type: str, task_class: type):
        """
        注册自定义任务类型

        Args:
            task_type: 任务类型标识符
            task_class: 任务类
        """
        TaskRegistry.register(task_type, task_class)

    def register_task(self, task: SyncTask, depends_on: List[str] = None):
        """
        手动注册任务

        Args:
            task: 同步任务实例
            depends_on: 依赖的任务名称列表
        """
        self.scheduler.register_task(task, depends_on)

    def run_task(self, task_name: str) -> Dict[str, Any]:
        """
        执行单个任务

        Args:
            task_name: 任务名称

        Returns:
            执行结果
        """
        return self.scheduler.run_task(task_name)

    def run_all(self) -> List[Dict[str, Any]]:
        """
        执行所有任务

        Returns:
            所有任务执行结果
        """
        return self.scheduler.run_all()

    def list_tasks(self) -> List[Dict]:
        """列出所有任务"""
        return self.scheduler.list_tasks()

    def get_task_status(self, task_name: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.scheduler.get_task_status(task_name)

    def list_registered_task_types(self) -> List[str]:
        """列出所有已注册的任务类型"""
        return TaskRegistry.list_registered()

    def init_log_tables(self):
        """初始化日志表"""
        SyncLogger.init_tables()
        print("✅ 同步日志表已初始化")


# 便捷函数
def create_sync_engine(config_path: str = None) -> DataSyncEngine:
    """创建同步引擎实例"""
    return DataSyncEngine(config_path)
