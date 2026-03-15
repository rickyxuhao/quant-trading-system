"""
日志系统配置 - 使用 loguru
提供统一日志配置，支持控制台和文件双通道输出
"""
import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def init_logging(
    log_level: Optional[str] = None,
    log_dir: Optional[str] = None,
    console_output: bool = True,
    file_output: bool = True
) -> None:
    """
    初始化日志配置

    Args:
        log_level: 日志级别，默认从环境变量 LOG_LEVEL 读取，否则 INFO
        log_dir: 日志目录，默认 logs/
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
    """
    # 从环境变量读取配置
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_dir = log_dir or os.getenv("LOG_DIR", "logs")

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 统一日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 控制台输出
    if console_output:
        logger.add(
            sys.stdout,
            level=log_level,
            format=log_format,
            colorize=True
        )

    # 文件输出 - 按日期轮转，保留30天
    if file_output:
        logger.add(
            log_path / "app_{time:YYYY-MM-DD}.log",
            rotation="00:00",  # 每天午夜轮转
            retention="30 days",  # 保留30天
            compression="zip",  # 压缩旧日志
            level="DEBUG",
            encoding="utf-8",
            format=log_format
        )

    logger.debug(f"日志系统初始化完成，级别: {log_level}, 目录: {log_path.absolute()}")


def get_logger(name: Optional[str] = None):
    """
    获取 logger 实例

    Args:
        name: 模块名称，用于标识日志来源

    Returns:
        loguru logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger


# 便捷函数
def debug(message: str, **kwargs):
    """DEBUG 级别日志"""
    logger.debug(message, **kwargs)


def info(message: str, **kwargs):
    """INFO 级别日志"""
    logger.info(message, **kwargs)


def warning(message: str, **kwargs):
    """WARNING 级别日志"""
    logger.warning(message, **kwargs)


def error(message: str, **kwargs):
    """ERROR 级别日志"""
    logger.error(message, **kwargs)


def critical(message: str, **kwargs):
    """CRITICAL 级别日志"""
    logger.critical(message, **kwargs)


# 模块导入时自动初始化（如果环境变量设置了 AUTO_INIT_LOG）
if os.getenv("AUTO_INIT_LOG", "false").lower() == "true":
    init_logging()
