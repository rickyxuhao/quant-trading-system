"""
同步任务定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from core.data_sync.logger import SyncLogger


class SyncTask(ABC):
    """同步任务基类"""
    
    def __init__(self, name: str, table_name: str, db_name: str,
                 sync_type: str = "full", check_after_sync: bool = True):
        self.name = name
        self.table_name = table_name
        self.db_name = db_name
        self.sync_type = sync_type  # full 或 incremental
        self.check_after_sync = check_after_sync
    
    @abstractmethod
    def fetch_data(self) -> Any:
        """获取数据（从数据源）"""
        pass
    
    @abstractmethod
    def sync_to_db(self, data: Any) -> Dict[str, int]:
        """同步数据到数据库，返回统计信息"""
        pass
    
    def run(self) -> Dict[str, Any]:
        """
        执行同步任务
        
        Returns:
            同步结果
        """
        result = {
            "task_name": self.name,
            "table_name": self.table_name,
            "sync_type": self.sync_type,
            "status": "failed",
            "rows_affected": 0,
            "rows_inserted": 0,
            "rows_updated": 0,
            "error": None,
            "check_passed": None
        }
        
        # 记录开始日志
        log_id = SyncLogger.start_log(self.name, self.table_name, self.sync_type)
        sync_date = datetime.now().strftime("%Y%m%d")
        
        try:
            print(f"\n{'='*60}")
            print(f"执行任务: {self.name}")
            print(f"表名: {self.db_name}.{self.table_name}")
            print(f"类型: {self.sync_type}")
            print(f"{'='*60}")
            
            # 1. 获取数据
            print("📥 获取数据...")
            data = self.fetch_data()
            
            # 2. 同步到数据库
            print("📤 同步到数据库...")
            stats = self.sync_to_db(data)
            
            result["rows_affected"] = stats.get("affected", 0)
            result["rows_inserted"] = stats.get("inserted", 0)
            result["rows_updated"] = stats.get("updated", 0)
            result["status"] = "success"
            
            print(f"✅ 同步完成: 插入 {result['rows_inserted']}, 更新 {result['rows_updated']}")
            
            # 3. 数据质量检查
            if self.check_after_sync:
                print("🔍 执行数据质量检查...")
                check_result = self._run_data_check()
                result["check_passed"] = check_result
                
                if check_result:
                    print("✅ 数据检查通过")
                else:
                    print("⚠️ 数据检查未通过")
            
            # 更新状态
            SyncLogger.end_log(
                log_id, "success",
                result["rows_affected"],
                result["rows_inserted"],
                result["rows_updated"]
            )
            SyncLogger.update_state(
                self.name, self.table_name,
                success=True,
                total_rows=result["rows_affected"],
                sync_date=sync_date
            )
            
        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            result["status"] = "failed"
            
            print(f"❌ 同步失败: {error_msg}")
            
            SyncLogger.end_log(log_id, "failed", error_message=error_msg)
            SyncLogger.update_state(
                self.name, self.table_name,
                success=False,
                sync_date=sync_date
            )
        
        return result
    
    def _run_data_check(self) -> bool:
        """运行数据质量检查"""
        try:
            from core.data_quality.checker import DataQualityChecker
            
            # 查找对应的检查配置
            config_path = f"core/data_quality/config/{self.table_name}.yaml"
            
            import os
            if not os.path.exists(config_path):
                print(f"  警告: 未找到检查配置 {config_path}，跳过检查")
                return True
            
            checker = DataQualityChecker(config_path)
            check_result = checker.check()
            
            return check_result.is_valid
            
        except Exception as e:
            print(f"  检查过程出错: {e}")
            return False
