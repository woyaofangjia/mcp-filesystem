"""配置管理模块单元测试"""
import pytest
from src.mcp_project.services.config import ConfigManager, ServerConfig, ENV_DEFAULTS


class TestConfigManager:
    def test_default_config(self):
        cm = ConfigManager(environment="dev")
        config = cm.get()
        assert config.environment == "dev"
        assert config.log_level == "DEBUG"

    def test_prod_config(self):
        cm = ConfigManager(environment="prod")
        config = cm.get()
        assert config.environment == "prod"
        assert config.log_level == "WARNING"
        assert config.max_concurrent_ops == 50

    def test_invalid_env_defaults_to_dev(self):
        cm = ConfigManager(environment="invalid")
        assert cm.get().environment == "dev"

    def test_validate_valid_config(self):
        cm = ConfigManager(environment="test")
        errors = cm.validate()
        assert len(errors) == 0

    def test_validate_invalid_config(self):
        cm = ConfigManager(environment="test")
        cm.update(log_level="INVALID", max_concurrent_ops=-1)
        errors = cm.validate()
        assert len(errors) >= 2

    def test_update_config(self):
        cm = ConfigManager(environment="dev")
        cm.update(log_level="ERROR")
        assert cm.get().log_level == "ERROR"

    def test_on_change_callback(self):
        cm = ConfigManager(environment="dev")
        called = []
        cm.on_change(lambda c: called.append(c))
        cm.update(log_level="ERROR")
        assert len(called) == 1
        assert called[0].log_level == "ERROR"

    def test_to_dict(self):
        cm = ConfigManager(environment="test")
        d = cm.to_dict()
        assert d["environment"] == "test"
        assert "log_level" in d
        assert "max_concurrent_ops" in d
