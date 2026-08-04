# 错误处理

> **Read based on task** - 实现错误处理相关功能时阅读

## 1. 错误码体系

### 1.1 错误码格式

```
EXXXX - 标准错误
  ├── E1xxx: 参数错误
  ├── E2xxx: 权限错误
  ├── E3xxx: 文件操作错误
  ├── E4xxx: 系统错误
  └── E5xxx: 业务规则错误

WXXXX - 警告码
IXXXX - 信息码
```

### 1.2 错误码定义

```python
class ErrorCode(Enum):
    # 参数错误 (1000-1999)
    INVALID_PARAMS = "E1001"
    MISSING_REQUIRED = "E1002"
    INVALID_TYPE = "E1003"
    INVALID_FORMAT = "E1004"
    PATH_TOO_LONG = "E1005"
    
    # 权限错误 (2000-2999)
    ACCESS_DENIED = "E2001"
    PERMISSION_DENIED = "E2002"
    SANDBOX_VIOLATION = "E2003"
    SENSITIVE_FILE = "E2004"
    
    # 文件操作错误 (3000-3999)
    FILE_NOT_FOUND = "E3001"
    FILE_ALREADY_EXISTS = "E3002"
    FILE_TOO_LARGE = "E3003"
    FILE_READ_ERROR = "E3004"
    FILE_WRITE_ERROR = "E3005"
    FILE_DELETE_ERROR = "E3006"
    ENCODING_ERROR = "E3007"
    
    # 系统错误 (4000-4999)
    INTERNAL_ERROR = "E4001"
    RESOURCE_EXHAUSTED = "E4002"
    TIMEOUT = "E4003"
    UNKNOWN = "E4999"
```

---

## 2. 标准错误响应

### 2.1 错误响应结构

```python
@dataclass
class ErrorResponse:
    code: str               # 错误码
    message: str            # 错误消息（用户友好）
    detail: str | None      # 详细信息（开发调试）
    request_id: str         # 请求ID
    retryable: bool         # 是否可重试
    suggested_action: str | None  # 建议操作
```

### 2.2 实现

```python
class ErrorResponseFactory:
    """错误响应工厂"""
    
    _ERROR_MESSAGES = {
        ErrorCode.INVALID_PARAMS: "参数格式不正确",
        ErrorCode.MISSING_REQUIRED: "缺少必要参数: {param}",
        ErrorCode.PATH_TOO_LONG: "路径过长，请缩短后重试",
        ErrorCode.FILE_NOT_FOUND: "文件不存在: {path}",
        ErrorCode.FILE_TOO_LARGE: "文件过大 ({size}MB)，限制为 {limit}MB",
        ErrorCode.ACCESS_DENIED: "无权访问该资源",
        ErrorCode.SANDBOX_VIOLATION: "路径超出允许范围",
        ErrorCode.INTERNAL_ERROR: "服务器内部错误",
        ErrorCode.TIMEOUT: "操作超时，请重试",
    }
    
    _RETRYABLE_CODES = {
        ErrorCode.RESOURCE_EXHAUSTED,
        ErrorCode.TIMEOUT,
    }
    
    @classmethod
    def create(
        cls,
        code: ErrorCode,
        request_id: str,
        **kwargs
    ) -> ErrorResponse:
        message = cls._ERROR_MESSAGES.get(code, "未知错误")
        if kwargs:
            message = message.format(**kwargs)
        
        return ErrorResponse(
            code=code.value,
            message=message,
            detail=kwargs.get("detail"),
            request_id=request_id,
            retryable=code in cls._RETRYABLE_CODES,
            suggested_action=cls._get_suggested_action(code),
        )
    
    @classmethod
    def _get_suggested_action(cls, code: ErrorCode) -> str | None:
        actions = {
            ErrorCode.FILE_NOT_FOUND: "检查文件路径是否正确",
            ErrorCode.ACCESS_DENIED: "联系管理员获取权限",
            ErrorCode.TIMEOUT: "稍后重试或联系管理员",
            ErrorCode.INVALID_PARAMS: "检查参数格式",
        }
        return actions.get(code)
```

---

## 3. 异常处理策略

### 3.1 异常分类

```python
# 业务异常 - 可预测，可处理
class BusinessError(Exception):
    def __init__(self, code: ErrorCode, message: str, **kwargs):
        self.code = code
        self.kwargs = kwargs
        super().__init__(message)

# 系统异常 - 不可预测，需记录
class SystemError(Exception):
    def __init__(self, message: str, cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)

# 安全异常 - 安全相关事件
class SecurityError(Exception):
    def __init__(self, message: str, severity: str = "medium"):
        self.severity = severity
        super().__init__(message)
```

### 3.2 处理流程

```python
async def handle_with_error_handling(
    handler: Callable,
    request_id: str,
    *args,
    **kwargs
) -> types.CallToolResult:
    """统一错误处理包装器"""
    
    try:
        result = await handler(*args, **kwargs)
        return result
        
    except BusinessError as e:
        # 业务异常 - 返回友好错误
        logger.warning(f"Business error: {e.code.value}", extra={
            "request_id": request_id,
            "error_code": e.code.value
        })
        error_resp = ErrorResponseFactory.create(e.code, request_id, **e.kwargs)
        return _to_tool_result(error_resp)
        
    except SecurityError as e:
        # 安全异常 - 告警+记录
        logger.error(f"Security incident: {e}", extra={
            "request_id": request_id,
            "severity": e.severity
        })
        await alert_system.notify(e)
        error_resp = ErrorResponseFactory.create(
            ErrorCode.ACCESS_DENIED, request_id
        )
        return _to_tool_result(error_resp)
        
    except Exception as e:
        # 未知异常 - 严格记录
        logger.exception(f"Unexpected error: {e}", extra={
            "request_id": request_id
        })
        error_resp = ErrorResponseFactory.create(
            ErrorCode.INTERNAL_ERROR, request_id,
            detail=str(e) if config.debug else None
        )
        return _to_tool_result(error_resp)
```

---

## 4. 重试机制

### 4.1 重试策略

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay: float = 1.0  # 秒
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retry_on: tuple[type[Exception], ...] = (TimeoutError, IOError)
```

### 4.2 实现

```python
import asyncio
import functools

def with_retry(config: RetryConfig):
    """重试装饰器"""
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retry_on as e:
                    last_exception = e
                    if attempt < config.max_attempts:
                        delay = min(
                            config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                            config.max_delay
                        )
                        logger.warning(
                            f"Retry {attempt}/{config.max_attempts} "
                            f"after error: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise
            
            raise last_exception
        return wrapper
    return decorator
```

### 4.3 使用示例

```python
@with_retry(RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    retry_on=(FileNotFoundError,)  # 示例
))
async def read_file_with_retry(path: str) -> bytes:
    """带重试的文件读取"""
    async with aiofiles.open(path, "rb") as f:
        return await f.read()
```

---

## 5. 超时控制

### 5.1 超时配置

```python
@dataclass
class TimeoutConfig:
    default_timeout: float = 30.0  # 秒
    per_operation: dict[str, float] = {
        "list_directory": 10.0,
        "read_file": 30.0,
        "write_file": 60.0,
        "search_files": 120.0,
    }
```

### 5.2 实现

```python
async def with_timeout(
    coro,
    operation: str,
    config: TimeoutConfig
):
    """带超时的协程执行"""
    timeout = config.per_operation.get(operation, config.default_timeout)
    
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise BusinessError(
            ErrorCode.TIMEOUT,
            f"操作 {operation} 超时 ({timeout}秒)"
        )
```

---

## 6. 优雅降级

### 6.1 降级策略

```python
class CircuitBreaker:
    """断路器模式"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed | open | half-open
    
    async def execute(self, func, fallback=None):
        """执行函数，失败时降级"""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            elif fallback:
                return fallback()
            else:
                raise CircuitOpenError()
        
        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            if self.state == "open" and fallback:
                return fallback()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self, error):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")
```

### 6.2 使用示例

```python
# 缓存降级
cache_breaker = CircuitBreaker(failure_threshold=3)

async def get_file_info_with_cache(path: str):
    try:
        return await cache_breaker.execute(
            lambda: cache.get(path) or fetch_file_info(path),
            fallback=lambda: fetch_file_info(path)  # 降级：绕过缓存
        )
    except CircuitOpenError:
        logger.warning("Cache circuit open, returning stale data")
        return get_stale_data(path)
```

---

## 7. 错误处理清单

### 7.1 必实现

- [x] 统一错误码体系
- [x] 标准错误响应格式
- [x] 业务异常与系统异常分离
- [x] 安全异常特殊处理
- [x] 可重试错误标记

### 7.2 推荐实现

- [x] 自动重试机制
- [x] 断路器模式
- [x] 超时控制
- [x] 优雅降级
- [x] 错误聚合统计
