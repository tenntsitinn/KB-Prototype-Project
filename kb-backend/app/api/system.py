from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import RequireSuperuser, get_current_user, get_db
from app.core.llm_config import resolve_system_llm_config
from app.core.permissions import UserPermissions
from app.core.security import decrypt_value, encrypt_value
from app.models.system_config import SystemConfig
from app.models.user import User

router = APIRouter(prefix="/api/system", tags=["系统配置"])


class SystemLLMConfigRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class SystemLLMConfigResponse(BaseModel):
    has_key: bool
    masked_key: str = ""
    source: str = "none"
    base_url: str = ""
    model: str = ""


def _mask(key: str) -> str:
    if len(key) > 8:
        return key[:4] + "****" + key[-4:]
    return "****" if key else ""


async def _load_stored(db: AsyncSession) -> dict[str, SystemConfig]:
    rows = (
        await db.execute(
            select(SystemConfig).where(
                SystemConfig.key.in_(("llm_api_key", "llm_base_url", "llm_model"))
            )
        )
    ).scalars().all()
    return {row.key: row for row in rows}


async def _build_response(db: AsyncSession) -> SystemLLMConfigResponse:
    stored = await _load_stored(db)
    raw_key = stored.get("llm_api_key").value if "llm_api_key" in stored else ""
    db_key = decrypt_value(raw_key) if raw_key else ""
    api_key, base_url, model = await resolve_system_llm_config(db)

    if db_key:
        source = "db"
    elif settings.LLM_API_KEY:
        source = "env"
    else:
        source = "none"
    return SystemLLMConfigResponse(
        has_key=bool(api_key),
        masked_key=_mask(api_key),
        source=source,
        base_url=base_url,
        model=model,
    )


@router.get("/llm-config", response_model=SystemLLMConfigResponse)
async def get_system_llm_config(
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    return await _build_response(db)


@router.put("/llm-config", response_model=SystemLLMConfigResponse)
async def update_system_llm_config(
    req: SystemLLMConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequireSuperuser()),
):
    api_key = req.api_key.strip()
    base_url = req.base_url.strip()
    model = req.model.strip()

    if api_key:
        if base_url and not base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="平台地址格式不正确")
        if not base_url:
            raise HTTPException(status_code=400, detail="请选择全局 API Key 所属平台")

    if api_key:
        values = {
            "llm_api_key": encrypt_value(api_key),
            "llm_base_url": base_url,
            "llm_model": model,
        }
        for key, value in values.items():
            row = await db.get(SystemConfig, key)
            if row:
                row.value = value
                row.updated_by = user.id
            else:
                db.add(SystemConfig(key=key, value=value, updated_by=user.id))
    else:
        for key in ("llm_api_key", "llm_base_url", "llm_model"):
            row = await db.get(SystemConfig, key)
            if row:
                await db.delete(row)
    await db.commit()
    return await _build_response(db)
