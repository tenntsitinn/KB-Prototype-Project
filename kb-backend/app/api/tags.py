from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, RequirePermission
from app.core.permissions import UserPermissions, PERM_KNOWLEDGE_MANAGE
from app.schemas.tag import TagCreate, TagUpdate, TagOut
from app.services import tag_service

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
async def list_tags(
    db: AsyncSession = Depends(get_db),
):
    """标签列表（知识查看权限即可读，供筛选/表单使用）"""
    tags = await tag_service.list_tags(db)
    return [TagOut(id=t.id, name=t.name, sort_order=t.sort_order, created_at=t.created_at) for t in tags]


@router.post("", response_model=TagOut)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """新建标签（需知识管理权限）"""
    try:
        tag = await tag_service.create_tag(db, data.name, data.sort_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TagOut(id=tag.id, name=tag.name, sort_order=tag.sort_order, created_at=tag.created_at)


@router.put("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: str,
    data: TagUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """更新标签名/排序，引用处同步更新（需知识管理权限）"""
    try:
        tag = await tag_service.update_tag(db, tag_id, data.name, data.sort_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    return TagOut(id=tag.id, name=tag.name, sort_order=tag.sort_order, created_at=tag.created_at)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """删除标签，引用该标签的知识单元类别置空（需知识管理权限）"""
    ok = await tag_service.delete_tag(db, tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="标签不存在")
