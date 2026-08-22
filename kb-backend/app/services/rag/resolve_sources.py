"""解析 chunk 对应的知识单元标题"""
import json
import logging
from sqlalchemy import select
from app.graphs.rag_graph import RAGState
from app.models.knowledge_unit import KnowledgeUnit, UnitStatus
from app.schemas.rag import SourceInfo

logger = logging.getLogger(__name__)

MIN_SCORE = 0.05
CLIFF_RATIO = 0.5
CLIFF_MIN_ABS_DROP = 0.2
MIN_TOP_SCORE = 0.15  # 最高分低于此阈值，视为无相关内容


def _detect_cliff(scores: list[float]) -> int:
    """
    从高到低扫描，找到第一个断崖位置。
    断崖定义：相邻分数跌幅 > 50% 且绝对差值 > 0.2。
    返回应该保留的个数（断崖之后的全部丢弃）。
    """
    for i, (a, b) in enumerate(zip(scores, scores[1:])):
        if b < MIN_SCORE:
            return i + 1
        drop = a - b
        if drop > CLIFF_MIN_ABS_DROP and drop / a > CLIFF_RATIO:
            return i + 1
    return len(scores)


async def do_resolve_sources(state: RAGState) -> dict:
    chunks = state["final_chunks"]
    if not chunks:
        return {"sources_json": "[]", "final_chunks": []}

    db = state["db"]
    unit_ids = {c.unit_id for c in chunks}
    stmt = select(KnowledgeUnit.id, KnowledgeUnit.title).where(
        KnowledgeUnit.id.in_(unit_ids),
        KnowledgeUnit.status != UnitStatus.DELETED,
    )
    result = await db.execute(stmt)
    title_map = {row[0]: row[1] for row in result.all()}

    # 按分数降序排列，过滤掉已删除的
    valid = sorted(
        [c for c in chunks if c.unit_id in title_map],
        key=lambda c: c.score,
        reverse=True,
    )

    if not valid:
        return {"sources_json": "[]", "final_chunks": []}

    scores = [c.score for c in valid]
    if scores[0] < MIN_TOP_SCORE:
        logger.info(f"resolve_sources: top score {scores[0]:.4f} < {MIN_TOP_SCORE}, treating as no match")
        return {"sources_json": "[]", "final_chunks": []}

    keep = _detect_cliff(scores)
    logger.info(f"resolve_sources: {len(valid)} valid, scores={scores[:5]}..., cliff at {keep}")

    kept = valid[:keep]
    sources = [
        SourceInfo(
            unit_id=c.unit_id, unit_code=c.unit_code,
            title=title_map[c.unit_id],
            chunk_index=c.chunk_index, chunk_text=c.chunk_text,
            score=round(c.score, 4), source=c.source,
        ).model_dump()
        for c in kept
    ]
    return {"sources_json": json.dumps(sources, ensure_ascii=False), "final_chunks": kept}