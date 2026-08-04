import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Optional, TypeVar
from threading import Lock

from .logger import get_logger

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""

    value: T
    mtime: float  # 文件修改时间
    created_at: float = field(default_factory=time.time)
    ttl: Optional[float] = None  # 秒，None表示永不过期
    size: int = 0  # 字节数，用于统计

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def is_stale(self, current_mtime: float) -> bool:
        """检查文件是否已修改"""
        return self.mtime != current_mtime


class LRUCache(Generic[T]):
    """线程安全的LRU缓存

    支持：
    - LRU淘汰策略
    - 基于文件修改时间自动失效
    - TTL过期
    - 最大条目数限制
    - 最大内存大小限制
    """

    def __init__(
        self,
        max_items: int = 1000,
        max_size: int = 100 * 1024 * 1024,  # 100MB
        default_ttl: Optional[float] = None,
    ):
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_items = max_items
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._current_size = 0
        self._lock = Lock()
        self._logger = get_logger("cache")

        # 统计
        self._hits = 0
        self._misses = 0

    def get(self, key: str, current_mtime: Optional[float] = None) -> Optional[T]:
        """获取缓存值

        Args:
            key: 缓存键
            current_mtime: 当前文件修改时间，用于检查缓存是否失效

        Returns:
            缓存值，如果未命中或已失效则返回None
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # 检查TTL过期
            if entry.is_expired():
                self._evict(key)
                self._misses += 1
                return None

            # 检查文件修改时间
            if current_mtime is not None and entry.is_stale(current_mtime):
                self._evict(key)
                self._misses += 1
                return None

            # LRU: 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: T,
        mtime: float,
        size: int = 0,
        ttl: Optional[float] = None,
    ) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            mtime: 文件修改时间
            size: 值的字节大小
            ttl: 过期时间（秒），None使用默认值
        """
        with self._lock:
            # 如果已存在，先删除
            if key in self._cache:
                self._evict(key)

            # 检查是否需要淘汰
            while (
                len(self._cache) >= self._max_items
                or self._current_size + size > self._max_size
            ):
                if not self._cache:
                    break
                # LRU: 删除最久未使用
                oldest_key = next(iter(self._cache))
                self._evict(oldest_key)

            # 添加新条目
            entry = CacheEntry(
                value=value,
                mtime=mtime,
                ttl=ttl if ttl is not None else self._default_ttl,
                size=size,
            )
            self._cache[key] = entry
            self._current_size += size
            self._cache.move_to_end(key)

    def invalidate(self, key: str) -> bool:
        """手动失效缓存"""
        with self._lock:
            if key in self._cache:
                self._evict(key)
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """批量失效匹配模式的缓存"""
        import fnmatch

        with self._lock:
            keys_to_delete = [
                k for k in self._cache if fnmatch.fnmatch(k, pattern)
            ]
            for key in keys_to_delete:
                self._evict(key)
            return len(keys_to_delete)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._current_size = 0

    def _evict(self, key: str) -> None:
        """内部删除方法（需在锁内调用）"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size -= entry.size

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests * 100 if total_requests > 0 else 0

            return {
                "items": len(self._cache),
                "max_items": self._max_items,
                "size_bytes": self._current_size,
                "max_size_bytes": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
            }

    def warmup(self, items: Dict[str, tuple]) -> None:
        """缓存预热

        Args:
            items: {key: (value, mtime, size)} 字典
        """
        for key, (value, mtime, size) in items.items():
            self.set(key, value, mtime, size)


class FileCacheManager:
    """文件缓存管理器

    管理两类缓存：
    1. 文件元数据缓存（stat信息）
    2. 文件内容缓存
    """

    def __init__(
        self,
        max_metadata_items: int = 2000,
        max_content_items: int = 500,
        max_content_size: int = 50 * 1024 * 1024,  # 50MB
        default_content_ttl: float = 300,  # 5分钟
    ):
        self._metadata_cache = LRUCache[Dict[str, Any]](
            max_items=max_metadata_items,
            max_size=0,  # 元数据不计大小
        )
        self._content_cache = LRUCache[str](
            max_items=max_content_items,
            max_size=max_content_size,
            default_ttl=default_content_ttl,
        )
        self._logger = get_logger("cache")

    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """获取文件元数据缓存"""
        try:
            mtime = Path(path).stat().st_mtime
            return self._metadata_cache.get(path, mtime)
        except OSError:
            return None

    def set_metadata(self, path: str, metadata: Dict[str, Any]) -> None:
        """设置文件元数据缓存"""
        try:
            mtime = Path(path).stat().st_mtime
            self._metadata_cache.set(path, metadata, mtime)
        except OSError:
            pass

    def get_content(self, path: str) -> Optional[str]:
        """获取文件内容缓存"""
        try:
            stat = Path(path).stat()
            mtime = stat.st_mtime
            cached = self._content_cache.get(path, mtime)
            return cached
        except OSError:
            return None

    def set_content(self, path: str, content: str) -> None:
        """设置文件内容缓存"""
        try:
            stat = Path(path).stat()
            mtime = stat.st_mtime
            size = len(content.encode("utf-8"))
            self._content_cache.set(path, content, mtime, size)
        except OSError:
            pass

    def invalidate(self, path: str) -> None:
        """失效指定路径的所有缓存"""
        self._metadata_cache.invalidate(path)
        self._content_cache.invalidate(path)

    def invalidate_pattern(self, pattern: str) -> Dict[str, int]:
        """批量失效匹配模式的缓存"""
        return {
            "metadata": self._metadata_cache.invalidate_pattern(pattern),
            "content": self._content_cache.invalidate_pattern(pattern),
        }

    def clear(self) -> None:
        """清空所有缓存"""
        self._metadata_cache.clear()
        self._content_cache.clear()

    def stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存统计"""
        return {
            "metadata": self._metadata_cache.stats(),
            "content": self._content_cache.stats(),
        }


_instances: Dict[str, FileCacheManager] = {}


def get_cache_manager(
    max_content_size: int = 50 * 1024 * 1024,
) -> FileCacheManager:
    """获取缓存管理器单例"""
    key = str(max_content_size)
    if key not in _instances:
        _instances[key] = FileCacheManager(max_content_size=max_content_size)
    return _instances[key]