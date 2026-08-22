"""
Celery 定时任务：FAQ 自动挖掘。
"""
import asyncio
from app.tasks import celery_app
from app.core.database import AsyncSessionLocal
from app.services.rag import faq_service


def _run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="faq.mine")
def mine_faqs() -> dict:
    """扫描问答日志，挖掘高频问题生成候选 FAQ"""
    async def _mine():
        async with AsyncSessionLocal() as db:
            count = await faq_service.mine_faqs(db)
            return {"new_candidates": count}

    return _run_async(_mine())