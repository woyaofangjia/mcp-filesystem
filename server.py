#!/usr/bin/env python3
"""
文件系统MCP服务器 - V2.0 工业级版本
基于 MCP 2.0.0 协议，集成安全加固、日志、审计、错误处理
"""

import os
import sys
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.context import ServerRequestContext
from mcp import types

from src.mcp_project.services import (
    get_logger,
    get_audit_logger,
    get_sandbox,
    get_sensitive_guard,
    get_permission_manager,
    Role,
    ErrorCode,
    MCPError,
    error_result,
    classify_error,
)
from src.mcp_project.services.sandbox import SecurityError

# ============================================================
# 服务初始化
# ============================================================

APP_ROOT = os.getcwd()
LOG_DIR = os.path.join(APP_ROOT, "logs")

logger = get_logger("filesystem-mcp", level="INFO", log_dir=LOG_DIR)
audit = get_audit_logger(db_path=os.path.join(LOG_DIR, "audit.db"))
sandbox = get_sandbox(allowed_roots=[APP_ROOT])
sensitive_guard = get_sensitive_guard()
perm_manager = get_permission_manager(default_role=Role.ADMIN)

logger.info("服务初始化完成", {
    "app_root": APP_ROOT,
    "sandbox_roots": sandbox.roots,
    "log_dir": LOG_DIR,
})

# ============================================================
# MCP 服务器
# ============================================================

server = Server("filesystem-server")

# ============================================================
# 工具定义（V2.0 扩展）
# ============================================================

TOOLS = [
    types.Tool(
        name="list_directory",
        description="列出指定目录下的文件和文件夹",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（默认为当前目录）",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录",
                    "default": False,
                },
            },
        },
    ),
    types.Tool(
        name="read_file",
        description="读取文本文件的内容",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认为utf-8）",
                    "default": "utf-8",
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="write_file",
        description="创建或修改文本文件（危险操作，需二次确认）",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认为utf-8）",
                    "default": "utf-8",
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式：a=追加，w=覆盖（默认）",
                    "default": "w",
                    "enum": ["w", "a"],
                },
            },
            "required": ["path", "content"],
        },
    ),
    types.Tool(
        name="delete_file",
        description="删除文件（危险操作，需二次确认）",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件或目录路径"},
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归删除目录",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="get_file_info",
        description="获取文件的详细信息",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="search_files",
        description="在目录中搜索文件",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "搜索目录（默认为当前目录）",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（支持通配符 * 和 ?）",
                },
                "search_text": {
                    "type": "string",
                    "description": "搜索文件内容中的文本",
                },
            },
        },
    ),
    types.Tool(
        name="copy_file",
        description="复制文件或目录",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源路径"},
                "destination": {"type": "string", "description": "目标路径"},
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归复制目录",
                    "default": True,
                },
            },
            "required": ["source", "destination"],
        },
    ),
    types.Tool(
        name="move_file",
        description="移动或重命名文件/目录",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        },
    ),
]

# ============================================================
# 请求路由
# ============================================================


async def handle_list_tools(
    ctx: ServerRequestContext, params: Any
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def handle_call_tool(
    ctx: ServerRequestContext, params: types.CallToolRequestParams
) -> types.CallToolResult:
    """统一工具调用入口，含安全校验和错误处理"""
    tool_name = params.name
    arguments = params.arguments or {}
    user_id = _get_user_id(ctx)
    start_time = time.time()

    try:
        # 1. 检查工具是否存在
        if not _tool_exists(tool_name):
            audit.log_failure(
                operation=tool_name,
                resource="",
                error=f"未知工具: {tool_name}",
                user_id=user_id,
            )
            return error_result(
                MCPError(
                    code=ErrorCode.UNKNOWN_TOOL,
                    detail=f"工具 '{tool_name}' 不存在",
                    suggestion=f"可用工具: {', '.join(t.name for t in TOOLS)}",
                )
            )

        # 2. 安全前置检查
        resource_paths = _extract_paths(tool_name, arguments)
        for path in resource_paths:
            try:
                sandbox.resolve(path)
                sensitive_guard.check(path)
            except SecurityError as e:
                audit.log_security_event(
                    operation=tool_name,
                    resource=path,
                    detail=str(e),
                    user_id=user_id,
                )
                return error_result(
                    MCPError(
                        code=ErrorCode.SANDBOX_VIOLATION,
                        detail=str(e),
                        suggestion="确保路径在允许的根目录内",
                    )
                )
            except MCPError as e:
                audit.log_security_event(
                    operation=tool_name,
                    resource=path,
                    detail=e.message,
                    user_id=user_id,
                )
                return error_result(e)
            except PermissionError as e:
                audit.log_security_event(
                    operation=tool_name,
                    resource=path,
                    detail=str(e),
                    user_id=user_id,
                )
                return error_result(
                    MCPError(code=ErrorCode.SENSITIVE_FILE, detail=str(e))
                )

        # 3. 权限检查
        action_map = {
            "list_directory": "read",
            "read_file": "read",
            "search_files": "read",
            "get_file_info": "read",
            "write_file": "write",
            "delete_file": "delete",
            "copy_file": "write",
            "move_file": "write",
        }
        action = action_map.get(tool_name, "read")
        for path in resource_paths:
            try:
                perm_manager.require_permission(user_id, action, path)
            except PermissionError as e:
                audit.log_security_event(
                    operation=tool_name,
                    resource=path,
                    detail=str(e),
                    user_id=user_id,
                )
                return error_result(
                    MCPError(code=ErrorCode.PERMISSION_DENIED, detail=str(e))
                )

        # 4. 路由到具体handler
        handlers = {
            "list_directory": handle_list_directory,
            "read_file": handle_read_file,
            "write_file": handle_write_file,
            "delete_file": handle_delete_file,
            "get_file_info": handle_get_file_info,
            "search_files": handle_search_files,
            "copy_file": handle_copy_file,
            "move_file": handle_move_file,
        }

        handler = handlers[tool_name]
        result = await handler(arguments)

        # 5. 记录成功审计
        elapsed_ms = int((time.time() - start_time) * 1000)
        resource = resource_paths[0] if resource_paths else ""
        audit.log_success(
            operation=tool_name,
            resource=resource,
            user_id=user_id,
            duration_ms=elapsed_ms,
        )

        return result

    except MCPError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        resource = resource_paths[0] if resource_paths else ""
        audit.log_failure(
            operation=tool_name,
            resource=resource,
            error=e.message,
            user_id=user_id,
            duration_ms=elapsed_ms,
        )
        return error_result(e)

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        resource = resource_paths[0] if resource_paths else ""
        logger.error(
            "未处理的异常",
            {"tool": tool_name, "error": str(e), "trace": _format_trace(e)},
        )
        audit.log_failure(
            operation=tool_name,
            resource=resource,
            error=str(e),
            user_id=user_id,
            duration_ms=elapsed_ms,
        )
        code = classify_error(e)
        return error_result(
            MCPError(code=code, message=str(e), detail=type(e).__name__)
        )


# ============================================================
# 辅助函数
# ============================================================


def _get_user_id(ctx: ServerRequestContext) -> str:
    """从请求上下文提取用户ID"""
    metadata = getattr(ctx, "metadata", None) or {}
    user_id = metadata.get("user_id", metadata.get("user", "system"))
    return str(user_id)


def _tool_exists(name: str) -> bool:
    """检查工具是否存在"""
    return any(t.name == name for t in TOOLS)


def _extract_paths(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """从参数中提取所有文件路径"""
    paths: List[str] = []
    for key in ("path", "source", "destination", "directory"):
        if key in args and args[key]:
            paths.append(str(args[key]))
    return paths


def _format_trace(e: Exception) -> str:
    """格式化异常堆栈"""
    import traceback

    return "".join(traceback.format_exception(type(e), e, e.__traceback__))


def _resolve_path(path: str) -> str:
    """安全解析路径（已在路由层通过沙箱校验）"""
    return sandbox.resolve(path)


def _read_text_file(file_path: Path, encoding: str = "utf-8") -> str:
    """读取文本文件，支持大小限制"""
    file_size = file_path.stat().st_size
    if file_size > 50 * 1024 * 1024:  # 50MB
        raise MCPError(
            code=ErrorCode.FILE_TOO_LARGE,
            detail=f"文件 {file_path} 大小 {file_size} 字节超过50MB限制",
            suggestion="使用分块读取或文件传输工具",
        )

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type and not mime_type.startswith("text"):
        raise MCPError(
            code=ErrorCode.INVALID_PARAMS,
            detail=f"文件 {file_path} 是二进制类型 ({mime_type})，无法以文本方式读取",
            suggestion="使用 get_file_info 查看二进制文件信息",
        )

    try:
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            return f.read()
    except UnicodeDecodeError:
        raise MCPError(
            code=ErrorCode.ENCODING_ERROR,
            detail=f"无法使用 {encoding} 编码读取文件 {file_path}",
            suggestion="尝试使用其他编码如 gbk、latin-1",
        )


# ============================================================
# 工具处理器
# ============================================================


async def handle_list_directory(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    path = arguments.get("path", ".")
    recursive = arguments.get("recursive", False)
    resolved = _resolve_path(path)

    path_obj = Path(resolved)
    if not path_obj.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"路径不存在: {path}")
    if not path_obj.is_dir():
        raise MCPError(
            ErrorCode.INVALID_PATH, detail=f"路径不是目录: {path}"
        )

    if recursive:
        files = []
        for root, dirs, filenames in os.walk(path_obj):
            level = root.replace(str(path_obj), "").count(os.sep)
            indent = "  " * level
            files.append(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for filename in filenames:
                files.append(f"{subindent}{filename}")
        result = "\n".join(files)
    else:
        items = []
        for item in sorted(path_obj.iterdir()):
            if item.is_dir():
                items.append(f"{item.name}/")
            else:
                items.append(item.name)
        result = "\n".join(items)

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text", text=f"目录: {path}\n\n{result}"
            )
        ]
    )


async def handle_read_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    path = arguments["path"]
    encoding = arguments.get("encoding", "utf-8")
    resolved = _resolve_path(path)

    path_obj = Path(resolved)
    if not path_obj.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {path}")
    if not path_obj.is_file():
        raise MCPError(
            ErrorCode.INVALID_PATH, detail=f"路径不是文件: {path}"
        )

    content = _read_text_file(path_obj, encoding)
    file_size = path_obj.stat().st_size

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"文件: {path}\n大小: {file_size} 字节\n\n{content}",
            )
        ]
    )


async def handle_write_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    path = arguments["path"]
    content = arguments["content"]
    encoding = arguments.get("encoding", "utf-8")
    mode = arguments.get("mode", "w")
    resolved = _resolve_path(path)

    path_obj = Path(resolved)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    write_mode = "a" if mode == "a" else "w"
    try:
        with open(path_obj, write_mode, encoding=encoding) as f:
            f.write(content)
    except OSError as e:
        raise MCPError(
            ErrorCode.WRITE_ERROR,
            detail=f"写入文件 {path} 失败: {e}",
            suggestion="检查磁盘空间和文件权限",
        )

    action = "追加到" if mode == "a" else "写入"
    file_size = path_obj.stat().st_size

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"成功{action}文件: {path}\n新文件大小: {file_size} 字节",
            )
        ]
    )


async def handle_delete_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    path = arguments["path"]
    recursive = arguments.get("recursive", False)
    resolved = _resolve_path(path)

    path_obj = Path(resolved)
    if not path_obj.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"路径不存在: {path}")

    try:
        if path_obj.is_file():
            path_obj.unlink()
        elif path_obj.is_dir():
            if recursive:
                import shutil

                shutil.rmtree(path_obj)
            else:
                raise MCPError(
                    ErrorCode.INVALID_PARAMS,
                    detail=f"路径是目录: {path}，设置 recursive=true 以删除",
                    suggestion="使用 recursive 参数删除目录",
                )
    except MCPError:
        raise
    except OSError as e:
        raise MCPError(
            ErrorCode.WRITE_ERROR,
            detail=f"删除 {path} 失败: {e}",
            suggestion="检查文件权限",
        )

    return types.CallToolResult(
        content=[
            types.TextContent(type="text", text=f"已删除: {path}")
        ]
    )


async def handle_get_file_info(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    path = arguments["path"]
    resolved = _resolve_path(path)

    path_obj = Path(resolved)
    if not path_obj.exists():
        raise MCPError(
            ErrorCode.FILE_NOT_FOUND,
            detail=f"文件/目录不存在: {path}",
        )

    stat_info = path_obj.stat()
    mime_type, file_encoding = mimetypes.guess_type(path)

    info = {
        "路径": str(path_obj),
        "类型": "目录" if path_obj.is_dir() else "文件",
        "大小": f"{stat_info.st_size} 字节",
        "创建时间": datetime.fromtimestamp(stat_info.st_ctime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "修改时间": datetime.fromtimestamp(stat_info.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "访问时间": datetime.fromtimestamp(stat_info.st_atime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "MIME类型": mime_type or "未知",
        "编码": file_encoding or "未知",
    }

    if path_obj.is_file():
        info["扩展名"] = path_obj.suffix
        info["文件名"] = path_obj.name

    info_text = "\n".join([f"{key}: {value}" for key, value in info.items()])

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=info_text)]
    )


async def handle_search_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    directory = arguments.get("directory", ".")
    pattern = arguments.get("pattern")
    search_text = arguments.get("search_text")
    resolved = _resolve_path(directory)

    dir_path = Path(resolved)
    if not dir_path.exists():
        raise MCPError(
            ErrorCode.FILE_NOT_FOUND,
            detail=f"目录不存在: {directory}",
        )
    if not dir_path.is_dir():
        raise MCPError(
            ErrorCode.INVALID_PATH,
            detail=f"路径不是目录: {directory}",
        )

    results: List[str] = []

    if pattern:
        search_pattern = pattern
        if "*" not in search_pattern and "?" not in search_pattern:
            search_pattern = f"*{search_pattern}*"

        glob_method = dir_path.rglob if "**" in search_pattern else dir_path.glob
        for file_path in glob_method(search_pattern):
            if file_path.is_file():
                try:
                    sandbox.resolve(str(file_path))
                except MCPError:
                    continue
                relative_path = file_path.relative_to(dir_path)
                results.append(str(relative_path))

    elif search_text:
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                try:
                    sandbox.resolve(str(file_path))
                    sensitive_guard.check(str(file_path))
                except (MCPError, PermissionError):
                    continue
                try:
                    mime_type, _ = mimetypes.guess_type(str(file_path))
                    if mime_type and mime_type.startswith("text"):
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                            if search_text.lower() in content.lower():
                                relative_path = file_path.relative_to(dir_path)
                                results.append(str(relative_path))
                except (OSError, UnicodeDecodeError):
                    continue

    else:
        raise MCPError(
            ErrorCode.MISSING_PARAMS,
            detail="请提供搜索模式(pattern)或搜索文本(search_text)",
            suggestion="pattern: 文件名通配符; search_text: 文件内容关键词",
        )

    if results:
        result_text = (
            f"在 {directory} 中找到 {len(results)} 个文件:\n\n"
            + "\n".join(sorted(results))
        )
    else:
        result_text = f"在 {directory} 中没有找到匹配的文件"

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=result_text)]
    )


async def handle_copy_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    import shutil

    source = arguments["source"]
    destination = arguments["destination"]
    recursive = arguments.get("recursive", True)

    src_resolved = _resolve_path(source)
    dst_resolved = _resolve_path(destination)

    src_path = Path(src_resolved)
    dst_path = Path(dst_resolved)

    if not src_path.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"源不存在: {source}")

    try:
        if src_path.is_file():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
        elif src_path.is_dir():
            if not recursive:
                raise MCPError(
                    ErrorCode.INVALID_PARAMS,
                    detail=f"源是目录: {source}，设置 recursive=true 复制",
                )
            if dst_path.exists():
                raise MCPError(
                    ErrorCode.FILE_ALREADY_EXISTS,
                    detail=f"目标已存在: {destination}",
                )
            shutil.copytree(src_path, dst_path)
    except MCPError:
        raise
    except OSError as e:
        raise MCPError(
            ErrorCode.WRITE_ERROR,
            detail=f"复制 {source} 到 {destination} 失败: {e}",
        )

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"已复制: {source} → {destination}",
            )
        ]
    )


async def handle_move_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    import shutil

    source = arguments["source"]
    destination = arguments["destination"]

    src_resolved = _resolve_path(source)
    dst_resolved = _resolve_path(destination)

    src_path = Path(src_resolved)
    dst_path = Path(dst_resolved)

    if not src_path.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"源不存在: {source}")

    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
    except OSError as e:
        raise MCPError(
            ErrorCode.WRITE_ERROR,
            detail=f"移动 {source} 到 {destination} 失败: {e}",
        )

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"已移动: {source} → {destination}",
            )
        ]
    )


# ============================================================
# 注册请求处理器
# ============================================================

server.add_request_handler(
    "tools/list", types.PaginatedRequestParams, handle_list_tools
)
server.add_request_handler(
    "tools/call", types.CallToolRequestParams, handle_call_tool
)


# ============================================================
# 启动
# ============================================================


async def main():
    """主函数"""
    logger.info("启动文件系统MCP服务器 V2.0", {
        "tools_count": len(TOOLS),
        "user": os.environ.get("USER", "unknown"),
    })

    for i, tool in enumerate(TOOLS, 1):
        logger.debug(f"注册工具", {"index": i, "name": tool.name})

    print("启动文件系统MCP服务器 V2.0...", file=sys.stderr)
    print(f"沙箱根目录: {sandbox.roots}", file=sys.stderr)
    print(f"日志目录: {LOG_DIR}", file=sys.stderr)
    print(f"可用工具数: {len(TOOLS)}", file=sys.stderr)
    print("正在运行...", file=sys.stderr)

    audit.log_success(operation="server_start", resource="", metadata={
        "version": "2.0",
        "tools": [t.name for t in TOOLS],
    })

    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
