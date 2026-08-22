"""
Celery 定时任务：看板数据预计算与缓存。

定时聚合指标数据写入 Redis 缓存，减少 API 请求时的实时查询压力。
建议每 5 分钟执行一次。
"""
import asyncio
import json
from celery import Celery
from redis import Redis
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.services import dashboard_service

celery_app = Celery("kb_stats", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

CACHE_KEY_METRICS = "dashboard:metrics"
CACHE_KEY_QUESTION_RANK = "dashboard:question_rankings"
CACHE_KEY_UNIT_RANK = "dashboard:unit_rankings"
CACHE_TTL = 600  # 10 分钟过期


def _run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="stats.compute_metrics")
def compute_metrics() -> dict:
    """预计算看板指标并缓存到 Redis"""

    async def _compute():
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

        async with AsyncSessionLocal() as db:
            metrics = await dashboard_service.get_metrics(db)
            question_rankings = await dashboard_service.get_question_rankings(db)
            unit_rankings = await dashboard_service.get_unit_rankings(db)

        redis_client.setex(CACHE_KEY_METRICS, CACHE_TTL, json.dumps(metrics, ensure_ascii=False, default=str))
        redis_client.setex(CACHE_KEY_QUESTION_RANK, CACHE_TTL, json.dumps(question_rankings, ensure_ascii=False))
        redis_client.setex(CACHE_KEY_UNIT_RANK, CACHE_TTL, json.dumps(unit_rankings, ensure_ascii=False))

        return {
            "cached": True,
            "metrics_keys": list(metrics.keys()),
            "question_ranking_count": len(question_rankings),
            "unit_ranking_count": len(unit_rankings),
        }

    return _run_async(_compute())