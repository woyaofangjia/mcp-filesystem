# CodeAgent Guide

> **Read First** - 架构概览与代码规范

## 1. 项目概述

基于 MCP 2.0.0 的企业级文件操作服务，为LLM客户端提供标准化文件管理能力。

- **当前**: V2.0（第一阶段：安全加固 ✅）
- **目标**: V3.0（性能优化 + 功能扩展）

## 2. 架构

### 分层架构（已实现）

```
┌─────────────────────────────┐
│   MCP Protocol Layer        │  ← 协议处理（server.py）
├─────────────────────────────┤
│   Handler Router Layer      │  ← 请求路由 + 安全校验
├─────────────────────────────┤
│   Business Logic Layer      │  ← 8个工具handler
├─────────────────────────────┤
│   Infrastructure Layer      │  ← services/*
└─────────────────────────────┘
```

### 当前结构（V2.0）

```
server.py
├── TOOLS (8个)               # 工具定义
├── handle_list_tools()       # 返回工具列表
├── handle_call_tool()        # 统一入口 + 安全校验 + 审计
├── handle_list_directory()   # 目录操作
├── handle_read_file()        # 文件读取
├── handle_write_file()       # 文件写入
├── handle_delete_file()      # 文件删除 🆕
├── handle_get_file_info()    # 文件信息
├── handle_search_files()     # 文件搜索
├── handle_copy_file()        # 文件复制 🆕
└── handle_move_file()        # 文件移动 🆕

src/mcp_project/services/
├── logger.py                 # 分级JSON日志
├── audit.py                  # SQLite审计日志
├── sandbox.py                # 路径沙箱
├── sensitive.py              # 敏感文件守卫
├── permissions.py            # RBAC权限控制
└── errors.py                 # 错误码 + 重试 + 超时
```

### 安全流程

```
请求 → 工具检查 → 沙箱校验 → 敏感文件检测 → 权限检查 → 业务处理 → 审计记录
         ↓            ↓              ↓             ↓          ↓          ↓
      错误码4004   错误码2004    错误码2003     错误码2002  错误码3xxx  trace_id
```

## 3. 代码规范

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件 | snake_case | `services/logger.py` |
| 类 | PascalCase | `SensitiveFileGuard` |
| 函数 | snake_case | `handle_read_file()` |
| 常量 | UPPER_CASE | `MAX_FILE_SIZE` |

### Handler 签名

```python
async def handle_xxx(arguments: Dict[str, Any]) -> types.CallToolResult:
    """处理xxx请求"""
    ...
```

### 返回格式

```python
# 成功
return types.CallToolResult(content=[types.TextContent(type="text", text="OK")])

# 错误（使用MCPError + error_result）
from src.mcp_project.services.errors import MCPError, ErrorCode, error_result
raise MCPError(code=ErrorCode.INVALID_PARAMS, message="参数错误")
```

### 异常处理

```python
# 在handler中抛出MCPError
except FileNotFoundError:
    raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {path}")
except Exception as e:
    logger.error(f"操作失败: {e}")
    raise MCPError(ErrorCode.INTERNAL_ERROR, message=str(e))
```

## 4. 工具规范

### Tool 结构

```python
types.Tool(
    name="tool_name",
    description="功能描述",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "说明"}
        },
        "required": ["param"]
    }
)
```

### 命名规则
- 动词开头: `list_`, `read_`, `write_`, `delete_`
- 清晰表达: `list_directory` 而非 `list`
- 面向LLM: 说明用途、参数、约束
- 危险操作标注: `description` 中注明 ⚠️

### 安全等级
- **只读**: list_directory, read_file, get_file_info, search_files
- **写入**: write_file, copy_file, move_file
- **危险**: delete_file, write_file（覆盖模式）

## 5. 开发流程

1. **定义**: 在 TOOLS 添加 Tool
2. **实现**: 创建 handler 函数（在 server.py 或 handlers/）
3. **注册**: 在 handle_call_tool 的 handler 字典添加
4. **安全**: 确保沙箱/敏感文件/权限检查覆盖
5. **测试**: 编写 MCP 协议集成测试
6. **文档**: 更新 README + 相关文档

### 提交规范
```
feat: 新功能
fix: Bug修复
docs: 文档更新
refactor: 重构
```

## 6. 文档索引

| 文档 | 时机 | 说明 |
|------|------|------|
| [security.md](security.md) | 安全开发 | 沙箱/权限/审计 |
| [logging.md](logging.md) | 日志开发 | 分级/结构化/轮转 |
| [error_handling.md](error_handling.md) | 错误处理 | 错误码/重试/降级 |
| [performance.md](performance.md) | 性能优化 | 异步/缓存/大文件 |
| [features.md](features.md) | 功能扩展 | 监听/分析/搜索 |
| [testing.md](testing.md) | 编写测试 | 单元/集成/安全 |
| [roadmap.md](roadmap.md) | 规划任务 | 路线图/优先级 |