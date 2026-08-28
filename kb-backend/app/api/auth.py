from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, RefreshRequest, UserInfo, PasswordChangeRequest, ProfileUpdateRequest
from app.services import auth_service
from app.services import user_service
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, request.username, request.password)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(request.username.strip()) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名至少 3 个字符")
    if len(request.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少 6 位")
    try:
        user = await user_service.create_user(
            db,
            username=request.username.strip(),
            password=request.password,
            display_name=request.display_name.strip() or request.username.strip(),
            email=request.email.strip() or "",
        )
        # 新注册用户默认角色：education→学员，personal→普通用户
        default_role = "student" if settings.APP_MODE == "education" else "regular_user"
        await user_service.assign_role(db, user.id, default_role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"detail": "注册成功", "user_id": user.id}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_access_token(db, request.refresh_token)


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        is_superuser=user.is_superuser,
        roles=[ur.role.role_code for ur in user.roles],
        status=user.status,
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")
    if len(request.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少需要 6 位")
    try:
        await user_service.change_password(db, user.id, request.old_password, request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"detail": "密码修改成功"}


@router.put("/profile", response_model=UserInfo)
async def update_profile(
    request: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await user_service.update_profile(
        db, user.id,
        display_name=request.display_name,
        email=request.email,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserInfo(
        id=updated.id,
        username=updated.username,
        display_name=updated.display_name,
        email=updated.email,
        department_id=updated.department_id,
        is_superuser=updated.is_superuser,
        roles=[ur.role.role_code for ur in updated.roles],
        status=updated.status,
    )


class ApiKeyResponse(BaseModel):
    has_key: bool
    masked_key: str
    is_superuser: bool
    base_url: str = ""
    model: str = ""


class ApiKeyUpdateRequest(BaseModel):
    api_key: str
    base_url: str = ""
    model: str = ""


# 支持的平台预设（与系统默认一致的平台排在首位）
LLM_PLATFORMS: list[dict] = [
    {"code": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com", "default_model": "deepseek-chat"},
    {"code": "siliconflow", "name": "硅基流动", "base_url": "https://api.siliconflow.cn/v1", "default_model": "deepseek-ai/DeepSeek-V3"},
    {"code": "moonshot", "name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1", "default_model": "moonshot-v1-8k"},
    {"code": "zhipu", "name": "智谱 AI", "base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash"},
    {"code": "qwen", "name": "阿里通义", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    {"code": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
]


@router.get("/llm-platforms")
async def get_llm_platforms():
    """获取支持的 LLM 平台预设清单"""
    return {"platforms": LLM_PLATFORMS}


@router.get("/api-key", response_model=ApiKeyResponse)
async def get_api_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的 API key 状态（脱敏显示）"""
    from app.core.security import decrypt_value

    if user.is_superuser:
        from app.core.llm_config import resolve_system_llm_config
        sys_key, sys_base_url, sys_model = await resolve_system_llm_config(db)
        masked = sys_key[:4] + "****" + sys_key[-4:] if len(sys_key) > 8 else ("****" if sys_key else "")
        return ApiKeyResponse(
            has_key=bool(sys_key),
            masked_key=masked or "使用系统默认密钥",
            is_superuser=True,
            base_url=sys_base_url, model=sys_model,
        )
    key = decrypt_value(user.llm_api_key) if user.llm_api_key else ""
    if key:
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        return ApiKeyResponse(
            has_key=True, masked_key=masked, is_superuser=False,
            base_url=user.llm_base_url or "", model=user.llm_model or "",
        )
    return ApiKeyResponse(has_key=False, masked_key="", is_superuser=False)


@router.put("/api-key", response_model=ApiKeyResponse)
async def update_api_key(
    req: ApiKeyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置/更新当前用户的 API key 及平台配置（超级管理员不允许设置，使用系统默认）"""
    from app.core.security import encrypt_value

    if user.is_superuser:
        raise HTTPException(status_code=403, detail="超级管理员使用系统默认密钥，无需设置")
    key = req.api_key.strip()
    base_url = req.base_url.strip()
    model = req.model.strip()

    if key:
        if base_url and not base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="平台地址格式不正确")
        if not base_url:
            raise HTTPException(status_code=400, detail="请选择 API Key 所属平台")
    else:
        base_url = ""
        model = ""

    encrypted_key = encrypt_value(key) if key else ""
    await db.execute(
        update(User).where(User.id == user.id).values(
            llm_api_key=encrypted_key, llm_base_url=base_url, llm_model=model,
        )
    )
    await db.commit()
    if key:
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        return ApiKeyResponse(
            has_key=True, masked_key=masked, is_superuser=False,
            base_url=base_url, model=model,
        )
    return ApiKeyResponse(has_key=False, masked_key="", is_superuser=False)