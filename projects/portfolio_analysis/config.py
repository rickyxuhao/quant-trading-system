"""
持仓分析系统配置

管理系统的配置参数，支持从环境变量和配置文件读取。

Example:
    >>> from projects.portfolio_analysis.config import Config
    >>> Config.RISK_FREE_RATE
    0.03
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


@dataclass
class Config:
    """配置类"""

    # 数据库配置
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME_INTERFACE: str = os.getenv("DB_NAME_INTERFACE", "interface")
    DB_NAME_TUSHARE: str = os.getenv("DB_NAME_TUSHARE", "tushare_biz")

    # Tushare配置
    TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")

    # 分析配置
    RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.03"))
    BENCHMARK_CODE: str = os.getenv("BENCHMARK_CODE", "000300.SH")
    TRADING_DAYS_PER_YEAR: int = int(os.getenv("TRADING_DAYS_PER_YEAR", "252"))

    # 风险阈值配置
    SINGLE_STOCK_LOSS_THRESHOLD: float = -0.15
    SECTOR_CONCENTRATION_THRESHOLD: float = 0.30
    DRAWDOWN_WARNING_THRESHOLD: float = -0.10
    DRAWDOWN_CRITICAL_THRESHOLD: float = -0.20
    SINGLE_STOCK_WEIGHT_WARNING: float = 0.15
    SINGLE_STOCK_WEIGHT_CRITICAL: float = 0.25

    # 报告配置
    REPORT_OUTPUT_DIR: str = os.getenv("REPORT_OUTPUT_DIR", "~/Documents/portfolio_reports")

    @classmethod
    def get_database_url(cls, db_name: str = "interface") -> str:
        """获取数据库连接URL

        Args:
            db_name: 数据库名称

        Returns:
            SQLAlchemy连接URL
        """
        database = cls.DB_NAME_INTERFACE if db_name == "interface" else cls.DB_NAME_TUSHARE
        return (
            f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{database}"
        )

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整

        Returns:
            配置是否有效
        """
        required = [
            cls.DB_PASSWORD,
            cls.TUSHARE_TOKEN,
        ]

        for value in required:
            if not value:
                return False

        return True


# 全局配置实例
config = Config()
