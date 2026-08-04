# 测试体系

> **Read based on task** - 编写或运行测试时阅读

## 1. 测试策略

### 1.1 测试金字塔

```
        ╱  E2E  ╲           ← 少量，关键流程
       ╱ 集成测试 ╲          ← MCP协议交互
      ╱   单元测试   ╲        ← 大量，核心逻辑
     ╱─────────────────╲
```

### 1.2 覆盖率目标

| 测试类型 | 覆盖率目标 | 说明 |
|----------|------------|------|
| 单元测试 | >= 80% | 核心业务逻辑 |
| 集成测试 | >= 60% | MCP协议交互 |
| 安全测试 | 100% | 所有安全相关功能 |

---

## 2. 单元测试

### 2.1 测试框架

```python
# requirements-test.txt
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
```

### 2.2 测试示例

```python
# tests/test_handlers/test_file_ops.py

import pytest
import asyncio
from pathlib import Path

class TestListDirectory:
    """测试目录列表功能"""
    
    @pytest.fixture
    async def setup(self, tmp_path):
        """创建临时目录结构"""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        
        # 注入临时路径
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        yield tmp_path
        os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_list_directory_success(self, setup):
        """测试成功列出目录"""
        result = await handle_list_directory({"path": "."})
        assert result.content[0].text
        assert "dir1/" in result.content[0].text
        assert "file1.txt" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_list_nonexistent_path(self):
        """测试路径不存在"""
        result = await handle_list_directory({"path": "/nonexistent"})
        assert "路径不存在" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_list_directory_recursive(self, setup):
        """测试递归列出"""
        result = await handle_list_directory({
            "path": ".",
            "recursive": True
        })
        assert result.content[0].text

class TestReadFile:
    """测试文件读取功能"""
    
    @pytest.mark.asyncio
    async def test_read_file_success(self, tmp_path):
        """测试成功读取"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello MCP!")
        
        result = await handle_read_file({"path": str(test_file)})
        assert "Hello MCP!" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """测试读取不存在的文件"""
        result = await handle_read_file({"path": "/no/file.txt"})
        assert "文件不存在" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_read_binary_file(self, tmp_path):
        """测试读取二进制文件"""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        
        result = await handle_read_file({"path": str(binary_file)})
        assert "二进制文件" in result.content[0].text
```

---

## 3. 集成测试

### 3.1 MCP协议测试

```python
# tests/integration/test_mcp_protocol.py

import pytest
import asyncio

class TestMCPProtocol:
    """MCP协议集成测试"""
    
    @pytest.fixture
    async def client_session(self):
        """创建测试会话"""
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    
    @pytest.mark.asyncio
    async def test_initialize(self, client_session):
        """测试初始化握手"""
        # 初始化已在fixture中完成
        assert client_session is not None
    
    @pytest.mark.asyncio
    async def test_list_tools(self, client_session):
        """测试获取工具列表"""
        tools = await client_session.list_tools()
        assert len(tools.tools) == 5
        tool_names = [t.name for t in tools.tools]
        assert "list_directory" in tool_names
        assert "read_file" in tool_names
    
    @pytest.mark.asyncio
    async def test_call_tool(self, client_session, tmp_path):
        """测试工具调用"""
        result = await client_session.call_tool(
            "read_file",
            {"path": str(tmp_path / "README.md")}
        )
        assert result.content
        assert len(result.content) > 0
```

### 3.2 完整流程测试

```python
class TestWorkflow:
    """完整工作流测试"""
    
    @pytest.mark.asyncio
    async def test_file_lifecycle(self, client_session, tmp_path):
        """测试文件完整生命周期"""
        # 1. 写入文件
        write_result = await client_session.call_tool("write_file", {
            "path": str(tmp_path / "lifecycle.txt"),
            "content": "Initial content"
        })
        assert "成功写入" in write_result.content[0].text
        
        # 2. 读取验证
        read_result = await client_session.call_tool("read_file", {
            "path": str(tmp_path / "lifecycle.txt")
        })
        assert "Initial content" in read_result.content[0].text
        
        # 3. 获取信息
        info_result = await client_session.call_tool("get_file_info", {
            "path": str(tmp_path / "lifecycle.txt")
        })
        assert "lifecycle.txt" in info_result.content[0].text
        
        # 4. 追加内容
        append_result = await client_session.call_tool("write_file", {
            "path": str(tmp_path / "lifecycle.txt"),
            "content": " + appended",
            "mode": "a"
        })
        assert "追加" in append_result.content[0].text
        
        # 5. 搜索文件
        search_result = await client_session.call_tool("search_files", {
            "directory": str(tmp_path),
            "pattern": "*.txt"
        })
        assert "lifecycle.txt" in search_result.content[0].text
```

---

## 4. 安全测试

### 4.1 路径遍历测试

```python
class TestSecurity:
    """安全测试"""
    
    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, client_session):
        """测试路径遍历攻击被阻止"""
        attack_paths = [
            "../../../etc/passwd",
            "..%2f..%2fetc%2fpasswd",
            "safe/../../../etc/passwd",
        ]
        
        for path in attack_paths:
            result = await client_session.call_tool("read_file", {
                "path": path
            })
            assert "权限" in result.content[0].text or \
                   "不存在" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_sensitive_file_protected(self, client_session, tmp_path):
        """测试敏感文件保护"""
        # 创建.env文件
        env_file = tmp_path / ".env"
        env_file.write_text("SECRET_KEY=xxx")
        
        result = await client_session.call_tool("read_file", {
            "path": str(env_file)
        })
        assert "敏感" in result.content[0].text or \
               "权限" in result.content[0].text
```

---

## 5. 性能测试

### 5.1 基准测试

```python
# tests/performance/test_benchmarks.py

import time
import statistics

class TestPerformance:
    """性能基准测试"""
    
    NORMAL_FILE = "test_normal.txt"
    LARGE_FILE = "test_large.txt"  # 100MB
    MANY_FILES_DIR = "test_many_files"  # 1000个文件
    
    @pytest.fixture
    def test_files(self, tmp_path):
        """创建测试文件"""
        # 普通文件 (1KB)
        (tmp_path / self.NORMAL_FILE).write_text("x" * 1024)
        
        # 大文件 (100MB)
        with open(tmp_path / self.LARGE_FILE, "wb") as f:
            f.write(b"x" * (100 * 1024 * 1024))
        
        # 多文件目录
        files_dir = tmp_path / self.MANY_FILES_DIR
        files_dir.mkdir()
        for i in range(1000):
            (files_dir / f"file_{i:04d}.txt").write_text(f"Content {i}")
        
        return tmp_path
    
    @pytest.mark.benchmark
    async def test_read_normal_file(self, client_session, test_files):
        """读取普通文件性能"""
        times = []
        for _ in range(100):
            start = time.perf_counter()
            await client_session.call_tool("read_file", {
                "path": str(test_files / self.NORMAL_FILE)
            })
            times.append(time.perf_counter() - start)
        
        p50 = statistics.percentile(times, 50)
        p95 = statistics.percentile(times, 95)
        
        assert p50 < 0.05  # 中位数 < 50ms
        assert p95 < 0.1   # P95 < 100ms
        print(f"\nRead normal file: P50={p50*1000:.1f}ms, P95={p95*1000:.1f}ms")
    
    @pytest.mark.benchmark
    async def test_list_many_files(self, client_session, test_files):
        """列出大量文件性能"""
        result = await client_session.call_tool("list_directory", {
            "path": str(test_files / self.MANY_FILES_DIR)
        })
        # 验证返回1000个文件
        assert "file_0999.txt" in result.content[0].text
```

---

## 6. 测试运行

### 6.1 常用命令

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit -v

# 运行集成测试
pytest tests/integration -v

# 运行安全测试
pytest tests/unit/test_security.py -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html

# 运行性能测试
pytest tests/performance -v -m benchmark
```

### 6.2 CI配置

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      
      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-fail-under=80%
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```
