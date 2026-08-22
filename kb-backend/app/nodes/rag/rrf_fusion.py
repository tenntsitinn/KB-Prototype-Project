"""RRF 融合节点"""
from app.graphs.rag_graph import RAGState


def node_rrf_fusion(state: RAGState) -> dict:
    from app.services.rag.rrf_fusion import do_rrf_fusion
    return do_rrf_fusion(state)