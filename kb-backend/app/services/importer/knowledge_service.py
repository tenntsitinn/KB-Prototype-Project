from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.knowledge_unit import KnowledgeUnit, UnitPermission, UnitStatus
from app.models.user import User, UserRole
from app.schemas.knowledge import KnowledgeUnitCreate, KnowledgeUnitUpdate, PermissionCreate
from app.config import settings
from pymilvus import MilvusClient


async def create_knowledge_unit(db: AsyncSession, data: KnowledgeUnitCreate) -> KnowledgeUnit:
    """创建知识单元记录"""
    unit = KnowledgeUnit(**data.model_dump())
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return unit


async def update_knowledge_unit(db: AsyncSession, unit_id: str, data: KnowledgeUnitUpdate) -> KnowledgeUnit | None:
    """更新知识单元内容"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id, KnowledgeUnit.status != UnitStatus.DELETED)
        .values(**data.model_dump(exclude_none=True))
        .returning(KnowledgeUnit)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.fetchone()
    return row[0] if row else None


async def soft_delete_knowledge_unit(db: AsyncSession, unit_id: str) -> bool:
    """软删除知识单元"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id, KnowledgeUnit.status != UnitStatus.DELETED)
        .values(status=UnitStatus.DELETED, deleted_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount > 0:
        _delete_milvus_vectors(unit_id)

    return result.rowcount > 0


def _delete_milvus_vectors(unit_id: str) -> None:
    """删除 Milvus 中指定 unit_id 的所有向量"""
    try:
        uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        client = MilvusClient(uri=uri)
        client.delete(
            collection_name=settings.MILVUS_COLLECTION,
            filter=f'unit_id == "{unit_id}"',
        )
    except Exception:
        pass


async def get_knowledge_unit(db: AsyncSession, unit_id: str) -> KnowledgeUnit | None:
    """按 ID 查询知识单元"""
    stmt = select(KnowledgeUnit).where(
        KnowledgeUnit.id == unit_id,
        KnowledgeUnit.status != UnitStatus.DELETED,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_knowledge_units(
    db: AsyncSession,
    title: str | None = None,
    category: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[KnowledgeUnit], int]:
    """分页查询知识单元列表"""
    if status == "deleted":
        conditions = [KnowledgeUnit.status == UnitStatus.DELETED]
    else:
        conditions = [KnowledgeUnit.status != UnitStatus.DELETED]
        if status:
            conditions.append(KnowledgeUnit.status == status)

    if title:
        conditions.append(KnowledgeUnit.title.ilike(f"%{title}%"))
    if category:
        conditions.append(KnowledgeUnit.category == category)

    count_stmt = select(KnowledgeUnit).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    stmt = (
        select(KnowledgeUnit)
        .where(*conditions)
        .order_by(KnowledgeUnit.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_unit_content(db: AsyncSession, unit_id: str, content: str, summary: str) -> None:
    """更新知识单元正文和摘要"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id)
        .values(content=content, summary=summary, status=UnitStatus.PUBLISHED)
    )
    await db.execute(stmt)
    await db.commit()


async def cleanup_soft_deleted(db: AsyncSession, days: int = 7) -> list[str]:
    """清理超过 N 天的软删除记录，同时删除 MinIO 文件和 Milvus 向量，返回被清理的 unit_id 列表"""
    from datetime import timedelta
    from app.services.importer.minio_client import delete_prefix
    from app.config import settings

    cutoff = datetime.utcnow() - timedelta(days=days)

    stmt = select(KnowledgeUnit.id, KnowledgeUnit.minio_path).where(
        KnowledgeUnit.status == UnitStatus.DELETED,
        KnowledgeUnit.deleted_at < cutoff,
    )
    result = await db.execute(stmt)
    rows = result.all()

    unit_ids = [row[0] for row in rows]

    if unit_ids:
        # 删除 MinIO 文件
        for uid in unit_ids:
            try:
                delete_prefix(settings.MINIO_BUCKET_DOCS, f"{uid}/")
            except Exception:
                pass

        # 删除 Milvus 向量
        for uid in unit_ids:
            _delete_milvus_vectors(uid)

        # 硬删除 DB 记录
        del_stmt = delete(KnowledgeUnit).where(KnowledgeUnit.id.in_(unit_ids))
        await db.execute(del_stmt)
        await db.commit()

    return unit_ids


async def get_unit_permissions(db: AsyncSession, unit_id: str) -> list[UnitPermission]:
    """查询知识单元的所有数据权限"""
    stmt = select(UnitPermission).where(UnitPermission.unit_id == unit_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def set_unit_permissions(db: AsyncSession, unit_id: str, permissions: list[PermissionCreate]) -> list[UnitPermission]:
    """批量替换知识单元的数据权限（先删后插）"""
    # 删除旧权限
    del_stmt = delete(UnitPermission).where(UnitPermission.unit_id == unit_id)
    await db.execute(del_stmt)

    # 插入新权限
    new_perms = [
        UnitPermission(unit_id=unit_id, target_type=p.target_type, target_id=p.target_id)
        for p in permissions
    ]
    if new_perms:
        db.add_all(new_perms)

    await db.commit()

    # 查询返回
    return await get_unit_permissions(db, unit_id)


async def check_unit_permissions(
    db: AsyncSession,
    user_id: str,
    unit_ids: list[str],
) -> tuple[list[str], list[str]]:
    """四维 OR 权限检查，返回 (authorized_unit_ids, unauthorized_unit_ids)"""
    if not unit_ids:
        return [], []

    # 加载用户及角色
    user_stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        return [], list(unit_ids)

    # 超管直接放行
    if user.is_superuser:
        return list(unit_ids), []

    role_ids = [ur.role_id for ur in user.roles]

    # 四维 OR 匹配
    perm_stmt = select(UnitPermission.unit_id).where(
        UnitPermission.unit_id.in_(unit_ids),
        (
            (UnitPermission.target_type == "global")
            | (
                (UnitPermission.target_type == "department")
                & (UnitPermission.target_id == user.department_id)
            )
            | (
                (UnitPermission.target_type == "role")
                & (UnitPermission.target_id.in_(role_ids))
            )
            | (
                (UnitPermission.target_type == "user")
                & (UnitPermission.target_id == user.id)
            )
        ),
    )
    perm_result = await db.execute(perm_stmt)
    authorized = [row[0] for row in perm_result.all()]
    authorized_set = set(authorized)
    unauthorized = [uid for uid in unit_ids if uid not in authorized_set]

    return authorized, unauthorized


async def restore_knowledge_unit(db: AsyncSession, unit_id: str) -> bool:
    """恢复软删除的知识单元"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id, KnowledgeUnit.status == UnitStatus.DELETED)
        .values(status=UnitStatus.DRAFT, deleted_at=None)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def permanent_delete_knowledge_unit(db: AsyncSession, unit_id: str) -> bool:
    """永久删除知识单元（清理 MinIO + Milvus + DB）"""
    from app.services.importer.minio_client import delete_prefix
    from app.config import settings

    # 确认记录存在
    stmt = select(KnowledgeUnit).where(KnowledgeUnit.id == unit_id)
    result = await db.execute(stmt)
    unit = result.scalar_one_or_none()
    if not unit:
        return False

    # 删除 MinIO 文件
    try:
        delete_prefix(settings.MINIO_BUCKET_DOCS, f"{unit_id}/")
    except Exception:
        pass

    # 删除 Milvus 向量
    _delete_milvus_vectors(unit_id)

    # 硬删除 DB 记录（含切片，软删除时保留以便恢复）
    del_stmt = delete(KnowledgeUnit).where(KnowledgeUnit.id == unit_id)
    await db.execute(del_stmt)
    from app.models.knowledge_unit import KnowledgeChunk
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id))
    await db.commit()
    return True


async def batch_soft_delete_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量软删除知识单元，返回成功删除的数量"""
    if not unit_ids:
        return 0
    stmt = (
        update(KnowledgeUnit)
        .where(
            KnowledgeUnit.id.in_(unit_ids),
            KnowledgeUnit.status != UnitStatus.DELETED,
        )
        .values(status=UnitStatus.DELETED, deleted_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount > 0:
        for uid in unit_ids:
            _delete_milvus_vectors(uid)
    return result.rowcount


async def batch_restore_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量恢复已删除的知识单元，返回成功恢复的数量"""
    if not unit_ids:
        return 0
    stmt = (
        update(KnowledgeUnit)
        .where(
            KnowledgeUnit.id.in_(unit_ids),
            KnowledgeUnit.status == UnitStatus.DELETED,
        )
        .values(status=UnitStatus.PUBLISHED, deleted_at=None)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def batch_permanent_delete_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量永久删除知识单元（清理 MinIO + Milvus + DB + 切片），返回成功删除的数量"""
    from app.services.importer.minio_client import delete_prefix
    from app.config import settings
    from app.models.knowledge_unit import KnowledgeChunk

    if not unit_ids:
        return 0

    stmt = select(KnowledgeUnit).where(
        KnowledgeUnit.id.in_(unit_ids),
        KnowledgeUnit.status == UnitStatus.DELETED,
    )
    result = await db.execute(stmt)
    units = result.scalars().all()
    if not units:
        return 0

    for unit in units:
        try:
            delete_prefix(settings.MINIO_BUCKET_DOCS, f"{unit.id}/")
        except Exception:
            pass
        _delete_milvus_vectors(unit.id)
        await db.execute(delete(KnowledgeUnit).where(KnowledgeUnit.id == unit.id))
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit.id))

    await db.commit()
    return len(units)