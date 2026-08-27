"""
Celery 异步任务：文档导入。

编排委托给 import_graph.py 的 LangGraph 状态图执行，
本层只负责 Celery 任务注册 + 进度同步。
"""
import asyncio
import logging

from sqlalchemy import delete as sqla_delete, select, update as sqla_update

from app.tasks import celery_app
from app.graphs.import_graph import ImportState, run_import_graph

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="import.process_document")
def process_document(self, file_path: str, filename: str, creator_id: str, category: str = "", use_unlimited_ocr: bool = False) -> dict:
    """
    文档导入全链路编排（委托给 LangGraph 状态图）。

    参数:
        file_path: 上传到本地临时目录的文件路径
        filename: 原始文件名
        creator_id: 上传用户 ID
        category: 上传者选定的标签名
        use_unlimited_ocr: 是否使用 Unlimited-OCR（默认 False 走 MinerU）

    返回:
        {"unit_id": str, "status": str}
    """
    return _run_async(_async_process_document(self, file_path, filename, creator_id, category, use_unlimited_ocr))


async def _async_process_document(task, file_path: str, filename: str, creator_id: str, category: str = "", use_unlimited_ocr: bool = False) -> dict:
    task.update_state(state="PROCESSING", meta={"progress": 0, "stage": "init"})

    state: ImportState = {
        "file_path": file_path,
        "filename": filename,
        "creator_id": creator_id,
        "category": category,
        "use_unlimited_ocr": use_unlimited_ocr,
    }

    result = await run_import_graph(state)

    # 同步进度到 Celery
    progress = result.get("progress", 0)
    stage = result.get("stage", "unknown")
    unit_id = result.get("unit_id", "")

    if result.get("status") == "failed":
        task.update_state(state="FAILURE", meta={"stage": stage, "error": result.get("error", "未知错误")})
        return {"status": "failed", "error": result.get("error", "未知错误")}

    task.update_state(state="SUCCESS", meta={"progress": progress, "stage": stage, "unit_id": unit_id})

    # 导入完成后自动触发知识点提取（异步链，不阻塞导入结果）
    if unit_id:
        try:
            from app.tasks.point_task import extract_points
            extract_points.delay(unit_id)
            logger.info("已触发知识点提取: unit=%s", unit_id)
        except Exception as e:
            logger.warning("触发知识点提取失败（不影响导入结果）: unit=%s err=%s", unit_id, e)

    return {"unit_id": unit_id, "status": "completed"}


@celery_app.task(bind=True, name="import.retry_vectorize")
def retry_vectorize(self, unit_id: str) -> dict:
    """断点续跑：对向量化失败的单元继续向量化，已成功的 chunk 不重做"""
    return _run_async(_async_retry_vectorize(self, unit_id))


async def _async_retry_vectorize(task, unit_id: str) -> dict:
    task.update_state(state="PROCESSING", meta={"progress": 10, "stage": "vectorize"})

    from app.core.database import AsyncSessionLocal
    from app.models.knowledge_unit import KnowledgeChunk, KnowledgeUnit
    from app.services.importer.text_chunker import Chunk, chunk_text, merge_chunks
    from app.services.vectorizer import vectorize_and_insert, delete_vectors

    async with AsyncSessionLocal() as db:
        unit = await db.get(KnowledgeUnit, unit_id)
        if not unit:
            raise ValueError(f"知识单元不存在: {unit_id}")

        # 优先用持久化的切片（序号与首次导入一致，可精确续跑）
        result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id).order_by(KnowledgeChunk.chunk_index)
        )
        rows = result.scalars().all()
        if rows:
            chunks = [Chunk(index=r.chunk_index, text=r.chunk_text, start_char=0, end_char=0) for r in rows]
        elif unit.content:
            # 兜底：旧数据无持久化切片，按内容重切并清空旧向量（重切后序号可能与旧向量错位）
            logger.warning("unit=%s 无持久化切片，按内容重切并清空旧向量", unit_id)
            await delete_vectors(unit_id)
            chunks = chunk_text(unit.content)
            await db.execute(sqla_delete(KnowledgeChunk).where(KnowledgeChunk.unit_id == unit_id))
            db.add_all([
                KnowledgeChunk(unit_id=unit_id, chunk_index=c.index, chunk_text=c.text)
                for c in chunks if c.text.strip()
            ])
            await db.commit()
        else:
            raise ValueError("无可向量化的内容")

        task.update_state(state="PROCESSING", meta={"progress": 40, "stage": "vectorizing"})
        await vectorize_and_insert(unit_id, unit.unit_code, chunks)

        # 首次导入中断时 update 节点未执行，补齐内容并发布
        merged = merge_chunks(chunks)
        await db.execute(sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
            content=merged,
            summary=merged[:500] if not unit.summary else unit.summary,
            status="published",
        ))
        await db.commit()
        logger.info("重试向量化完成: unit=%s", unit_id)

    # 补齐发布的单元同样触发知识点提取
    try:
        from app.tasks.point_task import extract_points
        extract_points.delay(unit_id)
    except Exception as e:
        logger.warning("触发知识点提取失败（不影响重试结果）: unit=%s err=%s", unit_id, e)

    task.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed", "unit_id": unit_id})
    return {"unit_id": unit_id, "status": "completed"}