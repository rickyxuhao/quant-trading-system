"""
核心模块 - Quant Trading System Core

提供数据访问、存储、同步、质量检查等基础设施能力。
"""
import os

# 自动初始化日志（如果环境变量设置）
if os.getenv("AUTO_INIT_LOG", "true").lower() == "true":
    from core.logger import init_logging
    init_logging()

__version__ = "0.1.0"
__all__ = ["logger", "init_logging"]
