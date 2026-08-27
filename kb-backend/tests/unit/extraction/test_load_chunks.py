"""知识点提取 load_chunks 节点测试。"""
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.models.education import KnowledgePoint
from app.models.knowledge_unit import KnowledgeChunk, KnowledgeUnit
from app.nodes.extraction.load_chunks import node_load_chunks, route_after_load


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture
def patch_session(monkeypatch, db_session):
    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr("app.nodes.extraction.load_chunks.AsyncSessionLocal", fake_session_factory)


async def test_missing_unit_returns_failed(patch_session):
    state = await node_load_chunks({"unit_id": "no-such-unit"})

    assert state["status"] == "failed"
    assert "不存在" in state["error"]
    assert route_after_load(state) == "failed"


async def test_already_extracted_unit_is_skipped(patch_session, db_session):
    unit = KnowledgeUnit(id="skip-unit", title="Skip", status="published", points_status="extraction_done")
    db_session.add(unit)
    await db_session.commit()

    state = await node_load_chunks({"unit_id": "skip-unit"})

    assert state["status"] == "skipped"
    assert route_after_load(state) == "skipped"


async def test_unpublished_unit_returns_failed(patch_session, db_session):
    unit = KnowledgeUnit(id="draft-unit", title="Draft", status="draft", points_status="none")
    db_session.add(unit)
    await db_session.commit()

    state = await node_load_chunks({"unit_id": "draft-unit"})

    assert state["status"] == "failed"
    assert "尚未发布" in state["error"]


async def test_unit_without_chunks_marks_done(patch_session, db_session):
    unit = KnowledgeUnit(id="empty-unit", title="Empty", status="published", points_status="none", content="")
    db_session.add(unit)
    await db_session.commit()

    state = await node_load_chunks({"unit_id": "empty-unit"})

    assert state["status"] == "completed"
    assert state["stats"]["chunks"] == 0
    assert route_after_load(state) == "empty"
    await db_session.refresh(unit)
    assert unit.points_status == "extraction_done"


async def test_chunks_loaded_and_unit_enters_extracting(patch_session, db_session):
    unit = KnowledgeUnit(id="run-unit", title="Run", status="published", points_status="none")
    db_session.add(unit)
    db_session.add_all([
        KnowledgeChunk(unit_id="run-unit", chunk_index=0, chunk_text="chunk zero"),
        KnowledgeChunk(unit_id="run-unit", chunk_index=1, chunk_text="chunk one"),
        KnowledgeChunk(unit_id="run-unit", chunk_index=2, chunk_text="   "),
    ])
    await db_session.commit()

    state = await node_load_chunks({"unit_id": "run-unit"})

    assert route_after_load(state) == "run"
    assert state["cursor"] == 0
    assert state["chunks"] == [
        {"chunk_index": 0, "chunk_text": "chunk zero"},
        {"chunk_index": 1, "chunk_text": "chunk one"},
    ]
    assert state["stats"] == {"chunks": 2, "auto_merged": 0, "candidates": 0, "created": 0}
    await db_session.refresh(unit)
    assert unit.points_status == "extracting"


async def test_force_rerun_clears_pending_review_points_only(patch_session, db_session, monkeypatch):
    deleted_units = []

    async def fake_delete_vectors(unit_id):
        deleted_units.append(unit_id)

    monkeypatch.setattr(
        "app.nodes.extraction.load_chunks.delete_topic_vectors_by_unit",
        fake_delete_vectors,
    )

    unit = KnowledgeUnit(id="force-unit", title="Force", status="published", points_status="extraction_done")
    pending = KnowledgePoint(id="kp-pending", unit_id="force-unit", title="Pending", status="pending_review")
    confirmed = KnowledgePoint(id="kp-confirmed", unit_id="force-unit", title="Confirmed", status="confirmed")
    db_session.add_all([unit, pending, confirmed])
    db_session.add(KnowledgeChunk(unit_id="force-unit", chunk_index=0, chunk_text="force content"))
    await db_session.commit()

    state = await node_load_chunks({"unit_id": "force-unit", "force": True})

    assert route_after_load(state) == "run"
    assert deleted_units == ["force-unit"]
    remaining = (await db_session.execute(
        select(KnowledgePoint.id).where(KnowledgePoint.unit_id == "force-unit")
    )).scalars().all()
    assert set(remaining) == {"kp-confirmed"}
