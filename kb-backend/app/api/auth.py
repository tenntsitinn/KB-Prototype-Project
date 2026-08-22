from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, RefreshRequest, UserInfo, PasswordChangeRequest, ProfileUpdateRequest
from app.services import auth_service
from app.services import user_service

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
        # 新注册用户默认赋予普通用户角色
        await user_service.assign_role(db, user.id, "regular_user")
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