# 安全加固

> **Read based on task** - 实现安全相关功能时阅读

## 1. 路径沙箱化

### 1.1 设计目标

限制文件操作只能在指定根目录范围内，防止路径遍历攻击。

### 1.2 实现方案

```python
class PathSandbox:
    """路径沙箱 - 限制文件访问范围"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
    
    def is_safe(self, target_path: str) -> bool:
        """检查路径是否在沙箱内"""
        try:
            resolved = Path(target_path).resolve()
            return str(resolved).startswith(str(self.root_path))
        except (OSError, ValueError):
            return False
    
    def validate_path(self, target_path: str) -> Path:
        """验证并返回安全路径"""
        if not self.is_safe(target_path):
            raise SecurityError(f"路径越界: {target_path}")
        return Path(target_path).resolve()
```

### 1.3 攻击场景

| 攻击类型 | 示例 | 防御方式 |
|----------|------|----------|
| 路径遍历 | `../../../etc/passwd` | `Path.resolve()` + 前缀检查 |
| 符号链接 | 指向外部的软链接 | `resolve()` 解析真实路径 |
| 编码绕过 | `..%2f` / `..\\` | 统一规范化处理 |

### 1.4 配置示例

```python
# server.yaml
security:
  sandbox:
    enabled: true
    root_paths:
      - "./workspace"
      - "/tmp/shared"
  blocked_extensions:
    - ".env"
    - ".key"
    - ".pem"
    - ".ssh"
```

---

## 2. 操作审计

### 2.1 审计日志结构

```python
@dataclass
class AuditLog:
    timestamp: datetime       # 操作时间
    user_id: str              # 操作者
    action: str               # 操作类型
    target_path: str          # 目标路径
    before_hash: str | None  # 操作前哈希
    after_hash: str | None   # 操作后哈希
    status: str               # 成功/失败
    ip_address: str           # 来源IP
    details: dict             # 附加信息
```

### 2.2 审计覆盖范围

必须记录的操作：
- [x] 文件读取（含元数据）
- [x] 文件写入/修改
- [x] 文件删除
- [x] 文件重命名
- [x] 权限变更
- [x] 配置变更

### 2.3 存储方案

```python
class AuditService:
    """审计服务"""
    
    async def log(self, log: AuditLog) -> None:
        """记录审计日志"""
        # 同步写入 - 确保不丢失
        await self._storage.save(log)
        
        # 异步通知 - 告警系统
        if log.status == "failed":
            asyncio.create_task(self._alert(log))
    
    async def query(self, filters: dict) -> list[AuditLog]:
        """查询审计日志"""
        return await self._storage.query(filters)
```

---

## 3. 权限控制

### 3.1 权限模型

```python
class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"

class Role(Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"

ROLE_PERMISSIONS = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.EXECUTE},
    Role.EDITOR: {Permission.READ, Permission.WRITE},
    Role.VIEWER: {Permission.READ},
    Role.GUEST: set()
}
```

### 3.2 权限检查

```python
class PermissionGuard:
    """权限守卫"""
    
    def check(self, user: User, permission: Permission, path: str) -> bool:
        """检查用户是否有权执行操作"""
        # 1. 检查角色权限
        if permission not in ROLE_PERMISSIONS[user.role]:
            return False
        
        # 2. 检查路径级权限
        path_perms = self._get_path_permissions(user, path)
        if path_perms and permission not in path_perms:
            return False
        
        # 3. 检查特殊限制
        if self._is_protected(path) and user.role != Role.ADMIN:
            return False
        
        return True
```

---

## 4. 危险操作保护

### 4.1 二次确认机制

```python
class DangerousOpGuard:
    """危险操作守卫"""
    
    CONFIRM_THRESHOLD = 0.7  # 70%置信度需要确认
    
    def requires_confirmation(self, op: Operation) -> bool:
        """判断是否需要二次确认"""
        factors = []
        
        # 因素1: 操作类型
        if op.type in {OperationType.DELETE, OperationType.OVERWRITE}:
            factors.append(0.4)
        
        # 因素2: 文件重要性
        if self._is_important(op.target):
            factors.append(0.3)
        
        # 因素3: 操作范围
        if op.is_batch:
            factors.append(0.2)
        
        risk_score = sum(factors)
        return risk_score >= self.CONFIRM_THRESHOLD
```

### 4.2 保护措施

| 操作类型 | 保护级别 | 实现 |
|----------|----------|------|
| 单文件删除 | 低 | 直接执行（可配置） |
| 批量删除 | 中 | 确认对话框 |
| 系统目录删除 | 高 | 必须管理员权限 + 确认 |
| 覆盖敏感文件 | 高 | 必须确认 + 审计 |

---

## 5. 敏感文件检测

### 5.1 敏感文件规则

```python
SENSITIVE_PATTERNS = [
    # 按扩展名
    (r'\.env$', '环境配置文件'),
    (r'\.key$', '密钥文件'),
    (r'\.pem$', '证书文件'),
    (r'\.p12$', 'PKCS12证书'),
    (r'\.ssh/', 'SSH目录'),
    (r'\.git/', 'Git仓库'),
    
    # 按文件名
    (r'(password|passwd)', '密码文件'),
    (r'(secret|token)', '密钥文件'),
    (r'\.htaccess$', 'Apache配置'),
    (r'\.npmrc$', 'NPM配置'),
    
    # 按内容类型（扩展）
    # 可扩展为内容检测
]
```

### 5.2 实现

```python
class SensitiveFileDetector:
    """敏感文件检测器"""
    
    def is_sensitive(self, path: str, content: bytes | None = None) -> bool:
        """检测是否为敏感文件"""
        # 1. 路径模式匹配
        for pattern, reason in SENSITIVE_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        
        # 2. 内容检测（可选）
        if content:
            return self._scan_content(content)
        
        return False
```

---

## 6. 安全测试清单

### 6.1 必测项

- [ ] 路径遍历攻击（`../`, `..\\`, URL编码）
- [ ] 符号链接逃逸
- [ ] 权限绕过尝试
- [ ] 敏感文件访问
- [ ] 大量删除操作
- [ ] 并发越权访问

### 6.2 测试代码示例

```python
# 路径遍历测试
def test_path_traversal():
    sandbox = PathSandbox("/safe/root")
    
    # 攻击向量
    attacks = [
        "../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "safe/../../../etc/passwd",
        "\\..\\..\\windows\\system32",
    ]
    
    for attack in attacks:
        assert not sandbox.is_safe(attack), f"Path traversal failed: {attack}"
```
