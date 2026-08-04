#!/usr/bin/env python3
"""
文件系统MCP服务器 - MCP 2.0.0版本
提供基本的文件操作功能，适合初学者学习MCP协议
"""

import os
import json
import sys
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.context import ServerRequestContext
from mcp import types

# 初始化MCP服务器
server = Server("filesystem-server")

# 定义工具列表
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
                    "default": "."
                },
                "recursive": {
                    "type": "boolean", 
                    "description": "是否递归列出子目录",
                    "default": False
                }
            }
        }
    ),
    types.Tool(
        name="read_file",
        description="读取文本文件的内容",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认为utf-8）",
                    "default": "utf-8"
                }
            },
            "required": ["path"]
        }
    ),
    types.Tool(
        name="write_file",
        description="创建或修改文本文件",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "文件内容"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认为utf-8）",
                    "default": "utf-8"
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式：a=追加，w=覆盖（默认）",
                    "default": "w",
                    "enum": ["w", "a"]
                }
            },
            "required": ["path", "content"]
        }
    ),
    types.Tool(
        name="get_file_info",
        description="获取文件的详细信息",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                }
            },
            "required": ["path"]
        }
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
                    "default": "."
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（支持通配符 * 和 ?）"
                },
                "search_text": {
                    "type": "string",
                    "description": "搜索文件内容中的文本"
                }
            }
        }
    )
]

# 处理ListTools请求
async def handle_list_tools(ctx: ServerRequestContext, params: Any) -> types.ListToolsResult:
    """处理工具列表请求"""
    return types.ListToolsResult(tools=TOOLS)

# 处理CallTool请求
async def handle_call_tool(ctx: ServerRequestContext, params: types.CallToolRequestParams) -> types.CallToolResult:
    """处理工具调用请求"""
    try:
        if params.name == "list_directory":
            return await handle_list_directory(params.arguments or {})
        elif params.name == "read_file":
            return await handle_read_file(params.arguments or {})
        elif params.name == "write_file":
            return await handle_write_file(params.arguments or {})
        elif params.name == "get_file_info":
            return await handle_get_file_info(params.arguments or {})
        elif params.name == "search_files":
            return await handle_search_files(params.arguments or {})
        else:
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"未知工具: {params.name}"
                )]
            )
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"执行工具时出错: {str(e)}"
            )]
        )

# 注册请求处理器
server.add_request_handler("tools/list", types.PaginatedRequestParams, handle_list_tools)
server.add_request_handler("tools/call", types.CallToolRequestParams, handle_call_tool)

# 实现各个工具的功能
async def handle_list_directory(arguments: Dict[str, Any]) -> types.CallToolResult:
    """列出目录内容"""
    path = arguments.get("path", ".")
    recursive = arguments.get("recursive", False)
    
    try:
        path_obj = Path(path).resolve()
        
        if not path_obj.exists():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"路径不存在: {path}"
                )]
            )
        
        if not path_obj.is_dir():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"路径不是目录: {path}"
                )]
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
            for item in path_obj.iterdir():
                if item.is_dir():
                    items.append(f"{item.name}/")
                else:
                    items.append(item.name)
            result = "\n".join(sorted(items))
        
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"目录: {path}\n\n{result}"
            )]
        )
        
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"列出目录时出错: {str(e)}"
            )]
        )

async def handle_read_file(arguments: Dict[str, Any]) -> types.CallToolResult:
    """读取文件内容"""
    path = arguments["path"]
    encoding = arguments.get("encoding", "utf-8")
    
    try:
        path_obj = Path(path).resolve()
        
        if not path_obj.exists():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"文件不存在: {path}"
                )]
            )
        
        if not path_obj.is_file():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"路径不是文件: {path}"
                )]
            )
        
        # 检查文件大小（限制读取大文件）
        file_size = path_obj.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB限制
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"文件过大 ({file_size} 字节)，请使用其他方式查看"
                )]
            )
        
        with open(path_obj, "r", encoding=encoding, errors="ignore") as f:
            content = f.read()
        
        # 如果是二进制文件，只显示基本信息
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and not mime_type.startswith("text"):
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"文件: {path}\n类型: {mime_type}\n大小: {file_size} 字节\n\n这是二进制文件，无法显示内容"
                )]
            )
        
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"文件: {path}\n大小: {file_size} 字节\n\n{content}"
            )]
        )
        
    except UnicodeDecodeError:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"无法使用 {encoding} 编码读取文件，可能是二进制文件"
            )]
        )
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"读取文件时出错: {str(e)}"
            )]
        )

async def handle_write_file(arguments: Dict[str, Any]) -> types.CallToolResult:
    """写入文件内容"""
    path = arguments["path"]
    content = arguments["content"]
    encoding = arguments.get("encoding", "utf-8")
    mode = arguments.get("mode", "w")
    
    try:
        path_obj = Path(path).resolve()
        
        # 确保目录存在
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        write_mode = "a" if mode == "a" else "w"
        with open(path_obj, write_mode, encoding=encoding) as f:
            f.write(content)
        
        action = "追加到" if mode == "a" else "写入"
        file_size = path_obj.stat().st_size
        
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"成功{action}文件: {path}\n新文件大小: {file_size} 字节"
            )]
        )
        
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"写入文件时出错: {str(e)}"
            )]
        )

async def handle_get_file_info(arguments: Dict[str, Any]) -> types.CallToolResult:
    """获取文件信息"""
    path = arguments["path"]
    
    try:
        path_obj = Path(path).resolve()
        
        if not path_obj.exists():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"文件/目录不存在: {path}"
                )]
            )
        
        stat_info = path_obj.stat()
        mime_type, encoding = mimetypes.guess_type(path)
        
        info = {
            "路径": str(path_obj),
            "类型": "目录" if path_obj.is_dir() else "文件",
            "大小": f"{stat_info.st_size} 字节",
            "创建时间": datetime.fromtimestamp(stat_info.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "修改时间": datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "访问时间": datetime.fromtimestamp(stat_info.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
            "MIME类型": mime_type or "未知",
            "编码": encoding or "未知"
        }
        
        if path_obj.is_file():
            info["扩展名"] = path_obj.suffix
            info["文件名"] = path_obj.name
        
        info_text = "\n".join([f"{key}: {value}" for key, value in info.items()])
        
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=info_text
            )]
        )
        
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"获取文件信息时出错: {str(e)}"
            )]
        )

async def handle_search_files(arguments: Dict[str, Any]) -> types.CallToolResult:
    """搜索文件"""
    directory = arguments.get("directory", ".")
    pattern = arguments.get("pattern")
    search_text = arguments.get("search_text")
    
    try:
        dir_path = Path(directory).resolve()
        
        if not dir_path.exists():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"目录不存在: {directory}"
                )]
            )
        
        if not dir_path.is_dir():
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"路径不是目录: {directory}"
                )]
            )
        
        results = []
        
        # 使用通配符搜索
        if pattern:
            search_pattern = pattern
            if "*" not in search_pattern and "?" not in search_pattern:
                search_pattern = f"*{search_pattern}*"
            
            for file_path in dir_path.rglob(search_pattern) if "**" in search_pattern else dir_path.glob(search_pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(dir_path)
                    results.append(str(relative_path))
        
        # 文本内容搜索
        elif search_text:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    try:
                        # 只搜索文本文件
                        mime_type, _ = mimetypes.guess_type(str(file_path))
                        if mime_type and mime_type.startswith("text"):
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if search_text.lower() in content.lower():
                                    relative_path = file_path.relative_to(dir_path)
                                    results.append(str(relative_path))
                    except:
                        continue
        
        else:
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text="请提供搜索模式(pattern)或搜索文本(search_text)"
                )]
            )
        
        if results:
            result_text = f"在 {directory} 中找到 {len(results)} 个文件:\n\n" + "\n".join(sorted(results))
        else:
            result_text = f"在 {directory} 中没有找到匹配的文件"
        
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=result_text
            )]
        )
        
    except Exception as e:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"搜索文件时出错: {str(e)}"
            )]
        )

async def main():
    """主函数"""
    print("启动文件系统MCP服务器...", file=sys.stderr)
    print("可用工具:", file=sys.stderr)
    for i, tool in enumerate(TOOLS, 1):
        print(f"{i}. {tool.name} - {tool.description}", file=sys.stderr)
    print("正在运行...", file=sys.stderr)
    
    # 运行服务器
    async with stdio_server() as streams:
        await server.run(
            streams[0], 
            streams[1],
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())