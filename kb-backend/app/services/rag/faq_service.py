import json
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

from pymilvus import MilvusClient
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.config import settings
from app.models.knowledge_unit import FAQ, FAQSourceType, FAQStatus, QAAccessLog, KnowledgeUnit
from app.services.vectorizer import embed_texts


# ---------------------------------------------------------------------------
# Milvus FAQ cache collection
# ---------------------------------------------------------------------------

_faq_cache_client: MilvusClient | None = None


def _get_faq_cache_client() -> MilvusClient:
    global _faq_cache_client
    if _faq_cache_client is None:
        if settings.MILVUS_LITE_DB:
            _faq_cache_client = MilvusClient(uri=settings.MILVUS_LITE_DB)
        else:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            _faq_cache_client = MilvusClient(uri=uri)
    return _faq_cache_client


def _ensure_faq_collection() -> MilvusClient:
    client = _get_faq_cache_client()
    collection = settings.FAQ_CACHE_COLLECTION
    if not client.has_collection(collection):
        client.create_collection(
            collection_name=collection,
            dimension=settings.EMBEDDING_DIM,
            metric_type="COSINE",
            auto_id=True,
            enable_dynamic_field=True,
        )
        client.create_index(
            collection_name=collection,
            field_name="vector",
            index_params={
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200},
            },
        )
    client.load_collection(collection)
    return client


# ---------------------------------------------------------------------------
# LLM FAQ answer generation
# ---------------------------------------------------------------------------

FAQ_ANSWER_PROMPT = """你是一个知识库助手。根据用户高频提问和相关知识库内容，生成一个标准化的FAQ答案。

规则：
1. 答案应准确、简洁、直接回答用户问题
2. 如果关联知识单元有相关内容，优先使用
3. 答案长度控制在200-500字
4. 如果知识库内容不足以回答问题，根据常识给出通用回答

用户问题：{question}

关联知识库内容：
{context}

FAQ答案："""


async def _generate_faq_answer(question: str, context: str) -> str:
    try:
        client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY or settings.EMBEDDING_API_KEY,
            base_url=settings.LLM_BASE_URL or settings.EMBEDDING_BASE_URL,
        )
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": FAQ_ANSWER_PROMPT.format(question=question, context=context),
            }],
            temperature=0.3,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# FAQ Cache
# ---------------------------------------------------------------------------

async def match_faq_cache(query_vector: list[float]) -> dict | None:
    """匹配 FAQ 缓存，返回 {faq_id, question, answer} 或 None"""
    try:
        client = _ensure_faq_collection()
        results = client.search(
            collection_name=settings.FAQ_CACHE_COLLECTION,
            data=[query_vector],
            limit=1,
            output_fields=["faq_id", "question", "answer"],
        )
        if not results or not results[0]:
            return None
        hit = results[0][0]
        if hit["distance"] >= settings.FAQ_CACHE_THRESHOLD:
            return {
                "faq_id": hit["entity"]["faq_id"],
                "question": hit["entity"]["question"],
                "answer": hit["entity"]["answer"],
            }
        return None
    except Exception:
        return None


async def _insert_faq_cache(faq_id: str, question: str, answer: str) -> None:
    embeddings = await embed_texts([question])
    if not embeddings:
        return
    client = _ensure_faq_collection()
    client.insert(
        collection_name=settings.FAQ_CACHE_COLLECTION,
        data=[{
            "faq_id": faq_id,
            "question": question,
            "answer": answer,
            "vector": np.array(embeddings[0], dtype=np.float32),
        }],
    )


async def _delete_faq_cache(faq_id: str) -> None:
    try:
        client = _get_faq_cache_client()
        client.delete(
            collection_name=settings.FAQ_CACHE_COLLECTION,
            filter=f'faq_id == "{faq_id}"',
        )
    except Exception:
        pass


async def sync_faq_cache(db: AsyncSession) -> int:
    """全量同步已发布 FAQ 到向量缓存，返回同步数量"""
    stmt = select(FAQ).where(FAQ.status == FAQStatus.PUBLISHED)
    result = await db.execute(stmt)
    faqs = list(result.scalars().all())

    if not faqs:
        return 0

    # 清空旧缓存
    try:
        client = _get_faq_cache_client()
        if client.has_collection(settings.FAQ_CACHE_COLLECTION):
            client.drop_collection(settings.FAQ_CACHE_COLLECTION)
    except Exception:
        pass

    for faq in faqs:
        await _insert_faq_cache(faq.id, faq.question, faq.answer)

    return len(faqs)


# ---------------------------------------------------------------------------
# FAQ Mining
# ---------------------------------------------------------------------------

async def _find_related_units(db: AsyncSession, question: str) -> str:
    """从知识库中查找与问题最相关的知识单元内容作为生成答案的上下文"""
    try:
        stmt = text("""
            SELECT content FROM knowledge_units
            WHERE status != 'deleted'
            ORDER BY ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', :query)) DESC
            LIMIT 3
        """)
        result = await db.execute(stmt, {"query": question})
        contents = [row[0] for row in result.all() if row[0]]
        return "\n\n".join(c[:500] for c in contents)
    except Exception:
        return ""


async def mine_faqs(db: AsyncSession) -> int:
    """从问答日志中挖掘高频问题，生成候选 FAQ。返回新增候选数量。"""
    cutoff = datetime.utcnow() - timedelta(days=settings.FAQ_MINING_DAYS)

    # 1. 获取近期提问
    stmt = select(QAAccessLog.question).where(
        QAAccessLog.created_at >= cutoff,
        func.length(QAAccessLog.question) > 5,
    )
    result = await db.execute(stmt)
    questions = [row[0] for row in result.all()]

    if len(questions) < settings.FAQ_MINING_THRESHOLD:
        return 0

    # 2. 向量化
    embeddings = await embed_texts(questions)
    if not embeddings:
        return 0

    # 3. 简单聚类：基于余弦相似度，将相似问题归为一组
    emb_matrix = np.array(embeddings)
    norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_matrix = emb_matrix / norms
    sim_matrix = np.dot(emb_matrix, emb_matrix.T)

    visited = [False] * len(questions)
    clusters: list[list[int]] = []

    for i in range(len(questions)):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, len(questions)):
            if not visited[j] and sim_matrix[i][j] >= 0.85:
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    # 4. 筛选达到阈值的聚类
    candidate_clusters = [c for c in clusters if len(c) >= settings.FAQ_MINING_THRESHOLD]

    if not candidate_clusters:
        return 0

    # 5. 检查已有 FAQ 避免重复
    existing_stmt = select(FAQ.question).where(
        FAQ.status.in_([FAQStatus.PENDING_REVIEW, FAQStatus.PUBLISHED])
    )
    existing_result = await db.execute(existing_stmt)
    existing_questions = [row[0] for row in existing_result.all()]

    new_count = 0
    for cluster in candidate_clusters:
        # 取聚类中第一个问题作为代表
        rep_question = questions[cluster[0]]

        # 简单去重：检查是否已存在类似问题
        if any(rep_question in eq or eq in rep_question for eq in existing_questions):
            continue

        # 查找关联知识单元
        context = await _find_related_units(db, rep_question)
        answer = await _generate_faq_answer(rep_question, context)

        faq = FAQ(
            question=rep_question,
            answer=answer,
            source_type=FAQSourceType.AUTO_MINED,
            status=FAQStatus.PENDING_REVIEW,
        )
        db.add(faq)
        new_count += 1

    if new_count:
        await db.commit()

    return new_count


# ---------------------------------------------------------------------------
# FAQ CRUD
# ---------------------------------------------------------------------------

async def list_recommendations(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[FAQ], int]:
    """查询待审核的 FAQ 推荐列表"""
    stmt = select(FAQ).where(FAQ.status == FAQStatus.PENDING_REVIEW)
    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        stmt.order_by(FAQ.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def review_faq(
    db: AsyncSession,
    faq_id: str,
    action: str,
    reviewer_id: str,
    edited_answer: str = "",
) -> FAQ | None:
    """审核 FAQ：approve 发布上线，reject 驳回"""
    stmt = select(FAQ).where(FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()
    if not faq:
        return None

    if action == "approve":
        if edited_answer:
            faq.answer = edited_answer
        faq.status = FAQStatus.PUBLISHED
        faq.reviewer_id = reviewer_id
        faq.reviewed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(faq)

        # 写入缓存
        await _insert_faq_cache(faq.id, faq.question, faq.answer)

    elif action == "reject":
        faq.status = FAQStatus.REJECTED
        faq.reviewer_id = reviewer_id
        faq.reviewed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(faq)

    return faq


async def list_published_faqs(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[FAQ], int]:
    """查询已发布 FAQ 列表"""
    stmt = select(FAQ).where(FAQ.status == FAQStatus.PUBLISHED)
    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        stmt.order_by(FAQ.updated_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def delete_faq(db: AsyncSession, faq_id: str) -> bool:
    """删除 FAQ 并清理缓存"""
    stmt = select(FAQ).where(FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()
    if not faq:
        return False

    await db.delete(faq)
    await db.commit()

    await _delete_faq_cache(faq_id)
    return True


async def update_faq(db: AsyncSession, faq_id: str, question: str, answer: str) -> FAQ | None:
    """更新 FAQ 问题与答案"""
    stmt = select(FAQ).where(FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()
    if not faq:
        return None

    faq.question = question
    faq.answer = answer
    await db.commit()
    await db.refresh(faq)
    return faq


async def increment_hit_count(db: AsyncSession, faq_id: str) -> None:
    """增加 FAQ 命中次数"""
    try:
        stmt = update(FAQ).where(FAQ.id == faq_id).values(hit_count=FAQ.hit_count + 1)
        await db.execute(stmt)
        await db.commit()
    except Exception:
        pass