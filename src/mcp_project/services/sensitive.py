import os
from pathlib import Path
from typing import List, Set

from .logger import get_logger


DEFAULT_SENSITIVE_PATTERNS: Set[str] = {
    # 环境/密钥
    ".env", ".env.*", "*.env",
    ".key", "*.key",
    ".pem", "*.pem",
    ".crt", "*.crt",
    ".p12", "*.p12",
    ".pfx", "*.pfx",
    # 配置
    ".git", ".gitignore",
    "config.ini", "*.config",
    "credentials.json",
    # 系统文件
    "etc/passwd", "etc/shadow",
    # 凭证
    ".npmrc", ".pypirc",
    ".ssh/id_rsa", ".ssh/id_ed25519",
}


class SensitiveFileGuard:
    """敏感文件检测

    禁止访问 .env、.key 等敏感文件，
    防止意外泄露凭证和配置信息。
    """

    def __init__(self, extra_patterns: List[str] | None = None):
        self._patterns = DEFAULT_SENSITIVE_PATTERNS.copy()
        if extra_patterns:
            self._patterns.update(extra_patterns)
        self._logger = get_logger("filesystem-mcp")

    def add_pattern(self, pattern: str) -> None:
        self._patterns.add(pattern)

    def is_sensitive(self, path: str) -> bool:
        """检查路径是否为敏感文件"""
        path_lower = path.lower().replace("\\", "/")

        for pattern in self._patterns:
            if pattern.startswith("*/") or pattern.startswith("*."):
                ext = pattern[1:]
                if path_lower.endswith(ext):
                    return True
            elif pattern.endswith(".*"):
                prefix = pattern[:-2]
                path_obj = Path(path)
                name = path_obj.stem.lower()
                if name == prefix:
                    return True
            elif pattern in path_lower:
                return True

        return False

    def check(self, path: str) -> None:
        """检查敏感文件，若命中则抛出异常

        Raises:
            PermissionError: 访问敏感文件
        """
        if self.is_sensitive(path):
            self._logger.warning(
                "敏感文件访问被阻止",
                {"path": path},
            )
            raise PermissionError(f"禁止访问敏感文件: {path}")

    def get_blocked_patterns(self) -> List[str]:
        return sorted(self._patterns)


_instances: dict = {}


def get_sensitive_guard(extra_patterns: List[str] | None = None) -> SensitiveFileGuard:
    """获取敏感文件守卫单例"""
    key = str(sorted(extra_patterns or []))
    if key not in _instances:
        _instances[key] = SensitiveFileGuard(extra_patterns=extra_patterns)
    return _instances[key]
