"""知识缺口检测节点"""
from app.graphs.rag_graph import RAGState


async def node_gap_detect(state: RAGState) -> dict:
    from app.services.rag.gap_detect import do_gap_detect
    return await do_gap_detect(state)