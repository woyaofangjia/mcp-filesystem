# CodeAgent Guide

> **Read First** - 架构概览与代码规范

## 1. 项目概述

基于 MCP 2.0.0 的文件操作服务，为LLM客户端提供标准化文件管理能力。

- **当前**: V0.1.0（基础版）
- **目标**: V2.0.0（工业级）

## 2. 架构

### 分层架构

```
┌─────────────────────────────┐
│   MCP Protocol Layer        │  ← 协议处理
├─────────────────────────────┤
│   Handler Router Layer      │  ← 请求路由
├─────────────────────────────┤
│   Business Logic Layer      │  ← 核心逻辑
├─────────────────────────────┤
│   Infrastructure Layer      │  ← 日志/缓存/安全
└─────────────────────────────┘
```

### 当前结构（V0.1）

```
server.py
├── TOOLS                    # 工具定义
├── handle_list_tools()      # 返回工具列表
├── handle_call_tool()       # 请求路由
├── handle_list_directory()  # 目录操作
├── handle_read_file()       # 文件读取
├── handle_write_file()      # 文件写入
├── handle_get_file_info()   # 文件信息
└── handle_search_files()    # 文件搜索
```

### 目标结构（V2.0）

```
src/mcp_project/
├── core/       # server.py, router.py, models.py
├── handlers/   # directory.py, file.py, search.py
├── services/   # security.py, logging.py, cache.py, audit.py
└── utils/      # path_utils.py, validators.py
```

## 3. 代码规范

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件 | snake_case | `handlers/file_ops.py` |
| 类 | PascalCase | `FileHandler` |
| 函数 | snake_case | `handle_read_file()` |
| 常量 | UPPER_CASE | `MAX_FILE_SIZE` |

### Handler 签名

```python
async def handle_xxx(ctx: ServerRequestContext, params: ParamsType) -> ResultType:
    """处理xxx请求"""
    ...
```

### 返回格式

```python
# 成功
return types.CallToolResult(content=[types.TextContent(type="text", text="OK")])

# 错误
return types.CallToolResult(
    content=[types.TextContent(type="text", text="E1001 - 参数错误")],
    isError=True
)
```

### 异常处理

```python
except FileNotFoundError:
    return error_result("E3001", "文件不存在")
except Exception as e:
    logger.error(f"操作失败: {e}")
    return error_result("E4001", "内部错误")
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
- 动词开头: `list_`, `read_`, `write_`
- 清晰表达: `list_directory` 而非 `list`
- 面向LLM: 说明用途、参数、约束

## 5. 开发流程

1. **定义**: 在 TOOLS 添加 Tool
2. **实现**: 创建 handler 函数
3. **注册**: 在 router 添加分支
4. **测试**: 编写单元/集成测试
5. **文档**: 更新相关文档

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
