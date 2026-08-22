import json
import numpy as np
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_unit import KnowledgeGap, GapStatus
from app.services.vectorizer import embed_texts


async def record_gap(db: AsyncSession, question: str) -> None:
    """记录一次知识缺口。如果与已有缺口相似则合并，否则新建。"""
    if not question or len(question) < 3:
        return

    # 1. 向量化当前问题
    embeddings = await embed_texts([question])
    if not embeddings:
        return
    query_vec = np.array(embeddings[0])

    # 2. 查询所有 unresolved 缺口
    stmt = select(KnowledgeGap).where(KnowledgeGap.status == GapStatus.UNRESOLVED)
    result = await db.execute(stmt)
    gaps = list(result.scalars().all())

    # 3. 尝试匹配已有缺口
    matched = await _match_existing_gap(db, gaps, question, query_vec)
    if matched:
        return

    # 4. 新建缺口
    new_gap = KnowledgeGap(
        question_pattern=question,
        sample_questions_json=json.dumps([question], ensure_ascii=False),
        ask_count=1,
        last_asked_at=datetime.utcnow(),
        status=GapStatus.UNRESOLVED,
    )
    db.add(new_gap)
    await db.commit()


async def _match_existing_gap(
    db: AsyncSession,
    gaps: list[KnowledgeGap],
    question: str,
    query_vec: np.ndarray,
) -> bool:
    """在已有缺口列表中查找相似项，找到则合并返回 True"""
    if not gaps:
        return False

    patterns = [g.question_pattern for g in gaps]
    pattern_embeddings = await embed_texts(patterns)
    if not pattern_embeddings:
        return False

    pattern_vecs = np.array(pattern_embeddings)
    # 余弦相似度
    norms_p = np.linalg.norm(pattern_vecs, axis=1, keepdims=True)
    norms_p[norms_p == 0] = 1
    pattern_vecs = pattern_vecs / norms_p
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return False
    query_vec_n = query_vec / query_norm
    scores = np.dot(pattern_vecs, query_vec_n)

    best_idx = int(np.argmax(scores))
    if scores[best_idx] < 0.85:
        return False

    # 合并到已有缺口
    gap = gaps[best_idx]
    try:
        samples = json.loads(gap.sample_questions_json)
    except (json.JSONDecodeError, TypeError):
        samples = []
    if question not in samples:
        samples.append(question)
        if len(samples) > 20:
            samples = samples[-20:]

    gap.ask_count += 1
    gap.sample_questions_json = json.dumps(samples, ensure_ascii=False)
    gap.last_asked_at = datetime.utcnow()
    await db.commit()
    return True


async def list_gaps(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    status: GapStatus | None = None,
) -> tuple[list[KnowledgeGap], int]:
    """查询缺口列表"""
    stmt = select(KnowledgeGap)
    count_stmt = select(func.count(KnowledgeGap.id))
    if status:
        stmt = stmt.where(KnowledgeGap.status == status)
        count_stmt = count_stmt.where(KnowledgeGap.status == status)

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    result = await db.execute(
        stmt.order_by(KnowledgeGap.ask_count.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def resolve_gap(db: AsyncSession, gap_id: str, unit_id: str = "") -> KnowledgeGap | None:
    """标记缺口为已解决"""
    stmt = select(KnowledgeGap).where(KnowledgeGap.id == gap_id)
    result = await db.execute(stmt)
    gap = result.scalar_one_or_none()
    if not gap:
        return None

    gap.status = GapStatus.RESOLVED
    if unit_id:
        gap.resolved_unit_id = unit_id
    await db.commit()
    await db.refresh(gap)
    return gap


async def ignore_gap(db: AsyncSession, gap_id: str) -> KnowledgeGap | None:
    """标记缺口为忽略"""
    stmt = select(KnowledgeGap).where(KnowledgeGap.id == gap_id)
    result = await db.execute(stmt)
    gap = result.scalar_one_or_none()
    if not gap:
        return None

    gap.status = GapStatus.IGNORED
    await db.commit()
    await db.refresh(gap)
    return gap