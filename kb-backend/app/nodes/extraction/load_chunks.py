"""加载切片节点：读 unit 与 chunks，重置提取状态"""
import logging

from sqlalchemy import delete as sqla_delete, select, update as sqla_update

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.graphs.point_extraction_graph import PointExtractionState
from app.models.education import KnowledgePoint
from app.models.knowledge_unit import KnowledgeChunk, KnowledgeUnit
from app.services.importer.text_chunker import chunk_text
from app.services.topic_store import delete_topic_vectors_by_unit

logger = logging.getLogger(__name__)


async def node_load_chunks(state: PointExtractionState) -> dict:
    unit_id = state["unit_id"]
    force = state.get("force", False)

    async with AsyncSessionLocal() as db:
        unit = await db.get(KnowledgeUnit, unit_id)
        if not unit:
            return {"status": "failed", "error": f"知识单元不存在: {unit_id}", "stage": "load_chunks"}
        if unit.points_status == "extraction_done" and not force:
            return {"status": "skipped", "error": "已提取完成，跳过", "stage": "load_chunks"}
        if unit.status != "published":
            return {"status": "failed", "error": "文档尚未发布，无法提取", "stage": "load_chunks"}

        # force 重跑：清掉本单元上一次提取产生的待审核知识点及其向量（confirmed 保留）
        if force:
            result = await db.execute(
                select(KnowledgePoint.id).where(
                    KnowledgePoint.unit_id == unit_id,
                    KnowledgePoint.status == "pending_review",
                )
            )
            stale_ids = [r[0] for r in result.all()]
            if stale_ids:
                await delete_topic_vectors_by_unit(unit_id)
                await db.execute(
                    sqla_delete(KnowledgePoint).where(KnowledgePoint.id.in_(stale_ids))
                )
                logger.info("force 重跑: 清理 unit=%s 待审核知识点 %d 个", unit_id, len(stale_ids))

        result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id).order_by(KnowledgeChunk.chunk_index)
        )
        rows = result.scalars().all()

        if rows:
            chunks = [{"chunk_index": r.chunk_index, "chunk_text": r.chunk_text} for r in rows if r.chunk_text.strip()]
        elif unit.content:
            # 兜底：无持久化切片时按内容重切
            chunks = [
                {"chunk_index": c.index, "chunk_text": c.text}
                for c in chunk_text(unit.content) if c.text.strip()
            ]
        else:
            chunks = []

        if not chunks:
            await db.execute(
                sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                    points_status="extraction_done", points_error=""
                )
            )
            await db.commit()
            return {"status": "completed", "stage": "load_chunks", "stats": {"chunks": 0}}

        await db.execute(
            sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                points_status="extracting", points_error=""
            )
        )
        await db.commit()

    logger.info("知识点提取开始: unit=%s chunks=%d interval=%d", unit_id, len(chunks), settings.POINT_REWRITE_INTERVAL)
    return {
        "chunks": chunks,
        "cursor": 0,
        "since_flush": 0,
        "topic_acc": {},
        "stats": {"chunks": len(chunks), "auto_merged": 0, "candidates": 0, "created": 0},
        "stage": "load_chunks",
    }


def route_after_load(state: PointExtractionState) -> str:
    status = state.get("status")
    if status == "failed":
        return "failed"
    if status == "skipped":
        return "skipped"
    if status == "completed":
        return "empty"
    return "run"
