"""智能出题服务：题库命中优先，未命中实时生成；判分 + 答题记录。"""
import json
import logging
import random
import time

from openai import AsyncOpenAI
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_unit import (
    KnowledgeUnit, QuizQuestion, QuizAnswer,
    QuizQuestionStatus, QuizQuestionSource,
)
from app.models.user import User
from app.prompts.quiz_prompts import QUIZ_GENERATE_PROMPT, QUIZ_GRADE_PROMPT

logger = logging.getLogger(__name__)

_llm_clients: dict[str, AsyncOpenAI] = {}


def _get_llm_client(api_key: str = "") -> AsyncOpenAI:
    key = api_key or settings.LLM_API_KEY or settings.EMBEDDING_API_KEY
    if key not in _llm_clients:
        _llm_clients[key] = AsyncOpenAI(
            api_key=key,
            base_url=settings.LLM_BASE_URL or settings.EMBEDDING_BASE_URL,
        )
    return _llm_clients[key]


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
        return [{"unit_id": uid, "unit_code": u.unit_code, "chunk_text": "\n\n".join(picked), "score": 0.0}]

    return []


async def _generate_question(context: str, asked_questions: list[str], user_api_key: str = "") -> dict | None:
    """调用 LLM 生成一道题，返回 {question, reference_answer, evidence}"""
    client = _get_llm_client(user_api_key)
    asked_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(asked_questions[-15:])) or "（暂无）"
    prompt = QUIZ_GENERATE_PROMPT.format(asked_questions=asked_text, context=context)
    try:
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
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
        return None


async def _grade_answer(question: str, reference_answer: str, evidence: str, user_answer: str, user_api_key: str = "") -> dict | None:
    """调用 LLM 判分，返回 {score, feedback}"""
    client = _get_llm_client(user_api_key)
    prompt = QUIZ_GRADE_PROMPT.format(
        question=question, reference_answer=reference_answer,
        evidence=evidence, user_answer=user_answer or "（未作答）",
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
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
        return None


async def next_question(
    db: AsyncSession, user: User, category: str, asked_question_ids: list[str],
    source_unit_id: str = "", source_unit_ids: list[str] | None = None,
) -> dict | None:
    """出题入口：题库优先，未命中实时生成并落候选。

    source_unit_ids 非空时按指定文档集合出题（树形勾选模式）。
    source_unit_id 非空时按单个文档出题（兼容旧模式）。
    否则按 category 标签出题。
    """
    user_api_key = user.llm_api_key or "" if not user.is_superuser else ""

    # 1) 题库命中（已发布 + 排除本会话已出）
    bank_stmt = (
        select(QuizQuestion)
        .where(
            QuizQuestion.status == QuizQuestionStatus.PUBLISHED,
            QuizQuestion.source_unit_id != "",
        )
    )
    if source_unit_ids:
        bank_stmt = bank_stmt.where(QuizQuestion.source_unit_id.in_(source_unit_ids))
    elif source_unit_id:
        bank_stmt = bank_stmt.where(QuizQuestion.source_unit_id == source_unit_id)
    elif category:
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
    chunks = await _recall_context(
        db, category, user,
        source_unit_id=source_unit_id,
        source_unit_ids=source_unit_ids,
    )
    if not chunks:
        return None

    context = "\n\n---\n\n".join(c["chunk_text"] for c in chunks)
    asked_texts: list[str] = []
    if asked_question_ids:
        prev = await db.execute(
            select(QuizQuestion.question).where(QuizQuestion.id.in_(asked_question_ids))
        )
        asked_texts = [row[0] for row in prev.all()]

    generated = await _generate_question(context, asked_texts, user_api_key)
    if not generated:
        return None

    source_unit_id = chunks[0]["unit_id"]
    unit_row = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == source_unit_id))
    unit = unit_row.scalars().first()
    unit_category = unit.category if unit else (category or "")

    # 落候选题库，待审批
    q = QuizQuestion(
        question=generated["question"],
        reference_answer=generated.get("reference_answer", ""),
        category=unit_category,
        source_unit_id=source_unit_id,
        source_type=QuizQuestionSource.AI_GENERATED,
        status=QuizQuestionStatus.PENDING_REVIEW,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

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
    user_api_key = user.llm_api_key or "" if not user.is_superuser else ""
    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return None

    reference = q.reference_answer or ""
    evidence = ""
    graded = await _grade_answer(q.question, reference, evidence, answer_text, user_api_key)
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
    await db.commit()

    return {
        "question_id": q.id,
        "question": q.question,
        "score": graded["score"],
        "feedback": graded["feedback"],
        "reference_answer": reference,
        "source_unit_id": q.source_unit_id,
    }


async def mine_questions_from_qa_logs(db: AsyncSession, limit: int = 20) -> int:
    """从问答日志挖掘用户真实提问作为候选题（user_question 来源）"""
    from app.models.knowledge_unit import QAAccessLog
    stmt = (
        select(QAAccessLog.question)
        .where(QAAccessLog.question != "")
        .order_by(QAAccessLog.created_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    questions = [row[0].strip() for row in result.all() if row[0] and row[0].strip()]

    if not questions:
        return 0

    existing_stmt = select(QuizQuestion.question).where(
        QuizQuestion.status.in_([QuizQuestionStatus.PENDING_REVIEW, QuizQuestionStatus.PUBLISHED])
    )
    existing_result = await db.execute(existing_stmt)
    existing = {row[0] for row in existing_result.all()}

    new_count = 0
    for q_text in questions[:limit]:
        if q_text in existing:
            continue
        db.add(QuizQuestion(
            question=q_text,
            reference_answer="",
            category="",
            source_unit_id="",
            source_type=QuizQuestionSource.USER_QUESTION,
            status=QuizQuestionStatus.PENDING_REVIEW,
        ))
        existing.add(q_text)
        new_count += 1

    if new_count:
        await db.commit()
    return new_count


async def review_question(db: AsyncSession, question_id: str, action: str, reviewer_id: str,
                          question: str | None = None, reference_answer: str | None = None) -> QuizQuestion | None:
    """审批候选题：approve 发布 / reject 驳回 / edit 编辑"""
    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return None

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
    else:
        return None

    await db.commit()
    await db.refresh(q)
    return q


async def delete_question(db: AsyncSession, question_id: str) -> bool:
    """硬删除题目"""
    q_result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
    q = q_result.scalars().first()
    if not q:
        return False
    await db.execute(delete(QuizQuestion).where(QuizQuestion.id == question_id))
    await db.commit()
    return True


async def batch_delete_questions(db: AsyncSession, question_ids: list[str]) -> int:
    """批量硬删除题目，返回实际删除数"""
    if not question_ids:
        return 0
    result = await db.execute(
        delete(QuizQuestion).where(QuizQuestion.id.in_(question_ids))
    )
    await db.commit()
    return result.rowcount
