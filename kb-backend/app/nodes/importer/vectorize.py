"""向量化节点：切片先落库（断点续跑依据），再执行向量化"""
import logging

from sqlalchemy import delete as sqla_delete, update as sqla_update

from app.core.database import AsyncSessionLocal
from app.graphs.import_graph import ImportState
from app.models.knowledge_unit import KnowledgeChunk, KnowledgeUnit
from app.services.importer.text_chunker import merge_chunks
from app.services.vectorizer import vectorize_and_insert

logger = logging.getLogger(__name__)


async def node_vectorize(state: ImportState) -> dict:
    unit_id = state["unit_id"]
    chunks = state["raw_chunks"]

    # 切片与内容先持久化：向量化中途失败时，重试任务可以从这里续跑
    async with AsyncSessionLocal() as db:
        await db.execute(sqla_delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id))
        db.add_all([
            KnowledgeChunk(unit_id=unit_id, chunk_index=c.index, chunk_text=c.text)
            for c in chunks if c.text.strip()
        ])
        await db.execute(sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
            content=merge_chunks(chunks),
            summary=state["merged_text"][:500],
            minio_path=state["minio_paths"][0] if state["minio_paths"] else "",
        ))
        await db.commit()
        logger.info("切片已持久化: unit=%s, %d chunks", unit_id, len(chunks))

    await vectorize_and_insert(unit_id, state["unit_code"], chunks)
    return {"progress": 85, "stage": "vectorized"}
