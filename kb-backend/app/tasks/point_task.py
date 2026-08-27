"""
Celery 异步任务：知识点提取。

由文档导入完成后的钩子自动触发，也可通过 API 手动触发存量文档回填。
LLM 走上传者的 BYOK 配置（users.llm_api_key），无个人配置时回退全局 key。
"""
import asyncio
import logging

from sqlalchemy import select, update as sqla_update

from app.config import settings
from app.tasks import celery_app
from app.graphs.point_extraction_graph import PointExtractionState, run_point_extraction_graph

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _resolve_llm_config(unit_id: str) -> tuple[str, str, str]:
    """优先使用上传者的 LLM 配置，回退全局配置"""
    from app.core.database import AsyncSessionLocal
    from app.models.knowledge_unit import KnowledgeUnit
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        unit = await db.get(KnowledgeUnit, unit_id)
        creator_id = unit.creator_id if unit else ""
        creator = await db.get(User, creator_id) if creator_id else None

    from app.core.security import decrypt_value

    raw_key = (creator.llm_api_key if creator else "") or ""
    api_key = decrypt_value(raw_key) if raw_key else ""
    if not api_key:
        api_key = settings.LLM_API_KEY
    base_url = (creator.llm_base_url if creator else "") or settings.LLM_BASE_URL
    model = (creator.llm_model if creator else "") or settings.LLM_MODEL
    return api_key, base_url, model


async def _mark_failed(unit_id: str, error: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.knowledge_unit import KnowledgeUnit

    async with AsyncSessionLocal() as db:
        await db.execute(
            sqla_update(KnowledgeUnit).where(KnowledgeUnit.id == unit_id).values(
                points_status="failed", points_error=error
            )
        )
        await db.commit()
    logger.error("知识点提取失败: unit=%s error=%s", unit_id, error)


@celery_app.task(bind=True, name="import.extract_points")
def extract_points(self, unit_id: str, force: bool = False) -> dict:
    """知识点提取全链路（委托给 LangGraph 状态图）"""
    return _run_async(_async_extract_points(self, unit_id, force))


async def _async_extract_points(task, unit_id: str, force: bool = False) -> dict:
    task.update_state(state="PROCESSING", meta={"progress": 0, "stage": "load_chunks"})

    api_key, base_url, model = await _resolve_llm_config(unit_id)
    if not api_key:
        await _mark_failed(unit_id, "未配置 LLM API Key（上传者与全局均无），无法提取知识点")
        return {"status": "failed", "error": "未配置 LLM API Key"}

    state: PointExtractionState = {
        "unit_id": unit_id,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "force": force,
    }

    try:
        result = await run_point_extraction_graph(state)
    except Exception as e:
        await _mark_failed(unit_id, str(e))
        task.update_state(state="FAILURE", meta={"stage": "extraction", "error": str(e)})
        return {"status": "failed", "error": str(e)}

    if result.get("status") == "failed":
        await _mark_failed(unit_id, result.get("error", "未知错误"))
        return {"status": "failed", "error": result.get("error", "未知错误")}

    task.update_state(state="SUCCESS", meta={
        "progress": 100, "stage": "extraction_done", "stats": result.get("stats"),
    })
    return {"status": result.get("status", "completed"), "stats": result.get("stats")}
