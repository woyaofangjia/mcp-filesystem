import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

from .logger import get_logger


class Role(str, Enum):
    READONLY = "readonly"
    READWRITE = "readwrite"
    ADMIN = "admin"


class Permission:
    """单个权限定义"""

    def __init__(self, can_read: bool = True, can_write: bool = False, can_delete: bool = False):
        self.can_read = can_read
        self.can_write = can_write
        self.can_delete = can_delete

    def to_dict(self) -> dict:
        return {
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_delete": self.can_delete,
        }


ROLE_PERMISSIONS: Dict[Role, Permission] = {
    Role.READONLY: Permission(can_read=True, can_write=False, can_delete=False),
    Role.READWRITE: Permission(can_read=True, can_write=True, can_delete=False),
    Role.ADMIN: Permission(can_read=True, can_write=True, can_delete=True),
}


class PermissionManager:
    """权限管理器

    基于角色的访问控制(RBAC)，支持读写执行权限管理。
    """

    def __init__(self, default_role: Role = Role.ADMIN):
        self._users: Dict[str, Role] = {}
        self._role_overrides: Dict[str, Dict[str, Permission]] = {}
        self._default_role = default_role
        self._logger = get_logger("filesystem-mcp")

    def assign_role(self, user_id: str, role: Role) -> None:
        self._users[user_id] = role
        self._logger.info("角色已分配", {"user_id": user_id, "role": role.value})

    def get_role(self, user_id: str) -> Role:
        return self._users.get(user_id, self._default_role)

    def check_permission(
        self,
        user_id: str,
        action: str,
        path: Optional[str] = None,
    ) -> bool:
        """检查用户是否有权执行操作

        Args:
            user_id: 用户ID
            action: 操作类型 (read/write/delete)
            path: 目标路径（用于路径级权限）

        Returns:
            是否有权限
        """
        role = self.get_role(user_id)
        base_perm = ROLE_PERMISSIONS[role]

        if path and user_id in self._role_overrides:
            overrides = self._role_overrides[user_id]
            path_key = self._match_path_override(path, overrides)
            if path_key:
                base_perm = overrides[path_key]

        if action == "read":
            return base_perm.can_read
        elif action == "write":
            return base_perm.can_write
        elif action == "delete":
            return base_perm.can_delete
        else:
            return False

    def require_permission(
        self,
        user_id: str,
        action: str,
        path: Optional[str] = None,
    ) -> None:
        """要求权限，若不满足则抛出异常"""
        if not self.check_permission(user_id, action, path):
            role = self.get_role(user_id)
            self._logger.warning(
                "权限不足",
                {"user_id": user_id, "role": role.value, "action": action, "path": path},
            )
            raise PermissionError(
                f"用户 {user_id} (角色: {role.value}) 无权执行 {action} 操作"
                + (f" 路径: {path}" if path else "")
            )

    def set_path_permission(
        self,
        user_id: str,
        path_pattern: str,
        permission: Permission,
    ) -> None:
        """设置路径级权限覆盖"""
        if user_id not in self._role_overrides:
            self._role_overrides[user_id] = {}
        self._role_overrides[user_id][path_pattern] = permission

    def _match_path_override(
        self,
        path: str,
        overrides: Dict[str, Permission],
    ) -> Optional[str]:
        """匹配路径级权限规则"""
        resolved = str(Path(path).resolve())
        for pattern, perm in overrides.items():
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                if resolved.startswith(prefix):
                    return pattern
            elif resolved == pattern:
                return pattern
        return None

    def get_user_permissions(self, user_id: str) -> Dict[str, dict]:
        """获取用户所有权限信息"""
        role = self.get_role(user_id)
        base = ROLE_PERMISSIONS[role]
        result: Dict[str, dict] = {"base": base.to_dict(), "paths": {}}

        if user_id in self._role_overrides:
            for path, perm in self._role_overrides[user_id].items():
                result["paths"][path] = perm.to_dict()

        return result


_instances: Dict[str, PermissionManager] = {}


def get_permission_manager(default_role: Role = Role.ADMIN) -> PermissionManager:
    """获取权限管理器单例"""
    key = default_role.value
    if key not in _instances:
        _instances[key] = PermissionManager(default_role=default_role)
    return _instances[key]
