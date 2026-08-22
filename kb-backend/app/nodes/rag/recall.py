"""多路召回节点"""
from app.graphs.rag_graph import RAGState


async def node_recall(state: RAGState) -> dict:
    from app.services.rag.recall import do_recall
    return await do_recall(state)