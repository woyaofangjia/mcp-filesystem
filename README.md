# 文件系统MCP服务器

一个基于 MCP 2.0.0 协议的企业级文件管理服务，为LLM客户端提供标准化的文件操作能力。

## ✨ 特性

- 🔒 **安全加固**：路径沙箱、RBAC权限、敏感文件守卫、操作审计
- 📝 **结构化日志**：JSON分级日志 + 文件轮转 + SQLite审计追踪
- ⚡ **12个工具**：批量操作、分块读取、缓存统计
- 🛡️ **安全防护**：自动阻止路径遍历、敏感文件访问、越权操作
- 📊 **可观测性**：所有操作可追溯，含trace_id追踪
- 🚀 **性能优化**：LRU缓存、并发控制（最大20并发）、分块传输

## 安装

```bash
pip install -e .
```

## 使用

### 启动MCP服务器
```bash
python server.py
```

### 客户端测试
```bash
# MCP协议集成测试
python -c "
import asyncio, sys
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

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

## 工具列表

| 工具 | 说明 | 安全等级 |
|------|------|----------|
| `list_directory` | 列出目录内容，支持递归 | 只读 |
| `read_file` | 读取文件内容，自动检测类型 | 只读 |
| `write_file` | 创建或修改文件，支持追加 | ⚠️ 危险 |
| `delete_file` | 删除文件或目录 | ⚠️ 危险 |
| `get_file_info` | 获取文件详细元信息 | 只读 |
| `search_files` | 按文件名或内容搜索 | 只读 |
| `copy_file` | 复制文件或目录 | 写入 |
| `move_file` | 移动或重命名文件 | 写入 |
| **`batch_read_files`** | 🆕 批量读取多个文件，支持缓存 | 只读 |
| **`batch_delete_files`** | 🆕 批量删除多个文件 | ⚠️ 危险 |
| **`read_file_chunked`** | 🆕 分块读取大文件（支持offset/limit） | 只读 |
| **`cache_stats`** | 🆕 查看缓存命中率和统计信息 | 只读 |

## 安全机制

```
请求 → 工具检查 → 沙箱校验 → 敏感文件检测 → 权限检查 → 业务处理 → 审计记录
```

- **路径沙箱**：限制访问范围在项目根目录内
- **敏感文件守卫**：禁止访问 `.env`、`.key`、`.pem` 等文件
- **RBAC权限**：支持 readonly / readwrite / admin 三级角色
- **结构化错误**：标准错误码（E1xxx参数/E2xxx安全/E3xxx IO/E4xxx系统）
- **审计日志**：所有操作记录到SQLite，含trace_id追踪

## 文档

> **开发者请先阅读 [CodeAgent.md](docs/CodeAgent.md)**

### 必读层
- [CodeAgent.md](docs/CodeAgent.md) - **Read First** - 架构概览、代码规范

### 选读层（按任务阅读）

| 文档 | 阅读时机 | 说明 |
|------|----------|------|
| [security.md](docs/security.md) | 安全开发 | 沙箱/权限/审计实现 |
| [logging.md](docs/logging.md) | 日志开发 | 分级/结构化/轮转 |
| [error_handling.md](docs/error_handling.md) | 错误处理 | 错误码/重试/超时 |
| [performance.md](docs/performance.md) | 性能优化 | 异步/缓存/大文件 |
| [features.md](docs/features.md) | 功能扩展 | 监听/分析/搜索 |
| [testing.md](docs/testing.md) | 编写测试 | 单元/集成/安全 |
| [roadmap.md](docs/roadmap.md) | 规划任务 | 路线图/优先级 |

## 项目结构

```
mcp-project/
├── docs/
│   ├── CodeAgent.md              # 架构与规范（必读）
│   ├── security.md               # 安全加固
│   ├── logging.md                # 日志系统
│   ├── error_handling.md         # 错误处理
│   ├── performance.md            # 性能优化
│   ├── features.md               # 功能扩展
│   ├── testing.md                # 测试体系
│   └── roadmap.md                 # 升级路线图
├── src/mcp_project/
│   ├── services/
│   │   ├── logger.py             # 分级JSON日志
│   │   ├── audit.py              # SQLite审计日志
│   │   ├── sandbox.py            # 路径沙箱
│   │   ├── sensitive.py          # 敏感文件守卫
│   │   ├── permissions.py        # RBAC权限控制
│   │   ├── errors.py             # 结构化错误处理
│   │   └── cache.py              # 🆕 LRU缓存管理
│   └── __init__.py
├── logs/                         # 运行时日志（gitignore）
│   ├── filesystem-mcp.log
│   └── audit.db
├── server.py                     # MCP服务器主文件
├── client.py                     # 客户端测试
├── test_examples.py              # 示例代码
├── test_mcp_api.py               # API兼容性测试
├── pyproject.toml                # 项目配置
└── README.md                     # 本文件
```

## 快速开始

```python
import asyncio, sys
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

async def main():
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

当前版本 V3.0，已完成：
- ✅ 第一阶段：安全加固、日志、审计、错误处理
- ✅ 第二阶段：LRU缓存、批量操作、并发控制、分块读取

后续将按 [roadmap.md](docs/roadmap.md) 进行第三阶段功能扩展和第四阶段企业级特性开发。

## 许可证

MIT License