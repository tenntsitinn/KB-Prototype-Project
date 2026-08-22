"""知识缺口检测"""
import logging
from app.config import settings
from app.graphs.rag_graph import RAGState
from app.services.rag import gap_service

logger = logging.getLogger(__name__)


async def do_gap_detect(state: RAGState) -> dict:
    chunks = state["final_chunks"]
    max_score = max((c.score for c in chunks), default=0)

    if not chunks or max_score < settings.GAP_SCORE_THRESHOLD:
        try:
            await gap_service.record_gap(state["db"], state["question"])
        except Exception:
            pass
        return {"gap_detected": True, "gap_score": max_score}

    return {"gap_detected": False, "gap_score": max_score}