from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, RequireSuperuser, get_current_user
from app.core.permissions import UserPermissions
from app.schemas.auth import (
    DepartmentResponse,
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
)
from app.services import user_service

router = APIRouter(prefix="/api/org/departments", tags=["部门管理"])


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    depts = await user_service.list_departments(db)
    return [
        DepartmentResponse(
            id=d.id, parent_id=d.parent_id, name=d.name, leader_id=d.leader_id, sort_order=d.sort_order
        )
        for d in depts
    ]


@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(
    dept_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    dept = await user_service.get_department(db, dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    return DepartmentResponse(
        id=dept.id, parent_id=dept.parent_id, name=dept.name,
        leader_id=dept.leader_id, sort_order=dept.sort_order,
    )


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    request: DepartmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    dept = await user_service.create_department(
        db, request.parent_id, request.name, request.leader_id, request.sort_order
    )
    return DepartmentResponse(
        id=dept.id, parent_id=dept.parent_id, name=dept.name,
        leader_id=dept.leader_id, sort_order=dept.sort_order,
    )


@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    dept_id: str,
    request: DepartmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    dept = await user_service.update_department(
        db, dept_id,
        parent_id=request.parent_id,
        name=request.name,
        leader_id=request.leader_id,
        sort_order=request.sort_order,
    )
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    return DepartmentResponse(
        id=dept.id, parent_id=dept.parent_id, name=dept.name,
        leader_id=dept.leader_id, sort_order=dept.sort_order,
    )


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    deleted = await user_service.delete_department(db, dept_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")