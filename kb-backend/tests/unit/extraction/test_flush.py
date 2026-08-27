"""知识点提取 flush 节点测试：三层相似度决策与落库。"""
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.education import KnowledgePoint
from app.models.knowledge_unit import KnowledgeUnit
from app.nodes.extraction.flush import _merge_source_refs, node_flush, route_after_flush
from tests.fakes import FakeEmbedding, FakeLLM


pytestmark = pytest.mark.integration


@pytest.fixture
def flush_deps(monkeypatch, db_session):
    """flush 节点依赖 AsyncSessionLocal/embed/search/LLM，全部替换为可控假件。"""

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr("app.nodes.extraction.flush.AsyncSessionLocal", fake_session_factory)

    fake_llm = FakeLLM(default_response='{"content": "重写后的内容"}')
    monkeypatch.setattr(
        "app.nodes.extraction.flush._get_llm_client", lambda api_key, base_url: fake_llm
    )

    embedding = FakeEmbedding()
    text_to_emb: dict[str, list[float]] = {}
    matches_by_text: dict[str, list[dict]] = {}

    async def fake_embed_texts(texts):
        vectors = await embedding.embed(texts)
        for text, vec in zip(texts, vectors):
            text_to_emb[text] = vec
        return vectors

    monkeypatch.setattr("app.nodes.extraction.flush.embed_texts", fake_embed_texts)

    recorded_vectors: list[dict] = []

    async def fake_insert(vectors):
        recorded_vectors.extend(vectors)

    monkeypatch.setattr("app.nodes.extraction.flush.insert_topic_vectors", fake_insert)

    async def fake_search(emb, limit=5):
        for text, vec in text_to_emb.items():
            if vec == emb:
                return matches_by_text.get(text, [])
        return []

    monkeypatch.setattr("app.nodes.extraction.flush.search_topic", fake_search)

    return SimpleNamespace(
        matches=matches_by_text, vectors=recorded_vectors, fake_llm=fake_llm,
    )


def _entry(topic: str, delta: str, indices: list[int]) -> dict:
    return {"topic": topic, "raw_delta": delta, "chunk_indices": indices}


def _base_state(unit_id: str, entries: list[dict]) -> dict:
    return {
        "unit_id": unit_id,
        "topic_acc": {e["topic"]: e for e in entries},
        "stats": {"chunks": 3, "auto_merged": 0, "candidates": 0, "created": 0},
        "cursor": 3,
        "api_key": "k", "base_url": "u", "model": "m",
        "stage": "extract",
    }


async def _add_unit(db_session, unit_id: str, status: str = "published") -> KnowledgeUnit:
    unit = KnowledgeUnit(id=unit_id, title=f"Unit {unit_id}", status=status)
    db_session.add(unit)
    await db_session.commit()
    return unit


@pytest.mark.asyncio
async def test_high_similarity_auto_merges_into_existing(db_session, flush_deps):
    await _add_unit(db_session, "u-merge")
    existing = KnowledgePoint(
        id="kp-exist", unit_id="u-merge", title="LangGraph",
        content="旧内容", summary="旧内容", status="confirmed",
        source_refs_json=json.dumps([{"unit_id": "u-merge", "chunk_indices": [1]}]),
    )
    db_session.add(existing)
    await db_session.commit()

    # 该 topic 的向量命中已有知识点（高于 TOPIC_MATCH_THRESHOLD=0.7）
    flush_deps.matches["LangGraph"] = [
        {"point_id": "kp-exist", "title": "LangGraph", "unit_id": "u-merge", "score": 0.9},
    ]

    state = _base_state("u-merge", [_entry("LangGraph", "新增的 delta", [4, 5])])
    result = await node_flush(state)

    await db_session.refresh(existing)
    assert existing.content == "重写后的内容"
    assert existing.status == "pending_review"
    # source_refs 合并：原 chunk 1 + 新 chunk 4,5
    refs = json.loads(existing.source_refs_json)
    assert refs[0]["chunk_indices"] == [1, 4, 5]
    assert result["stats"]["auto_merged"] == 1
    assert result["stats"]["created"] == 0
    # 自动合并不写新向量
    assert flush_deps.vectors == []
    assert result["topic_acc"] == {}


@pytest.mark.asyncio
async def test_medium_similarity_creates_candidate(db_session, flush_deps):
    await _add_unit(db_session, "u-cand")
    db_session.add(KnowledgePoint(id="kp-old", unit_id="u-cand", title="RAG 基础", status="confirmed"))
    await db_session.commit()

    # 0.5 < score 0.55 <= 0.7 → 新建 + 记录合并候选
    flush_deps.matches["LangGraph 状态机"] = [
        {"point_id": "kp-old", "title": "RAG 基础", "unit_id": "u-cand", "score": 0.55},
    ]

    state = _base_state("u-cand", [_entry("LangGraph 状态机", "delta 内容", [0])])
    result = await node_flush(state)

    points = (await db_session.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.unit_id == "u-cand", KnowledgePoint.title == "LangGraph 状态机"
        )
    )).scalars().all()
    assert len(points) == 1
    point = points[0]
    assert point.status == "pending_review"
    candidates = json.loads(point.candidate_merge_json)
    assert candidates[0]["point_id"] == "kp-old"
    assert result["stats"]["candidates"] == 1
    # 新建候选写入了向量
    assert len(flush_deps.vectors) == 1
    assert flush_deps.vectors[0]["point_id"] == point.id


@pytest.mark.asyncio
async def test_low_similarity_creates_new_point(db_session, flush_deps):
    await _add_unit(db_session, "u-new")

    state = _base_state("u-new", [_entry("全新知识点", "全新内容", [2])])
    result = await node_flush(state)

    points = (await db_session.execute(
        select(KnowledgePoint).where(KnowledgePoint.unit_id == "u-new")
    )).scalars().all()
    assert len(points) == 1
    assert points[0].title == "全新知识点"
    assert points[0].status == "pending_review"
    assert points[0].candidate_merge_json == "[]"
    assert result["stats"]["created"] == 1
    assert len(flush_deps.vectors) == 1


@pytest.mark.asyncio
async def test_rejected_matches_are_ignored(db_session, flush_deps):
    """rejected 知识点不能作为合并目标，也不能触发候选分支。"""
    await _add_unit(db_session, "u-rej")
    db_session.add(KnowledgePoint(id="kp-rej", unit_id="u-rej", title="旧主题", status="rejected"))
    await db_session.commit()

    # 高分命中 rejected 点 → 被过滤 → 走全新创建分支
    flush_deps.matches["旧 主题"] = [
        {"point_id": "kp-rej", "title": "旧主题", "unit_id": "u-rej", "score": 0.95},
    ]

    state = _base_state("u-rej", [_entry("旧 主题", "delta", [0])])
    result = await node_flush(state)

    assert result["stats"]["created"] == 1
    assert result["stats"]["auto_merged"] == 0
    points = (await db_session.execute(
        select(KnowledgePoint).where(KnowledgePoint.unit_id == "u-rej")
    )).scalars().all()
    assert len(points) == 2  # rejected 旧点 + 新建的点
    assert flush_deps.vectors[0]["point_id"] != "kp-rej"


def test_merge_source_refs_merges_same_unit():
    existing = json.dumps([{"unit_id": "u1", "chunk_indices": [1, 2]}])
    merged = _merge_source_refs(existing, "u1", [2, 3])
    assert json.loads(merged) == [{"unit_id": "u1", "chunk_indices": [1, 2, 3]}]


def test_merge_source_refs_appends_new_unit():
    existing = json.dumps([{"unit_id": "u1", "chunk_indices": [1]}])
    merged = _merge_source_refs(existing, "u2", [5])
    refs = json.loads(merged)
    assert {r["unit_id"] for r in refs} == {"u1", "u2"}


def test_merge_source_refs_handles_empty():
    assert json.loads(_merge_source_refs("", "u1", [0])) == [
        {"unit_id": "u1", "chunk_indices": [0]}
    ]


def test_route_after_flush():
    assert route_after_flush({"cursor": 2, "chunks": [0, 0, 0]}) == "loop"
    assert route_after_flush({"cursor": 3, "chunks": [0, 0, 0]}) == "finalize"
