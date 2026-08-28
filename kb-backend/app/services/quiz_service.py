"""智能出题服务：题库命中优先，未命中实时生成；判分 + 答题记录。"""
import json
import logging
import random
import time
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_unit import (
    KnowledgeUnit, QuizQuestion, QuizAnswer, QuizQuestionPoint,
    QuizQuestionStatus, QuizQuestionSource,
)
from app.models.education import KnowledgePoint, MasteryRecord
from app.models.user import User
from app.prompts.quiz_prompts import QUIZ_GENERATE_PROMPT, QUIZ_POINT_GENERATE_PROMPT, QUIZ_GRADE_PROMPT

logger = logging.getLogger(__name__)


class InsufficientBalanceError(Exception):
    pass


_llm_clients: dict[str, AsyncOpenAI] = {}


def _get_llm_client(api_key: str = "", base_url: str = "") -> AsyncOpenAI:
    key = api_key or settings.LLM_API_KEY or settings.EMBEDDING_API_KEY
    url = base_url or settings.LLM_BASE_URL or settings.EMBEDDING_BASE_URL
    cache_key = f"{url}::{key}"
    if cache_key not in _llm_clients:
        _llm_clients[cache_key] = AsyncOpenAI(api_key=key, base_url=url)
    return _llm_clients[cache_key]


async def _recall_context(
    db: AsyncSession, category: str, user: User, top_k: int = 3,
    source_unit_id: str = "", source_unit_ids: list[str] | None = None,
) -> list[dict]:
    """随机选一篇可见文档，随机起点取连续若干切片作为出题素材。

    source_unit_ids 非空时按指定文档集合取素材（树形勾选模式）。
    source_unit_id 非空时按单个文档取素材（兼容旧模式）。
    否则按 category 标签取素材。
    """
    from app.models.knowledge_unit import KnowledgeChunk

    stmt = (
        select(KnowledgeUnit.id, KnowledgeUnit.unit_code, KnowledgeUnit.content)
        .where(KnowledgeUnit.status == "published")
    )
    if source_unit_ids:
        stmt = stmt.where(KnowledgeUnit.id.in_(source_unit_ids))
    elif source_unit_id:
        stmt = stmt.where(KnowledgeUnit.id == source_unit_id)
    elif category:
        stmt = stmt.where(KnowledgeUnit.category == category)
    result = await db.execute(stmt)
    units = result.all()
    if not units:
        return []

    unit_map = {u.id: u for u in units}
    # 轮询多篇文档，取到第一个有可用素材的
    unit_order = sorted(unit_map)
    random.shuffle(unit_order)
    for uid in unit_order:
        u = unit_map[uid]
        rows = await db.execute(
            select(KnowledgeChunk.chunk_index, KnowledgeChunk.chunk_text)
            .where(KnowledgeChunk.unit_id == uid)
            .order_by(KnowledgeChunk.chunk_index)
        )
        chunks = [r.chunk_text for r in rows.all() if r.chunk_text]

        if not chunks:
            # 旧数据没有切片记录：按内容做简单切窗
            text = (u.content or "").strip()
            if len(text) < 200:
                continue
            window = random.randint(0, max(0, len(text) - 2000))
            chunks = [text[window:window + 2000]]

        if not chunks:
            continue

        start = random.randint(0, max(0, len(chunks) - 1))
        picked = chunks[start:start + top_k]
        # 查询该文档关联的知识点，供出题时对齐粒度
        kp_result = await db.execute(
            select(KnowledgePoint.id, KnowledgePoint.title)
            .where(KnowledgePoint.unit_id == uid)
            .where(KnowledgePoint.status != "rejected")
            .order_by(KnowledgePoint.sort_order)
        )
        kps = [{"id": r.id, "title": r.title} for r in kp_result.all()]
        return [{"unit_id": uid, "unit_code": u.unit_code, "chunk_text": "\n\n".join(picked), "score": 0.0, "knowledge_points": kps}]

    return []


async def _recall_point_context(db: AsyncSession, point_ids: list[str], top_k: int = 3) -> list[dict]:
    """按指定知识点取出题素材：知识点内容本身即上下文。

    返回结构与 _recall_context 一致（unit_id/unit_code/chunk_text/knowledge_points），
    仅取 confirmed / pending_review 状态的知识点。
    """
    rows = await db.execute(
        select(
            KnowledgePoint.id, KnowledgePoint.title, KnowledgePoint.content,
            KnowledgePoint.summary, KnowledgePoint.unit_id, KnowledgeUnit.unit_code,
        )
        .join(KnowledgeUnit, KnowledgeUnit.id == KnowledgePoint.unit_id)
        .where(KnowledgePoint.id.in_(point_ids))
        .where(KnowledgePoint.status.in_(("confirmed", "pending_review")))
    )
    points = [r for r in rows.all() if (r[2] or r[3] or "").strip()]
    if not points:
        return []

    random.shuffle(points)
    picked = points[:top_k]
    context = "\n\n---\n\n".join(
        f"【{r[1]}】\n{r[2] or r[3]}" for r in picked
    )
    kps = [{"id": r[0], "title": r[1]} for r in picked]
    return [{
        "unit_id": picked[0][4],
        "unit_code": picked[0][5],
        "chunk_text": context,
        "score": 0.0,
        "knowledge_points": kps,
    }]


async def _generate_question(context: str, asked_questions: list[str], knowledge_points: list[dict] | None = None, user_api_key: str = "", user_base_url: str = "", user_model: str = "", point_mode: bool = False) -> dict | None:
    """调用 LLM 生成一道题，返回 {question, reference_answer, evidence, knowledge_points}"""
    client = _get_llm_client(user_api_key, user_base_url)
    asked_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(asked_questions[-15:])) or "（暂无）"
    kp_text = "\n".join(f"- {kp['title']}" for kp in (knowledge_points or [])) or "（无）"
    template = QUIZ_POINT_GENERATE_PROMPT if point_mode else QUIZ_GENERATE_PROMPT
    prompt = template.format(asked_questions=asked_text, context=context, knowledge_points=kp_text)
    try:
        resp = await client.chat.completions.create(
            model=user_model or settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8, max_tokens=1024,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # 剥掉可能的 ```json 包裹
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"出题生成失败: {e}")
        if "402" in str(e) or "Insufficient Balance" in str(e):
            raise InsufficientBalanceError(str(e))
        return None


async def _grade_answer(question: str, reference_answer: str, evidence: str, user_answer: str, user_api_key: str = "", user_base_url: str = "", user_model: str = "") -> dict | None:
    """调用 LLM 判分，返回 {score, feedback}"""
    client = _get_llm_client(user_api_key, user_base_url)
    prompt = QUIZ_GRADE_PROMPT.format(
        question=question, reference_answer=reference_answer,
        evidence=evidence, user_answer=user_answer or "（未作答）",
    )
    try:
        resp = await client.chat.completions.create(
            model=user_model or settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=512,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        score = int(data.get("score", 0))
        score = max(0, min(100, score))
        return {"score": score, "feedback": data.get("feedback", "")}
    except Exception as e:
        logger.warning(f"判分失败: {e}")
        if "402" in str(e) or "Insufficient Balance" in str(e):
            raise InsufficientBalanceError(str(e))
        return None


TAG_MATCH_THRESHOLD = 0.55
TAG_TITLE_THRESHOLD = 0.45
TAG_MAX_PER_QUESTION = 3

DEDUP_SEMANTIC_THRESHOLD = 0.92
DEDUP_PENDING_LIMIT = 50


def _normalize_question(text: str) -> str:
    """规范化题目文本：去空白、全角转半角、统一标点，用于精确去重。"""
    import re
    t = (text or "").strip().lower()
    t = t.replace("　", " ").replace("，", ",").replace("。", ".").replace("！", "!").replace("？", "?")
    t = t.replace("（", "(").replace("）", ")").replace("：", ":").replace("；", ";")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[,.!?;:、，。！？；：]+$", "", t)
    return t


async def _find_duplicate_question(
    db: AsyncSession, question_text: str,
    source_unit_id: str = "", source_unit_ids: list[str] | None = None,
    category: str = "",
) -> QuizQuestion | None:
    """检查是否存在重复题目，命中则返回第一个匹配的 QuizQuestion。

    两级检查：
    1. 规范化精确匹配（待审核 + 已发布）
    2. 语义相似度匹配（已发布走 Milvus FAQ 缓存；同范围待审核走嵌入比对）
    """
    norm = _normalize_question(question_text)
    if not norm:
        return None

    # 1) 规范化精确匹配
    stmt = (
        select(QuizQuestion)
        .where(QuizQuestion.status.in_([
            QuizQuestionStatus.PENDING_REVIEW,
            QuizQuestionStatus.PUBLISHED,
        ]))
    )
    if source_unit_ids:
        stmt = stmt.where(QuizQuestion.source_unit_id.in_(source_unit_ids))
    elif source_unit_id:
        stmt = stmt.where(QuizQuestion.source_unit_id == source_unit_id)
    elif category:
        stmt = stmt.where(QuizQuestion.category == category)

    exact_rows = await db.execute(stmt)
    for q in exact_rows.scalars().all():
        if _normalize_question(q.question) == norm:
            return q

    # 2) 语义相似度匹配
    from app.services.vectorizer import embed_texts
    import numpy as np

    embeddings = await embed_texts([question_text])
    if not embeddings or not embeddings[0]:
        return None
    vec = np.array(embeddings[0], dtype=np.float32)

    # 2a) 已发布题：走 Milvus FAQ 缓存
    try:
        from app.services.rag.faq_service import match_faq_cache
        hit = await match_faq_cache(embeddings[0])
        if hit and hit.get("faq_id"):
            hit_q_result = await db.execute(
                select(QuizQuestion).where(QuizQuestion.id == hit["faq_id"])
            )
            hit_q = hit_q_result.scalars().first()
            if hit_q and hit_q.status == QuizQuestionStatus.PUBLISHED:
                in_scope = False
                if source_unit_ids and hit_q.source_unit_id in source_unit_ids:
                    in_scope = True
                elif source_unit_id and hit_q.source_unit_id == source_unit_id:
                    in_scope = True
                elif category and hit_q.category == category:
                    in_scope = True
                elif not source_unit_id and not source_unit_ids and not category:
                    in_scope = True
                if in_scope:
                    return hit_q
    except Exception as e:
        logger.debug("FAQ 缓存去重查询失败: %s", e)

    # 2b) 待审核题：同范围内嵌入比对（限制数量避免过大）
    pending_stmt = (
        select(QuizQuestion.id, QuizQuestion.question)
        .where(QuizQuestion.status == QuizQuestionStatus.PENDING_REVIEW)
        .order_by(QuizQuestion.created_at.desc())
        .limit(DEDUP_PENDING_LIMIT)
    )
    if source_unit_ids:
        pending_stmt = pending_stmt.where(QuizQuestion.source_unit_id.in_(source_unit_ids))
    elif source_unit_id:
        pending_stmt = pending_stmt.where(QuizQuestion.source_unit_id == source_unit_id)
    elif category:
        pending_stmt = pending_stmt.where(QuizQuestion.category == category)

    pending_rows = await db.execute(pending_stmt)
    pending_list = pending_rows.all()
    if not pending_list:
        return None

    pending_texts = [r.question for r in pending_list]
    pending_embeds = await embed_texts(pending_texts)
    if not pending_embeds:
        return None

    best_sim = 0.0
    best_idx = -1
    for i, pe in enumerate(pending_embeds):
        if not pe:
            continue
        pv = np.array(pe, dtype=np.float32)
        sim = float(np.dot(vec, pv) / (np.linalg.norm(vec) * np.linalg.norm(pv) + 1e-9))
        if sim > best_sim:
            best_sim = sim
            best_idx = i

    if best_sim >= DEDUP_SEMANTIC_THRESHOLD and best_idx >= 0:
        dup_id = pending_list[best_idx].id
        dup_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == dup_id))
        return dup_result.scalars().first()

    return None


async def auto_tag_question(
    db: AsyncSession, question_id: str, replace: bool = True,
    unit_ids: list[str] | None = None,
) -> list[dict]:
    """语义打标：题目（问+答）向量在知识点向量库中检索最相关知识点的标签。

    unit_ids 非空时限定这些文档内匹配（如问答日志的召回文档），否则退回题目
    自身的 source_unit_id，都没有则全库匹配。只取相似度达标的前几个。
    题目文本明确包含知识点标题时视为强信号，阈值放宽（题目问"LangGraph 的 State"，
    知识点"LangGraph"理应挂上）。
    replace=True 时先清掉旧标签再写入。返回 [{id, title}]。
    """
    from app.services.vectorizer import embed_texts
    from app.services.topic_store import search_topic

    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return []

    text = (q.question or "").strip()
    if q.reference_answer:
        text = f"{text}\n{q.reference_answer.strip()[:500]}"
    embeddings = await embed_texts([text])
    if not embeddings or not embeddings[0]:
        return []

    if not unit_ids:
        unit_ids = [q.source_unit_id] if q.source_unit_id else None
    hits = await search_topic(
        embeddings[0], limit=TAG_MAX_PER_QUESTION * 5,
        unit_ids=unit_ids,
    )
    text_lower = text.lower()

    def match(h: dict) -> bool:
        if h["score"] >= TAG_MATCH_THRESHOLD:
            return True
        title = (h["title"] or "").strip()
        # 标题过短时子串信号不可靠，跳过
        if len(title) >= 2 and title.lower() in text_lower and h["score"] >= TAG_TITLE_THRESHOLD:
            return True
        return False

    matched = [h for h in hits if match(h)][:TAG_MAX_PER_QUESTION]
    if not matched:
        if replace:
            await db.execute(delete(QuizQuestionPoint).where(QuizQuestionPoint.question_id == question_id))
            await db.commit()
        return []

    # 校验知识点仍然存在（向量库可能有已删除点的残留）
    point_ids = [h["point_id"] for h in matched]
    rows = await db.execute(
        select(KnowledgePoint.id).where(KnowledgePoint.id.in_(point_ids))
    )
    valid_ids = set(rows.scalars().all())
    matched = [h for h in matched if h["point_id"] in valid_ids]
    if not matched:
        return []

    if replace:
        await db.execute(delete(QuizQuestionPoint).where(QuizQuestionPoint.question_id == question_id))
    for h in matched:
        db.add(QuizQuestionPoint(question_id=question_id, point_id=h["point_id"]))
    await db.commit()
    return [{"id": h["point_id"], "title": h["title"]} for h in matched]


async def next_question(
    db: AsyncSession, user: User, category: str, asked_question_ids: list[str],
    source_unit_id: str = "", source_unit_ids: list[str] | None = None,
    point_ids: list[str] | None = None,
) -> dict | None:
    """出题入口：题库优先，未命中实时生成并落候选。

    point_ids 非空时按指定知识点出题（题库命中按知识点关联筛选，生成以知识点内容为素材）。
    source_unit_ids 非空时按指定文档集合出题（树形勾选模式）。
    source_unit_id 非空时按单个文档出题（兼容旧模式）。
    否则按 category 标签出题。
    """
    from app.core.llm_config import resolve_user_llm_config
    user_api_key, user_base_url, user_model = resolve_user_llm_config(user)
    point_ids = [p for p in (point_ids or []) if p]

    # 1) 题库命中（已发布 + 排除本会话已出）
    bank_stmt = (
        select(QuizQuestion)
        .where(
            QuizQuestion.status == QuizQuestionStatus.PUBLISHED,
            QuizQuestion.source_unit_id != "",
        )
    )
    if point_ids:
        bank_stmt = bank_stmt.where(
            QuizQuestion.id.in_(
                select(QuizQuestionPoint.question_id)
                .where(QuizQuestionPoint.point_id.in_(point_ids))
            )
        )
    if source_unit_ids:
        bank_stmt = bank_stmt.where(QuizQuestion.source_unit_id.in_(source_unit_ids))
    elif source_unit_id:
        bank_stmt = bank_stmt.where(QuizQuestion.source_unit_id == source_unit_id)
    elif category and not point_ids:
        bank_stmt = bank_stmt.where(QuizQuestion.category == category)
    if asked_question_ids:
        bank_stmt = bank_stmt.where(~QuizQuestion.id.in_(asked_question_ids))

    bank_result = await db.execute(bank_stmt)
    bank_questions = list(bank_result.scalars().all())

    if bank_questions:
        q = random.choice(bank_questions)
        await db.execute(
            update(QuizQuestion).where(QuizQuestion.id == q.id).values(
                usage_count=QuizQuestion.usage_count + 1
            )
        )
        await db.commit()
        return {
            "question_id": q.id,
            "question": q.question,
            "from_bank": True,
            "source_unit_id": q.source_unit_id,
        }

    # 2) 实时生成
    if point_ids:
        chunks = await _recall_point_context(db, point_ids)
    else:
        chunks = await _recall_context(
            db, category, user,
            source_unit_id=source_unit_id,
            source_unit_ids=source_unit_ids,
        )
    if not chunks:
        return None

    context = "\n\n---\n\n".join(c["chunk_text"] for c in chunks)
    kps = chunks[0].get("knowledge_points", [])
    asked_texts: list[str] = []
    if asked_question_ids:
        prev = await db.execute(
            select(QuizQuestion.question).where(QuizQuestion.id.in_(asked_question_ids))
        )
        asked_texts = [row[0] for row in prev.all()]

    generated = await _generate_question(
        context, asked_texts, kps, user_api_key, user_base_url, user_model,
        point_mode=bool(point_ids),
    )
    if not generated:
        return None

    new_question = generated["question"]
    source_unit_id = chunks[0]["unit_id"]
    unit_row = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == source_unit_id))
    unit = unit_row.scalars().first()
    unit_category = unit.category if unit else (category or "")

    # 去重检查：命中则复用已有题，不再新落库（知识点模式下按所选知识点的来源文档限定范围）
    dedup_unit_ids = source_unit_ids
    if point_ids and not dedup_unit_ids:
        unit_rows = await db.execute(
            select(KnowledgePoint.unit_id).where(KnowledgePoint.id.in_(point_ids))
        )
        dedup_unit_ids = list({r[0] for r in unit_rows.all()})
    dup = await _find_duplicate_question(
        db, new_question,
        source_unit_id=source_unit_id,
        source_unit_ids=dedup_unit_ids,
        category=unit_category,
    )
    if dup:
        await db.execute(
            update(QuizQuestion).where(QuizQuestion.id == dup.id).values(
                usage_count=QuizQuestion.usage_count + 1
            )
        )
        await db.commit()
        return {
            "question_id": dup.id,
            "question": dup.question,
            "from_bank": True,
            "source_unit_id": dup.source_unit_id,
        }

    # 落候选题库，待审批
    q = QuizQuestion(
        question=new_question,
        reference_answer=generated.get("reference_answer", ""),
        category=unit_category,
        source_unit_id=source_unit_id,
        source_type=QuizQuestionSource.AI_GENERATED,
        status=QuizQuestionStatus.PENDING_REVIEW,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    # 优先用 LLM 识别的知识点创建关联，未匹配时回退语义打标
    llm_kp_titles = generated.get("knowledge_points", [])
    kp_matched = False
    if llm_kp_titles and kps:
        kp_title_map = {kp["title"]: kp["id"] for kp in kps}
        matched_ids = [kp_title_map[t] for t in llm_kp_titles if t in kp_title_map]
        if matched_ids:
            for pid in matched_ids[:TAG_MAX_PER_QUESTION]:
                db.add(QuizQuestionPoint(question_id=q.id, point_id=pid))
            await db.commit()
            kp_matched = True
    if not kp_matched:
        try:
            await auto_tag_question(db, q.id)
        except Exception as e:
            logger.warning("自动打标失败: question_id=%s err=%s", q.id, e)

    return {
        "question_id": q.id,
        "question": q.question,
        "from_bank": False,
        "source_unit_id": source_unit_id,
        "reference_answer": q.reference_answer,
        "evidence": generated.get("evidence", ""),
    }


async def grade_and_record(
    db: AsyncSession, user: User, question_id: str, answer_text: str,
) -> dict | None:
    """判分入口：优先题库参考答案；生成题用判分时返回的参考答案兜底"""
    from app.core.llm_config import resolve_user_llm_config
    user_api_key, user_base_url, user_model = resolve_user_llm_config(user)
    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return None

    reference = q.reference_answer or ""
    evidence = ""
    graded = await _grade_answer(q.question, reference, evidence, answer_text, user_api_key, user_base_url, user_model)
    if not graded:
        graded = {"score": 0, "feedback": "判分服务暂不可用，请稍后重试"}

    record = QuizAnswer(
        question_id=q.id,
        user_id=user.id,
        answer_text=answer_text,
        score=graded["score"],
        feedback=graded["feedback"],
    )
    db.add(record)

    # 更新知识点掌握度：score≥60 视为正确
    point_result = await db.execute(
        select(QuizQuestionPoint.point_id).where(QuizQuestionPoint.question_id == question_id)
    )
    point_ids = [r[0] for r in point_result.all()]
    is_correct = graded["score"] >= 60
    now = datetime.utcnow()
    for pid in point_ids:
        mr_result = await db.execute(
            select(MasteryRecord).where(
                MasteryRecord.user_id == user.id,
                MasteryRecord.point_id == pid,
            )
        )
        mr = mr_result.scalars().first()
        if mr:
            mr.total_questions += 1
            if is_correct:
                mr.correct_count += 1
            mr.mastery_level = round(mr.correct_count / mr.total_questions * 100)
            mr.last_assessed_at = now
        else:
            db.add(MasteryRecord(
                user_id=user.id,
                point_id=pid,
                total_questions=1,
                correct_count=1 if is_correct else 0,
                mastery_level=100 if is_correct else 0,
                last_assessed_at=now,
            ))

    await db.commit()

    return {
        "question_id": q.id,
        "question": q.question,
        "score": graded["score"],
        "feedback": graded["feedback"],
        "reference_answer": reference,
        "source_unit_id": q.source_unit_id,
    }


async def mine_questions_from_qa_logs(db: AsyncSession, limit: int = 20) -> dict:
    """从问答日志挖掘用户真实提问作为候选题（user_question 来源）。

    日志里留存的 RAG 回答作为参考答案草稿，提问时召回的文档作为打标范围；
    落库后立即按召回文档范围语义打标，供审核时参考。
    返回 {new_count, tagged_count}。
    """
    from app.models.knowledge_unit import QAAccessLog

    stmt = (
        select(QAAccessLog.question, QAAccessLog.answer, QAAccessLog.recalled_unit_ids_json)
        .where(
            QAAccessLog.question != "",
            QAAccessLog.question != "[FAQ缓存命中]",
        )
        .order_by(QAAccessLog.created_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    # 同一问题的多次提问：答案取最新一次，召回文档取全部提问的并集
    mined: dict[str, tuple[str, set[str]]] = {}
    for question, answer, recalled_json in result.all():
        q_text = (question or "").strip()
        if not q_text or len(q_text) <= 3:
            continue
        try:
            recalled = {u for u in json.loads(recalled_json or "[]") if u}
        except Exception:
            recalled = set()
        if q_text in mined:
            mined[q_text][1].update(recalled)
        else:
            mined[q_text] = ((answer or "").strip(), recalled)

    if not mined:
        return {"new_count": 0, "tagged_count": 0}

    existing_stmt = select(QuizQuestion.question).where(
        QuizQuestion.status.in_([QuizQuestionStatus.PENDING_REVIEW, QuizQuestionStatus.PUBLISHED])
    )
    existing_result = await db.execute(existing_stmt)
    existing = {row[0] for row in existing_result.all()}

    new_count = 0
    tagged_count = 0
    dup_count = 0
    for q_text, (answer, recalled) in list(mined.items())[:limit]:
        # 先做规范化精确匹配（existing 集合里的是原始文本，再补一层规范化检查）
        if q_text in existing:
            dup_count += 1
            continue
        recalled_list = sorted(recalled)
        # 语义去重：在召回文档范围内检查是否已有相似题
        try:
            dup_q = await _find_duplicate_question(
                db, q_text,
                source_unit_id=recalled_list[0] if recalled_list else "",
                source_unit_ids=recalled_list if len(recalled_list) > 1 else None,
            )
            if dup_q:
                dup_count += 1
                continue
        except Exception as e:
            logger.debug("挖掘题语义去重检查失败: %s", e)

        q = QuizQuestion(
            question=q_text,
            reference_answer=answer[:2000],
            category="",
            source_unit_id=recalled_list[0] if recalled_list else "",
            source_type=QuizQuestionSource.USER_QUESTION,
            status=QuizQuestionStatus.PENDING_REVIEW,
        )
        db.add(q)
        await db.flush()
        existing.add(q_text)
        new_count += 1
        # 用户题只按提问时召回的文档范围打标；无召回记录则留给审核人手动补
        if not recalled_list:
            continue
        try:
            tags = await auto_tag_question(db, q.id, replace=True, unit_ids=recalled_list)
            if tags:
                tagged_count += 1
        except Exception as e:
            logger.warning("挖掘题打标失败: question_id=%s err=%s", q.id, e)

    if new_count:
        await db.commit()
    return {"new_count": new_count, "tagged_count": tagged_count, "dup_count": dup_count}


async def review_question(db: AsyncSession, question_id: str, action: str, reviewer_id: str,
                          question: str | None = None, reference_answer: str | None = None,
                          point_ids: list[str] | None = None) -> QuizQuestion | None:
    """审批候选题：approve 发布 / reject 驳回 / offline 下线 / edit 编辑。发布与下线同步问答缓存。"""
    from app.services.rag import faq_service
    from app.models.education import KnowledgePoint

    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return None

    was_published = q.status == QuizQuestionStatus.PUBLISHED

    if action == "approve":
        if question is not None:
            q.question = question
        if reference_answer is not None:
            q.reference_answer = reference_answer
        q.status = QuizQuestionStatus.PUBLISHED
        q.reviewer_id = reviewer_id
        from datetime import datetime
        q.reviewed_at = datetime.utcnow()
    elif action == "reject":
        q.status = QuizQuestionStatus.REJECTED
        q.reviewer_id = reviewer_id
        from datetime import datetime
        q.reviewed_at = datetime.utcnow()
    elif action == "offline":
        q.status = QuizQuestionStatus.OFFLINE
    elif action == "edit":
        if question is not None:
            q.question = question
        if reference_answer is not None:
            q.reference_answer = reference_answer
        if point_ids is not None:
            await db.execute(
                delete(QuizQuestionPoint).where(QuizQuestionPoint.question_id == question_id)
            )
            if point_ids:
                valid = await db.execute(
                    select(KnowledgePoint.id).where(KnowledgePoint.id.in_(point_ids))
                )
                for pid in valid.scalars():
                    db.add(QuizQuestionPoint(question_id=question_id, point_id=pid))
    else:
        return None

    await db.commit()
    await db.refresh(q)

    # 缓存同步：发布/编辑已发布条目时刷新；离开发布态时清理
    try:
        if q.status == QuizQuestionStatus.PUBLISHED:
            if was_published:
                await faq_service.delete_pool_cache(question_id)
            await faq_service.insert_pool_cache(q.id, q.question, q.reference_answer)
        elif was_published:
            await faq_service.delete_pool_cache(question_id)
    except Exception as e:
        logger.warning("题库缓存同步失败（不影响审核结果）: question=%s err=%s", question_id, e)

    return q


async def delete_question(db: AsyncSession, question_id: str) -> bool:
    """硬删除题目，同步清理问答缓存"""
    from app.services.rag import faq_service

    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return False
    await db.execute(delete(QuizQuestion).where(QuizQuestion.id == question_id))
    await db.commit()

    try:
        await faq_service.delete_pool_cache(question_id)
    except Exception as e:
        logger.warning("题库缓存清理失败: question=%s err=%s", question_id, e)
    return True


async def batch_delete_questions(db: AsyncSession, question_ids: list[str]) -> int:
    """批量硬删除题目，返回实际删除数，同步清理问答缓存"""
    from app.services.rag import faq_service

    if not question_ids:
        return 0
    result = await db.execute(
        delete(QuizQuestion).where(QuizQuestion.id.in_(question_ids))
    )
    await db.commit()

    try:
        for qid in question_ids:
            await faq_service.delete_pool_cache(qid)
    except Exception as e:
        logger.warning("题库缓存批量清理失败: err=%s", e)
    return result.rowcount


async def find_duplicates(
    db: AsyncSession, status: str = "pending_review",
    threshold: float = DEDUP_SEMANTIC_THRESHOLD,
    limit: int = 200,
) -> list[dict]:
    """扫描题库中的重复题目，返回重复组列表。

    算法：按规范化文本精确分组 → 同组内按语义相似度聚类。
    每组保留一道主题（最早创建的），其余标记为重复。
    返回 [{group_key, keep_id, keep_question, duplicates: [{id, question, similarity}]}]
    """
    from app.services.vectorizer import embed_texts
    import numpy as np

    stmt = (
        select(QuizQuestion.id, QuizQuestion.question, QuizQuestion.created_at)
        .where(QuizQuestion.status == status)
        .order_by(QuizQuestion.created_at.asc())
        .limit(limit)
    )
    rows = await db.execute(stmt)
    all_qs = rows.all()
    if not all_qs:
        return []

    # 1) 按规范化文本分组
    groups: dict[str, list] = {}
    for r in all_qs:
        norm = _normalize_question(r.question)
        if not norm:
            continue
        groups.setdefault(norm, []).append(r)

    exact_groups = [g for g in groups.values() if len(g) > 1]

    # 2) 精确重复组：直接按创建时间保留最早的
    result = []
    for g in exact_groups:
        g_sorted = sorted(g, key=lambda x: x.created_at)
        keep = g_sorted[0]
        dups = [
            {"id": r.id, "question": r.question, "similarity": 1.0}
            for r in g_sorted[1:]
        ]
        result.append({
            "group_key": _normalize_question(keep.question)[:30],
            "keep_id": keep.id,
            "keep_question": keep.question,
            "duplicates": dups,
        })

    # 3) 对只有单条的组，做语义相似度聚类找近似重复
    singles = [g[0] for g in groups.values() if len(g) == 1]
    if len(singles) >= 2:
        texts = [r.question for r in singles]
        embeds = await embed_texts(texts)
        if embeds and len(embeds) == len(singles):
            vecs = []
            for e in embeds:
                v = np.array(e, dtype=np.float32)
                norm = np.linalg.norm(v)
                vecs.append(v / (norm + 1e-9) if norm > 0 else v)

            visited = set()
            for i in range(len(singles)):
                if i in visited:
                    continue
                cluster = [i]
                for j in range(i + 1, len(singles)):
                    if j in visited:
                        continue
                    sim = float(np.dot(vecs[i], vecs[j]))
                    if sim >= threshold:
                        cluster.append(j)
                        visited.add(j)
                if len(cluster) > 1:
                    visited.add(i)
                    cluster_sorted = sorted(cluster, key=lambda idx: singles[idx].created_at)
                    keep_idx = cluster_sorted[0]
                    keep = singles[keep_idx]
                    dups = []
                    for idx in cluster_sorted[1:]:
                        sim = float(np.dot(vecs[keep_idx], vecs[idx]))
                        dups.append({
                            "id": singles[idx].id,
                            "question": singles[idx].question,
                            "similarity": round(sim, 4),
                        })
                    result.append({
                        "group_key": _normalize_question(keep.question)[:30],
                        "keep_id": keep.id,
                        "keep_question": keep.question,
                        "duplicates": dups,
                    })

    return result


async def merge_duplicates(db: AsyncSession, keep_id: str, duplicate_ids: list[str]) -> dict:
    """合并重复题目：保留 keep_id，将其余题的使用次数和知识点标签合并后删除。

    合并规则：
    - usage_count 累加
    - 知识点标签取并集（已关联则跳过）
    - 重复题删除（同步清理 FAQ 缓存）
    """
    from app.services.rag import faq_service

    if not duplicate_ids:
        return {"merged": 0}

    keep_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.id == keep_id)
    )
    keep = keep_result.scalars().first()
    if not keep:
        return {"merged": 0, "error": "keep_id 不存在"}

    # 收集重复题的 usage_count 和知识点
    total_usage = 0
    point_ids_to_add: set[str] = set()
    for dup_id in duplicate_ids:
        dup_result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == dup_id)
        )
        dup = dup_result.scalars().first()
        if not dup:
            continue
        total_usage += dup.usage_count or 0
        pt_result = await db.execute(
            select(QuizQuestionPoint.point_id).where(QuizQuestionPoint.question_id == dup_id)
        )
        for pid in pt_result.scalars().all():
            point_ids_to_add.add(pid)

    # 累加使用次数
    if total_usage > 0:
        keep.usage_count = (keep.usage_count or 0) + total_usage

    # 合并知识点标签
    if point_ids_to_add:
        existing_result = await db.execute(
            select(QuizQuestionPoint.point_id).where(QuizQuestionPoint.question_id == keep_id)
        )
        existing_pids = set(existing_result.scalars().all())
        for pid in point_ids_to_add - existing_pids:
            db.add(QuizQuestionPoint(question_id=keep_id, point_id=pid))

    # 删除重复题
    merged = 0
    for dup_id in duplicate_ids:
        try:
            await faq_service.delete_pool_cache(dup_id)
        except Exception:
            pass
        await db.execute(delete(QuizQuestion).where(QuizQuestion.id == dup_id))
        merged += 1

    await db.commit()
    return {"merged": merged, "keep_id": keep_id}
