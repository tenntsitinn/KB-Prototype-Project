"""权限模型：基于 permission_code 的细粒度权限检查"""

from dataclasses import dataclass, field

from app.models.user import User

# ---- 权限码常量 ----
PERM_KNOWLEDGE_MANAGE = "knowledge:manage"
PERM_KNOWLEDGE_MANAGE_PERMISSIONS = "knowledge:manage_permissions"
PERM_GAP_MANAGE = "gap:manage"
PERM_DASHBOARD_VIEW = "dashboard:view"
PERM_QUIZ_MANAGE = "quiz:manage"

# 仅超级管理员拥有的权限（不进入角色可配置列表）
PERM_PERMISSION_MANAGE = "permission:manage"

# 角色可配置权限列表（不包含 permission:manage）
# knowledge:read 和 ai:access 对所有登录用户默认开放，无需配置
ALL_PERMISSIONS = [
    PERM_KNOWLEDGE_MANAGE,
    PERM_KNOWLEDGE_MANAGE_PERMISSIONS,
    PERM_GAP_MANAGE,
    PERM_DASHBOARD_VIEW,
    PERM_QUIZ_MANAGE,
]


@dataclass
class UserPermissions:
    """用户权限集合，superuser 拥有通配符 '*'"""
    codes: set[str] = field(default_factory=set)

    def has(self, code: str) -> bool:
        return "*" in self.codes or code in self.codes

    def has_any(self, *codes: str) -> bool:
        return "*" in self.codes or any(c in self.codes for c in codes)

    @property
    def is_superuser(self) -> bool:
        return "*" in self.codes

    @property
    def list(self) -> list[str]:
        if "*" in self.codes:
            return ["*"] + ALL_PERMISSIONS
        return sorted(self.codes)


def get_permissions(user: User) -> UserPermissions:
    """从 User 对象提取权限集合"""
    if user.is_superuser:
        return UserPermissions({"*"})

    codes: set[str] = set()
    for ur in user.roles:
        for rp in ur.role.permissions:
            codes.add(rp.permission_code)
    return UserPermissions(codes)
