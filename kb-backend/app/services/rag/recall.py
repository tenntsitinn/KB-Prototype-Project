"""多路召回 + 权限过滤 + 范围过滤 + 补召（最多 2 轮）"""
import asyncio
import logging
from sqlalchemy import text as sa_text
from app.config import settings
from app.graphs.rag_graph import (
    ChunkResult, RecallConfig, RAGState,
    _embedding_search, _hyde_search, _keyword_search, _get_allowed_unit_ids,
)

logger = logging.getLogger(__name__)


async def _resolve_scope_unit_ids(state: RAGState) -> set[str] | None:
    """如果指定了 scope_chapter_id，递归查出章节及子孙下所有 unit_id"""
    chapter_id = state.get("scope_chapter_id")
    if not chapter_id:
        return None
    db = state["db"]
    row = await db.execute(sa_text("""
        WITH RECURSIVE ct AS (
            SELECT id FROM chapters WHERE id = :cid
            UNION ALL
            SELECT c.id FROM chapters c JOIN ct ON c.parent_id = ct.id
        )
        SELECT DISTINCT ku.id FROM knowledge_units ku
        WHERE ku.chapter_id IN (SELECT id FROM ct)
          AND ku.status = 'published'
    """), {"cid": chapter_id})
    return {r[0] for r in row.all()}


async def do_recall(state: RAGState) -> dict:
    db = state["db"]
    user = state["user"]
    query = state["rewritten_query"]
    top_k = state.get("top_k", settings.RAG_TOP_K)
    from app.core.llm_config import resolve_user_llm_config
    user_api_key, user_base_url, user_model = await resolve_user_llm_config(db, user)

    scope_unit_ids = await _resolve_scope_unit_ids(state)

    config = RecallConfig(
        target_k=top_k,
        round1_multiplier=settings.RAG_RECALL_MULTIPLIER,
        round2_multiplier=settings.RAG_RECALL_MULTIPLIER_FALLBACK,
        round1_threshold=settings.RAG_SIMILARITY_THRESHOLD,
        round2_threshold=settings.RAG_SIMILARITY_THRESHOLD_FALLBACK,
    )

    all_embedding: list[ChunkResult] = []
    all_hyde: list[ChunkResult] = []
    all_keyword: list[ChunkResult] = []

    for round_num in range(1, config.max_rounds + 1):
        multiplier = config.round1_multiplier if round_num == 1 else config.round2_multiplier
        threshold = config.round1_threshold if round_num == 1 else config.round2_threshold
        limit = config.target_k * multiplier

        new_embedding, new_hyde, new_keyword = await asyncio.gather(
            _embedding_search(query, limit, threshold),
            _hyde_search(query, limit, threshold, user_api_key, user_base_url, user_model),
            _keyword_search(db, query, limit),
        )

        seen = {(r.unit_id, r.chunk_index) for r in all_embedding}
        all_embedding += [r for r in new_embedding if (r.unit_id, r.chunk_index) not in seen]
        seen = {(r.unit_id, r.chunk_index) for r in all_hyde}
        all_hyde += [r for r in new_hyde if (r.unit_id, r.chunk_index) not in seen]
        seen = {(r.unit_id, r.chunk_index) for r in all_keyword}
        all_keyword += [r for r in new_keyword if (r.unit_id, r.chunk_index) not in seen]

        all_unit_ids = {r.unit_id for sublist in [all_embedding, all_hyde, all_keyword] for r in sublist}
        allowed_ids = await _get_allowed_unit_ids(db, user, all_unit_ids)

        all_embedding = [r for r in all_embedding if r.unit_id in allowed_ids]
        all_hyde = [r for r in all_hyde if r.unit_id in allowed_ids]
        all_keyword = [r for r in all_keyword if r.unit_id in allowed_ids]

        if scope_unit_ids is not None:
            all_embedding = [r for r in all_embedding if r.unit_id in scope_unit_ids]
            all_hyde = [r for r in all_hyde if r.unit_id in scope_unit_ids]
            all_keyword = [r for r in all_keyword if r.unit_id in scope_unit_ids]

        total = len(all_embedding) + len(all_hyde) + len(all_keyword)
        if total >= config.target_k:
            break

    return {"embedding_results": all_embedding, "hyde_results": all_hyde, "keyword_results": all_keyword}