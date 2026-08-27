"""收尾节点：标记提取完成，输出统计"""
import logging

from sqlalchemy import update as sqla_update

from app.core.database import AsyncSessionLocal
from app.graphs.point_extraction_graph import PointExtractionState
from app.models.knowledge_unit import KnowledgeUnit

logger = logging.getLogger(__name__)


async def node_finalize(state: PointExtractionState) -> dict:
    unit_id = state["unit_id"]
    async with AsyncSessionLocal() as db:
        await db.execute(
            sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                points_status="extraction_done", points_error=""
            )
        )
        await db.commit()

    stats = state.get("stats") or {}
    logger.info("知识点提取完成: unit=%s stats=%s", unit_id, stats)
    return {"status": "completed", "stage": "finalize"}
