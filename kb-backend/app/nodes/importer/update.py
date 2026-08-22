"""更新知识单元节点"""
import logging
from sqlalchemy import update as sqla_update
from app.core.database import AsyncSessionLocal
from app.graphs.import_graph import ImportState
from app.models.knowledge_unit import KnowledgeUnit
from app.services.importer.text_chunker import merge_chunks

logger = logging.getLogger(__name__)


async def node_update(state: ImportState) -> dict:
    unit_id = state["unit_id"]
    merged = merge_chunks(state["raw_chunks"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                content=merged,
                summary=state["merged_text"][:500],
                minio_path=state["minio_paths"][0] if state["minio_paths"] else "",
                status="published",
            )
        )
        await db.commit()
        logger.info(f"知识单元 {unit_id} 已更新为 published, rowcount={result.rowcount}")

    return {"status": "completed", "progress": 100, "stage": "completed"}