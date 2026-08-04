#!/usr/bin/env python3
"""
测试MCP 2.0.0 API
"""

from mcp import types
from mcp.server import Server
import inspect

# 查看Server类的文档
print("=== Server类方法 ===")
s = Server("test-server")
methods = [x for x in dir(s) if not x.startswith('_')]
print("可用方法:", methods)

print("\n=== Tool类型结构 ===")
# 查看Tool类的结构
tool_signature = inspect.signature(types.Tool.__init__)
print(f"Tool.__init__ 签名: {tool_signature}")

# 查看Tool类的字段
print("\nTool字段:")
for attr in dir(types.Tool):
    if not attr.startswith('_'):
        value = getattr(types.Tool, attr, None)
        if not callable(value):
            print(f"  {attr}: {type(value).__name__}")

# 尝试创建工具
print("\n=== 创建工具示例 ===")
try:
    tool = types.Tool(
        name="test_tool",
        description="测试工具",
        inputSchema={
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
    )
    print(f"工具创建成功: {tool.name}")
    print(f"工具描述: {tool.description}")
    print(f"输入模式: {tool.inputSchema}")
except Exception as e:
    print(f"创建工具出错: {e}")

# 查看如何添加工具到服务器
print("\n=== 服务器工具管理 ===")
print("查看是否有添加工具的方法...")
if hasattr(s, 'add_tool'):
    print("有 add_tool 方法")
else:
    print("没有 add_tool 方法")
    
# 查看add_request_handler的使用
print("\n查看add_request_handler:")
print("参数:", inspect.signature(s.add_request_handler))

# 查看list_tools的请求类型
print("\n=== ListTools请求 ===")
print("ListToolsRequest:", types.ListToolsRequest)
print("ListToolsResult:", types.ListToolsResult)

# 测试创建服务器能力
print("\n=== 创建服务器能力 ===")
capabilities = types.ServerCapabilities(
    tools=types.ToolsCapability()
)
print("服务器能力:", capabilities)

print("\n测试完成！")