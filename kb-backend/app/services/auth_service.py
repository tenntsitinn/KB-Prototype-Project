from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.user import User, UserRole, Role, RolePermission
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.schemas.auth import TokenResponse, UserInfo


def _build_user_info(user: User) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        is_superuser=user.is_superuser,
        roles=[ur.role.role_code for ur in user.roles],
        status=user.status,
    )


def _extract_permissions(user: User) -> list[str]:
    from app.core.permissions import ALL_PERMISSIONS
    if user.is_superuser:
        return ["*"] + ALL_PERMISSIONS
    perms: set[str] = set()
    for ur in user.roles:
        if hasattr(ur.role, 'permissions'):
            for rp in ur.role.permissions:
                perms.add(rp.permission_code)
    return sorted(perms)


async def _load_user_with_permissions(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
        )
        .where(User.username == username)
    )
    return result.scalar_one_or_none()


async def _load_user_by_id_with_permissions(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
        )
        .where(User.id == user_id, User.status == "active")
    )
    return result.scalar_one_or_none()


async def login(db: AsyncSession, username: str, password: str) -> TokenResponse:
    user = await _load_user_with_permissions(db, username)

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户已被禁用")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    token_data = {"sub": user.id, "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user_info=_build_user_info(user),
        permissions=_extract_permissions(user),
    )


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌类型")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")

    user = await _load_user_by_id_with_permissions(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    token_data = {"sub": user.id, "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user_info=_build_user_info(user),
        permissions=_extract_permissions(user),
    )