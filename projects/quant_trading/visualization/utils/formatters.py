"""格式化工具函数"""
from datetime import datetime, date
from typing import Union, Optional


def format_number(value: Union[int, float], precision: int = 2, prefix: str = "", suffix: str = "") -> str:
    """
    格式化数字

    Args:
        value: 数值
        precision: 小数精度
        prefix: 前缀
        suffix: 后缀

    Returns:
        格式化后的字符串
    """
    if value is None:
        return "N/A"

    formatted = f"{value:,.{precision}f}"
    return f"{prefix}{formatted}{suffix}"


def format_percentage(value: float, precision: int = 2, signed: bool = False) -> str:
    """
    格式化为百分比

    Args:
        value: 小数形式的数值（如0.15表示15%）
        precision: 小数精度
        signed: 是否显示正负号

    Returns:
        百分比字符串
    """
    if value is None:
        return "N/A"

    if signed:
        return f"{value * 100:+.{precision}f}%"
    return f"{value * 100:.{precision}f}%"


def format_currency(value: float, precision: int = 2, currency: str = "¥") -> str:
    """
    格式化为货币

    Args:
        value: 数值
        precision: 小数精度
        currency: 货币符号

    Returns:
        货币字符串
    """
    if value is None:
        return "N/A"

    return f"{currency}{value:,.{precision}f}"


def format_date(value: Union[datetime, date, str], format_str: str = "%Y-%m-%d") -> str:
    """
    格式化日期

    Args:
        value: 日期值
        format_str: 日期格式字符串

    Returns:
        格式化后的日期字符串
    """
    if value is None:
        return "N/A"

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return value

    return value.strftime(format_str)


def format_sharpe(value: float) -> str:
    """
    格式化夏普比率，添加颜色指示

    Args:
        value: 夏普比率值

    Returns:
        格式化字符串
    """
    if value is None:
        return "N/A"

    if value >= 2:
        return f"🟢 {value:.2f} (优秀)"
    elif value >= 1:
        return f"🟡 {value:.2f} (良好)"
    elif value >= 0:
        return f"🟠 {value:.2f} (一般)"
    else:
        return f"🔴 {value:.2f} (较差)"


def format_drawdown(value: float) -> str:
    """
    格式化回撤值，添加颜色指示

    Args:
        value: 回撤值（负数）

    Returns:
        格式化字符串
    """
    if value is None:
        return "N/A"

    abs_dd = abs(value)
    if abs_dd <= 0.1:
        return f"🟢 {value * 100:.2f}%"
    elif abs_dd <= 0.2:
        return f"🟡 {value * 100:.2f}%"
    elif abs_dd <= 0.3:
        return f"🟠 {value * 100:.2f}%"
    else:
        return f"🔴 {value * 100:.2f}%"


def format_duration(days: int) -> str:
    """
    格式化持续时间

    Args:
        days: 天数

    Returns:
        格式化字符串
    """
    if days is None or days < 0:
        return "N/A"

    years = days // 365
    remaining_days = days % 365
    months = remaining_days // 30
    remaining_days = remaining_days % 30

    parts = []
    if years > 0:
        parts.append(f"{years}年")
    if months > 0:
        parts.append(f"{months}月")
    if remaining_days > 0 or not parts:
        parts.append(f"{remaining_days}天")

    return "".join(parts)


def format_compact_number(value: float) -> str:
    """
    格式化为紧凑数字（K, M, B）

    Args:
        value: 数值

    Returns:
        紧凑格式字符串
    """
    if value is None:
        return "N/A"

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    if abs_value >= 1e9:
        return f"{sign}{abs_value/1e9:.2f}B"
    elif abs_value >= 1e6:
        return f"{sign}{abs_value/1e6:.2f}M"
    elif abs_value >= 1e3:
        return f"{sign}{abs_value/1e3:.2f}K"
    else:
        return f"{sign}{abs_value:.2f}"
