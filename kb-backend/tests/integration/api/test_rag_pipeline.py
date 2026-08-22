from types import SimpleNamespace

import pytest

from app.graphs.rag_graph import ChunkResult
from app.services.rag.build_context import do_build_context
from app.services.rag.recall import do_recall
from app.services.rag.rerank import do_rerank
from app.services.rag.rrf_fusion import do_rrf_fusion


pytestmark = pytest.mark.integration


class FakeRerankResponse:
    def __init__(self, results):
        self._results = results

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": self._results}


class FakeRerankHttpClient:
    def __init__(self, provider):
        self.provider = provider

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, headers, json):
        del url, headers
        results = await self.provider.rerank(json["query"], json["documents"], json["top_n"])
        return FakeRerankResponse(results)


@pytest.mark.asyncio
async def test_question_fake_recall_rerank_and_context(db_session, monkeypatch, fake_rerank):
    relevant = ChunkResult(
        unit_id="leave-policy",
        unit_code="KB-LEAVE",
        chunk_index=0,
        chunk_text="The annual leave policy grants employees paid annual leave.",
        score=0.82,
        source="embedding",
    )
    unrelated = ChunkResult(
        unit_id="security-policy",
        unit_code="KB-SECURITY",
        chunk_index=0,
        chunk_text="Password security requirements for company systems.",
        score=0.77,
        source="embedding",
    )

    async def fake_embedding_search(query, limit, threshold):
        del query, limit, threshold
        return [unrelated, relevant]

    async def fake_hyde_search(query, limit, threshold):
        del query, limit, threshold
        return [relevant]

    async def fake_keyword_search(db, query, limit):
        del db, query, limit
        return []

    async def allow_all(db, user, unit_ids):
        del db, user
        return unit_ids

    monkeypatch.setattr("app.services.rag.recall._embedding_search", fake_embedding_search)
    monkeypatch.setattr("app.services.rag.recall._hyde_search", fake_hyde_search)
    monkeypatch.setattr("app.services.rag.recall._keyword_search", fake_keyword_search)
    monkeypatch.setattr("app.services.rag.recall._get_allowed_unit_ids", allow_all)
    monkeypatch.setattr(
        "app.services.rag.rerank.httpx.AsyncClient",
        lambda **kwargs: FakeRerankHttpClient(fake_rerank),
    )

    state = {
        "question": "annual leave",
        "rewritten_query": "annual leave",
        "db": db_session,
        "user": SimpleNamespace(id="user-1", is_superuser=True, roles=[]),
        "top_k": 2,
    }
    state.update(await do_recall(state))
    state.update(do_rrf_fusion(state))
    state.update(await do_rerank(state))
    state.update(do_build_context(state))

    assert state["final_chunks"][0].unit_id == "leave-policy"
    assert "annual leave policy" in state["context"]
    assert "KB-LEAVE" in state["context"]
    assert len(fake_rerank.calls) == 1
