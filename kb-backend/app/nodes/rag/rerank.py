"""Rerank 重排序节点"""
from app.graphs.rag_graph import RAGState


async def node_rerank(state: RAGState) -> dict:
    from app.services.rag.rerank import do_rerank
    return await do_rerank(state)