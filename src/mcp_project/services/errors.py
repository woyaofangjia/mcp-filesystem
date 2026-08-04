import asyncio
import time
from enum import IntEnum
from typing import Any, Callable, Dict, Optional, Type

from mcp import types

from .logger import get_logger


class ErrorCode(IntEnum):
    """标准化错误码

    1xxx - 参数/验证错误
    2xxx - 安全/权限错误
    3xxx - IO/文件错误
    4xxx - 系统/内部错误
    """

    # 参数错误 (1000-1999)
    INVALID_PARAMS = 1001
    MISSING_PARAMS = 1002
    INVALID_PATH = 1003
    INVALID_ENCODING = 1004

    # 安全错误 (2000-2999)
    PATH_TRAVERSAL = 2001
    PERMISSION_DENIED = 2002
    SENSITIVE_FILE = 2003
    SANDBOX_VIOLATION = 2004
    UNAUTHENTICATED = 2005

    # IO错误 (3000-3999)
    FILE_NOT_FOUND = 3001
    FILE_ALREADY_EXISTS = 3002
    FILE_TOO_LARGE = 3003
    READ_ERROR = 3004
    WRITE_ERROR = 3005
    ENCODING_ERROR = 3006

    # 系统错误 (4000-4999)
    INTERNAL_ERROR = 4001
    TIMEOUT = 4002
    RESOURCE_EXHAUSTED = 4003
    UNKNOWN_TOOL = 4004


ERROR_MESSAGES: Dict[ErrorCode, str] = {
    ErrorCode.INVALID_PARAMS: "参数无效",
    ErrorCode.MISSING_PARAMS: "缺少必要参数",
    ErrorCode.INVALID_PATH: "路径格式无效",
    ErrorCode.INVALID_ENCODING: "编码不支持",
    ErrorCode.PATH_TRAVERSAL: "路径遍历攻击被阻止",
    ErrorCode.PERMISSION_DENIED: "权限不足",
    ErrorCode.SENSITIVE_FILE: "禁止访问敏感文件",
    ErrorCode.SANDBOX_VIOLATION: "路径超出沙箱范围",
    ErrorCode.UNAUTHENTICATED: "未认证",
    ErrorCode.FILE_NOT_FOUND: "文件不存在",
    ErrorCode.FILE_ALREADY_EXISTS: "文件已存在",
    ErrorCode.FILE_TOO_LARGE: "文件过大",
    ErrorCode.READ_ERROR: "读取文件失败",
    ErrorCode.WRITE_ERROR: "写入文件失败",
    ErrorCode.ENCODING_ERROR: "编码错误",
    ErrorCode.INTERNAL_ERROR: "内部错误",
    ErrorCode.TIMEOUT: "操作超时",
    ErrorCode.RESOURCE_EXHAUSTED: "资源耗尽",
    ErrorCode.UNKNOWN_TOOL: "未知工具",
}


class MCPError(Exception):
    """结构化MCP错误"""

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        detail: Optional[str] = None,
        trace_id: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.detail = detail
        self.trace_id = trace_id
        self.suggestion = suggestion
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result

    def to_text(self) -> str:
        parts = [f"E{self.code:04d}: {self.message}"]
        if self.detail:
            parts.append(f"  详情: {self.detail}")
        if self.suggestion:
            parts.append(f"  建议: {self.suggestion}")
        return "\n".join(parts)


def error_result(error: MCPError) -> types.CallToolResult:
    """将MCPError转换为CallToolResult"""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=error.to_text())],
        isError=True,
    )


def with_retry(
    func: Callable[..., Any],
    max_retries: int = 3,
    retry_delay: float = 0.5,
    retryable_exceptions: Optional[tuple] = None,
) -> Callable[..., Any]:
    """重试装饰器

    对IO/网络错误自动重试，使用指数退避。
    """
    if retryable_exceptions is None:
        retryable_exceptions = (
            IOError,
            OSError,
            ConnectionError,
            TimeoutError,
        )

    logger = get_logger("filesystem-mcp")

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "操作重试",
                        {
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "重试耗尽",
                        {"attempts": max_retries, "error": str(e)},
                    )
        raise last_exception  # type: ignore[misc]

    return wrapper


def with_timeout(
    func: Callable[..., Any],
    timeout: float = 30.0,
) -> Callable[..., Any]:
    """超时控制装饰器

    超时时间可配置，超时后抛出MCPError。
    """
    logger = get_logger("filesystem-mcp")

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        try:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, lambda: func(*args, **kwargs))
            return loop.run_until_complete(
                asyncio.wait_for(future, timeout=timeout)
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            logger.error(
                "操作超时",
                {"timeout": timeout, "elapsed": elapsed},
            )
            raise MCPError(
                code=ErrorCode.TIMEOUT,
                detail=f"操作耗时 {elapsed:.2f}s，超过 {timeout}s 限制",
                suggestion="尝试减小操作范围或使用异步模式",
            )

    return wrapper


def classify_error(exception: Exception) -> ErrorCode:
    """将异常分类为错误码"""
    if isinstance(exception, MCPError):
        return exception.code
    if isinstance(exception, FileNotFoundError):
        return ErrorCode.FILE_NOT_FOUND
    if isinstance(exception, FileExistsError):
        return ErrorCode.FILE_ALREADY_EXISTS
    if isinstance(exception, PermissionError):
        return ErrorCode.PERMISSION_DENIED
    if isinstance(exception, IsADirectoryError):
        return ErrorCode.INVALID_PATH
    if isinstance(exception, NotADirectoryError):
        return ErrorCode.INVALID_PATH
    if isinstance(exception, UnicodeDecodeError):
        return ErrorCode.ENCODING_ERROR
    if isinstance(exception, UnicodeEncodeError):
        return ErrorCode.ENCODING_ERROR
    if isinstance(exception, OSError):
        return ErrorCode.READ_ERROR
    return ErrorCode.INTERNAL_ERROR
