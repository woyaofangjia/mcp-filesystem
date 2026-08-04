# 文件系统MCP服务器

一个基于 MCP 2.0.0 协议的企业级文件管理服务，为LLM客户端提供标准化的文件操作能力。

## ✨ 特性

- 🔒 **安全加固**：路径沙箱、RBAC权限、敏感文件守卫、操作审计
- 📝 **结构化日志**：JSON分级日志 + 文件轮转 + SQLite审计追踪
- ⚡ **33个工具**：批量操作、分块读取、缓存统计、高级文件操作、可观测性
- 🛡️ **安全防护**：自动阻止路径遍历、敏感文件访问、越权操作
- 📊 **可观测性**：健康检查端点、性能指标采集、告警系统、trace_id追踪
- ⚙️ **配置管理**：dev/test/prod环境分离、配置验证、动态配置热更新
- 🧪 **测试体系**：单元测试(47项)、集成测试(8项)、安全测试三层覆盖
- 🚀 **性能优化**：LRU缓存、并发控制（最大20并发）、分块传输
- 🔍 **高级搜索**：全文搜索、正则搜索、模糊搜索、索引搜索
- 📁 **文件分析**：文件类型检测、编码检测、内容统计、重复检测
- 🛠️ **高级操作**：文件比较、文件合并、批量重命名、文件压缩解压

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

### 基础文件操作
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

### 第二阶段：性能优化
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`batch_read_files`** | 🆕 批量读取多个文件，支持缓存 | 只读 |
| **`batch_delete_files`** | 🆕 批量删除多个文件 | ⚠️ 危险 |
| **`read_file_chunked`** | 🆕 分块读取大文件（支持offset/limit） | 只读 |
| **`cache_stats`** | 🆕 查看缓存命中率和统计信息 | 只读 |

### 第三阶段：高级文件操作
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`compare_files`** | 🆕 比较两个文本文件的内容差异 | 只读 |
| **`merge_files`** | 🆕 合并多个文本文件为一个文件 | 写入 |
| **`batch_rename_files`** | 🆕 批量重命名文件（支持正则表达式） | 写入 |
| **`analyze_file_content`** | 🆕 分析文本文件的统计信息 | 只读 |
| **`find_duplicate_files`** | 🆕 查找目录中的重复文件（基于内容哈希） | 只读 |

### 第三阶段：增强搜索
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`full_text_search`** | 🆕 全文搜索（支持大小写敏感、整词匹配） | 只读 |
| **`regex_search`** | 🆕 使用正则表达式搜索文件内容 | 只读 |
| **`fuzzy_search`** | 🆕 模糊搜索（支持拼写错误的匹配） | 只读 |
| **`advanced_search`** | 🆕 多条件高级搜索（按类型、大小、时间等） | 只读 |

### 第三阶段：文件类型和编码
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`detect_file_type`** | 🆕 检测文件的真实类型（基于魔数） | 只读 |
| **`detect_file_encoding`** | 🆕 检测文本文件的编码 | 只读 |

### 第三阶段：搜索索引管理
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`index_directory`** | 🆕 为目录创建搜索索引以提高搜索性能 | 写入 |
| **`search_index`** | 🆕 使用预建的索引进行快速搜索 | 只读 |
| **`index_stats`** | 🆕 获取搜索索引统计信息 | 只读 |

### 第三阶段：文件压缩
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`compress_file`** | 🆕 压缩单个文件（支持zip、gzip、bzip2格式） | 写入 |
| **`decompress_file`** | 🆕 解压文件（支持zip、gzip、bzip2、tar格式） | 写入 |

### 第四阶段：可观测性与配置管理
| 工具 | 说明 | 安全等级 |
|------|------|----------|
| **`health_check`** | 🆕 服务健康状态检查（组件级状态） | 只读 |
| **`get_metrics`** | 🆕 获取性能指标（响应时间/吞吐量/错误率） | 只读 |
| **`get_alerts`** | 🆕 获取告警列表（异常操作实时告警） | 只读 |
| **`get_config`** | 🆕 获取当前配置（dev/test/prod环境配置） | 只读 |
| **`update_config`** | 🆕 动态更新配置（运行时热更新） | ⚠️ 危险 |

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
│   │   ├── cache.py              # LRU缓存管理
│   │   ├── advanced_operations.py # 高级文件操作（比较/合并/重命名）
│   │   ├── search_enhancement.py # 增强搜索（全文/正则/模糊/索引）
│   │   ├── file_analysis.py      # 文件分析（类型/编码/压缩）
│   │   ├── observability.py      # 🆕 可观测性（MetricsCollector/HealthChecker/AlertManager）
│   │   └── config.py             # 🆕 配置管理（ConfigManager/ServerConfig）
│   └── __init__.py
├── tests/                        # 🆕 测试体系
│   ├── unit/                     # 单元测试（47项全通过）
│   ├── integration/              # 集成测试（8项通过）
│   └── security/                 # 安全测试
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

### 🎯 项目进度（V4.0 - 2026-08-04）

| 阶段 | 状态 | 工具数量 | 主要成就 |
|------|------|----------|----------|
| **第一阶段** | ✅ 已完成 | 5→8个 | 安全加固、日志系统、错误处理 |
| **第二阶段** | ✅ 已完成 | 8→12个 | 性能优化、缓存机制、大文件支持 |
| **第三阶段** | ✅ 已完成 | 12→**29个** | 功能扩展、高级搜索、文件分析 |
| **第四阶段** | ✅ 已完成 | 29→**33个** | 可观测性、配置管理、测试体系 |

### ✅ 第四阶段完成成果
- **新增5个企业级工具**（工具总数从28增至33）：health_check、get_metrics、get_alerts、get_config、update_config
- **新增2个服务模块**：`services/observability.py`（MetricsCollector/HealthChecker/AlertManager）、`services/config.py`（ConfigManager/ServerConfig）
- **建立完整测试体系**：`tests/` 目录含 unit/integration/security 三层
- **47个单元测试全部通过**，8项集成测试通过（5个新工具 + 3项回归测试）
- **Bug修复**：修复 `server.py` 中 `if __name__` 块位置错误导致 Phase 3 handler 未加载的问题
- **Bug修复**：修复 `observability.py` 中 `Lock` 死锁问题（改为 `RLock`）

### 📚 详细文档
- [第三阶段实现文档](docs/phase3_implementation.md) - 详细技术实现
- [第三阶段完成总结](docs/phase3_summary.md) - 项目成果总结
- [功能扩展文档](docs/features.md) - 功能设计和实现指南
- [项目路线图](docs/roadmap.md) - 后续开发计划

后续将按 [roadmap.md](docs/roadmap.md) 进行第五阶段生态集成开发。

## 许可证

MIT License