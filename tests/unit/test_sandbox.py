"""沙箱模块单元测试"""
import pytest
from pathlib import Path
from src.mcp_project.services.sandbox import Sandbox, SecurityError


class TestSandbox:
    def test_within_bounds(self, sandbox, tmp_workspace):
        f = tmp_workspace / "test.txt"
        f.write_text("hello")
        assert sandbox.is_within_bounds(str(f))

    def test_outside_bounds(self, sandbox):
        assert not sandbox.is_within_bounds("/etc/passwd")
        assert not sandbox.is_within_bounds("C:\\Windows\\System32")

    def test_resolve_valid(self, sandbox, tmp_workspace):
        f = tmp_workspace / "test.txt"
        f.write_text("hello")
        resolved = sandbox.resolve(str(f))
        assert Path(resolved).exists()

    def test_resolve_traversal(self, sandbox):
        with pytest.raises(SecurityError):
            sandbox.resolve("../../../etc/passwd")

    def test_validate_path_dangerous_pattern(self, sandbox):
        with pytest.raises(SecurityError):
            sandbox.validate_path("../../secret")

    def test_add_remove_root(self, tmp_path):
        # 用 tmp_path 外部的目录测试 remove
        import tempfile
        sb = Sandbox(allowed_roots=[str(tmp_path)])
        # 添加一个不在 tmp_path 下的临时目录
        external = Path(tempfile.mkdtemp())
        try:
            sb.add_root(str(external))
            assert sb.is_within_bounds(str(external / "file.txt"))
            sb.remove_root(str(external))
            assert not sb.is_within_bounds(str(external / "file.txt"))
        finally:
            external.rmdir()
