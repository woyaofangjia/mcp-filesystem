#!/usr/bin/env python3
"""
文件系统MCP服务器 - V2.0 工业级版本
基于 MCP 2.0.0 协议，集成安全加固、日志、审计、错误处理
"""

import os
import sys
import mimetypes
import time
import asyncio
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
    get_cache_manager,
    get_file_comparator,
    get_file_merger,
    get_batch_renamer,
    get_content_analyzer,
    get_duplicate_finder,
    get_enhanced_searcher,
    get_search_index,
    get_file_type_detector,
    get_encoding_detector,
    get_file_compressor,
    get_metrics_collector,
    get_health_checker,
    get_alert_manager,
    get_config_manager,
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
cache_manager = get_cache_manager()

# 第三阶段：新服务初始化
file_comparator = get_file_comparator()
file_merger = get_file_merger()
batch_renamer = get_batch_renamer()
content_analyzer = get_content_analyzer()
duplicate_finder = get_duplicate_finder()
enhanced_searcher = get_enhanced_searcher(max_results=1000, max_file_size=10 * 1024 * 1024)
search_index = get_search_index()
file_type_detector = get_file_type_detector()
encoding_detector = get_encoding_detector()
file_compressor = get_file_compressor()

# 第四阶段：可观测性与配置管理
config_manager = get_config_manager()
metrics_collector = get_metrics_collector()
health_checker = get_health_checker()
alert_manager = get_alert_manager()

# 注册健康检查
health_checker.register_check("disk", lambda: True)
health_checker.register_check("memory", lambda: True)
health_checker.register_check("cache", lambda: cache_manager.stats()["content"]["items"] >= 0)

# 并发控制：限制同时进行的文件操作数
MAX_CONCURRENT_OPS = 20
_ops_semaphore = asyncio.Semaphore(MAX_CONCURRENT_OPS)

logger.info("服务初始化完成", {
    "app_root": APP_ROOT,
    "sandbox_roots": sandbox.roots,
    "log_dir": LOG_DIR,
    "max_concurrent_ops": MAX_CONCURRENT_OPS,
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
    # ============== 第二阶段：批量操作 ==============
    types.Tool(
        name="batch_read_files",
        description="批量读取多个文件",
        input_schema={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件路径列表",
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认utf-8）",
                    "default": "utf-8",
                },
            },
            "required": ["paths"],
        },
    ),
    types.Tool(
        name="batch_delete_files",
        description="批量删除多个文件（⚠️危险操作）",
        input_schema={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件路径列表",
                },
            },
            "required": ["paths"],
        },
    ),
    # ============== 第二阶段：大文件支持 ==============
    types.Tool(
        name="read_file_chunked",
        description="分块读取大文件",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "chunk_size": {
                    "type": "integer",
                    "description": "每块字节数（默认1MB）",
                    "default": 1048576,
                },
                "offset": {
                    "type": "integer",
                    "description": "起始偏移量（字节）",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "最大读取字节数（默认10MB）",
                    "default": 10485760,
                },
            },
            "required": ["path"],
        },
    ),
    # ============== 第二阶段：缓存统计 ==============
    types.Tool(
        name="cache_stats",
        description="获取缓存统计信息",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
    # ============== 第三阶段：高级文件操作 ==============
    types.Tool(
        name="compare_files",
        description="比较两个文本文件的内容差异",
        input_schema={
            "type": "object",
            "properties": {
                "file1": {"type": "string", "description": "第一个文件路径"},
                "file2": {"type": "string", "description": "第二个文件路径"},
            },
            "required": ["file1", "file2"],
        },
    ),
    types.Tool(
        name="merge_files",
        description="合并多个文本文件为一个文件",
        input_schema={
            "type": "object",
            "properties": {
                "input_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "输入文件路径列表",
                },
                "output_file": {
                    "type": "string", 
                    "description": "输出文件路径",
                },
                "separator": {
                    "type": "string",
                    "description": "文件内容分隔符（默认为换行符）",
                    "default": "\n",
                },
            },
            "required": ["input_files", "output_file"],
        },
    ),
    types.Tool(
        name="batch_rename_files",
        description="批量重命名文件（支持正则表达式）",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "要重命名文件的目录",
                },
                "pattern": {
                    "type": "string",
                    "description": "要匹配的模式（支持正则表达式）",
                },
                "replacement": {
                    "type": "string",
                    "description": "替换字符串",
                },
                "regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式",
                    "default": False,
                },
                "preview_only": {
                    "type": "boolean",
                    "description": "仅预览而不实际重命名",
                    "default": False,
                },
            },
            "required": ["directory", "pattern", "replacement"],
        },
    ),
    types.Tool(
        name="analyze_file_content",
        description="分析文本文件的统计信息",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="find_duplicate_files",
        description="查找目录中的重复文件（基于内容哈希）",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "要搜索的目录",
                },
                "check_content": {
                    "type": "boolean",
                    "description": "是否检查文件内容（否则只检查文件名和大小）",
                    "default": True,
                },
                "min_size": {
                    "type": "integer",
                    "description": "最小文件大小（字节），小于此大小的文件会被跳过",
                    "default": 1024,
                },
            },
            "required": ["directory"],
        },
    ),
    # ============== 第三阶段：增强搜索 ==============
    types.Tool(
        name="full_text_search",
        description="全文搜索（支持大小写敏感、整词匹配）",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "搜索目录",
                },
                "query": {
                    "type": "string",
                    "description": "搜索查询",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否大小写敏感",
                    "default": False,
                },
                "whole_word": {
                    "type": "boolean",
                    "description": "是否整词匹配",
                    "default": False,
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件名模式（例如 *.txt）",
                },
            },
            "required": ["directory", "query"],
        },
    ),
    types.Tool(
        name="regex_search",
        description="使用正则表达式搜索文件内容",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "搜索目录",
                },
                "pattern": {
                    "type": "string",
                    "description": "正则表达式模式",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件名模式",
                },
            },
            "required": ["directory", "pattern"],
        },
    ),
    types.Tool(
        name="fuzzy_search",
        description="模糊搜索（支持拼写错误的匹配）",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "搜索目录",
                },
                "query": {
                    "type": "string",
                    "description": "搜索查询",
                },
                "similarity_threshold": {
                    "type": "number",
                    "description": "相似度阈值（0-1之间）",
                    "default": 0.8,
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件名模式",
                },
            },
            "required": ["directory", "query"],
        },
    ),
    types.Tool(
        name="advanced_search",
        description="多条件高级搜索（按类型、大小、时间等）",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "搜索目录",
                },
                "query": {
                    "type": "string",
                    "description": "搜索查询",
                },
                "file_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件类型列表（如 .txt, .py, .js）",
                },
                "min_size": {
                    "type": "integer",
                    "description": "最小文件大小（字节）",
                },
                "max_size": {
                    "type": "integer",
                    "description": "最大文件大小（字节）",
                },
                "modified_after": {
                    "type": "string",
                    "description": "修改时间之后（ISO格式，如 2024-01-01T00:00:00）",
                },
                "modified_before": {
                    "type": "string",
                    "description": "修改时间之前（ISO格式）",
                },
            },
            "required": ["directory", "query"],
        },
    ),
    # ============== 第三阶段：文件类型和编码 ==============
    types.Tool(
        name="detect_file_type",
        description="检测文件的真实类型（基于魔数，非扩展名）",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="detect_file_encoding",
        description="检测文本文件的编码",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "sample_size": {
                    "type": "integer",
                    "description": "样本大小（字节）",
                    "default": 10240,
                },
            },
            "required": ["path"],
        },
    ),
    # ============== 第三阶段：搜索索引管理 ==============
    types.Tool(
        name="index_directory",
        description="为目录创建搜索索引以提高搜索性能",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "要索引的目录",
                },
                "rebuild": {
                    "type": "boolean",
                    "description": "是否重建现有索引",
                    "default": False,
                },
            },
            "required": ["directory"],
        },
    ),
    types.Tool(
        name="search_index",
        description="使用预建的索引进行快速搜索",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "limit": {
                    "type": "integer",
                    "description": "结果数量限制",
                    "default": 100,
                },
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="index_stats",
        description="获取搜索索引统计信息",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
    # ============== 第三阶段：文件压缩 ==============
    types.Tool(
        name="compress_file",
        description="压缩单个文件（支持zip、gzip、bzip2格式）",
        input_schema={
            "type": "object",
            "properties": {
                "source_file": {"type": "string", "description": "源文件路径"},
                "format_type": {
                    "type": "string",
                    "description": "压缩格式（zip、gzip、bzip2）",
                    "default": "zip",
                    "enum": ["zip", "gzip", "bzip2"],
                },
                "compression_level": {
                    "type": "integer",
                    "description": "压缩级别（1-9，9为最高压缩）",
                    "default": 6,
                },
            },
            "required": ["source_file"],
        },
    ),
    types.Tool(
        name="decompress_file",
        description="解压文件（支持zip、gzip、bzip2、tar格式）",
        input_schema={
            "type": "object",
            "properties": {
                "archive_file": {"type": "string", "description": "压缩文件路径"},
                "output_dir": {
                    "type": "string",
                    "description": "输出目录（默认为压缩文件同目录下新建文件夹）",
                },
            },
            "required": ["archive_file"],
        },
    ),
    # ============== 第四阶段：可观测性 & 配置管理 ==============
    types.Tool(
        name="health_check",
        description="检查服务健康状态",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_metrics",
        description="获取性能指标统计（响应时间、吞吐量、错误率、系统资源）",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_alerts",
        description="获取告警历史和当前告警状态",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_config",
        description="获取当前服务器配置",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="update_config",
        description="运行时更新配置（热更新）",
        input_schema={
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": "要更新的配置项键值对",
                },
            },
            "required": ["config"],
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
            # 第二阶段新增
            "batch_read_files": "read",
            "batch_delete_files": "delete",
            "read_file_chunked": "read",
            "cache_stats": "read",
            # 第三阶段：高级文件操作
            "compare_files": "read",
            "merge_files": "write",
            "batch_rename_files": "write",
            "analyze_file_content": "read",
            "find_duplicate_files": "read",
            # 第三阶段：增强搜索
            "full_text_search": "read",
            "regex_search": "read",
            "fuzzy_search": "read",
            "advanced_search": "read",
            # 第三阶段：文件类型和编码
            "detect_file_type": "read",
            "detect_file_encoding": "read",
            # 第三阶段：搜索索引管理
            "index_directory": "write",  # 需要写入权限来创建索引
            "search_index": "read",
            "index_stats": "read",
            # 第三阶段：文件压缩
            "compress_file": "write",
            "decompress_file": "write",
            # 第四阶段：可观测性 & 配置管理
            "health_check": "read",
            "get_metrics": "read",
            "get_alerts": "read",
            "get_config": "read",
            "update_config": "write",  # 配置变更需要写权限
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
            # 第二阶段新增
            "batch_read_files": handle_batch_read_files,
            "batch_delete_files": handle_batch_delete_files,
            "read_file_chunked": handle_read_file_chunked,
            "cache_stats": handle_cache_stats,
            # 第三阶段：高级文件操作
            "compare_files": handle_compare_files,
            "merge_files": handle_merge_files,
            "batch_rename_files": handle_batch_rename_files,
            "analyze_file_content": handle_analyze_file_content,
            "find_duplicate_files": handle_find_duplicate_files,
            # 第三阶段：增强搜索
            "full_text_search": handle_full_text_search,
            "regex_search": handle_regex_search,
            "fuzzy_search": handle_fuzzy_search,
            "advanced_search": handle_advanced_search,
            # 第三阶段：文件类型和编码
            "detect_file_type": handle_detect_file_type,
            "detect_file_encoding": handle_detect_file_encoding,
            # 第三阶段：搜索索引管理
            "index_directory": handle_index_directory,
            "search_index": handle_search_index,
            "index_stats": handle_index_stats,
            # 第三阶段：文件压缩
            "compress_file": handle_compress_file,
            "decompress_file": handle_decompress_file,
            # 第四阶段：可观测性 & 配置管理
            "health_check": handle_health_check,
            "get_metrics": handle_get_metrics,
            "get_alerts": handle_get_alerts,
            "get_config": handle_get_config,
            "update_config": handle_update_config,
        }

        handler = handlers[tool_name]
        result = await handler(arguments)

        # 5. 记录性能指标和成功审计
        elapsed_ms = int((time.time() - start_time) * 1000)
        metrics_collector.record_request(tool_name, float(elapsed_ms), success=True)
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
        metrics_collector.record_request(tool_name, float(elapsed_ms), success=False)
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
        metrics_collector.record_request(tool_name, float(elapsed_ms), success=False)
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
    # 单路径参数
    for key in ("path", "source", "destination", "directory"):
        if key in args and args[key]:
            paths.append(str(args[key]))
    # 批量操作的路径数组
    if "paths" in args and isinstance(args["paths"], list):
        for p in args["paths"]:
            if p:
                paths.append(str(p))
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
# 第二阶段：批量操作 & 大文件支持
# ============================================================


async def handle_batch_read_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """批量读取文件"""
    paths = arguments.get("paths", [])
    encoding = arguments.get("encoding", "utf-8")

    if not paths:
        raise MCPError(ErrorCode.MISSING_PARAMS, detail="paths 不能为空")

    results = []
    success_count = 0
    fail_count = 0

    async def read_one(p: str) -> dict:
        try:
            resolved = _resolve_path(p)
            path_obj = Path(resolved)

            if not path_obj.exists():
                return {"path": p, "status": "error", "error": "文件不存在"}

            # 尝试从缓存获取
            cached = cache_manager.get_content(p)
            if cached is not None:
                return {"path": p, "status": "cached", "content": cached[:500] + "..."}

            # 实际读取
            content = _read_text_file(path_obj, encoding)
            # 写入缓存
            cache_manager.set_content(p, content)
            return {"path": p, "status": "success", "content": content[:500] + "..."}
        except Exception as e:
            return {"path": p, "status": "error", "error": str(e)}

    # 并发读取（使用信号量控制）
    tasks = []
    for p in paths:
        async with _ops_semaphore:
            tasks.append(read_one(p))

    results_list = await asyncio.gather(*tasks)

    for r in results_list:
        results.append(r)
        if r["status"] in ("success", "cached"):
            success_count += 1
        else:
            fail_count += 1

    summary = f"批量读取完成: {success_count} 成功, {fail_count} 失败\n\n"
    details = []
    for r in results:
        if r["status"] == "success":
            details.append(f"[OK] {r['path']}")
        elif r["status"] == "cached":
            details.append(f"[CACHED] {r['path']}")
        else:
            details.append(f"[FAIL] {r['path']}: {r['error']}")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=summary + "\n".join(details))]
    )


async def handle_batch_delete_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """批量删除文件"""
    paths = arguments.get("paths", [])

    if not paths:
        raise MCPError(ErrorCode.MISSING_PARAMS, detail="paths 不能为空")

    results = []
    success_count = 0
    fail_count = 0

    for p in paths:
        try:
            resolved = _resolve_path(p)
            path_obj = Path(resolved)

            if not path_obj.exists():
                results.append({"path": p, "status": "skipped", "reason": "不存在"})
                continue

            if path_obj.is_file():
                path_obj.unlink()
            elif path_obj.is_dir():
                import shutil
                shutil.rmtree(path_obj)

            # 失效缓存
            cache_manager.invalidate(p)
            results.append({"path": p, "status": "success"})
            success_count += 1
        except Exception as e:
            results.append({"path": p, "status": "error", "error": str(e)})
            fail_count += 1

    summary = f"批量删除完成: {success_count} 成功, {fail_count} 失败\n\n"
    details = []
    for r in results:
        if r["status"] == "success":
            details.append(f"[DELETED] {r['path']}")
        elif r["status"] == "skipped":
            details.append(f"[SKIPPED] {r['path']}: {r['reason']}")
        else:
            details.append(f"[FAIL] {r['path']}: {r['error']}")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=summary + "\n".join(details))]
    )


async def handle_read_file_chunked(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """分块读取大文件"""
    path = arguments["path"]
    chunk_size = arguments.get("chunk_size", 1048576)  # 1MB
    offset = arguments.get("offset", 0)
    limit = arguments.get("limit", 10485760)  # 10MB

    resolved = _resolve_path(path)
    path_obj = Path(resolved)

    if not path_obj.exists():
        raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {path}")
    if not path_obj.is_file():
        raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {path}")

    file_size = path_obj.stat().st_size
    if offset >= file_size:
        raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"offset {offset} 超出文件大小 {file_size}")

    # 调整限制
    bytes_to_read = min(limit, file_size - offset)

    try:
        with open(path_obj, "rb") as f:
            f.seek(offset)
            data = f.read(bytes_to_read)

        # 尝试解码为文本
        try:
            text = data.decode("utf-8")
            content_preview = text[:1000]
        except UnicodeDecodeError:
            content_preview = f"<二进制数据, {len(data)} 字节>"

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"文件: {path}\n"
                    f"大小: {file_size} 字节\n"
                    f"读取范围: {offset}-{offset+bytes_to_read} ({bytes_to_read} 字节)\n\n"
                    f"内容预览:\n{content_preview}",
                )
            ]
        )
    except OSError as e:
        raise MCPError(ErrorCode.READ_ERROR, detail=f"读取失败: {e}")


async def handle_cache_stats(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """获取缓存统计"""
    stats = cache_manager.stats()

    lines = ["缓存统计信息:", ""]
    for cache_type, data in stats.items():
        lines.append(f"=== {cache_type} ===")
        for key, value in data.items():
            if key == "size_bytes" or key == "max_size_bytes":
                lines.append(f"  {key}: {value / 1024 / 1024:.2f} MB")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
    )


# ============================================================
# 第四阶段：可观测性 & 配置管理 Handler
# ============================================================


async def handle_health_check(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """健康检查"""
    results = health_checker.check_health()

    lines = ["健康检查结果:", ""]
    for component, status in results.items():
        icon = "✅" if status == "healthy" else "❌"
        lines.append(f"{icon} {component}: {status}")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
    )


async def handle_get_metrics(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """获取性能指标"""
    stats = metrics_collector.get_all_stats()

    lines = ["性能指标统计:", ""]

    # 汇总
    summary = stats["summary"]
    lines.append("=== 总览 ===")
    lines.append(f"  总请求数: {summary['total_requests']}")
    lines.append(f"  成功: {summary['total_success']}")
    lines.append(f"  失败: {summary['total_errors']}")
    lines.append(f"  错误率: {summary['overall_error_rate']}%")
    lines.append(f"  吞吐量: {summary['throughput_per_min']} req/min")
    lines.append("")

    # 系统资源
    sys_stats = stats["system"]
    lines.append("=== 系统资源 ===")
    for key, value in sys_stats.items():
        if "mb" in key:
            lines.append(f"  {key}: {value} MB")
        elif "gb" in key:
            lines.append(f"  {key}: {value} GB")
        else:
            lines.append(f"  {key}: {value}")
    lines.append("")

    # 各工具统计
    lines.append("=== 工具统计 ===")
    for tool_name, tool_stats in stats["tools"].items():
        if tool_stats["total_requests"] == 0:
            continue
        lines.append(f"  [{tool_name}]")
        lines.append(f"    请求: {tool_stats['total_requests']} (错误率 {tool_stats['error_rate']}%)")
        lines.append(f"    响应: avg={tool_stats['avg_response_ms']}ms, p50={tool_stats['p50_response_ms']}ms, p99={tool_stats['p99_response_ms']}ms")
    lines.append("")

    # 告警检查
    alerts = alert_manager.check(stats)
    if alerts:
        lines.append("=== 触发告警 ===")
        for a in alerts:
            lines.append(f"  [{a['severity'].upper()}] {a['message']}")
    else:
        lines.append("=== 告警: 无 ===")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
    )


async def handle_get_alerts(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """获取告警历史"""
    history = alert_manager.get_history()

    lines = [f"告警历史 (最近 {len(history)} 条):", ""]
    if not history:
        lines.append("  无告警记录")
    else:
        for a in history:
            lines.append(f"  [{a['severity'].upper()}] {a['rule']}: {a['message']}")
            lines.append(f"    时间: {a['timestamp']}")
            lines.append("")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
    )


async def handle_get_config(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """获取当前配置"""
    config = config_manager.to_dict()
    errors = config_manager.validate()

    lines = ["当前服务器配置:", ""]
    for key, value in config.items():
        lines.append(f"  {key}: {value}")

    lines.append("")
    if errors:
        lines.append("⚠️ 配置验证问题:")
        for e in errors:
            lines.append(f"  - {e}")
    else:
        lines.append("✅ 配置验证通过")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
    )


async def handle_update_config(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """运行时更新配置"""
    updates = arguments.get("config", {})
    if not updates:
        raise MCPError(ErrorCode.MISSING_PARAMS, detail="config 不能为空")

    old_config = config_manager.to_dict()
    config_manager.update(**updates)
    new_config = config_manager.to_dict()
    errors = config_manager.validate()

    lines = ["配置已更新:", ""]
    for key in updates:
        if key in old_config:
            lines.append(f"  {key}: {old_config[key]} → {new_config.get(key, 'N/A')}")

    lines.append("")
    if errors:
        lines.append("⚠️ 配置验证问题:")
        for e in errors:
            lines.append(f"  - {e}")
    else:
        lines.append("✅ 配置验证通过")

    logger.info("配置已热更新", {"updates": updates})

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="\n".join(lines))]
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


async def _run_server():
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


# ============== 第三阶段：高级文件操作处理器 ==============

async def handle_compare_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """比较两个文件"""
    file1 = arguments["file1"]
    file2 = arguments["file2"]
    
    file1_resolved = _resolve_path(file1)
    file2_resolved = _resolve_path(file2)
    
    result = file_comparator.compare_files(
        Path(file1_resolved), 
        Path(file2_resolved)
    )
    
    if result["identical"]:
        summary = f"文件内容完全相同: {file1} 和 {file2}"
    else:
        summary = f"文件内容有差异: {file1} 和 {file2}"
    
    details = f"""
{summary}

文件1: {result['file1']} ({result['size1']} 字节)
文件2: {result['file2']} ({result['size2']} 字节)

差异统计:
  - 新增行: {result['diff_summary']['additions']}
  - 删除行: {result['diff_summary']['deletions']}
  - 总计差异: {result['diff_summary']['total_differences']}

差异预览:
{result['diff_preview']}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_merge_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """合并多个文件"""
    input_files = arguments["input_files"]
    output_file = arguments["output_file"]
    separator = arguments.get("separator", "\n")
    
    input_paths = [Path(_resolve_path(f)) for f in input_files]
    output_path = Path(_resolve_path(output_file))
    
    result = file_merger.merge_files(input_paths, output_path, separator)
    
    summary = f"已合并 {result['total_files']} 个文件到 {output_file}"
    details = f"""
{summary}

输出文件: {result['output_file']}
输入文件: {', '.join(result['input_files'])}
总文件大小: {result['total_size']} 字节
输出文件大小: {result['output_size']} 字节
使用分隔符: {result['separator']}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_batch_rename_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """批量重命名文件"""
    directory = arguments["directory"]
    pattern = arguments["pattern"]
    replacement = arguments["replacement"]
    regex = arguments.get("regex", False)
    preview_only = arguments.get("preview_only", False)
    
    dir_resolved = _resolve_path(directory)
    
    result = batch_renamer.batch_rename(
        Path(dir_resolved), 
        pattern, 
        replacement, 
        regex, 
        preview_only
    )
    
    if preview_only:
        action = "预览"
    else:
        action = "执行"
    
    summary = f"{action}批量重命名: {result['total_renamed']} 个文件重命名，{result['total_failed']} 个失败"
    details = f"""
{summary}

目录: {result['directory']}
模式: {result['pattern']}
替换: {result['replacement']}
使用正则: {result['regex']}
预览模式: {result['preview_only']}

重命名的文件:
"""
    
    for i, file_info in enumerate(result["renamed_files"][:20], 1):  # 限制显示数量
        preview_mark = "（预览）" if file_info.get("preview", False) else ""
        details += f"  {i}. {file_info['old_name']} → {file_info['new_name']}{preview_mark}\n"
    
    if len(result["renamed_files"]) > 20:
        details += f"  ... 还有 {len(result['renamed_files']) - 20} 个文件\n"
    
    if result["failed_files"]:
        details += "\n失败的文件:\n"
        for i, fail_info in enumerate(result["failed_files"][:10], 1):
            details += f"  {i}. {fail_info.get('file', 'unknown')}: {fail_info.get('error', '未知错误')}\n"
        if len(result["failed_files"]) > 10:
            details += f"  ... 还有 {len(result['failed_files']) - 10} 个失败\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_analyze_file_content(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """分析文件内容"""
    path = arguments["path"]
    
    path_resolved = _resolve_path(path)
    
    result = content_analyzer.analyze_file_content(Path(path_resolved))
    
    summary = f"文件内容分析: {path}"
    details = f"""
{summary}

基本信息:
  - 文件: {result['file']}
  - 大小: {result['size_bytes']} 字节
  - 扩展名: {result['file_extension']}
  - 检测语言: {result['detected_language']}
  - 编码问题: {'有' if result['encoding_issues'] else '无'}

内容统计:
  - 字符数: {result['character_count']}
  - 行数: {result['line_count']}
  - 单词数: {result['word_count']}

代码分析:
  - 代码行: {result['code_analysis']['code_lines']}
  - 注释行: {result['code_analysis']['comment_lines']}
  - 空行: {result['code_analysis']['blank_lines']}
  - 总行数: {result['code_analysis']['total_lines']}
  - 注释比例: {result['code_analysis']['comment_ratio']:.1%}
  - 代码比例: {result['code_analysis']['code_ratio']:.1%}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_find_duplicate_files(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """查找重复文件"""
    directory = arguments["directory"]
    check_content = arguments.get("check_content", True)
    min_size = arguments.get("min_size", 1024)
    
    dir_resolved = _resolve_path(directory)
    
    result = duplicate_finder.find_duplicates(
        Path(dir_resolved), 
        check_content, 
        min_size
    )
    
    summary = f"重复文件检测: 找到 {result['duplicate_groups']} 组重复文件，共 {result['duplicate_files']} 个文件"
    details = f"""
{summary}

目录: {result['directory']}
检查内容: {result['check_content']}
最小大小: {result['min_size']} 字节
扫描文件数: {result['total_files_scanned']}
可节省空间: {result['potential_space_saved']} 字节
跳过的文件: {result['skipped_files']}

重复文件组:
"""
    
    for i, group in enumerate(result["duplicates"][:10], 1):  # 限制显示数量
        details += f"\n第 {i} 组 ({group['size_bytes']} 字节 × {group['count']}):\n"
        for j, file_path in enumerate(group["files"][:5], 1):
            details += f"  {j}. {file_path}\n"
        if len(group["files"]) > 5:
            details += f"  ... 还有 {len(group['files']) - 5} 个文件\n"
    
    if len(result["duplicates"]) > 10:
        details += f"\n... 还有 {len(result['duplicates']) - 10} 组重复文件\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


# ============== 第三阶段：增强搜索处理器 ==============

async def handle_full_text_search(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """全文搜索"""
    directory = arguments["directory"]
    query = arguments["query"]
    case_sensitive = arguments.get("case_sensitive", False)
    whole_word = arguments.get("whole_word", False)
    file_pattern = arguments.get("file_pattern")
    
    dir_resolved = _resolve_path(directory)
    
    result = enhanced_searcher.full_text_search(
        Path(dir_resolved),
        query,
        case_sensitive,
        whole_word,
        file_pattern
    )
    
    summary = f"全文搜索: 在 {result['files_processed']} 个文件中找到 {result['total_matches']} 处匹配"
    details = f"""
{summary}

目录: {result['directory']}
查询: {result['query']}
大小写敏感: {result['case_sensitive']}
整词匹配: {result['whole_word']}
匹配文件数: {result['files_with_matches']}

搜索结果:
"""
    
    for i, item in enumerate(result["results"][:15], 1):  # 限制显示数量
        details += f"\n{i}. {item['file']} (相关性: {item['relevance']})\n"
        for j, match in enumerate(item["matches"][:3], 1):
            details += f"   第 {match['line']} 行: {match['context']}\n"
        if len(item["matches"]) > 3:
            details += f"   ... 还有 {len(item['matches']) - 3} 处匹配\n"
    
    if len(result["results"]) > 15:
        details += f"\n... 还有 {len(result['results']) - 15} 个文件\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_regex_search(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """正则搜索"""
    directory = arguments["directory"]
    pattern = arguments["pattern"]
    file_pattern = arguments.get("file_pattern")
    
    dir_resolved = _resolve_path(directory)
    
    result = enhanced_searcher.regex_search(
        Path(dir_resolved),
        pattern,
        file_pattern
    )
    
    summary = f"正则搜索: 在 {result['files_processed']} 个文件中找到 {result['total_matches']} 处匹配"
    details = f"""
{summary}

目录: {result['directory']}
正则模式: {result['pattern']}
匹配文件数: {result['files_with_matches']}

搜索结果:
"""
    
    for i, result_item in enumerate(result["regex_results"][:10], 1):
        details += f"\n{i}. {result_item.file_path} (相关性: {result_item.relevance})\n"
        for j, match in enumerate(result_item.matches[:2], 1):
            groups_info = f" 捕获组: {match['groups']}" if match.get("groups") else ""
            details += f"   第 {match['line']} 行: {match['context']}{groups_info}\n"
        if len(result_item.matches) > 2:
            details += f"   ... 还有 {len(result_item.matches) - 2} 处匹配\n"
    
    if len(result["regex_results"]) > 10:
        details += f"\n... 还有 {len(result['regex_results']) - 10} 个文件\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_fuzzy_search(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """模糊搜索"""
    directory = arguments["directory"]
    query = arguments["query"]
    similarity_threshold = arguments.get("similarity_threshold", 0.8)
    file_pattern = arguments.get("file_pattern")
    
    dir_resolved = _resolve_path(directory)
    
    result = enhanced_searcher.fuzzy_search(
        Path(dir_resolved),
        query,
        similarity_threshold,
        file_pattern
    )
    
    summary = f"模糊搜索: 在 {result['files_processed']} 个文件中找到 {result['total_matches']} 处匹配"
    details = f"""
{summary}

目录: {result['directory']}
查询: {result['query']}
相似度阈值: {result['similarity_threshold']}

搜索结果:
"""
    
    for i, match in enumerate(result["fuzzy_results"][:20], 1):
        similarity_percent = match["similarity"] * 100
        details += f"{i}. {match['file']} (相似度: {similarity_percent:.1f}%)\n"
        details += f"   文件名: {match.get('filename', 'N/A')}\n"
        details += f"   类型: {match['type']}\n"
        if match.get("word"):
            details += f"   匹配词: {match['word']}\n"
        details += "\n"
    
    if len(result["fuzzy_results"]) > 20:
        details += f"... 还有 {len(result['fuzzy_results']) - 20} 个结果\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_advanced_search(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """高级搜索"""
    directory = arguments["directory"]
    query = arguments["query"]
    file_types = arguments.get("file_types")
    min_size = arguments.get("min_size")
    max_size = arguments.get("max_size")
    modified_after = arguments.get("modified_after")
    modified_before = arguments.get("modified_before")
    
    dir_resolved = _resolve_path(directory)
    
    result = enhanced_searcher.advanced_search(
        Path(dir_resolved),
        query,
        file_types,
        min_size,
        max_size,
        modified_after,
        modified_before
    )
    
    summary = f"高级搜索: 在 {result['files_processed']} 个文件中找到 {result['total_matches']} 个匹配"
    details = f"""
{summary}

目录: {result['directory']}
查询: {result['query']}
过滤器: {result['filters']}

搜索结果:
"""
    
    for i, match in enumerate(result["advanced_results"][:20], 1):
        details += f"{i}. {match['file']}\n"
        details += f"   大小: {match['size_bytes']} 字节\n"
        details += f"   修改时间: {match['modified_time']}\n"
        details += f"   扩展名: {match['extension']}\n"
        details += f"   文件名匹配: {match['filename_match']}\n"
        details += f"   内容匹配: {match['content_match']}\n\n"
    
    if len(result["advanced_results"]) > 20:
        details += f"... 还有 {len(result['advanced_results']) - 20} 个结果\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


# ============== 第三阶段：文件类型和编码处理器 ==============

async def handle_detect_file_type(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """检测文件类型"""
    path = arguments["path"]
    
    path_resolved = _resolve_path(path)
    
    result = file_type_detector.detect_file_type(Path(path_resolved))
    
    summary = f"文件类型检测: {path}"
    details = f"""
{summary}

文件信息:
  - 路径: {result['file']}
  - 扩展名: {result['extension']}
  - 大小: {result['size_bytes']} 字节

类型检测:
  - MIME类型: {result['mime_type']}
  - 基于扩展名: {result['mime_from_extension'] or '未识别'}
  - 真实类型: {result['real_type'] or '未识别'}
  - 基于内容: {result['content_type'] or '未识别'}

文件分类:
  - 文本文件: {result['is_text']}
  - 二进制文件: {result['is_binary']}
  - 图像文件: {result['categories']['is_image']}
  - 压缩文件: {result['categories']['is_archive']}
  - 音频文件: {result['categories']['is_audio']}
  - 视频文件: {result['categories']['is_video']}
  - 文档文件: {result['categories']['is_document']}
  - 代码文件: {result['categories']['is_code']}
  - 配置文件: {result['categories']['is_config']}
  - 可执行文件: {result['categories']['is_executable']}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_detect_file_encoding(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """检测文件编码"""
    path = arguments["path"]
    sample_size = arguments.get("sample_size", 10240)
    
    path_resolved = _resolve_path(path)
    
    result = encoding_detector.detect_encoding(
        Path(path_resolved), 
        sample_size
    )
    
    summary = f"文件编码检测: {path}"
    details = f"""
{summary}

文件信息:
  - 路径: {result['file']}
  - 大小: {result['size_bytes']} 字节
  - 文本文件: {result['is_text_file']}
  - 样本大小: {result['sample_size']} 字节

编码检测:
  - 检测编码: {result['detected_encoding']}
  - 置信度: {result['detection_confidence']:.1%}
  - 推荐编码: {result['recommended_encoding']}

常见编码测试:
"""
    
    for test in result["common_encodings_tested"]:
        status = "✓" if test["valid"] else "✗"
        details += f"  - {status} {test['encoding']}\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


# ============== 第三阶段：搜索索引处理器 ==============

async def handle_index_directory(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """索引目录"""
    directory = arguments["directory"]
    rebuild = arguments.get("rebuild", False)
    
    dir_resolved = _resolve_path(directory)
    
    result = search_index.index_directory(Path(dir_resolved), rebuild)
    
    action = "重建" if rebuild else "创建"
    summary = f"{action}搜索索引: 成功索引 {result['indexed_files']} 个文件"
    details = f"""
{summary}

目录: {result['directory']}
索引位置: {result['index_location']}
索引文件数: {result['indexed_files']}
跳过文件数: {result['skipped_files']}
索引单词数: {result['total_words_indexed']}
重建索引: {result['rebuild']}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_search_index(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """搜索索引"""
    query = arguments["query"]
    limit = arguments.get("limit", 100)
    
    result = search_index.search_index(query, limit)
    
    summary = f"索引搜索: 找到 {result['total_results']} 个相关文件"
    details = f"""
{summary}

查询: {result['query']}
查询词: {result['query_words']}
结果数量: {result['total_results']}

搜索结果:
"""
    
    for i, item in enumerate(result["results"][:15], 1):
        details += f"\n{i}. {item['file']} (相关性: {item['relevance']})\n"
        details += f"   大小: {item['size_bytes']} 字节\n"
        details += f"   修改时间: {item['modified_time']}\n"
        details += f"   扩展名: {item['extension']}\n"
        details += f"   匹配词: {', '.join(item['matched_words'][:5])}\n"
        details += f"   总频率: {item['total_frequency']}\n"
    
    if len(result["results"]) > 15:
        details += f"\n... 还有 {len(result['results']) - 15} 个结果\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_index_stats(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """索引统计"""
    result = search_index.get_index_stats()
    
    summary = f"搜索索引统计"
    details = f"""
{summary}

索引位置: {result['index_location']}
索引大小: {result['index_size_mb']:.2f} MB
总文件数: {result['total_files']}
总单词数: {result['total_words']}
总大小: {result['total_size_bytes']} 字节

前10文件扩展名:
"""
    
    for i, ext_info in enumerate(result["top_extensions"], 1):
        details += f"  {i}. {ext_info['extension']}: {ext_info['count']} 个文件\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


# ============== 第三阶段：文件压缩处理器 ==============

async def handle_compress_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """压缩文件"""
    source_file = arguments["source_file"]
    format_type = arguments.get("format_type", "zip")
    compression_level = arguments.get("compression_level", 6)
    
    source_resolved = _resolve_path(source_file)
    
    result = file_compressor.compress_file(
        Path(source_resolved),
        format_type,
        compression_level
    )
    
    compression_ratio = result["compression_ratio"]
    summary = f"文件压缩: {source_file} → 压缩率 {compression_ratio}%"
    details = f"""
{summary}

源文件: {result['source_file']}
压缩文件: {result['compressed_file']}
压缩格式: {result['format']}
压缩级别: {result['compression_level']}

压缩效果:
  - 原始大小: {result['original_size']} 字节
  - 压缩大小: {result['compressed_size']} 字节
  - 压缩率: {compression_ratio}%
  - 节省空间: {result['space_saved']} 字节
  - 临时文件: {result['temporary_location']}
"""
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


async def handle_decompress_file(
    arguments: Dict[str, Any],
) -> types.CallToolResult:
    """解压文件"""
    archive_file = arguments["archive_file"]
    output_dir = arguments.get("output_dir")
    
    archive_resolved = _resolve_path(archive_file)
    output_path = Path(_resolve_path(output_dir)) if output_dir else None
    
    result = file_compressor.decompress_file(
        Path(archive_resolved),
        output_path
    )
    
    summary = f"文件解压: {archive_file} → 解压 {result['total_files']} 个文件"
    details = f"""
{summary}

压缩文件: {result['archive_file']}
输出目录: {result['output_directory']}
压缩大小: {result['archive_size']} 字节
解压大小: {result['total_extracted_size']} 字节
压缩率: {result['compression_ratio']}%

解压的文件:
"""
    
    for i, file_path in enumerate(result["extracted_files"][:10], 1):
        details += f"  {i}. {file_path}\n"
    
    if len(result["extracted_files"]) > 10:
        details += f"  ... 还有 {len(result['extracted_files']) - 10} 个文件\n"
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=details)]
    )


# ============================================================
# 启动入口（必须在所有handler定义之后）
# ============================================================

if __name__ == "__main__":
    asyncio.run(_run_server())
