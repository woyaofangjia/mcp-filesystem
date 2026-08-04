"""安全测试

测试路径遍历、敏感文件访问、权限控制等安全机制。
"""
import asyncio
import sys
import pytest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.mcp_project.services.sandbox import Sandbox, SecurityError
from src.mcp_project.services.sensitive import SensitiveFileGuard
from src.mcp_project.services.permissions import PermissionManager, Role, Permission

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def server_params():
    return StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=str(PROJECT_ROOT),
    )


class TestPathTraversal:
    """路径遍历攻击测试"""

    TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\Windows\\System32\\config\\SAM",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "..%252f..%252f..%252fetc%252fpasswd",
        "....\\\\....\\\\....\\\\Windows",
    ]

    def test_sandbox_blocks_traversal(self, sandbox):
        """沙箱阻止所有遍历模式"""
        for payload in self.TRAVERSAL_PAYLOADS:
            with pytest.raises((SecurityError, Exception)):
                sandbox.resolve(payload)

    def test_sandbox_blocks_double_dot(self, sandbox):
        with pytest.raises(SecurityError):
            sandbox.validate_path("../secret")

    @pytest.mark.asyncio
    async def test_server_blocks_traversal(self, server_params):
        """服务器阻止路径遍历"""
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for payload in ["../../../etc/passwd", "../../Windows/System32"]:
                    r = await session.call_tool("read_file", {"path": payload})
                    assert r.is_error, f"路径遍历未被阻止: {payload}"


class TestSensitiveFileAccess:
    """敏感文件访问测试"""

    SENSITIVE_FILES = [
        ".env",
        "config.key",
        "cert.pem",
        "private.key",
        "credentials.json",
    ]

    def test_guard_blocks_sensitive(self):
        guard = SensitiveFileGuard()
        for f in self.SENSITIVE_FILES:
            with pytest.raises(PermissionError):
                guard.check(f)

    @pytest.mark.asyncio
    async def test_server_blocks_sensitive(self, server_params):
        """服务器阻止敏感文件访问"""
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("read_file", {"path": ".env"})
                assert r.is_error

    def test_guard_allows_normal(self):
        guard = SensitiveFileGuard()
        guard.check("server.py")
        guard.check("README.md")
        guard.check("config.json")


class TestPermissionControl:
    """权限控制测试"""

    def test_readonly_cannot_write(self):
        pm = PermissionManager(default_role=Role.READONLY)
        assert pm.check_permission("user1", "read")
        assert not pm.check_permission("user1", "write")
        assert not pm.check_permission("user1", "delete")

    def test_readwrite_cannot_delete(self):
        pm = PermissionManager(default_role=Role.READWRITE)
        assert pm.check_permission("user1", "read")
        assert pm.check_permission("user1", "write")
        assert not pm.check_permission("user1", "delete")

    def test_admin_can_all(self):
        pm = PermissionManager(default_role=Role.ADMIN)
        assert pm.check_permission("user1", "read")
        assert pm.check_permission("user1", "write")
        assert pm.check_permission("user1", "delete")

    def test_require_permission_raises(self):
        pm = PermissionManager(default_role=Role.READONLY)
        with pytest.raises(PermissionError):
            pm.require_permission("user1", "delete")

    def test_role_assignment(self):
        pm = PermissionManager(default_role=Role.READONLY)
        assert pm.get_role("user1") == Role.READONLY
        pm.assign_role("user1", Role.ADMIN)
        assert pm.get_role("user1") == Role.ADMIN
        assert pm.check_permission("user1", "delete")

    def test_path_level_permission(self):
        pm = PermissionManager(default_role=Role.ADMIN)
        pm.set_path_permission("user1", "/restricted/*", Permission(can_read=False))
        assert pm.check_permission("user1", "read", "/restricted/file.txt") is False
        assert pm.check_permission("user1", "read", "/normal/file.txt") is True


class TestSandboxBoundary:
    """沙箱边界测试"""

    def test_symlink_escape(self, tmp_path):
        """符号链接逃逸测试"""
        sb = Sandbox(allowed_roots=[str(tmp_path)])
        # 在沙箱内创建指向沙箱外的符号链接
        import os
        target = tmp_path.parent / "outside_target.txt"
        target.write_text("secret")
        link = tmp_path / "escape_link"
        try:
            os.symlink(str(target), str(link))
            # 沙箱应该阻止访问（resolved path 在沙箱外）
            assert not sb.is_within_bounds(str(target))
        except (OSError, NotImplementedError):
            pytest.skip("系统不支持符号链接")

    def test_nested_traversal(self, sandbox, tmp_workspace):
        """嵌套路径遍历"""
        nested = tmp_workspace / "a" / "b" / "c"
        nested.mkdir(parents=True)
        f = nested / "file.txt"
        f.write_text("ok")
        assert sandbox.is_within_bounds(str(f))

    def test_root_itself_in_bounds(self, sandbox, tmp_workspace):
        """根目录本身在范围内"""
        assert sandbox.is_within_bounds(str(tmp_workspace))
