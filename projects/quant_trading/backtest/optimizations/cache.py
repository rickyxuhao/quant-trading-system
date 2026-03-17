"""
缓存优化模块

提供多级缓存机制，优化数据加载和计算性能。
"""

import pickle
import hashlib
import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器

    提供内存缓存和磁盘缓存两级缓存机制。

    Example:
        >>> cache = CacheManager(memory_size=1000, disk_path="./cache")
        >>> cache.set("key", value)
        >>> value = cache.get("key")
    """

    def __init__(
        self,
        memory_size: int = 1000,
        disk_path: Optional[str] = None,
        ttl_seconds: int = 3600,
    ):
        """初始化缓存管理器

        Args:
            memory_size: 内存缓存最大条目数
            disk_path: 磁盘缓存路径
            ttl_seconds: 缓存过期时间（秒）
        """
        self.memory_size = memory_size
        self.disk_path = Path(disk_path) if disk_path else None
        self.ttl_seconds = ttl_seconds

        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: list = []
        self._lock = threading.Lock()

        if self.disk_path:
            self.disk_path.mkdir(parents=True, exist_ok=True)

    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_expired(self, timestamp: datetime) -> bool:
        """检查是否过期"""
        return (datetime.now() - timestamp).total_seconds() > self.ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在或过期返回None
        """
        with self._lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]

                if self._is_expired(entry["timestamp"]):
                    del self._memory_cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)
                    return None

                # 更新访问顺序
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)

                logger.debug(f"Memory cache hit: {key}")
                return entry["value"]

        # 尝试从磁盘缓存获取
        if self.disk_path:
            disk_file = self.disk_path / f"{key}.pkl"
            if disk_file.exists():
                try:
                    with open(disk_file, "rb") as f:
                        entry = pickle.load(f)

                    if not self._is_expired(entry["timestamp"]):
                        # 加载到内存
                        self.set(key, entry["value"])
                        logger.debug(f"Disk cache hit: {key}")
                        return entry["value"]
                    else:
                        disk_file.unlink()  # 删除过期文件

                except Exception as e:
                    logger.warning(f"Failed to load disk cache: {e}")

        return None

    def set(self, key: str, value: Any):
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            # 检查是否需要淘汰
            if len(self._memory_cache) >= self.memory_size and key not in self._memory_cache:
                self._evict_lru()

            self._memory_cache[key] = {
                "value": value,
                "timestamp": datetime.now(),
            }

            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

        # 写入磁盘缓存
        if self.disk_path:
            try:
                disk_file = self.disk_path / f"{key}.pkl"
                with open(disk_file, "wb") as f:
                    pickle.dump(
                        {
                            "value": value,
                            "timestamp": datetime.now(),
                        },
                        f,
                    )
            except Exception as e:
                logger.warning(f"Failed to write disk cache: {e}")

    def _evict_lru(self):
        """淘汰最久未使用的缓存"""
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._memory_cache:
                del self._memory_cache[oldest_key]
                logger.debug(f"Cache evicted: {oldest_key}")

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._memory_cache.clear()
            self._access_order.clear()

        if self.disk_path:
            for file in self.disk_path.glob("*.pkl"):
                try:
                    file.unlink()
                except Exception:
                    pass

        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            memory_entries = len(self._memory_cache)

        disk_entries = 0
        if self.disk_path:
            disk_entries = len(list(self.disk_path.glob("*.pkl")))

        return {
            "memory_entries": memory_entries,
            "memory_size": self.memory_size,
            "disk_entries": disk_entries,
            "ttl_seconds": self.ttl_seconds,
        }


# 全局缓存实例
_global_cache: Optional[CacheManager] = None


def get_global_cache() -> CacheManager:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache


def cached(
    key_func: Optional[Callable] = None,
    ttl_seconds: int = 3600,
    cache: Optional[CacheManager] = None,
):
    """缓存装饰器

    Args:
        key_func: 自定义缓存键生成函数
        ttl_seconds: 缓存过期时间
        cache: 自定义缓存管理器

    Example:
        >>> @cached()
        ... def expensive_function(x, y):
        ...     return x + y
    """

    def decorator(func: Callable) -> Callable:
        _cache = cache or get_global_cache()

        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _cache._generate_key(func.__name__, *args, **kwargs)

            # 尝试获取缓存
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = func(*args, **kwargs)

            # 保存到缓存
            _cache.set(cache_key, result)

            return result

        return wrapper

    return decorator
