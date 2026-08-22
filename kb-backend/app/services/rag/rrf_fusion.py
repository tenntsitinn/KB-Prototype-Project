"""RRF 多路结果融合"""
from app.config import settings
from app.graphs.rag_graph import ChunkResult, RAGState


def do_rrf_fusion(state: RAGState) -> dict:
    result_lists = [state["embedding_results"], state["hyde_results"], state["keyword_results"]]
    k = settings.RAG_RRF_K
    scores: dict[tuple[str, int], tuple[float, ChunkResult]] = {}

    for results in result_lists:
        for rank, r in enumerate(results):
            key = (r.unit_id, r.chunk_index)
            rrf_score = 1.0 / (k + rank + 1)
            if key not in scores or rrf_score > scores[key][0]:
                scores[key] = (rrf_score, r)

    merged = [r for _, r in sorted(scores.values(), key=lambda x: x[0], reverse=True)]
    for r in merged:
        r.score = scores[(r.unit_id, r.chunk_index)][0]

    return {"merged_chunks": merged}