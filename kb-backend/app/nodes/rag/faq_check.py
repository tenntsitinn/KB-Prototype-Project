"""FAQ 缓存匹配节点"""
from app.graphs.rag_graph import RAGState


async def node_faq_check(state: RAGState) -> dict:
    from app.services.rag.faq_check import do_faq_check
    return await do_faq_check(state)


def route_after_faq_check(state: RAGState) -> str:
    return "faq_hit" if state.get("faq_cache_hit") else "faq_miss"