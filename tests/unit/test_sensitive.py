"""敏感文件检测单元测试"""
import pytest
from src.mcp_project.services.sensitive import SensitiveFileGuard


class TestSensitiveFileGuard:
    def test_env_is_sensitive(self):
        guard = SensitiveFileGuard()
        assert guard.is_sensitive(".env")
        assert guard.is_sensitive("config.env")

    def test_key_is_sensitive(self):
        guard = SensitiveFileGuard()
        assert guard.is_sensitive("private.key")
        assert guard.is_sensitive("cert.pem")

    def test_normal_file_not_sensitive(self):
        guard = SensitiveFileGuard()
        assert not guard.is_sensitive("server.py")
        assert not guard.is_sensitive("README.md")
        assert not guard.is_sensitive("config.json")

    def test_check_raises_for_sensitive(self):
        guard = SensitiveFileGuard()
        with pytest.raises(PermissionError):
            guard.check(".env")

    def test_check_passes_for_normal(self):
        guard = SensitiveFileGuard()
        guard.check("server.py")  # should not raise

    def test_custom_pattern(self):
        guard = SensitiveFileGuard(extra_patterns=["*.secret"])
        assert guard.is_sensitive("api.secret")
