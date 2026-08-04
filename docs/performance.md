# 性能优化

> **Read based on task** - 实现性能优化功能时阅读

## 1. 异步处理

### 1.1 当前瓶颈

```python
# 当前问题: 同步文件IO阻塞事件循环
async def handle_read_file(arguments):
    with open(path, "r") as f:  # 阻塞！
        content = f.read()
```

### 1.2 异步IO改造

```python
import aiofiles

async def handle_read_file(arguments):
    # 使用aiofiles进行异步文件操作
    async with aiofiles.open(path, "r", encoding=encoding) as f:
        content = await f.read()
```

### 1.3 并发控制

```python
import asyncio

class FileOperationPool:
    """文件操作并发池"""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
    
    async def execute(self, coro):
        async with self.semaphore:
            self.active_count += 1
            try:
                return await coro
            finally:
                self.active_count -= 1
```

---

## 2. 缓存机制

### 2.1 缓存层级

```
请求 → L1 内存缓存 → L2 文件缓存 → 磁盘
         (命中快)      (命中较快)     (慢但可靠)
```

### 2.2 LRU缓存实现

```python
from collections import OrderedDict
import time

class LRUCache:
    """LRU缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: float = 300):
        self.max_size = max_size
        self.ttl = ttl  # 过期时间（秒）
        self._cache = OrderedDict()
        self._timestamps = {}
    
    def get(self, key: str):
        """获取缓存"""
        if key not in self._cache:
            return None
        
        # 检查过期
        ts = self._timestamps.get(key, 0)
        if time.time() - ts > self.ttl:
            self._remove(key)
            return None
        
        # 移动到最近使用
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def set(self, key: str, value, ttl: float | None = None):
        """设置缓存"""
        if key in self._cache:
            self._remove(key)
        
        # 容量检查
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # 删除最久未使用
        
        self._cache[key] = value
        self._timestamps[key] = time.time() + (ttl or self.ttl)
    
    def _remove(self, key: str):
        del self._cache[key]
        self._timestamps.pop(key, None)
    
    def invalidate(self, key: str):
        """失效缓存"""
        self._remove(key)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._timestamps.clear()
```

### 2.3 文件内容缓存

```python
class FileContentCache:
    """文件内容缓存（基于修改时间自动失效）"""
    
    def __init__(self, max_entries: int = 500):
        self._cache = LRUCache(max_size=max_entries)
        self._mtime_cache = {}
    
    def get(self, path: str) -> bytes | None:
        """获取文件缓存"""
        # 检查修改时间
        try:
            current_mtime = os.path.getmtime(path)
            cached_mtime = self._mtime_cache.get(path)
            
            if cached_mtime and current_mtime == cached_mtime:
                return self._cache.get(path)
            
            # 修改时间变化，失效缓存
            self.invalidate(path)
            self._mtime_cache[path] = current_mtime
        except OSError:
            pass
        
        return None
    
    def set(self, path: str, content: bytes):
        """缓存文件内容"""
        try:
            mtime = os.path.getmtime(path)
            self._mtime_cache[path] = mtime
            self._cache.set(path, content)
        except OSError:
            pass
    
    def invalidate(self, path: str):
        """失效缓存"""
        self._cache.invalidate(path)
        self._mtime_cache.pop(path, None)
```

### 2.4 缓存失效策略

```python
class CacheInvalidationStrategy:
    """缓存失效策略"""
    
    @staticmethod
    def on_file_change(path: str, event: str):
        """文件变更时失效缓存"""
        if event in ("modified", "deleted", "moved"):
            file_cache.invalidate(path)
            dir_cache.invalidate(os.path.dirname(path))
    
    @staticmethod
    def on_config_change():
        """配置变更时全量失效"""
        file_cache.clear()
        dir_cache.clear()
```

---

## 3. 批量操作

### 3.1 批量读取

```python
async def batch_read_files(paths: list[str], max_concurrent: int = 10):
    """批量读取文件"""
    sem = asyncio.Semaphore(max_concurrent)
    
    async def read_one(path):
        async with sem:
            try:
                async with aiofiles.open(path, "r") as f:
                    content = await f.read()
                return {"path": path, "content": content, "error": None}
            except Exception as e:
                return {"path": path, "content": None, "error": str(e)}
    
    tasks = [read_one(p) for p in paths]
    return await asyncio.gather(*tasks)
```

### 3.2 批量删除

```python
async def batch_delete_files(paths: list[str], confirm: bool = True):
    """批量删除文件"""
    results = {
        "success": [],
        "failed": [],
        "skipped": []
    }
    
    # 确认检查
    if confirm and len(paths) > 10:
        raise BusinessError(
            ErrorCode.DANGEROUS_OPERATION,
            f"批量删除 {len(paths)} 个文件需要确认"
        )
    
    for path in paths:
        try:
            os.remove(path)
            results["success"].append(path)
            # 触发缓存失效
            cache.invalidate(path)
        except FileNotFoundError:
            results["skipped"].append(path)
        except Exception as e:
            results["failed"].append({"path": path, "error": str(e)})
    
    return results
```

---

## 4. 大文件支持

### 4.1 分块读写

```python
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB

class ChunkedFileHandler:
    """分块文件处理器"""
    
    async def chunked_read(
        self,
        path: str,
        chunk_size: int = CHUNK_SIZE,
        progress_callback: Callable | None = None
    ) -> AsyncIterator[bytes]:
        """分块读取"""
        async with aiofiles.open(path, "rb") as f:
            total_read = 0
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                total_read += len(chunk)
                if progress_callback:
                    await progress_callback(total_read)
                yield chunk
    
    async def chunked_write(
        self,
        path: str,
        chunks: AsyncIterator[bytes],
        mode: str = "wb"
    ):
        """分块写入"""
        async with aiofiles.open(path, mode) as f:
            async for chunk in chunks:
                await f.write(chunk)
```

### 4.2 流式传输

```python
class StreamTransfer:
    """流式传输"""
    
    async def upload(
        self,
        local_path: str,
        remote_writer: Callable[[bytes], Awaitable[None]]
    ):
        """上传（本地 -> 远程）"""
        async for chunk in self.chunked_read(local_path):
            await remote_writer(chunk)
    
    async def download(
        self,
        remote_reader: Callable[[], Awaitable[bytes | None]],
        local_path: str
    ):
        """下载（远程 -> 本地）"""
        async with aiofiles.open(local_path, "wb") as f:
            while True:
                chunk = await remote_reader()
                if not chunk:
                    break
                await f.write(chunk)
```

### 4.3 断点续传

```python
class ResumableTransfer:
    """可断点续传的传输"""
    
    def __init__(self, progress_file: str = ".transfer_progress"):
        self.progress_file = progress_file
    
    def save_progress(self, transfer_id: str, bytes_transferred: int):
        """保存进度"""
        progress = self._load_progress()
        progress[transfer_id] = {
            "bytes_transferred": bytes_transferred,
            "timestamp": time.time()
        }
        self._save_progress(progress)
    
    def load_progress(self, transfer_id: str) -> int:
        """加载进度"""
        progress = self._load_progress()
        return progress.get(transfer_id, {}).get("bytes_transferred", 0)
    
    def resume_upload(self, local_path: str, transfer_id: str, writer):
        """续传"""
        start_from = self.load_progress(transfer_id)
        with open(local_path, "rb") as f:
            f.seek(start_from)
            while chunk := f.read(CHUNK_SIZE):
                writer(chunk)
                start_from += len(chunk)
                self.save_progress(transfer_id, start_from)
```

---

## 5. 性能指标

### 5.1 目标指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 单次响应时间 | >100ms | <50ms (缓存命中) |
| 并发支持 | 1 | 50+ |
| 最大文件 | 10MB | 1GB+ |
| 缓存命中率 | 0% | 70%+ |

### 5.2 监控点

```python
class PerformanceMonitor:
    """性能监控"""
    
    async def track_operation(self, operation: str, duration: float):
        """记录操作耗时"""
        await self._db.execute(
            "INSERT INTO metrics (operation, duration_ms, timestamp) VALUES (?, ?, ?)",
            (operation, duration * 1000, datetime.now())
        )
    
    async def get_stats(self, hours: int = 24) -> dict:
        """获取性能统计"""
        # 查询平均耗时、P95耗时、调用次数
        return await self._db.fetch_all(
            "SELECT operation, AVG(duration_ms) as avg_ms, "
            "PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_ms, "
            "COUNT(*) as total_calls "
            "FROM metrics WHERE timestamp > ? "
            "GROUP BY operation",
            (datetime.now() - timedelta(hours=hours),)
        )
```
