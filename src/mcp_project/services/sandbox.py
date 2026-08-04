import os
from pathlib import Path
from typing import List, Optional, Set

from .logger import get_logger


class Sandbox:
    """路径沙箱

    限制文件操作范围在指定根目录下，
    防止路径遍历攻击。
    """

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        if allowed_roots is None:
            allowed_roots = [os.getcwd()]
        self._roots: Set[str] = set()
        for root in allowed_roots:
            resolved = str(Path(root).resolve())
            self._roots.add(resolved)
        self._logger = get_logger("filesystem-mcp")

    @property
    def roots(self) -> List[str]:
        return sorted(self._roots)

    def add_root(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        self._roots.add(resolved)

    def remove_root(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        self._roots.discard(resolved)

    def is_within_bounds(self, path: str) -> bool:
        """检查路径是否在沙箱范围内"""
        try:
            resolved = str(Path(path).resolve())
        except (OSError, ValueError):
            return False

        for root in self._roots:
            if resolved == root or resolved.startswith(root + os.sep):
                return True
        return False

    def resolve(self, path: str) -> str:
        """安全解析路径，返回绝对路径。超出沙箱则抛异常"""
        try:
            resolved = str(Path(path).resolve())
        except (OSError, ValueError) as e:
            raise SecurityError(f"无效路径: {path}") from e

        if not self.is_within_bounds(resolved):
            raise SecurityError(
                f"路径超出沙箱范围: {path} "
                f"(允许的根目录: {', '.join(sorted(self._roots))})"
            )

        return resolved

    def validate_path(self, path: str) -> str:
        """验证并返回安全路径，用于文件操作。

        Raises:
            SecurityError: 路径遍历或超出范围
        """
        # 检测路径遍历模式
        path_str = str(path)
        dangerous_patterns = ["..", "~", "//", "\\\\"]
        for pattern in dangerous_patterns:
            if pattern in path_str:
                self._logger.warning(
                    "可疑路径模式被阻止",
                    {"path": path, "pattern": pattern},
                )
                raise SecurityError(f"路径包含危险模式 '{pattern}': {path}")

        return self.resolve(path)


class SecurityError(Exception):
    """安全相关错误"""
    pass


_instances: dict = {}


def get_sandbox(allowed_roots: Optional[List[str]] = None) -> Sandbox:
    """获取沙箱单例"""
    key = str(sorted(allowed_roots or [os.getcwd()]))
    if key not in _instances:
        _instances[key] = Sandbox(allowed_roots=allowed_roots)
    return _instances[key]
