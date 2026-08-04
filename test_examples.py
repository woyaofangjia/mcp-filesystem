#!/usr/bin/env python3
"""
文件系统MCP服务器示例代码
展示如何使用各个工具
"""

import os
import json
from pathlib import Path

def example_usage():
    """示例用法"""
    print("=== 文件系统MCP服务器使用示例 ===")
    
    # 示例1: 列出目录
    print("\n1. 列出当前目录内容:")
    example1 = {
        "tool": "list_directory",
        "arguments": {
            "path": ".",
            "recursive": False
        }
    }
    print(f"   命令: {json.dumps(example1, indent=2, ensure_ascii=False)}")
    print("   预期结果: 显示当前目录下的所有文件和文件夹")
    
    # 示例2: 读取文件
    print("\n2. 读取README.md文件:")
    example2 = {
        "tool": "read_file",
        "arguments": {
            "path": "README.md",
            "encoding": "utf-8"
        }
    }
    print(f"   命令: {json.dumps(example2, indent=2, ensure_ascii=False)}")
    print("   预期结果: 显示README.md文件的内容")
    
    # 示例3: 写入文件
    print("\n3. 创建测试文件:")
    example3 = {
        "tool": "write_file",
        "arguments": {
            "path": "test_note.txt",
            "content": "这是通过MCP服务器创建的测试文件\n创建时间: 2024年",
            "mode": "w"
        }
    }
    print(f"   命令: {json.dumps(example3, indent=2, ensure_ascii=False)}")
    print("   预期结果: 创建test_note.txt文件并写入内容")
    
    # 示例4: 获取文件信息
    print("\n4. 获取文件信息:")
    example4 = {
        "tool": "get_file_info",
        "arguments": {
            "path": "server.py"
        }
    }
    print(f"   命令: {json.dumps(example4, indent=2, ensure_ascii=False)}")
    print("   预期结果: 显示server.py文件的详细信息")
    
    # 示例5: 搜索文件
    print("\n5. 搜索Python文件:")
    example5 = {
        "tool": "search_files",
        "arguments": {
            "directory": ".",
            "pattern": "*.py"
        }
    }
    print(f"   命令: {json.dumps(example5, indent=2, ensure_ascii=False)}")
    print("   预期结果: 列出所有.py文件")
    
    # 实际创建一些测试文件
    print("\n=== 创建测试文件 ===")
    
    # 创建测试目录结构
    test_dir = Path("example_test")
    test_dir.mkdir(exist_ok=True)
    
    # 创建几个测试文件
    files = {
        "hello.txt": "Hello, MCP Server!\n这是一个测试文件。",
        "notes.md": "# 测试笔记\n\n- 项目: 文件系统MCP服务器\n- 状态: 开发中\n- 功能: 基本文件操作",
        "data.json": '{"name": "测试数据", "value": 42, "active": true}',
        "subfolder/another.txt": "子目录中的文件"
    }
    
    for filename, content in files.items():
        file_path = test_dir / filename
        
        # 确保子目录存在
        file_path.parent.mkdir(exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"创建文件: {file_path}")
    
    print("\n=== 在Claude中使用的示例命令 ===")
    print("""
# 列出测试目录
"列出example_test目录的内容"

# 读取笔记文件
"读取example_test/notes.md文件"

# 搜索文本文件
"在example_test目录中搜索.txt文件"

# 获取文件信息
"获取example_test/data.json文件的信息"

# 创建新文件
"在example_test目录中创建welcome.txt文件，内容为'欢迎使用MCP服务器'"

# 追加内容
"在example_test/hello.txt文件中追加一行'这是追加的内容'"
""")
    
    print("\n=== 测试完成后清理 ===")
    print("可以使用以下命令清理测试文件:")
    print('"删除example_test目录"')
    print("或者手动运行:")
    print("  import shutil")
    print("  shutil.rmtree('example_test')")

def quick_manual_test():
    """手动快速测试"""
    print("\n=== 手动快速测试 ===")
    
    # 测试当前目录
    print("当前目录内容:")
    for item in sorted(os.listdir('.')):
        if os.path.isdir(item):
            print(f"  📁 {item}/")
        else:
            size = os.path.getsize(item)
            print(f"  📄 {item} ({size} bytes)")
    
    # 检查关键文件
    print("\n关键文件检查:")
    required_files = ["server.py", "client.py", "pyproject.toml", "README.md"]
    for file in required_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"  ✓ {file} ({size} bytes)")
        else:
            print(f"  ✗ {file} (缺失)")
    
    # Python版本检查
    print(f"\nPython版本: {sys.version.split()[0]}")
    
    # MCP库检查
    try:
        import mcp
        print("  ✓ MCP库可用")
    except ImportError:
        print("  ✗ MCP库未安装")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        quick_manual_test()
    else:
        example_usage()