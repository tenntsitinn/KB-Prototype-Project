"""题库去重测试：规范化、精确/语义两级匹配、重复扫描。"""
import pytest

from app.models.knowledge_unit import KnowledgeUnit, QuizQuestion
from app.services.quiz_service import (
    DEDUP_SEMANTIC_THRESHOLD,
    _find_duplicate_question,
    _normalize_question,
    find_duplicates,
)
from tests.fakes import FakeEmbedding


pytestmark = pytest.mark.integration


SAME_VEC = [1.0, 0.0, 0.0, 0.0]

_hash_embedding = FakeEmbedding()


async def same_vector_embed(texts):
    return [list(SAME_VEC) for _ in texts]


@pytest.fixture
def patch_vectorizer(monkeypatch):
    """屏蔽 FAQ 缓存的真实 Milvus 检索；embed 默认返回哈希向量（不同文本不相似）。"""
    monkeypatch.setattr(
        "app.services.vectorizer.embed_texts", _hash_embedding.embed_texts
    )

    async def no_cache(emb):
        return None

    monkeypatch.setattr("app.services.rag.faq_service.match_faq_cache", no_cache)


def _add_question(db_session, question: str, status: str = "published",
                  unit_id: str = "u1", usage: int = 0) -> QuizQuestion:
    q = QuizQuestion(
        question=question,
        reference_answer="ref",
        category="cat",
        source_unit_id=unit_id,
        status=status,
        usage_count=usage,
    )
    db_session.add(q)
    return q


def test_normalize_collapses_whitespace_and_fullwidth():
    assert _normalize_question("你好 ， 世界？") == _normalize_question("你好,世界")
    assert _normalize_question("　Test　Question　") == "testquestion"


def test_normalize_strips_trailing_punctuation():
    assert _normalize_question("什么是RAG？") == _normalize_question("什么是RAG")
    assert _normalize_question("value。") == "value"


def test_normalize_empty_and_none():
    assert _normalize_question("") == ""
    assert _normalize_question(None) == ""


@pytest.mark.asyncio
async def test_exact_match_finds_duplicate(db_session, patch_vectorizer):
    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    await db_session.commit()
    existing = _add_question(db_session, "什么是 RAG？")
    await db_session.commit()

    # 全角标点 + 空白差异，规范化后精确命中
    hit = await _find_duplicate_question(db_session, "什么是　RAG？", source_unit_id="u1")

    assert hit is not None
    assert hit.id == existing.id


@pytest.mark.asyncio
async def test_semantic_match_against_pending_questions(db_session, patch_vectorizer, monkeypatch):
    monkeypatch.setattr("app.services.vectorizer.embed_texts", same_vector_embed)

    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    await db_session.commit()
    pending = _add_question(
        db_session, "如何使用 Docker 部署向量数据库", status="pending_review", unit_id="u1"
    )
    await db_session.commit()

    # 文本不同（精确不命中），但 embed 返回相同向量 → 语义相似度 1.0 命中
    hit = await _find_duplicate_question(
        db_session, "怎样安装部署 Milvus 检索引擎", source_unit_id="u1"
    )

    assert hit is not None
    assert hit.id == pending.id


@pytest.mark.asyncio
async def test_semantic_below_threshold_returns_none(db_session, patch_vectorizer):
    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    await db_session.commit()
    _add_question(db_session, "完全不同的问题关于量子力学", status="pending_review", unit_id="u1")
    await db_session.commit()

    hit = await _find_duplicate_question(db_session, "如何烤制那不勒斯披萨", source_unit_id="u1")

    assert hit is None


@pytest.mark.asyncio
async def test_scope_filters_by_unit(db_session, patch_vectorizer):
    db_session.add_all([
        KnowledgeUnit(id="u1", title="U1", status="published"),
        KnowledgeUnit(id="u2", title="U2", status="published"),
    ])
    await db_session.commit()
    _add_question(db_session, "什么是向量检索", unit_id="u2")
    await db_session.commit()

    # 同题但在 u2，u1 范围内查不到
    hit = await _find_duplicate_question(db_session, "什么是向量检索", source_unit_id="u1")

    assert hit is None


@pytest.mark.asyncio
async def test_find_duplicates_groups_exact_copies(db_session, patch_vectorizer):
    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    await db_session.commit()
    _add_question(db_session, "重复的问题A", status="pending_review", unit_id="u1")
    _add_question(db_session, "重复的问题A", status="pending_review", unit_id="u1")
    _add_question(db_session, "独一无二的问题B", status="pending_review", unit_id="u1")
    await db_session.commit()

    groups = await find_duplicates(db_session, status="pending_review")

    exact_groups = [g for g in groups if g["duplicates"] and g["duplicates"][0]["similarity"] == 1.0]
    assert len(exact_groups) == 1
    assert exact_groups[0]["keep_question"] == "重复的问题A"
    assert len(exact_groups[0]["duplicates"]) == 1
    assert exact_groups[0]["duplicates"][0]["question"] == "重复的问题A"


@pytest.mark.asyncio
async def test_find_duplicates_semantic_cluster(db_session, patch_vectorizer, monkeypatch):
    # 同向量 embed → 不同文本聚类为语义重复
    monkeypatch.setattr("app.services.vectorizer.embed_texts", same_vector_embed)

    db_session.add(KnowledgeUnit(id="u1", title="Unit", status="published"))
    await db_session.commit()
    _add_question(db_session, "语义重复的题目一", status="pending_review", unit_id="u1")
    _add_question(db_session, "语义重复的题目二", status="pending_review", unit_id="u1")
    await db_session.commit()

    groups = await find_duplicates(
        db_session, status="pending_review", threshold=DEDUP_SEMANTIC_THRESHOLD
    )

    # 两条文本不同（无精确重复），被语义聚类为一组
    assert len(groups) == 1
    group = groups[0]
    assert group["keep_question"] in ("语义重复的题目一", "语义重复的题目二")
    assert len(group["duplicates"]) == 1
    assert group["duplicates"][0]["similarity"] >= DEDUP_SEMANTIC_THRESHOLD
