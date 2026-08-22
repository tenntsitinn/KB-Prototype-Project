"""来源解析节点"""
from app.graphs.rag_graph import RAGState


async def node_resolve_sources(state: RAGState) -> dict:
    from app.services.rag.resolve_sources import do_resolve_sources
    return await do_resolve_sources(state)