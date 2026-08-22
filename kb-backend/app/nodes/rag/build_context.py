"""上下文构建节点"""
from app.graphs.rag_graph import RAGState


def node_build_context(state: RAGState) -> dict:
    from app.services.rag.build_context import do_build_context
    return do_build_context(state)