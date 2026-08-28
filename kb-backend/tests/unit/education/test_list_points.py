"""知识点管理列表：全量默认 + 来源/审核状态/关键词筛选 + 关联题目数。"""
import json

import pytest
from fastapi import HTTPException

from app.api.education import list_points
from app.models.education import KnowledgePoint
from app.models.knowledge_unit import (
    KnowledgeUnit,
    QuizQuestion,
    QuizQuestionPoint,
    QuizQuestionStatus,
)


pytestmark = pytest.mark.integration


def _add_point(db, point_id: str, unit_id: str, title: str, status: str,
               content: str = "内容", source_refs: list | None = None) -> KnowledgePoint:
    p = KnowledgePoint(
        id=point_id, unit_id=unit_id, title=title, status=status,
        summary=content[:50], content=content,
        source_refs_json=json.dumps(source_refs or []),
    )
    db.add(p)
    return p


@pytest.mark.asyncio
async def test_default_lists_all_non_rejected(db_session):
    db_session.add_all([
        KnowledgeUnit(id="u-a", title="Unit A", status="published"),
        KnowledgeUnit(id="u-b", title="Unit B", status="published"),
    ])
    _add_point(db_session, "kp-pending", "u-a", "待审核点", "pending_review")
    _add_point(db_session, "kp-confirmed", "u-a", "已确认点", "confirmed")
    _add_point(db_session, "kp-delete", "u-b", "删除待处理点", "delete_pending")
    _add_point(db_session, "kp-rejected", "u-b", "已拒绝点", "rejected")
    await db_session.commit()

    res = await list_points(status="", offset=0, limit=10, db=db_session)

    assert res["total"] == 3
    ids = {i["id"] for i in res["items"]}
    assert ids == {"kp-pending", "kp-confirmed", "kp-delete"}
    assert "kp-rejected" not in ids
    options = {o["unit_id"]: o["count"] for o in res["source_options"]}
    assert options == {"u-a": 2, "u-b": 1}
    for item in res["items"]:
        assert item["question_count"] == 0
        assert item["created_at"] != ""


@pytest.mark.asyncio
async def test_question_count_counts_published_only(db_session):
    db_session.add(KnowledgeUnit(id="u-a", title="Unit A", status="published"))
    _add_point(db_session, "kp-hit", "u-a", "有关联点", "confirmed")
    _add_point(db_session, "kp-miss", "u-a", "无关联点", "confirmed")

    def _question(question: str, status) -> QuizQuestion:
        q = QuizQuestion(
            question=question, reference_answer="ref", category="cat",
            source_unit_id="u-a", status=status,
        )
        db_session.add(q)
        return q

    published_1 = _question("已发布题目一？", QuizQuestionStatus.PUBLISHED)
    published_2 = _question("已发布题目二？", QuizQuestionStatus.PUBLISHED)
    pending = _question("待审核题目？", QuizQuestionStatus.PENDING_REVIEW)
    await db_session.commit()
    db_session.add_all([
        QuizQuestionPoint(question_id=published_1.id, point_id="kp-hit"),
        QuizQuestionPoint(question_id=published_2.id, point_id="kp-hit"),
        QuizQuestionPoint(question_id=pending.id, point_id="kp-hit"),
        QuizQuestionPoint(question_id=published_1.id, point_id="kp-miss"),
    ])
    await db_session.commit()

    res = await list_points(status="confirmed", offset=0, limit=10, db=db_session)

    counts = {i["id"]: i["question_count"] for i in res["items"]}
    assert counts == {"kp-hit": 2, "kp-miss": 1}


@pytest.mark.asyncio
async def test_status_filter_confirmed(db_session):
    db_session.add(KnowledgeUnit(id="u-a", title="Unit A", status="published"))
    _add_point(db_session, "kp-pending", "u-a", "待审核点", "pending_review")
    _add_point(db_session, "kp-confirmed", "u-a", "已确认点", "confirmed")
    await db_session.commit()

    res = await list_points(status="confirmed", offset=0, limit=10, db=db_session)

    assert res["total"] == 1
    assert [i["id"] for i in res["items"]] == ["kp-confirmed"]


@pytest.mark.asyncio
async def test_invalid_status_rejected(db_session):
    with pytest.raises(HTTPException) as exc:
        await list_points(status="rejected", offset=0, limit=10, db=db_session)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_unit_filter_matches_primary_and_source_refs(db_session):
    db_session.add_all([
        KnowledgeUnit(id="u-a", title="Unit A", status="published"),
        KnowledgeUnit(id="u-b", title="Unit B", status="published"),
    ])
    _add_point(db_session, "kp-primary", "u-a", "主章节点", "confirmed")
    _add_point(db_session, "kp-merged", "u-a", "融合点", "confirmed",
               source_refs=[{"unit_id": "u-b", "chunk_indices": [1, 4]}])
    _add_point(db_session, "kp-other", "u-b", "独立点", "confirmed")
    await db_session.commit()

    res = await list_points(status="", unit_id="u-b", offset=0, limit=10, db=db_session)

    ids = {i["id"] for i in res["items"]}
    assert ids == {"kp-merged", "kp-other"}


@pytest.mark.asyncio
async def test_keyword_filter_matches_title_or_content(db_session):
    db_session.add(KnowledgeUnit(id="u-a", title="Unit A", status="published"))
    _add_point(db_session, "kp-1", "u-a", "LangGraph 状态机", "confirmed", content="状态流转")
    _add_point(db_session, "kp-2", "u-a", "检索引擎", "confirmed", content="Milvus 部署")
    await db_session.commit()

    by_title = await list_points(status="", keyword="LangGraph", offset=0, limit=10, db=db_session)
    by_content = await list_points(status="", keyword="部署", offset=0, limit=10, db=db_session)
    no_hit = await list_points(status="", keyword="不存在的词", offset=0, limit=10, db=db_session)

    assert [i["id"] for i in by_title["items"]] == ["kp-1"]
    assert [i["id"] for i in by_content["items"]] == ["kp-2"]
    assert no_hit["total"] == 0 and no_hit["items"] == []
