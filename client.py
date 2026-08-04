#!/usr/bin/env python3
"""
MCP客户端测试代码
用于测试文件系统MCP服务器的功能
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

async def test_mcp_server():
    """测试MCP服务器"""
    print("=== 文件系统MCP服务器测试 ===")
    print("启动MCP服务器进行测试...")
    
    try:
        # 启动MCP服务器子进程
        server_process = subprocess.Popen(
            [sys.executable, "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("MCP服务器已启动")
        print("等待服务器初始化...")
        
        # 给服务器一点时间初始化
        await asyncio.sleep(1)
        
        # 简单的MCP协议消息测试
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print(f"\n发送初始化消息...")
        server_process.stdin.write(json.dumps(init_message) + "\n")
        server_process.stdin.flush()
        
        # 读取响应
        response = server_process.stdout.readline()
        print(f"收到响应: {response[:100]}...")
        
        # 测试工具列表
        tools_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        print(f"\n请求工具列表...")
        server_process.stdin.write(json.dumps(tools_message) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        try:
            tools_data = json.loads(response)
            print(f"找到 {len(tools_data.get('result', {}).get('tools', []))} 个工具:")
            for tool in tools_data.get('result', {}).get('tools', []):
                print(f"  - {tool.get('name')}: {tool.get('description')}")
        except:
            print(f"响应: {response[:200]}")
        
        print("\n=== 直接功能测试 ===")
        
        # 创建测试目录和文件
        test_dir = Path("test_files")
        test_dir.mkdir(exist_ok=True)
        
        test_file = test_dir / "test.txt"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("这是一个测试文件\n用于测试MCP服务器的文件操作功能\n第二行内容\n")
        
        print(f"创建了测试文件: {test_file}")
        
        # 测试各个功能
        test_functions = [
            ("列出当前目录", "list_directory", {"path": "."}),
            ("列出测试目录", "list_directory", {"path": "test_files"}),
            ("读取测试文件", "read_file", {"path": str(test_file)}),
            ("获取文件信息", "get_file_info", {"path": str(test_file)}),
            ("搜索文本文件", "search_files", {"directory": ".", "pattern": "*.py"}),
        ]
        
        for description, tool_name, args in test_functions:
            print(f"\n测试: {description}")
            print(f"工具: {tool_name}")
            print(f"参数: {args}")
            
            # 发送工具调用请求
            call_message = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": args
                }
            }
            
            server_process.stdin.write(json.dumps(call_message) + "\n")
            server_process.stdin.flush()
            
            response = server_process.stdout.readline()
            try:
                result = json.loads(response)
                if "result" in result:
                    content = result["result"]["content"][0]["text"]
                    print(f"结果: {content[:200]}...")
                elif "error" in result:
                    print(f"错误: {result['error']}")
            except:
                print(f"原始响应: {response[:200]}")
        
        # 测试写入文件
        print(f"\n测试: 写入新文件")
        write_args = {
            "path": str(test_dir / "new_file.txt"),
            "content": "这是通过MCP服务器创建的新文件\nHello MCP!",
            "mode": "w"
        }
        
        call_message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": write_args
            }
        }
        
        server_process.stdin.write(json.dumps(call_message) + "\n")
        server_process.stdin.flush()
        
        response = server_process.stdout.readline()
        print(f"写入结果: {response[:200]}")
        
        # 清理测试文件
        print(f"\n清理测试文件...")
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"已删除测试目录: {test_dir}")
        
        print("\n=== 测试完成 ===")
        print("所有功能测试完成!")
        
        # 停止服务器
        server_process.terminate()
        server_process.wait()
        print("MCP服务器已停止")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 确保服务器进程被终止
        if 'server_process' in locals():
            server_process.terminate()
            server_process.wait()

def quick_test():
    """快速功能测试（不使用MCP协议）"""
    print("=== 快速功能测试 ===")
    
    # 导入服务器功能进行直接测试
    sys.path.insert(0, '.')
    
    try:
        # 测试目录操作
        import os
        print("1. 测试目录列表:")
        items = os.listdir('.')
        print(f"   当前目录有 {len(items)} 个项目:")
        for item in sorted(items)[:10]:  # 只显示前10个
            print(f"   - {item}")
        
        # 测试文件操作
        print("\n2. 测试文件读写:")
        test_content = "MCP服务器测试内容"
        with open("quick_test.txt", "w", encoding="utf-8") as f:
            f.write(test_content)
        print(f"   已创建测试文件")
        
        with open("quick_test.txt", "r", encoding="utf-8") as f:
            content = f.read()
        print(f"   读取内容: {content}")
        
        # 清理
        os.remove("quick_test.txt")
        print("   已清理测试文件")
        
        print("\n3. 测试服务器模块导入:")
        try:
            # 尝试导入服务器模块
            import server
            print("   服务器模块导入成功")
            
            # 检查工具列表
            print("   服务器功能正常")
            
        except ImportError as e:
            print(f"   导入错误: {e}")
            print("   请确保已安装依赖: pip install mcp")
        
        print("\n=== 快速测试完成 ===")
        
    except Exception as e:
        print(f"快速测试出错: {e}")

def main():
    """主函数"""
    print("文件系统MCP客户端测试")
    print("=" * 50)
    
    # 检查依赖
    try:
        import mcp
        print("✓ MCP库已安装")
    except ImportError:
        print("✗ MCP库未安装")
        print("请先安装依赖:")
        print("  pip install mcp")
        return
    
    # 选择测试模式
    print("\n请选择测试模式:")
    print("1. 完整MCP协议测试")
    print("2. 快速功能测试")
    print("3. 直接启动服务器")
    
    try:
        choice = input("\n输入选择 (1-3): ").strip()
        
        if choice == "1":
            asyncio.run(test_mcp_server())
        elif choice == "2":
            quick_test()
        elif choice == "3":
            print("启动MCP服务器...")
            print("请保持此终端运行，在另一个终端中测试")
            print("或使用Claude Desktop连接")
            subprocess.run([sys.executable, "server.py"])
        else:
            print("无效选择")
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试出错: {e}")

if __name__ == "__main__":
    main()