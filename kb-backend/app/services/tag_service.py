"""标签管理服务：tags 表 CRUD + 种子初始化"""
import logging

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_unit import Tag, KnowledgeUnit

logger = logging.getLogger(__name__)


async def seed_tags(db: AsyncSession) -> None:
    """初始化标签：以库内已有 distinct 类别值作为种子（无数据则留空）"""
    result = await db.execute(
        select(KnowledgeUnit.category)
        .where(KnowledgeUnit.category != "", KnowledgeUnit.status != "deleted")
        .distinct()
    )
    existing_categories = {row[0] for row in result.all()}

    existing_tags = await db.execute(select(Tag.name))
    existing_tag_names = {row[0] for row in existing_tags.all()}

    to_create = existing_categories - existing_tag_names
    if to_create:
        for i, name in enumerate(sorted(to_create)):
            db.add(Tag(name=name, sort_order=i))
        await db.commit()


async def ensure_tag(db: AsyncSession, name: str) -> Tag | None:
    """确保标签存在（不存在则自动创建）。

    供上传/编辑场景使用：上传者在表单里输入的新标签值直接入库，
    让标签表随上传自然增长，由标签管理页做后续维护。
    """
    name = (name or "").strip()
    if not name:
        return None
    existing = await db.execute(select(Tag).where(Tag.name == name))
    tag = existing.scalar_one_or_none()
    if tag:
        return tag
    try:
        return await create_tag(db, name)
    except ValueError:
        # 并发下已被创建，重新读取
        existing = await db.execute(select(Tag).where(Tag.name == name))
        return existing.scalar_one_or_none()


async def list_tags(db: AsyncSession) -> list[Tag]:
    result = await db.execute(select(Tag).order_by(Tag.sort_order, Tag.created_at))
    return list(result.scalars().all())


async def create_tag(db: AsyncSession, name: str, sort_order: int = 0) -> Tag:
    name = name.strip()
    if not name:
        raise ValueError("标签名不能为空")

    existing = await db.execute(select(Tag).where(Tag.name == name))
    if existing.scalar_one_or_none():
        raise ValueError("标签已存在")

    if sort_order == 0:
        max_result = await db.execute(select(func.max(Tag.sort_order)))
        sort_order = (max_result.scalar() or 0) + 1

    tag = Tag(name=name, sort_order=sort_order)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def update_tag(db: AsyncSession, tag_id: str, name: str | None = None, sort_order: int | None = None) -> Tag | None:
    tag = await db.get(Tag, tag_id)
    if not tag:
        return None

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("标签名不能为空")
        if name != tag.name:
            existing = await db.execute(select(Tag).where(Tag.name == name, Tag.id != tag_id))
            if existing.scalar_one_or_none():
                raise ValueError("标签已存在")
            # 同步更新引用该标签的知识单元
            from sqlalchemy import update
            await db.execute(
                update(KnowledgeUnit).where(KnowledgeUnit.category == tag.name).values(category=name)
            )
            # 同步更新题库中引用该标签的题目
            from app.models.knowledge_unit import QuizQuestion
            await db.execute(
                update(QuizQuestion).where(QuizQuestion.category == tag.name).values(category=name)
            )
        tag.name = name

    if sort_order is not None:
        tag.sort_order = sort_order

    await db.commit()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag_id: str) -> bool:
    tag = await db.get(Tag, tag_id)
    if not tag:
        return False
    name = tag.name
    await db.execute(delete(Tag).where(Tag.id == tag_id))
    # 引用该标签的知识单元 category 置空
    from sqlalchemy import update
    await db.execute(
        update(KnowledgeUnit).where(KnowledgeUnit.category == name).values(category="")
    )
    await db.commit()
    return True
