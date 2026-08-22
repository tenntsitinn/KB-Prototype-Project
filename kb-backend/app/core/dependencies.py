from typing import AsyncGenerator
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.core.permissions import UserPermissions, get_permissions, PERM_PERMISSION_MANAGE
from app.models.user import User, UserRole, Role

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌类型")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")

    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.permissions))
        .where(User.id == user_id, User.status == "active")
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选认证：无/无效凭证时返回 None 而非抛错，供签名 URL 等场景使用"""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    user_id: str | None = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.permissions))
        .where(User.id == user_id, User.status == "active")
    )
    return result.scalar_one_or_none()


async def get_current_permissions_optional(
    user: User | None = Depends(get_current_user_optional),
) -> UserPermissions | None:
    return get_permissions(user) if user else None


async def get_current_permissions(
    user: User = Depends(get_current_user),
) -> UserPermissions:
    return get_permissions(user)


class RequirePermission:
    """权限守卫：必须持有指定权限码之一"""

    def __init__(self, *codes: str):
        self.codes = codes

    async def __call__(self, perms: UserPermissions = Depends(get_current_permissions)) -> UserPermissions:
        if not perms.has_any(*self.codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return perms


class RequireSuperuser:
    """超级管理员守卫：is_superuser 或拥有 permission:manage 权限"""

    async def __call__(self, perms: UserPermissions = Depends(get_current_permissions)) -> UserPermissions:
        if not perms.is_superuser and not perms.has(PERM_PERMISSION_MANAGE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
        return perms