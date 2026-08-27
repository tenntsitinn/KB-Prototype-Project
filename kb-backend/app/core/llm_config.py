from fastapi import HTTPException

from app.core.security import decrypt_value
from app.models.user import User


def resolve_user_llm_config(user: User) -> tuple[str, str, str]:
    if user.is_superuser:
        return "", "", ""
    api_key = decrypt_value(user.llm_api_key) if user.llm_api_key else ""
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="请先配置 API Key 后再使用 AI 功能（个人中心 → API Key 管理）",
        )
    return api_key, user.llm_base_url or "", user.llm_model or ""
