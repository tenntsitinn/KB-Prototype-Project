import pytest
from fastapi import HTTPException

from app.core.dependencies import RequirePermission
from app.core.permissions import PERM_KNOWLEDGE_READ, UserPermissions
from app.core.security import decode_token, hash_password
from app.models.user import Role, RolePermission, User, UserRole
from app.services.auth_service import login


async def _create_user_with_permission(db_session, username: str = "reader") -> User:
    user = User(
        id=f"user-{username}",
        username=username,
        password_hash=hash_password("correct-password"),
        display_name="Reader",
        status="active",
    )
    role = Role(id=f"role-{username}", role_name="Reader", role_code=f"reader-{username}")
    role.permissions.append(RolePermission(permission_code=PERM_KNOWLEDGE_READ))
    user.roles.append(UserRole(role=role))
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_login_returns_tokens_and_role_permissions(db_session):
    await _create_user_with_permission(db_session)

    response = await login(db_session, "reader", "correct-password")

    assert decode_token(response.access_token)["type"] == "access"
    assert decode_token(response.refresh_token)["type"] == "refresh"
    assert response.permissions == [PERM_KNOWLEDGE_READ]
    assert response.user_info.username == "reader"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(db_session):
    await _create_user_with_permission(db_session, "wrong-password-user")

    with pytest.raises(HTTPException) as exc_info:
        await login(db_session, "wrong-password-user", "incorrect")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_permission_guard_allows_required_permission():
    guard = RequirePermission(PERM_KNOWLEDGE_READ)
    permissions = UserPermissions({PERM_KNOWLEDGE_READ})

    assert await guard(permissions) is permissions


@pytest.mark.asyncio
async def test_permission_guard_returns_403_when_permission_is_missing():
    guard = RequirePermission(PERM_KNOWLEDGE_READ)

    with pytest.raises(HTTPException) as exc_info:
        await guard(UserPermissions())

    assert exc_info.value.status_code == 403
