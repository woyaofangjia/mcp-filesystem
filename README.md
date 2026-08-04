# 文件系统MCP服务器

一个基于 MCP 2.0.0 协议的企业级文件管理服务，为LLM客户端提供标准化的文件操作能力。

## 功能

1. **列出目录内容** - 查看指定目录下的文件和文件夹（支持递归）
2. **读取文件内容** - 读取文本文件，自动检测编码和二进制
3. **写入文件** - 创建或修改文本文件，支持追加模式
4. **文件信息** - 获取文件的详细信息（大小、时间、MIME类型等）
5. **搜索文件** - 按文件名模式或内容搜索

## 安装

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -e .
```

## 使用

### 启动MCP服务器
```bash
python server.py
```

### 使用客户端测试
```bash
# 快速功能测试
python test_examples.py test

# MCP协议测试
python -c "
import asyncio
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
import sys

async def test():
    params = StdioServerParameters(command=sys.executable, args=['server.py'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print('可用工具:', [t.name for t in tools.tools])

asyncio.run(test())
"
```

### 与Claude Desktop集成
将以下配置添加到Claude Desktop的MCP设置中：

```json
{
  "mcpServers": {
    "filesystem-server": {
      "command": "python",
      "args": ["server.py"],
      "env": {}
    }
  }
}
```

## 工具列表

| 工具名 | 说明 |
|--------|------|
| `list_directory` | 列出目录内容，支持递归 |
| `read_file` | 读取文件内容，自动检测类型 |
| `write_file` | 创建或修改文件，支持追加 |
| `get_file_info` | 获取文件详细元信息 |
| `search_files` | 按文件名或内容搜索 |

## 文档

> **开发者请先阅读 [CodeAgent.md](docs/CodeAgent.md)**

### 必读层（架构与规范）
- [CodeAgent.md](docs/CodeAgent.md) - **Read First** - 架构概览、代码规范、开发流程

### 选读层（按任务阅读）

| 文档 | 阅读时机 | 说明 |
|------|----------|------|
| [security.md](docs/security.md) | 实现安全相关功能 | 路径沙箱、权限控制、审计日志 |
| [logging.md](docs/logging.md) | 实现日志功能 | 分级日志、结构化日志、日志轮转 |
| [error_handling.md](docs/error_handling.md) | 实现错误处理 | 错误码、异常处理、重试机制 |
| [performance.md](docs/performance.md) | 实现性能优化 | 异步IO、缓存、大文件支持 |
| [features.md](docs/features.md) | 实现扩展功能 | 文件监听、内容分析、搜索增强 |
| [testing.md](docs/testing.md) | 编写或运行测试 | 单元测试、集成测试、安全测试 |
| [roadmap.md](docs/roadmap.md) | 规划开发任务 | 升级路线图、优先级、验收标准 |

## 项目结构

```
mcp-project/
├── docs/                    # 文档目录
│   ├── CodeAgent.md          # 架构与规范（必读）
│   ├── security.md           # 安全加固
│   ├── logging.md            # 日志系统
│   ├── error_handling.md     # 错误处理
│   ├── performance.md       # 性能优化
│   ├── features.md           # 功能扩展
│   ├── testing.md            # 测试体系
│   └── roadmap.md             # 升级路线图
├── src/mcp_project/
│   └── __init__.py
├── server.py                # MCP服务器主文件
├── client.py                # 客户端测试
├── test_examples.py         # 示例代码
├── test_mcp_api.py          # API兼容性测试
├── pyproject.toml           # 项目配置
└── README.md                # 项目说明（本文件）
```

## 快速开始

```python
import asyncio
import sys
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

async def main():
    # 连接到服务器
    server_params = StdioServerParameters(
        command=sys.executable,
        args=['server.py']
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print(f"可用工具: {[t.name for t in tools.tools]}")
            
            # 调用工具
            result = await session.call_tool("read_file", {
                "path": "README.md"
            })
            print(result.content[0].text)

asyncio.run(main())
```

## 开发说明

这是一个基于 MCP 2.0.0 协议的文件系统服务器，当前版本为基础实现，后续将按 [roadmap.md](docs/roadmap.md) 进行工业级升级。

## 许可证

MIT License
