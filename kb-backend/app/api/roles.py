from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user, RequireSuperuser
from app.core.permissions import UserPermissions
from app.schemas.auth import (
    RoleResponse,
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleDetailResponse,
    RolePermissionAssignRequest,
)
from app.services import user_service

router = APIRouter(prefix="/api/org/roles", tags=["角色管理"])


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    roles = await user_service.list_roles(db)
    return [
        RoleResponse(id=r.id, role_name=r.role_name, role_code=r.role_code, description=r.description)
        for r in roles
    ]


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    role = await user_service.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return RoleDetailResponse(
        id=role.id,
        role_name=role.role_name,
        role_code=role.role_code,
        description=role.description,
        permissions=[p.permission_code for p in role.permissions],
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    request: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    try:
        role = await user_service.create_role(
            db, request.role_name, request.role_code, request.description
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return RoleResponse(
        id=role.id, role_name=role.role_name, role_code=role.role_code, description=role.description
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    request: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    role = await user_service.update_role(
        db, role_id,
        role_name=request.role_name,
        description=request.description,
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return RoleResponse(
        id=role.id, role_name=role.role_name, role_code=role.role_code, description=role.description
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    deleted = await user_service.delete_role(db, role_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")


@router.post("/{role_id}/permissions")
async def assign_role_permissions(
    role_id: str,
    request: RolePermissionAssignRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    role = await user_service.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    perms = await user_service.set_role_permissions(db, role_id, request.permissions)
    return {
        "role_id": role_id,
        "permissions": [p.permission_code for p in perms],
    }