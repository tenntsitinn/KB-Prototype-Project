"""Rerank 重排序"""
import logging
import httpx
from app.config import settings
from app.graphs.rag_graph import ChunkResult, RAGState

logger = logging.getLogger(__name__)


async def do_rerank(state: RAGState) -> dict:
    chunks = state["merged_chunks"]
    top_k = state.get("top_k", settings.RAG_TOP_K)

    if not chunks:
        return {"reranked_chunks": [], "final_chunks": []}

    try:
        rerank_api_key = settings.RERANK_API_KEY or settings.EMBEDDING_API_KEY
        rerank_base = settings.RERANK_BASE_URL or settings.EMBEDDING_BASE_URL
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{rerank_base.rstrip('/')}/rerank",
                headers={"Authorization": f"Bearer {rerank_api_key}"},
                json={
                    "model": settings.RERANK_MODEL,
                    "query": state["question"],
                    "documents": [c.chunk_text for c in chunks],
                    "top_n": len(chunks),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        reranked: list[ChunkResult] = []
        for item in data.get("results", []):
            idx = item["index"]
            if idx < len(chunks):
                chunks[idx].score = float(item.get("relevance_score", 0))
                reranked.append(chunks[idx])

        return {"reranked_chunks": reranked, "final_chunks": reranked[:top_k]}
    except Exception:
        return {"reranked_chunks": chunks, "final_chunks": chunks[:top_k]}