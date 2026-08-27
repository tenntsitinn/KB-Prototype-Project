"""语义查重节点：解析后、切片前，用向量检索检测语义重复文档"""
import logging
from sqlalchemy import update as sqla_update
from app.core.database import AsyncSessionLocal
from app.graphs.import_graph import ImportState
from app.models.knowledge_unit import KnowledgeUnit
from app.services.vectorizer import embed_texts, search_vectors

logger = logging.getLogger(__name__)

DEDUP_THRESHOLD = 0.92
DEDUP_TEXT_LIMIT = 2000


async def node_semantic_dedup(state: ImportState) -> dict:
    merged_text = state.get("merged_text", "")
    unit_id = state["unit_id"]

    if not merged_text.strip():
        return {}

    doc_text = merged_text[:DEDUP_TEXT_LIMIT]
    embeddings = await embed_texts([doc_text])
    if not embeddings:
        logger.warning("semantic_dedup: embedding 生成失败，跳过查重")
        return {}

    results = await search_vectors(embeddings[0], limit=1, threshold=DEDUP_THRESHOLD)
    results = [r for r in results if r["unit_id"] != unit_id]

    if results:
        dup = results[0]
        logger.info(
            "semantic_dedup: unit=%s 与已有 unit=%s 语义重复, score=%.4f",
            unit_id, dup["unit_id"], dup["score"],
        )
        async with AsyncSessionLocal() as db:
            await db.execute(
                sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                    status="semantic_duplicate",
                )
            )
            await db.commit()
        return {
            "status": "semantic_duplicate",
            "error": f"文档与已有知识单元语义重复 (相似度: {dup['score']:.2f})",
            "progress": 60,
            "stage": "semantic_duplicate",
        }

    logger.info("semantic_dedup: unit=%s 未检测到语义重复", unit_id)
    return {"progress": 62, "stage": "dedup_passed"}


def route_after_semantic_dedup(state: ImportState) -> str:
    if state.get("status") == "semantic_duplicate":
        return "duplicate"
    return "continue"
