# 日志系统

> **Read based on task** - 实现日志相关功能时阅读

## 1. 分级日志

### 1.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 函数入口、参数值、中间状态 |
| INFO | 业务流程 | 请求开始/结束、关键状态变更 |
| WARN | 警告信息 | 非预期但可恢复的异常 |
| ERROR | 错误信息 | 操作失败、需要关注的问题 |
| CRITICAL | 严重错误 | 系统不可用、数据丢失 |

### 1.2 配置示例

```yaml
# config/logging.yaml
logging:
  level: INFO  # 生产环境默认INFO
  
  levels:
    development: DEBUG
    testing: DEBUG
    staging: INFO
    production: WARNING
  
  modules:
    # 可按模块单独设置级别
    security: DEBUG  # 安全模块详细日志
    performance: WARNING  # 性能模块精简日志
```

---

## 2. 结构化日志

### 2.1 日志格式

```python
@dataclass
class LogEntry:
    timestamp: str          # ISO 8601 时间
    level: str               # 日志级别
    service: str             # 服务名称
    module: str              # 模块名
    request_id: str | None   # 请求追踪ID
    message: str             # 日志消息
    data: dict | None        # 附加数据
    stack_trace: str | None  # 错误堆栈
```

### 2.2 JSON输出格式

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "service": "filesystem-mcp",
  "module": "handlers.file",
  "request_id": "req-abc-123",
  "message": "File read successfully",
  "data": {
    "path": "/workspace/test.txt",
    "size": 1024,
    "duration_ms": 15
  }
}
```

### 2.3 实现

```python
import json
import logging
from datetime import datetime, timezone
from contextvars import ContextVar

request_id_var = ContextVar("request_id", default=None)

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "filesystem-mcp",
            "module": record.module,
            "request_id": request_id_var.get(),
            "message": record.getMessage(),
        }
        
        # 附加数据
        if hasattr(record, "data"):
            entry["data"] = record.data
        
        # 错误堆栈
        if record.exc_info:
            entry["stack_trace"] = self.formatException(record.exc_info)
        
        return json.dumps(entry, ensure_ascii=False)
```

---

## 3. 日志轮转

### 3.1 轮转策略

```python
class RotationConfig:
    """日志轮转配置"""
    
    # 按大小轮转
    max_bytes: int = 100 * 1024 * 1024  # 100MB
    
    # 按时间轮转
    when: str = "midnight"  # 每天午夜
    interval: int = 1
    
    # 保留策略
    backup_count: int = 30  # 保留30天
    
    # 压缩
    compress: bool = True
    encoding: str = "utf-8"
```

### 3.2 配置示例

```yaml
logging:
  rotation:
    # 二选一或组合使用
    strategy: combined  # size | time | combined
    
    max_size_mb: 100
    rotation_time: "00:00"  # 每天零点
    retention_days: 30
    compress: true
```

### 3.3 实现

```python
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

def create_file_handler(config: RotationConfig) -> logging.Handler:
    """创建轮转文件处理器"""
    
    if config.strategy == "size":
        handler = RotatingFileHandler(
            filename=config.path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding=config.encoding
        )
    elif config.strategy == "time":
        handler = TimedRotatingFileHandler(
            filename=config.path,
            when="midnight",
            interval=config.interval,
            backupCount=config.backup_count,
            encoding=config.encoding
        )
    else:  # combined
        # 使用自定义处理器
        handler = CombinedRotatingHandler(config)
    
    return handler
```

---

## 4. 日志持久化

### 4.1 存储方案

```python
class LogStorage:
    """日志存储抽象"""
    
    async def save(self, entry: LogEntry) -> None:
        """存储单条日志"""
        raise NotImplementedError
    
    async def batch_save(self, entries: list[LogEntry]) -> None:
        """批量存储"""
        raise NotImplementedError
    
    async def query(self, filters: dict) -> list[LogEntry]:
        """查询日志"""
        raise NotImplementedError
```

### 4.2 本地文件存储

```python
class FileLogStorage(LogStorage):
    """文件日志存储"""
    
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def save(self, entry: LogEntry) -> None:
        # 按日期分文件
        filename = f"app-{entry.timestamp[:10]}.log"
        filepath = self.log_dir / filename
        
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)
```

### 4.3 SQLite存储（可选）

```python
class SQLiteLogStorage(LogStorage):
    """SQLite日志存储"""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL,
        module TEXT,
        request_id TEXT,
        message TEXT NOT NULL,
        data TEXT,
        stack_trace TEXT
    );
    CREATE INDEX idx_logs_timestamp ON logs(timestamp);
    CREATE INDEX idx_logs_level ON logs(level);
    CREATE INDEX idx_logs_request_id ON logs(request_id);
    """
    
    async def save(self, entry: LogEntry) -> None:
        await self._db.execute(
            "INSERT INTO logs (timestamp, level, module, request_id, message, data) VALUES (?, ?, ?, ?, ?, ?)",
            (entry.timestamp, entry.level, entry.module, entry.request_id, 
             entry.message, json.dumps(entry.data) if entry.data else None)
        )
```

---

## 5. 日志使用规范

### 5.1 何时记录

| 场景 | 级别 | 说明 |
|------|------|------|
| 请求开始/结束 | INFO | 记录请求ID、耗时 |
| 成功操作 | INFO | 记录关键结果 |
| 参数验证失败 | DEBUG | 调试信息 |
| 可恢复错误 | WARN | 重试、降级等 |
| 操作失败 | ERROR | 业务异常 |
| 系统异常 | CRITICAL | 需立即处理 |

### 5.2 日志内容

```python
# GOOD: 包含足够上下文
logger.info("File operation completed", extra={
    "request_id": req_id,
    "operation": "write_file",
    "path": target_path,
    "size": content_length,
    "duration_ms": elapsed,
    "user_id": user.id
})

# BAD: 信息不足
logger.info("Done")

# BAD: 包含敏感信息
logger.debug(f"Password: {password}")
```

### 5.3 性能考虑

```python
# 延迟格式化
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Large data: {expensive_serialize(data)}")

# 避免在循环中记录
for item in large_list:
    # WRONG: 每条都记录
    logger.debug(f"Processing item: {item}")

# 应改为: 批量或采样记录
logger.debug(f"Processing batch of {len(large_list)} items")
```

---

## 6. 日志配置示例

```python
# config/logging.py

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": StructuredFormatter,
        },
        "simple": {
            "format": "%(asctime)s [%(levelname)s] %(module)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "structured",
            "filename": "logs/app.log",
            "maxBytes": 104857600,  # 100MB
            "backupCount": 30,
            "encoding": "utf-8"
        }
    },
    "loggers": {
        "filesystem_mcp": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "filesystem_mcp.security": {
            "level": "DEBUG",
            "handlers": ["file"],
            "propagate": False
        }
    }
}
```
