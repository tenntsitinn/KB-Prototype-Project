"""统一沉淀池缓存：已发布题库条目构建问答缓存（Milvus），供 RAG 优先命中。"""
import numpy as np
from datetime import datetime, timedelta

from pymilvus import MilvusClient
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.config import settings
from app.models.knowledge_unit import QuizQuestion, QuizQuestionStatus, QAAccessLog, KnowledgeUnit
from app.services.vectorizer import embed_texts


# ---------------------------------------------------------------------------
# Milvus 题库缓存 collection
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
        # pymilvus>=3 快速建集合自带 AUTOINDEX，显式 create_index 会报
        # "at most one distinct index is allowed per field"
        client.create_collection(
            collection_name=collection,
            dimension=settings.EMBEDDING_DIM,
            metric_type="COSINE",
            auto_id=True,
            enable_dynamic_field=True,
        )
    client.load_collection(collection)
    return client


# ---------------------------------------------------------------------------
# LLM 答案生成（问答日志挖掘用）
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
# 题库缓存读写
# ---------------------------------------------------------------------------

async def match_faq_cache(query_vector: list[float]) -> dict | None:
    """匹配题库缓存，返回 {faq_id, question, answer} 或 None（faq_id 即题库条目 id）"""
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


async def insert_pool_cache(question_id: str, question: str, answer: str) -> None:
    """题库条目发布后写入缓存（answer 为空不入缓存；先删同 id 保证幂等）"""
    if not answer or not answer.strip():
        return
    embeddings = await embed_texts([question])
    if not embeddings:
        return
    client = _ensure_faq_collection()
    await delete_pool_cache(question_id)
    client.insert(
        collection_name=settings.FAQ_CACHE_COLLECTION,
        data=[{
            "faq_id": question_id,
            "question": question,
            "answer": answer,
            "vector": np.array(embeddings[0], dtype=np.float32),
        }],
    )


async def delete_pool_cache(question_id: str) -> None:
    """题库条目驳回/下线/删除后清理缓存"""
    try:
        client = _get_faq_cache_client()
        client.delete(
            collection_name=settings.FAQ_CACHE_COLLECTION,
            filter=f'faq_id == "{question_id}"',
        )
    except Exception:
        pass


async def sync_faq_cache(db: AsyncSession) -> int:
    """全量重建缓存：已发布且有参考答案的题库条目，返回同步数量。

    多 uvicorn worker 同时启动时通过 Postgres advisory lock 保证只有一个
    worker 执行重建，其余直接跳过，避免集合被交错 drop/insert 产生重复。
    """
    lock = await db.execute(text("SELECT pg_try_advisory_lock(88080001)"))
    if not lock.scalar():
        return 0
    try:
        stmt = select(QuizQuestion).where(
            QuizQuestion.status == QuizQuestionStatus.PUBLISHED,
            func.length(QuizQuestion.reference_answer) > 0,
        )
        result = await db.execute(stmt)
        questions = list(result.scalars().all())

        # 清空旧缓存
        try:
            client = _get_faq_cache_client()
            if client.has_collection(settings.FAQ_CACHE_COLLECTION):
                client.drop_collection(settings.FAQ_CACHE_COLLECTION)
        except Exception:
            pass

        for q in questions:
            await insert_pool_cache(q.id, q.question, q.reference_answer)

        return len(questions)
    finally:
        await db.execute(text("SELECT pg_advisory_unlock(88080001)"))


# ---------------------------------------------------------------------------
# 问答日志挖掘（沉淀池候选来源之一）
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
    """从问答日志中挖掘高频问题，生成候选题（含参考答案）。返回新增候选数量。"""
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
            if not visited[j] and sim_matrix[i][j] >= settings.FAQ_CLUSTER_THRESHOLD:
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    # 4. 筛选达到阈值的聚类
    candidate_clusters = [c for c in clusters if len(c) >= settings.FAQ_MINING_THRESHOLD]

    if not candidate_clusters:
        return 0

    # 5. 检查池内已有条目避免重复
    existing_stmt = select(QuizQuestion.question).where(
        QuizQuestion.status.in_([QuizQuestionStatus.PENDING_REVIEW, QuizQuestionStatus.PUBLISHED])
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

        # 查找关联知识单元并生成参考答案
        context = await _find_related_units(db, rep_question)
        answer = await _generate_faq_answer(rep_question, context)

        db.add(QuizQuestion(
            question=rep_question,
            reference_answer=answer,
            category="",
            source_unit_id="",
            source_type="auto_mined",
            status=QuizQuestionStatus.PENDING_REVIEW,
        ))
        existing_questions.append(rep_question)
        new_count += 1

    if new_count:
        await db.commit()

    return new_count


# ---------------------------------------------------------------------------
# 命中计数
# ---------------------------------------------------------------------------

async def increment_hit_count(db: AsyncSession, question_id: str) -> None:
    """增加题库条目命中次数"""
    try:
        stmt = update(QuizQuestion).where(QuizQuestion.id == question_id).values(
            usage_count=QuizQuestion.usage_count + 1
        )
        await db.execute(stmt)
        await db.commit()
    except Exception:
        pass
