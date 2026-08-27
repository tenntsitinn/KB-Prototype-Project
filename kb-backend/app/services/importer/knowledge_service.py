from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.knowledge_unit import (
    KnowledgeUnit, UnitPermission, UnitStatus,
    QuizQuestion, QuizQuestionStatus,
)
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
    """软删除知识单元，同步下架关联题目"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id, KnowledgeUnit.status != UnitStatus.DELETED)
        .values(status=UnitStatus.DELETED, deleted_at=datetime.utcnow())
    )
    result = await db.execute(stmt)

    if result.rowcount > 0:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.source_unit_id == unit_id,
                QuizQuestion.status == QuizQuestionStatus.PUBLISHED,
            )
            .values(status=QuizQuestionStatus.OFFLINE)
        )
        await db.commit()
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
    course_id: str | None = None,
    chapter_id: str | None = None,
) -> tuple[list[KnowledgeUnit], int]:
    """分页查询知识单元列表，支持按课程/章节递归筛选"""
    from sqlalchemy import text as sa_text

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

    # 章节/课程递归筛选
    scope_ids: list[str] | None = None
    if chapter_id:
        row = await db.execute(sa_text("""
            WITH RECURSIVE ct AS (
                SELECT id FROM chapters WHERE id = :cid
                UNION ALL
                SELECT c.id FROM chapters c JOIN ct ON c.parent_id = ct.id
            )
            SELECT id FROM ct
        """), {"cid": chapter_id})
        scope_ids = [r[0] for r in row.all()]
    elif course_id:
        row = await db.execute(sa_text("""
            SELECT id FROM chapters WHERE course_id = :course_id
        """), {"course_id": course_id})
        scope_ids = [r[0] for r in row.all()]

    if scope_ids is not None:
        if scope_ids:
            conditions.append(KnowledgeUnit.chapter_id.in_(scope_ids))
        else:
            conditions.append(KnowledgeUnit.id == "__none__")

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

    if not unit_ids:
        return unit_ids

    # 知识点分流：转移归属或标记 delete_pending，避免 FK CASCADE 误删交叉引用
    all_vectors_to_clean: list[str] = []
    for uid in unit_ids:
        vectors_to_clean, _ = await _detach_points_on_unit_deletion(db, uid)
        all_vectors_to_clean.extend(vectors_to_clean)
        await db.flush()

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
    await db.execute(delete(QuizQuestion).where(QuizQuestion.source_unit_id.in_(unit_ids)))
    await db.commit()

    # 清理被删知识点的 topic 向量
    await _clean_point_vectors(all_vectors_to_clean)

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
    """恢复软删除的知识单元，同步重新发布已下架题目"""
    stmt = (
        update(KnowledgeUnit)
        .where(KnowledgeUnit.id == unit_id, KnowledgeUnit.status == UnitStatus.DELETED)
        .values(status=UnitStatus.DRAFT, deleted_at=None)
    )
    result = await db.execute(stmt)

    if result.rowcount > 0:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.source_unit_id == unit_id,
                QuizQuestion.status == QuizQuestionStatus.OFFLINE,
            )
            .values(status=QuizQuestionStatus.PUBLISHED)
        )
        await db.commit()

    return result.rowcount > 0


async def _detach_points_on_unit_deletion(db: AsyncSession, unit_id: str) -> tuple[list[str], int]:
    """永久删除单元前的知识点分流。

    - 仅关联本单元（source_refs 剔除本单元后为空）→ 直接删除
    - 关联多个单元 → 转移归属到剩余来源单元，剔除本单元引用，置为 delete_pending 待人工处理
    - 其他单元名下但引用了本单元 → 剔除引用，置为 delete_pending 待人工处理（内容含本单元贡献）

    返回 (待清理向量的 point_id 列表, 转人工处理数量)。调用方负责 commit。
    """
    import json as _json

    from app.models.education import KnowledgePoint

    vectors_to_clean: list[str] = []
    pending = 0

    async def _valid_owner(candidate_id: str) -> bool:
        return (await db.get(KnowledgeUnit, candidate_id)) is not None

    # 1) 本单元名下的知识点
    result = await db.execute(select(KnowledgePoint).where(KnowledgePoint.unit_id == unit_id))
    for point in result.scalars().all():
        try:
            refs = _json.loads(point.source_refs_json) if point.source_refs_json else []
        except (ValueError, TypeError):
            refs = []
        if not isinstance(refs, list):
            refs = []
        remaining = [r for r in refs if isinstance(r, dict) and r.get("unit_id") != unit_id]

        new_owner = ""
        for ref in remaining:
            if isinstance(ref, dict) and ref.get("unit_id") and await _valid_owner(ref["unit_id"]):
                new_owner = ref["unit_id"]
                break

        if new_owner:
            point.unit_id = new_owner
            point.source_refs_json = _json.dumps(remaining, ensure_ascii=False)
            point.status = "delete_pending"
            pending += 1
        else:
            vectors_to_clean.append(point.id)
            await _clean_candidate_merge_refs(db, point.id)
            await db.execute(delete(KnowledgePoint).where(KnowledgePoint.id == point.id))

    # 2) 其他单元名下但引用了本单元的知识点（自动合并进来的 delta）
    result = await db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.unit_id != unit_id,
            KnowledgePoint.source_refs_json.like(f"%{unit_id}%"),
        )
    )
    for point in result.scalars().all():
        try:
            refs = _json.loads(point.source_refs_json) if point.source_refs_json else []
        except (ValueError, TypeError):
            continue
        if not isinstance(refs, list):
            continue
        if not any(isinstance(r, dict) and r.get("unit_id") == unit_id for r in refs):
            continue
        remaining = [r for r in refs if isinstance(r, dict) and r.get("unit_id") != unit_id]
        point.source_refs_json = _json.dumps(remaining, ensure_ascii=False)
        point.status = "delete_pending"
        pending += 1

    return vectors_to_clean, pending


async def _clean_candidate_merge_refs(db: AsyncSession, deleted_point_id: str) -> None:
    """从其他知识点的 candidate_merge_json 中移除已删除知识点的引用"""
    import json as _json
    from app.models.education import KnowledgePoint

    result = await db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.candidate_merge_json.like(f"%{deleted_point_id}%"),
        )
    )
    for point in result.scalars().all():
        try:
            candidates = _json.loads(point.candidate_merge_json) if point.candidate_merge_json else []
        except (ValueError, TypeError):
            continue
        if not isinstance(candidates, list):
            continue
        filtered = [c for c in candidates if isinstance(c, dict) and c.get("point_id") != deleted_point_id]
        if len(filtered) != len(candidates):
            point.candidate_merge_json = _json.dumps(filtered, ensure_ascii=False)


async def _clean_point_vectors(point_ids: list[str]) -> None:
    if not point_ids:
        return
    from app.services.topic_store import delete_topic_vectors_by_point

    for pid in point_ids:
        await delete_topic_vectors_by_point(pid)


async def permanent_delete_knowledge_unit(db: AsyncSession, unit_id: str) -> bool:
    """永久删除知识单元（清理 MinIO + Milvus + DB + 题目 + 知识点分流）"""
    from app.services.importer.minio_client import delete_prefix
    from app.config import settings

    # 确认记录存在
    stmt = select(KnowledgeUnit).where(KnowledgeUnit.id == unit_id)
    result = await db.execute(stmt)
    unit = result.scalar_one_or_none()
    if not unit:
        return False

    # 知识点分流：单文档的直接删，多文档的转 delete_pending 人工处理
    vectors_to_clean, pending = await _detach_points_on_unit_deletion(db, unit_id)
    # 归属转移是 ORM 修改，必须先落库再删单元行，否则外键级联会把转移中的知识点一起删掉
    await db.flush()

    # 删除 MinIO 文件
    try:
        delete_prefix(settings.MINIO_BUCKET_DOCS, f"{unit_id}/")
    except Exception:
        pass

    # 删除 Milvus 向量
    _delete_milvus_vectors(unit_id)

    # 硬删除 DB 记录（含切片和关联题目）
    del_stmt = delete(KnowledgeUnit).where(KnowledgeUnit.id == unit_id)
    await db.execute(del_stmt)
    from app.models.knowledge_unit import KnowledgeChunk
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id))
    await db.execute(delete(QuizQuestion).where(QuizQuestion.source_unit_id == unit_id))
    await db.commit()

    await _clean_point_vectors(vectors_to_clean)
    return True


async def batch_soft_delete_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量软删除知识单元，同步下架关联题目"""
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

    if result.rowcount > 0:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.source_unit_id.in_(unit_ids),
                QuizQuestion.status == QuizQuestionStatus.PUBLISHED,
            )
            .values(status=QuizQuestionStatus.OFFLINE)
        )
        await db.commit()
        for uid in unit_ids:
            _delete_milvus_vectors(uid)
    return result.rowcount


async def batch_restore_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量恢复已删除的知识单元，同步重新发布已下架题目"""
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

    if result.rowcount > 0:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.source_unit_id.in_(unit_ids),
                QuizQuestion.status == QuizQuestionStatus.OFFLINE,
            )
            .values(status=QuizQuestionStatus.PUBLISHED)
        )
        await db.commit()
    return result.rowcount


async def batch_permanent_delete_knowledge_units(db: AsyncSession, unit_ids: list[str]) -> int:
    """批量永久删除知识单元（清理 MinIO + Milvus + DB + 切片 + 题目 + 知识点分流），返回成功删除的数量"""
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

    vectors_to_clean: list[str] = []
    for unit in units:
        clean, _ = await _detach_points_on_unit_deletion(db, unit.id)
        vectors_to_clean.extend(clean)
        # 归属转移是 ORM 修改，必须先落库再删单元行，否则外键级联会把转移中的知识点一起删掉
        await db.flush()
        try:
            delete_prefix(settings.MINIO_BUCKET_DOCS, f"{unit.id}/")
        except Exception:
            pass
        _delete_milvus_vectors(unit.id)
        await db.execute(delete(KnowledgeUnit).where(KnowledgeUnit.id == unit.id))
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit.id))
        await db.execute(delete(QuizQuestion).where(QuizQuestion.source_unit_id == unit.id))

    await db.commit()
    await _clean_point_vectors(vectors_to_clean)
    return len(units)