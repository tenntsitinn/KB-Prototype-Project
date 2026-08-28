"""题库出题、判分、审核、合并测试。"""
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.education import KnowledgePoint, MasteryRecord
from app.models.knowledge_unit import (
    KnowledgeUnit,
    QuizAnswer,
    QuizQuestion,
    QuizQuestionPoint,
    QuizQuestionStatus,
)
from app.models.user import User
from app.services import quiz_service
from app.services.quiz_service import (
    grade_and_record,
    merge_duplicates,
    next_question,
    review_question,
)


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def superuser(db_session):
    user = User(id="admin-u", username="quiz-admin", password_hash="x", is_superuser=True)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def no_faq_cache(monkeypatch):
    """审核/合并时的缓存同步全部短路，避免真实 Milvus 调用。"""
    async def noop_insert(qid, question, answer):
        return None

    async def noop_delete(qid):
        return None

    monkeypatch.setattr("app.services.rag.faq_service.insert_pool_cache", noop_insert)
    monkeypatch.setattr("app.services.rag.faq_service.delete_pool_cache", noop_delete)


def _published_question(db_session, question: str, unit_id: str = "u1", usage: int = 0) -> QuizQuestion:
    q = QuizQuestion(
        question=question,
        reference_answer="ref answer",
        category="cat",
        source_unit_id=unit_id,
        status=QuizQuestionStatus.PUBLISHED,
        usage_count=usage,
    )
    db_session.add(q)
    return q


@pytest.mark.asyncio
async def test_next_question_returns_bank_hit(db_session, superuser):
    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    bank_q = _published_question(db_session, "已有题库题目？", usage=3)
    await db_session.commit()

    result = await next_question(db_session, superuser, category="cat", asked_question_ids=[])

    assert result is not None
    assert result["from_bank"] is True
    assert result["question_id"] == bank_q.id
    await db_session.refresh(bank_q)
    assert bank_q.usage_count == 4


@pytest.mark.asyncio
async def test_next_question_bank_excludes_asked(db_session, superuser, monkeypatch):
    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    bank_q = _published_question(db_session, "唯一题库题目？")
    await db_session.commit()

    # 已出过的题被排除 → 走实时生成 → 无素材返回 None
    async def no_recall(*args, **kwargs):
        return []

    monkeypatch.setattr(quiz_service, "_recall_context", no_recall)

    result = await next_question(db_session, superuser, category="cat", asked_question_ids=[bank_q.id])

    assert result is None


@pytest.mark.asyncio
async def test_generated_question_saved_as_pending_review(db_session, superuser, monkeypatch, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-gen", title="Gen Unit", status="published", category="target-cat"))
    kp = KnowledgePoint(id="kp-gen", unit_id="u-gen", title="LangGraph 状态机", status="confirmed")
    db_session.add(kp)
    await db_session.commit()

    async def fake_recall(*args, **kwargs):
        return [{
            "unit_id": "u-gen", "unit_code": "KB-GEN",
            "chunk_text": "LangGraph 内容素材", "score": 0.9,
            "knowledge_points": [{"id": "kp-gen", "title": "LangGraph 状态机"}],
        }]

    async def fake_generate(context, asked, kps, *args, **kwargs):
        return {
            "question": "新生成的题目是什么？",
            "reference_answer": "参考答案",
            "evidence": "依据",
            "knowledge_points": ["LangGraph 状态机"],
        }

    async def no_dup(db, question_text, *args, **kwargs):
        return None

    monkeypatch.setattr(quiz_service, "_recall_context", fake_recall)
    monkeypatch.setattr(quiz_service, "_generate_question", fake_generate)
    monkeypatch.setattr(quiz_service, "_find_duplicate_question", no_dup)

    result = await next_question(db_session, superuser, category="", asked_question_ids=[])

    assert result is not None
    assert result["from_bank"] is False
    q = (await db_session.execute(
        select(QuizQuestion).where(QuizQuestion.question == "新生成的题目是什么？")
    )).scalars().first()
    assert q is not None
    assert q.status == QuizQuestionStatus.PENDING_REVIEW
    assert q.source_unit_id == "u-gen"
    assert q.category == "target-cat"
    # LLM 标注的知识点标题匹配成功，直接创建关联
    points = (await db_session.execute(
        select(QuizQuestionPoint).where(QuizQuestionPoint.question_id == q.id)
    )).scalars().all()
    assert [p.point_id for p in points] == ["kp-gen"]


@pytest.mark.asyncio
async def test_generated_duplicate_reuses_existing(db_session, superuser, monkeypatch, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-dup", title="Dup Unit", status="published"))
    await db_session.commit()

    existing = _published_question(db_session, "重复出现的问题？", unit_id="u-dup", usage=1)
    await db_session.commit()

    async def fake_recall(*args, **kwargs):
        return [{
            "unit_id": "u-dup", "unit_code": "KB-DUP",
            "chunk_text": "素材", "score": 0.9, "knowledge_points": [],
        }]

    async def fake_generate(context, asked, kps, *args, **kwargs):
        return {"question": "新生成但语义重复的问题？", "reference_answer": "答案", "evidence": "", "knowledge_points": []}

    async def fake_dup(db, question_text, *args, **kwargs):
        return existing

    monkeypatch.setattr(quiz_service, "_recall_context", fake_recall)
    monkeypatch.setattr(quiz_service, "_generate_question", fake_generate)
    monkeypatch.setattr(quiz_service, "_find_duplicate_question", fake_dup)

    result = await next_question(db_session, superuser, category="", asked_question_ids=[])

    assert result["from_bank"] is True
    assert result["question_id"] == existing.id
    await db_session.refresh(existing)
    assert existing.usage_count == 2
    # 未新落库
    count = len((await db_session.execute(
        select(QuizQuestion).where(QuizQuestion.question == "新生成但语义重复的问题？")
    )).scalars().all())
    assert count == 0


@pytest.mark.asyncio
async def test_grade_and_record_upserts_mastery(db_session, superuser, monkeypatch, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-grade", title="Grade Unit", status="published"))
    kp1 = KnowledgePoint(id="kp-1", unit_id="u-grade", title="知识点一", status="confirmed")
    kp2 = KnowledgePoint(id="kp-2", unit_id="u-grade", title="知识点二", status="confirmed")
    db_session.add_all([kp1, kp2])
    q = _published_question(db_session, "判分题目？", unit_id="u-grade")
    await db_session.commit()
    db_session.add_all([
        QuizQuestionPoint(question_id=q.id, point_id="kp-1"),
        QuizQuestionPoint(question_id=q.id, point_id="kp-2"),
    ])
    await db_session.commit()

    async def fake_grade(question, reference, evidence, answer, *args, **kwargs):
        return {"score": 85, "feedback": "不错"}

    monkeypatch.setattr(quiz_service, "_grade_answer", fake_grade)

    result = await grade_and_record(db_session, superuser, q.id, "我的回答")
    assert result["score"] == 85

    records = (await db_session.execute(
        select(MasteryRecord).where(MasteryRecord.user_id == superuser.id)
    )).scalars().all()
    by_point = {r.point_id: r for r in records}
    assert set(by_point) == {"kp-1", "kp-2"}
    assert all(r.total_questions == 1 and r.correct_count == 1 and r.mastery_level == 100 for r in records)

    # 第二次答错（<60）→ 增量更新
    async def fail_grade(question, reference, evidence, answer, *args, **kwargs):
        return {"score": 30, "feedback": "再练练"}

    monkeypatch.setattr(quiz_service, "_grade_answer", fail_grade)
    await grade_and_record(db_session, superuser, q.id, "错误回答")

    rec = by_point["kp-1"]
    await db_session.refresh(rec)
    assert rec.total_questions == 2
    assert rec.correct_count == 1
    assert rec.mastery_level == 50
    answers = (await db_session.execute(
        select(QuizAnswer).where(QuizAnswer.question_id == q.id)
    )).scalars().all()
    assert len(answers) == 2


@pytest.mark.asyncio
async def test_review_question_approve_and_reject(db_session, superuser, no_faq_cache):
    q = QuizQuestion(question="待审核题目？", reference_answer="答案",
                     status=QuizQuestionStatus.PENDING_REVIEW)
    db_session.add(q)
    await db_session.commit()

    approved = await review_question(db_session, q.id, "approve", reviewer_id=superuser.id)
    assert approved.status == QuizQuestionStatus.PUBLISHED
    assert approved.reviewer_id == superuser.id

    rejected = await review_question(db_session, q.id, "reject", reviewer_id=superuser.id)
    assert rejected.status == QuizQuestionStatus.REJECTED


@pytest.mark.asyncio
async def test_review_question_edit_replaces_points(db_session, superuser, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-edit", title="Edit Unit", status="published"))
    kp_old = KnowledgePoint(id="kp-old", unit_id="u-edit", title="旧标签", status="confirmed")
    kp_new = KnowledgePoint(id="kp-new", unit_id="u-edit", title="新标签", status="confirmed")
    db_session.add_all([kp_old, kp_new])
    q = QuizQuestion(question="编辑题目？", status=QuizQuestionStatus.PENDING_REVIEW)
    db_session.add(q)
    await db_session.commit()
    db_session.add(QuizQuestionPoint(question_id=q.id, point_id="kp-old"))
    await db_session.commit()

    updated = await review_question(
        db_session, q.id, "edit", reviewer_id=superuser.id,
        question="编辑后的题目？", point_ids=["kp-new"],
    )
    assert updated.question == "编辑后的题目？"
    points = (await db_session.execute(
        select(QuizQuestionPoint).where(QuizQuestionPoint.question_id == q.id)
    )).scalars().all()
    assert [p.point_id for p in points] == ["kp-new"]


@pytest.mark.asyncio
async def test_merge_duplicates_merges_usage_and_tags(db_session, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-m", title="M Unit", status="published"))
    keep = _published_question(db_session, "保留题目？", unit_id="u-m", usage=5)
    dup1 = _published_question(db_session, "重复题目一？", unit_id="u-m", usage=2)
    dup2 = _published_question(db_session, "重复题目二？", unit_id="u-m", usage=1)
    db_session.add(KnowledgePoint(id="kp-m1", unit_id="u-m", title="标签A", status="confirmed"))
    db_session.add(KnowledgePoint(id="kp-m2", unit_id="u-m", title="标签B", status="confirmed"))
    await db_session.commit()
    db_session.add(QuizQuestionPoint(question_id=keep.id, point_id="kp-m1"))
    db_session.add(QuizQuestionPoint(question_id=dup1.id, point_id="kp-m2"))
    await db_session.commit()

    result = await merge_duplicates(db_session, keep.id, [dup1.id, dup2.id])

    assert result["merged"] == 2
    await db_session.refresh(keep)
    assert keep.usage_count == 8
    points = (await db_session.execute(
        select(QuizQuestionPoint).where(QuizQuestionPoint.question_id == keep.id)
    )).scalars().all()
    assert {p.point_id for p in points} == {"kp-m1", "kp-m2"}
    remaining = (await db_session.execute(
        select(QuizQuestion).where(QuizQuestion.id.in_([dup1.id, dup2.id]))
    )).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_merge_duplicates_missing_keep_id(db_session, no_faq_cache):
    result = await merge_duplicates(db_session, "no-such-id", ["dup-x"])

    assert result == {"merged": 0, "error": "keep_id 不存在"}


# --- 按知识点出题 ---


@pytest.mark.asyncio
async def test_next_question_point_mode_bank_hit_filters_by_point(db_session, superuser):
    db_session.add(KnowledgeUnit(id="u-pt", title="Point Unit", status="published"))
    tagged = _published_question(db_session, "关联知识点的题目？", unit_id="u-pt")
    other = _published_question(db_session, "未关联的题目？", unit_id="u-pt")
    await db_session.commit()
    db_session.add(QuizQuestionPoint(question_id=tagged.id, point_id="kp-target"))
    await db_session.commit()

    result = await next_question(
        db_session, superuser, category="", asked_question_ids=[],
        point_ids=["kp-target"],
    )

    assert result is not None
    assert result["from_bank"] is True
    assert result["question_id"] == tagged.id
    assert result["question_id"] != other.id


@pytest.mark.asyncio
async def test_next_question_point_mode_generates_from_point_content(db_session, superuser, monkeypatch, no_faq_cache):
    db_session.add(KnowledgeUnit(id="u-point", title="Point Unit", status="published", category="pt-cat"))
    db_session.add(KnowledgePoint(
        id="kp-point", unit_id="u-point", title="LangGraph 状态机",
        summary="状态机摘要", content="LangGraph 通过 StateGraph 管理状态流转", status="confirmed",
    ))
    await db_session.commit()

    captured: dict = {}

    async def fake_generate(context, asked, kps, *args, **kwargs):
        captured["context"] = context
        captured["kps"] = kps
        captured["point_mode"] = kwargs.get("point_mode")
        return {
            "question": "LangGraph 中 StateGraph 的作用是什么？",
            "reference_answer": "管理状态流转",
            "evidence": "StateGraph 管理状态流转",
            "knowledge_points": ["LangGraph 状态机"],
        }

    async def no_dup(db, question_text, *args, **kwargs):
        return None

    monkeypatch.setattr(quiz_service, "_generate_question", fake_generate)
    monkeypatch.setattr(quiz_service, "_find_duplicate_question", no_dup)

    result = await next_question(
        db_session, superuser, category="", asked_question_ids=[],
        point_ids=["kp-point"],
    )

    assert result is not None
    assert result["from_bank"] is False
    assert result["source_unit_id"] == "u-point"
    # 上下文来自知识点内容本身
    assert "LangGraph 状态机" in captured["context"]
    assert "StateGraph 管理状态流转" in captured["context"]
    assert captured["point_mode"] is True
    # 生成题按 LLM 返回的知识点标题建立关联
    links = (await db_session.execute(
        select(QuizQuestionPoint).where(QuizQuestionPoint.question_id == result["question_id"])
    )).scalars().all()
    assert [l.point_id for l in links] == ["kp-point"]


@pytest.mark.asyncio
async def test_next_question_point_mode_rejects_invalid_points(db_session, superuser, monkeypatch):
    db_session.add(KnowledgeUnit(id="u-rej", title="Rej Unit", status="published"))
    db_session.add(KnowledgePoint(
        id="kp-rej", unit_id="u-rej", title="已拒绝知识点",
        content="内容", status="rejected",
    ))
    await db_session.commit()

    async def fail_generate(*args, **kwargs):
        raise AssertionError("不应触发生成")

    monkeypatch.setattr(quiz_service, "_generate_question", fail_generate)

    result = await next_question(
        db_session, superuser, category="", asked_question_ids=[],
        point_ids=["kp-rej", "kp-missing"],
    )

    assert result is None
