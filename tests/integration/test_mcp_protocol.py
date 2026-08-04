"""MCP协议集成测试

通过 stdio_client 启动服务器进程，验证完整的 MCP 协议交互。
"""
import asyncio
import sys
import pytest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def server_params():
    return StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=str(PROJECT_ROOT),
    )


@pytest.fixture
def mcp_session(server_params):
    """创建MCP客户端会话"""
    async def _create():
        ctx = stdio_client(server_params)
        read, write = await ctx.__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        return session, ctx

    loop = asyncio.get_event_loop()
    session, ctx = loop.run_until_complete(_create())

    yield session

    async def _cleanup():
        await session.__aexit__(None, None, None)
        await ctx.__aexit__(None, None, None)

    loop.run_until_complete(_cleanup())


class TestToolListing:
    """测试工具列表"""

    @pytest.mark.asyncio
    async def test_list_tools(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) >= 12
                names = [t.name for t in tools.tools]
                assert "list_directory" in names
                assert "read_file" in names
                assert "write_file" in names
                assert "cache_stats" in names


class TestFileOperations:
    """测试文件操作工具"""

    @pytest.mark.asyncio
    async def test_write_and_read(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Write
                r = await session.call_tool("write_file", {
                    "path": "test_integration.txt",
                    "content": "integration test content",
                })
                assert not r.is_error

                # Read back
                r = await session.call_tool("read_file", {
                    "path": "test_integration.txt",
                })
                assert not r.is_error
                assert "integration test content" in r.content[0].text

                # Cleanup
                await session.call_tool("delete_file", {"path": "test_integration.txt"})

    @pytest.mark.asyncio
    async def test_list_directory(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("list_directory", {"path": "."})
                assert not r.is_error
                assert "server.py" in r.content[0].text

    @pytest.mark.asyncio
    async def test_get_file_info(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("get_file_info", {"path": "server.py"})
                assert not r.is_error
                assert "server.py" in r.content[0].text
                assert "大小" in r.content[0].text

    @pytest.mark.asyncio
    async def test_search_files(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("search_files", {
                    "directory": ".",
                    "pattern": "*.py",
                })
                assert not r.is_error
                assert "server.py" in r.content[0].text


class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("read_file", {"path": "no_such_file.txt"})
                assert r.is_error

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("nonexistent_tool", {})
                assert r.is_error


class TestBatchOperations:
    """测试批量操作"""

    @pytest.mark.asyncio
    async def test_batch_read(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create test files
                await session.call_tool("write_file", {"path": "b1.txt", "content": "1"})
                await session.call_tool("write_file", {"path": "b2.txt", "content": "2"})

                # Batch read
                r = await session.call_tool("batch_read_files", {
                    "paths": ["b1.txt", "b2.txt", "no_such.txt"],
                })
                assert not r.is_error
                text = r.content[0].text
                assert "b1.txt" in text
                assert "b2.txt" in text

                # Cleanup
                await session.call_tool("batch_delete_files", {"paths": ["b1.txt", "b2.txt"]})


class TestCacheAndMetrics:
    """测试缓存和可观测性"""

    @pytest.mark.asyncio
    async def test_cache_stats(self, server_params):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("cache_stats", {})
                assert not r.is_error
                assert "metadata" in r.content[0].text
                assert "content" in r.content[0].text
