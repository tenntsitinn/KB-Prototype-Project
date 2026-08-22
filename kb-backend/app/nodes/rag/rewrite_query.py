"""问题重写节点"""
from app.graphs.rag_graph import RAGState


async def node_rewrite_query(state: RAGState) -> dict:
    from app.services.rag.rewrite_query import do_rewrite_query
    return await do_rewrite_query(state)