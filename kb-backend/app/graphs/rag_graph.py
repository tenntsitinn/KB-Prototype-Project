"""
RAG 检索链路 LangGraph 状态图。

图结构:
  START → faq_check ──[命中]──→ END (提前退出)
       │
       └──[未命中]──→ rewrite_query → recall → rrf_fusion → rerank → gap_detect → resolve_sources → build_context → END

本文件包含：共享类型、LLM 客户端、召回辅助函数、图构建。
Prompt 模板在 app/prompts/，节点函数在 app/nodes/rag/。
"""
import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_unit import UnitPermission
from app.models.user import User
from app.prompts.rag_prompts import HYDE_PROMPT
from app.services.vectorizer import embed_texts, search_vectors

logger = logging.getLogger(__name__)


# ============================================================================
# 共享类型
# ============================================================================


@dataclass
class ChunkResult:
    unit_id: str
    unit_code: str
    chunk_index: int
    chunk_text: str
    score: float
    source: str  # embedding | hyde | keyword


@dataclass
class RecallConfig:
    target_k: int = 10
    round1_multiplier: int = 5
    round2_multiplier: int = 10
    round1_threshold: float = 0.5
    round2_threshold: float = 0.4
    max_rounds: int = 2


class RAGState(TypedDict, total=False):
    """RAG 管道状态，在节点间传递"""

    # ── 输入 ──
    question: str
    user: User
    db: AsyncSession
    session_id: str
    top_k: int

    # ── 中间结果 ──
    faq_cache_hit: bool
    faq_cached_answer: str
    faq_cached_id: str
    rewritten_query: str
    embedding_results: list[ChunkResult]
    hyde_results: list[ChunkResult]
    keyword_results: list[ChunkResult]
    merged_chunks: list[ChunkResult]
    reranked_chunks: list[ChunkResult]
    final_chunks: list[ChunkResult]
    sources_json: str
    context: str
    context_images: list[str]  # 从召回 chunk 中提取的图片引用
    gap_detected: bool
    gap_score: float


# ============================================================================
# LLM 客户端（单例）
# ============================================================================

_llm_client: AsyncOpenAI | None = None


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY or settings.EMBEDDING_API_KEY,
            base_url=settings.LLM_BASE_URL or settings.EMBEDDING_BASE_URL,
        )
    return _llm_client


# ============================================================================
# 召回辅助函数（被 rag_service._do_recall 调用）
# ============================================================================


async def _embedding_search(query: str, limit: int, threshold: float) -> list[ChunkResult]:
    embeddings = await embed_texts([query])
    if not embeddings:
        return []
    results = await search_vectors(embeddings[0], limit=limit, threshold=threshold)
    return [
        ChunkResult(
            unit_id=r["unit_id"], unit_code=r["unit_code"],
            chunk_index=r["chunk_index"], chunk_text=r["chunk_text"],
            score=r["score"], source="embedding",
        )
        for r in results
    ]


async def _hyde_search(question: str, limit: int, threshold: float) -> list[ChunkResult]:
    try:
        client = _get_llm_client()
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": HYDE_PROMPT.format(question=question)}],
            temperature=0.7, max_tokens=512,
        )
        hyde_text = resp.choices[0].message.content.strip()
        if not hyde_text:
            return []
        embeddings = await embed_texts([hyde_text])
        if not embeddings:
            return []
        results = await search_vectors(embeddings[0], limit=limit, threshold=threshold)
        return [
            ChunkResult(
                unit_id=r["unit_id"], unit_code=r["unit_code"],
                chunk_index=r["chunk_index"], chunk_text=r["chunk_text"],
                score=r["score"], source="hyde",
            )
            for r in results
        ]
    except Exception:
        return []


async def _keyword_search(db: AsyncSession, query: str, limit: int) -> list[ChunkResult]:
    try:
        config_sql = text("SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhparser'")
        config_result = await db.execute(config_sql)
        ts_config = "zhparser" if config_result.scalar() else "simple"

        stmt = text(f"""
            SELECT ku.id AS unit_id, ku.unit_code,
                   ts_rank(to_tsvector('{ts_config}', ku.content), query) AS rank,
                   ku.content AS chunk_text
            FROM knowledge_units ku,
                 plainto_tsquery('{ts_config}', :query) AS query
            WHERE to_tsvector('{ts_config}', ku.content) @@ query
              AND ku.status != 'deleted'
            ORDER BY rank DESC
            LIMIT :limit
        """)
        result = await db.execute(stmt, {"query": query, "limit": limit})
        rows = result.all()
        return [
            ChunkResult(
                unit_id=row.unit_id, unit_code=row.unit_code,
                chunk_index=0, chunk_text=(row.chunk_text or "")[:500],
                score=float(row.rank), source="keyword",
            )
            for row in rows
        ]
    except Exception:
        return []


async def _get_allowed_unit_ids(db: AsyncSession, user: User, unit_ids: set[str]) -> set[str]:
    if not unit_ids:
        return set()
    if user.is_superuser:
        return unit_ids

    role_ids = [ur.role_id for ur in user.roles]
    stmt = select(UnitPermission.unit_id).where(
        UnitPermission.unit_id.in_(unit_ids),
        (
            (UnitPermission.target_type == "global")
            | ((UnitPermission.target_type == "department") & (UnitPermission.target_id == user.department_id))
            | ((UnitPermission.target_type == "role") & (UnitPermission.target_id.in_(role_ids)))
            | ((UnitPermission.target_type == "user") & (UnitPermission.target_id == user.id))
        ),
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


# ============================================================================
# 图构建
# ============================================================================

_compiled_graph: CompiledStateGraph | None = None


def build_rag_graph() -> CompiledStateGraph:
    """构建并编译 RAG 检索图（单例）"""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    from app.nodes.rag.faq_check import node_faq_check, route_after_faq_check
    from app.nodes.rag.rewrite_query import node_rewrite_query
    from app.nodes.rag.recall import node_recall
    from app.nodes.rag.rrf_fusion import node_rrf_fusion
    from app.nodes.rag.rerank import node_rerank
    from app.nodes.rag.gap_detect import node_gap_detect
    from app.nodes.rag.resolve_sources import node_resolve_sources
    from app.nodes.rag.build_context import node_build_context

    builder = StateGraph(RAGState)

    builder.add_node("faq_check", node_faq_check)
    builder.add_node("rewrite_query", node_rewrite_query)
    builder.add_node("recall", node_recall)
    builder.add_node("rrf_fusion", node_rrf_fusion)
    builder.add_node("rerank", node_rerank)
    builder.add_node("gap_detect", node_gap_detect)
    builder.add_node("resolve_sources", node_resolve_sources)
    builder.add_node("build_context", node_build_context)

    builder.set_entry_point("faq_check")
    builder.add_conditional_edges("faq_check", route_after_faq_check, {"faq_hit": END, "faq_miss": "rewrite_query"})
    builder.add_edge("rewrite_query", "recall")
    builder.add_edge("recall", "rrf_fusion")
    builder.add_edge("rrf_fusion", "rerank")
    builder.add_edge("rerank", "gap_detect")
    builder.add_edge("gap_detect", "resolve_sources")
    builder.add_edge("resolve_sources", "build_context")
    builder.add_edge("build_context", END)

    _compiled_graph = builder.compile()
    return _compiled_graph


async def run_rag_graph(state: RAGState) -> RAGState:
    """执行 RAG 检索图，返回最终状态"""
    graph = build_rag_graph()
    result = await graph.ainvoke(state)
    return result