"""FAQ 缓存匹配"""
import logging
from app.graphs.rag_graph import RAGState
from app.services.vectorizer import embed_texts
from app.services.rag import faq_service

logger = logging.getLogger(__name__)


async def do_faq_check(state: RAGState) -> dict:
    try:
        question = state["question"]
        embeddings = await embed_texts([question])
        if embeddings:
            cached = await faq_service.match_faq_cache(embeddings[0])
            if cached:
                await faq_service.increment_hit_count(state["db"], cached["faq_id"])
                return {
                    "faq_cache_hit": True,
                    "faq_cached_answer": cached["answer"],
                    "faq_cached_id": cached["faq_id"],
                }
    except Exception:
        pass
    return {"faq_cache_hit": False}