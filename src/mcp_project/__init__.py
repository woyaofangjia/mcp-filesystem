"""
文件系统MCP服务器项目
提供基本的文件操作功能，适合初学者学习MCP协议
"""

__version__ = "0.1.0"
__author__ = "vvan汪汪队大队长"
__email__ = "whu13611614482@163.com"

import os
import sys
from pathlib import Path

def main() -> None:
    """主入口函数"""
    print("文件系统MCP服务器")
    print("=" * 50)
    print(f"版本: {__version__}")
    print(f"作者: {__author__}")
    print("=" * 50)
    
    # 检查当前环境
    print("Python版本:", sys.version.split()[0])
    print("当前目录:", Path.cwd())
    print("操作系统:", sys.platform)
    
    print("\n可用命令:")
    print("  python server.py    # 启动MCP服务器")
    print("  python client.py    # 测试客户端")
    print("  pip install -e .    # 安装项目")
    
    print("\n快速开始:")
    print("1. 安装依赖: pip install -e .")
    print("2. 启动服务器: python server.py")
    print("3. 测试功能: python client.py")
    print("4. 连接到Claude Desktop进行使用")
    
    print("\n项目特点:")
    print("✓ 适合MCP初学者")
    print("✓ 提供5个实用的文件操作工具")
    print("✓ 无外部API依赖")
    print("✓ 完整的错误处理")
    print("✓ 详细的文档和测试")

def check_dependencies() -> bool:
    """检查项目依赖"""
    try:
        import mcp
        print("✓ MCP库已安装")
        return True
    except ImportError:
        print("✗ MCP库未安装")
        print("请运行: pip install mcp")
        return False

def get_project_info() -> dict:
    """获取项目信息"""
    return {
        "name": "mcp-project",
        "version": __version__,
        "description": "文件系统MCP服务器 - 初学者友好的文件操作工具",
        "author": __author__,
        "tools": [
            "list_directory - 列出目录内容",
            "read_file - 读取文件内容", 
            "write_file - 创建或修改文件",
            "get_file_info - 获取文件信息",
            "search_files - 搜索文件"
        ]
    }

if __name__ == "__main__":
    main()