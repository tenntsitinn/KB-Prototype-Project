"""
Celery 定时任务：软删除知识单元清理。

定时扫描超过 SOFT_DELETE_DAYS 天的软删除记录，物理删除数据并清理 MinIO 文件。
建议每天凌晨执行一次。
"""
import asyncio
from celery import Celery
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.services.importer.knowledge_service import cleanup_soft_deleted
from app.services.importer.minio_client import delete_file

celery_app = Celery("kb_cleanup", broker=settings.REDIS_URL, backend=settings.REDIS_URL)


def _run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="cleanup.soft_deleted")
def cleanup_soft_deleted_documents() -> dict:
    """清理超过 SOFT_DELETE_DAYS 天的软删除记录，返回清理数量"""

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            unit_ids = await cleanup_soft_deleted(db, days=settings.SOFT_DELETE_DAYS)

            # 清理 MinIO 中的对应文件
            for uid in unit_ids:
                try:
                    delete_file(settings.MINIO_BUCKET_DOCS, f"{uid}/")
                except Exception:
                    pass

            return {"deleted_count": len(unit_ids), "deleted_ids": unit_ids}

    return _run_async(_cleanup())