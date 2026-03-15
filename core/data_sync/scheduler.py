"""
同步调度器
管理任务依赖和执行顺序
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

from core.data_sync.task import SyncTask


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, SyncTask] = {}
        self.dependencies: Dict[str, List[str]] = {}  # task_name -> [依赖的任务名]
    
    def register_task(self, task: SyncTask, depends_on: List[str] = None):
        """
        注册任务
        
        Args:
            task: 同步任务
            depends_on: 依赖的任务名称列表
        """
        self.tasks[task.name] = task
        self.dependencies[task.name] = depends_on or []
    
    def run_task(self, task_name: str, executed: set = None) -> Dict[str, Any]:
        """
        执行单个任务（包括其依赖）
        
        Args:
            task_name: 任务名称
            executed: 已执行的任务集合（用于递归）
            
        Returns:
            执行结果
        """
        if executed is None:
            executed = set()
        
        # 检查循环依赖
        if task_name in executed:
            return {"status": "skipped", "reason": "already_executed"}
        
        if task_name not in self.tasks:
            return {"task_name": task_name, "status": "failed", "error": f"未知任务: {task_name}"}
        
        # 先执行依赖
        task = self.tasks[task_name]
        deps = self.dependencies.get(task_name, [])
        
        dep_results = []
        for dep_name in deps:
            print(f"  📋 依赖任务: {dep_name}")
            dep_result = self.run_task(dep_name, executed)
            dep_results.append(dep_result)
            
            # 如果依赖失败，当前任务也失败
            if dep_result.get("status") == "failed":
                return {
                    "status": "failed",
                    "error": f"依赖任务 {dep_name} 失败",
                    "task_name": task_name,
                    "dependency_results": dep_results
                }
        
        # 执行当前任务
        executed.add(task_name)
        result = task.run()
        result["dependencies"] = dep_results
        
        return result
    
    def run_all(self) -> List[Dict[str, Any]]:
        """
        执行所有任务（按依赖顺序）
        
        Returns:
            所有任务执行结果
        """
        print("\n" + "="*60)
        print("执行所有同步任务")
        print("="*60)
        
        # 拓扑排序确定执行顺序
        execution_order = self._topological_sort()
        
        results = []
        executed = set()
        
        for task_name in execution_order:
            result = self.run_task(task_name, executed)
            results.append(result)
            
            # 如果有严重失败，可以选择停止
            if result.get("status") == "failed":
                print(f"\n🚨 任务 {task_name} 失败，停止后续任务")
                break
        
        return results
    
    def _topological_sort(self) -> List[str]:
        """
        拓扑排序，确定任务执行顺序
        
        Returns:
            按依赖顺序排列的任务名称列表
        """
        # 计算入度
        in_degree = {name: 0 for name in self.tasks}
        for task_name, deps in self.dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[task_name] += 1
        
        # 找到入度为0的任务
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            # 按字母顺序执行（确保一致性）
            queue.sort()
            current = queue.pop(0)
            result.append(current)
            
            # 减少依赖当前任务的其他任务的入度
            for task_name, deps in self.dependencies.items():
                if current in deps:
                    in_degree[task_name] -= 1
                    if in_degree[task_name] == 0:
                        queue.append(task_name)
        
        # 检查是否有循环依赖
        if len(result) != len(self.tasks):
            remaining = set(self.tasks.keys()) - set(result)
            raise ValueError(f"存在循环依赖或无法解析的依赖: {remaining}")
        
        return result
    
    def get_task_status(self, task_name: str) -> Optional[Dict]:
        """获取任务状态"""
        from core.data_sync.logger import SyncLogger
        
        logs = SyncLogger.get_recent_logs(task_name, 1)
        if logs:
            log = logs[0]
            return {
                "task_name": task_name,
                "last_sync": log['start_time'],
                "status": log['status'],
                "rows": log.get('rows_affected', 0)
            }
        return None
    
    def list_tasks(self) -> List[Dict]:
        """列出所有任务及其状态"""
        tasks = []
        for name, task in self.tasks.items():
            status = self.get_task_status(name)
            tasks.append({
                "name": name,
                "table": task.table_name,
                "type": task.sync_type,
                "dependencies": self.dependencies.get(name, []),
                "status": status
            })
        return tasks
