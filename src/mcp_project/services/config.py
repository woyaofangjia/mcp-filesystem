"""配置管理服务

支持 dev/test/prod 环境分离、配置验证和运行时热更新。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from threading import Lock

from .logger import get_logger


@dataclass
class ServerConfig:
    """服务器配置"""
    # 环境
    environment: str = "dev"  # dev / test / prod

    # 日志
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    # 安全
    sandbox_roots: List[str] = field(default_factory=list)
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    chunk_read_limit: int = 10 * 1024 * 1024  # 10MB

    # 性能
    max_concurrent_ops: int = 20
    cache_max_items: int = 500
    cache_max_size: int = 50 * 1024 * 1024
    cache_ttl: int = 300  # 5分钟

    # 审计
    audit_db_path: str = "logs/audit.db"
    audit_retention_days: int = 90

    # 告警
    alert_cooldown: int = 300
    alert_error_rate_threshold: float = 10.0
    alert_memory_threshold: int = 500  # MB


# 环境默认配置
ENV_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "dev": {
        "log_level": "DEBUG",
        "max_concurrent_ops": 5,
        "cache_max_size": 10 * 1024 * 1024,
        "cache_ttl": 60,
    },
    "test": {
        "log_level": "INFO",
        "max_concurrent_ops": 10,
        "cache_max_size": 20 * 1024 * 1024,
        "cache_ttl": 120,
    },
    "prod": {
        "log_level": "WARNING",
        "max_concurrent_ops": 50,
        "cache_max_size": 100 * 1024 * 1024,
        "cache_ttl": 600,
    },
}


class ConfigValidationError(Exception):
    """配置验证错误"""
    pass


class ConfigManager:
    """配置管理器

    功能：
    - 环境配置分离（dev/test/prod）
    - 配置文件加载（JSON）
    - 配置验证
    - 运行时热更新
    - 配置变更回调
    """

    def __init__(self, environment: Optional[str] = None):
        self._lock = Lock()
        self._callbacks: List[Callable[[ServerConfig], None]] = []
        self._logger = get_logger("config")

        # 确定环境
        env = environment or os.environ.get("MCP_ENV", "dev")
        if env not in ENV_DEFAULTS:
            env = "dev"

        self._config = self._create_default_config(env)
        self._logger.info(f"配置管理器初始化", {"environment": env})

    def _create_default_config(self, env: str) -> ServerConfig:
        """创建带环境默认值的配置"""
        defaults = ENV_DEFAULTS.get(env, ENV_DEFAULTS["dev"])
        config = ServerConfig(environment=env)

        for key, value in defaults.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # 沙箱根目录默认为当前工作目录
        if not config.sandbox_roots:
            config.sandbox_roots = [os.getcwd()]

        return config

    def load_from_file(self, config_path: str) -> None:
        """从JSON文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            self._logger.warning(f"配置文件不存在: {config_path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                for key, value in data.items():
                    if hasattr(self._config, key):
                        setattr(self._config, key, value)

            self._logger.info(f"配置已从文件加载: {config_path}")
            self._notify_callbacks()
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"配置文件JSON格式错误: {e}")
        except OSError as e:
            raise ConfigValidationError(f"读取配置文件失败: {e}")

    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors: List[str] = []
        c = self._config

        if c.environment not in ("dev", "test", "prod"):
            errors.append(f"无效的环境: {c.environment}")

        if c.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            errors.append(f"无效的日志级别: {c.log_level}")

        if c.max_concurrent_ops < 1:
            errors.append("max_concurrent_ops 必须 >= 1")

        if c.max_file_size < 1024:
            errors.append("max_file_size 必须 >= 1KB")

        if c.cache_max_items < 1:
            errors.append("cache_max_items 必须 >= 1")

        if c.audit_retention_days < 1:
            errors.append("audit_retention_days 必须 >= 1")

        if not c.sandbox_roots:
            errors.append("sandbox_roots 不能为空")

        return errors

    def get(self) -> ServerConfig:
        """获取当前配置"""
        with self._lock:
            return self._config

    def update(self, **kwargs: Any) -> None:
        """运行时更新配置（热更新）"""
        with self._lock:
            changes: Dict[str, Any] = {}
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    old = getattr(self._config, key)
                    setattr(self._config, key, value)
                    changes[key] = {"old": old, "new": value}

            if changes:
                self._logger.info("配置已更新", {"changes": changes})

        self._notify_callbacks()

    def on_change(self, callback: Callable[[ServerConfig], None]) -> None:
        """注册配置变更回调"""
        self._callbacks.append(callback)

    def _notify_callbacks(self) -> None:
        """通知所有回调"""
        config = self.get()
        for cb in self._callbacks:
            try:
                cb(config)
            except Exception as e:
                self._logger.error(f"配置变更回调失败: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典"""
        c = self._config
        return {
            "environment": c.environment,
            "log_level": c.log_level,
            "log_dir": c.log_dir,
            "max_concurrent_ops": c.max_concurrent_ops,
            "max_file_size": c.max_file_size,
            "cache_max_items": c.cache_max_items,
            "cache_max_size_mb": round(c.cache_max_size / 1024 / 1024, 2),
            "cache_ttl": c.cache_ttl,
            "sandbox_roots": c.sandbox_roots,
            "audit_retention_days": c.audit_retention_days,
        }

    def save_template(self, path: str) -> None:
        """保存配置模板到文件"""
        template = {
            "environment": "dev",
            "log_level": "INFO",
            "log_dir": "logs",
            "max_concurrent_ops": 20,
            "max_file_size": 52428800,
            "cache_max_items": 500,
            "cache_max_size": 52428800,
            "cache_ttl": 300,
            "sandbox_roots": ["."],
            "audit_retention_days": 90,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        self._logger.info(f"配置模板已保存: {path}")


# 单例
_config: Optional[ConfigManager] = None


def get_config_manager(environment: Optional[str] = None) -> ConfigManager:
    global _config
    if _config is None:
        _config = ConfigManager(environment=environment)
    return _config