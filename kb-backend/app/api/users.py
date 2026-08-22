from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, RequireSuperuser
from app.core.permissions import UserPermissions
from app.schemas.auth import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListResponse,
    RoleAssignRequest,
)
from app.services import user_service

router = APIRouter(prefix="/api/org/users", tags=["用户管理"])


@router.get("", response_model=UserListResponse)
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    users, total = await user_service.list_users(db, offset, limit)
    items = [
        UserResponse(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            email=u.email,
            department_id=u.department_id,
            status=u.status,
            is_superuser=u.is_superuser,
            roles=[ur.role.role_code for ur in u.roles],
            last_login_at=u.last_login_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]
    return UserListResponse(items=items, total=total)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    try:
        user = await user_service.create_user(
            db, request.username, request.password, request.display_name, request.email
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        status=user.status,
        is_superuser=user.is_superuser,
        roles=[],
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        status=user.status,
        is_superuser=user.is_superuser,
        roles=[ur.role.role_code for ur in user.roles],
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    user = await user_service.update_user(
        db, user_id,
        display_name=request.display_name,
        email=request.email,
        department_id=request.department_id,
        status=request.status,
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        status=user.status,
        is_superuser=user.is_superuser,
        roles=[ur.role.role_code for ur in user.roles],
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role(
    user_id: str,
    request: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    try:
        await user_service.assign_role(db, user_id, request.role_code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: str,
    role_code: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    try:
        await user_service.remove_role(db, user_id, role_code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))