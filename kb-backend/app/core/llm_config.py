from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decrypt_value
from app.models.system_config import SystemConfig
from app.models.user import User

SYSTEM_LLM_KEYS = ("llm_api_key", "llm_base_url", "llm_model")


async def resolve_system_llm_config(db: AsyncSession) -> tuple[str, str, str]:
    """全局 LLM 配置：数据库（超管在系统管理页配置）优先，回退环境变量"""
    rows = (
        await db.execute(select(SystemConfig).where(SystemConfig.key.in_(SYSTEM_LLM_KEYS)))
    ).scalars().all()
    stored = {row.key: row.value for row in rows}

    api_key = stored.get("llm_api_key", "")
    api_key = decrypt_value(api_key) if api_key else ""
    base_url = stored.get("llm_base_url", "")
    model = stored.get("llm_model", "")

    return (
        api_key or settings.LLM_API_KEY,
        base_url or settings.LLM_BASE_URL,
        model or settings.LLM_MODEL,
    )


async def resolve_system_llm_config_standalone() -> tuple[str, str, str]:
    """Celery 任务等无请求级 session 的上下文使用"""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await resolve_system_llm_config(db)


async def resolve_user_llm_config(db: AsyncSession, user: User) -> tuple[str, str, str]:
    if user.is_superuser:
        return await resolve_system_llm_config(db)
    api_key = decrypt_value(user.llm_api_key) if user.llm_api_key else ""
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="请先配置 API Key 后再使用 AI 功能（个人中心 → API Key 管理）",
        )
    return api_key, user.llm_base_url or "", user.llm_model or ""
