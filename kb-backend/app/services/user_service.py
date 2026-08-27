from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from app.models.user import User, Role, UserRole, RolePermission, Department
from app.core.security import hash_password, verify_password
from app.config import settings


async def seed_roles(db: AsyncSession) -> None:
    """初始化默认角色和权限。education 模式：超管/系统管理/教师/学员；personal 模式：超管/系统管理/知识管理/普通用户"""
    from app.core.permissions import (
        PERM_KNOWLEDGE_MANAGE,
        PERM_KNOWLEDGE_MANAGE_PERMISSIONS,
        PERM_GAP_MANAGE, PERM_DASHBOARD_VIEW,
        PERM_QUIZ_MANAGE, PERM_PERMISSION_MANAGE,
    )

    all_knowledge = [
        PERM_KNOWLEDGE_MANAGE,
        PERM_KNOWLEDGE_MANAGE_PERMISSIONS,
        PERM_GAP_MANAGE, PERM_DASHBOARD_VIEW,
        PERM_QUIZ_MANAGE,
    ]

    # knowledge:read 和 ai:access 对所有登录用户默认开放，无需配置
    student_perms = []

    if settings.APP_MODE == "education":
        default_roles = [
            {
                "role_name": "超级管理员",
                "role_code": "super_admin",
                "description": "系统最高权限，拥有权限配置能力",
                "permissions": all_knowledge + [PERM_PERMISSION_MANAGE],
            },
            {
                "role_name": "系统管理员",
                "role_code": "system_admin",
                "description": "系统管理权限",
                "permissions": all_knowledge,
            },
            {
                "role_name": "教师",
                "role_code": "teacher",
                "description": "教学管理权限",
                "permissions": all_knowledge,
            },
            {
                "role_name": "学员",
                "role_code": "student",
                "description": "基础学习权限",
                "permissions": student_perms,
            },
        ]
    else:
        default_roles = [
            {
                "role_name": "超级管理员",
                "role_code": "super_admin",
                "description": "系统最高权限，拥有权限配置能力",
                "permissions": all_knowledge + [PERM_PERMISSION_MANAGE],
            },
            {
                "role_name": "系统管理员",
                "role_code": "system_admin",
                "description": "系统管理权限",
                "permissions": all_knowledge,
            },
            {
                "role_name": "知识管理员",
                "role_code": "knowledge_admin",
                "description": "知识库管理权限",
                "permissions": all_knowledge,
            },
            {
                "role_name": "普通用户",
                "role_code": "regular_user",
                "description": "基础查询权限",
                "permissions": student_perms,
            },
        ]

    for role_data in default_roles:
        result = await db.execute(select(Role).where(Role.role_code == role_data["role_code"]))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(
                role_name=role_data["role_name"],
                role_code=role_data["role_code"],
                description=role_data["description"],
            )
            db.add(role)
            await db.flush()

        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for perm_code in role_data["permissions"]:
            db.add(RolePermission(role_id=role.id, permission_code=perm_code))

    # education 模式下清理不应存在的旧角色（regular_user / knowledge_admin / personal_user）
    if settings.APP_MODE == "education":
        obsolete_codes = ["regular_user", "knowledge_admin", "personal_user"]
        for code in obsolete_codes:
            role_res = await db.execute(select(Role).where(Role.role_code == code))
            obsolete_role = role_res.scalar_one_or_none()
            if obsolete_role:
                student_res = await db.execute(select(Role).where(Role.role_code == "student"))
                student_role = student_res.scalar_one_or_none()
                if student_role:
                    # 迁移用户到 student 角色
                    await db.execute(
                        update(UserRole)
                        .where(UserRole.role_id == obsolete_role.id)
                        .values(role_id=student_role.id)
                    )
                    # 去重：同一用户不能有重复 student 角色
                    await db.execute(
                        delete(UserRole).where(
                            UserRole.role_id == student_role.id,
                            UserRole.user_id.in_(
                                select(UserRole.user_id)
                                .where(UserRole.role_id == student_role.id)
                                .group_by(UserRole.user_id)
                                .having(func.count() > 1)
                            )
                        )
                    )
                await db.execute(delete(RolePermission).where(RolePermission.role_id == obsolete_role.id))
                await db.delete(obsolete_role)

    await db.commit()


async def seed_users(db: AsyncSession) -> None:
    """初始化默认超级管理员账号，确保其拥有 super_admin 角色"""
    result = await db.execute(select(User).where(User.username == "admin"))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="超级管理员",
            email="admin@kb.local",
            is_superuser=True,
        )
        db.add(user)
        await db.flush()

    # 确保 is_superuser 标记
    if not user.is_superuser:
        user.is_superuser = True
        await db.flush()

    # 确保分配了 super_admin 角色
    role_result = await db.execute(select(Role).where(Role.role_code == "super_admin"))
    super_admin_role = role_result.scalar_one_or_none()
    if super_admin_role:
        existing = await db.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == super_admin_role.id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(UserRole(user_id=user.id, role_id=super_admin_role.id))

    await db.commit()


async def cleanup_unknown_permissions(db: AsyncSession) -> None:
    """清除 role_permissions 表中不属于当前权限体系的旧权限码"""
    import logging
    logger = logging.getLogger(__name__)
    from app.core.permissions import ALL_PERMISSIONS, PERM_PERMISSION_MANAGE
    valid_codes = set(ALL_PERMISSIONS) | {PERM_PERMISSION_MANAGE}
    try:
        await db.execute(delete(RolePermission).where(~RolePermission.permission_code.in_(valid_codes)))
        await db.commit()
    except Exception as e:
        logger.warning(f"清理旧权限码失败（非致命）: {e}")
        await db.rollback()


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: str = "",
    email: str = "",
) -> User:
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise ValueError("用户名已存在")

    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        email=email,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, offset: int = 0, limit: int = 20) -> tuple[list[User], int]:
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def assign_role(db: AsyncSession, user_id: str, role_code: str) -> UserRole:
    user = await db.execute(select(User).where(User.id == user_id))
    if not user.scalar_one_or_none():
        raise ValueError("用户不存在")

    role = await db.execute(select(Role).where(Role.role_code == role_code))
    role_obj = role.scalar_one_or_none()
    if not role_obj:
        raise ValueError(f"角色 {role_code} 不存在")

    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_obj.id)
    )
    if existing.scalar_one_or_none():
        raise ValueError("用户已拥有该角色")

    user_role = UserRole(user_id=user_id, role_id=role_obj.id)
    db.add(user_role)
    await db.commit()
    return user_role


async def remove_role(db: AsyncSession, user_id: str, role_code: str) -> None:
    result = await db.execute(
        select(UserRole)
        .join(Role)
        .where(UserRole.user_id == user_id, Role.role_code == role_code)
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        raise ValueError("用户未拥有该角色")
    await db.delete(user_role)
    await db.commit()


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).order_by(Role.created_at))
    return list(result.scalars().all())


async def list_departments(db: AsyncSession) -> list[Department]:
    result = await db.execute(select(Department).order_by(Department.sort_order))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# User update
# ---------------------------------------------------------------------------

async def update_user(db: AsyncSession, user_id: str, **kwargs) -> User | None:
    """更新用户字段（display_name, email, department_id, status 等）"""
    values = {k: v for k, v in kwargs.items() if v is not None}
    if not values:
        return await get_user(db, user_id)

    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(**values)
        .returning(User)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.fetchone()
    if row:
        return await get_user(db, user_id)
    return None


# ---------------------------------------------------------------------------
# Role CRUD
# ---------------------------------------------------------------------------

async def get_role(db: AsyncSession, role_id: str) -> Role | None:
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    return result.scalar_one_or_none()


async def create_role(db: AsyncSession, role_name: str, role_code: str, description: str = "") -> Role:
    existing = await db.execute(select(Role).where(Role.role_code == role_code))
    if existing.scalar_one_or_none():
        raise ValueError(f"角色编码 {role_code} 已存在")

    role = Role(role_name=role_name, role_code=role_code, description=description)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: str, **kwargs) -> Role | None:
    values = {k: v for k, v in kwargs.items() if v is not None}
    if not values:
        return await get_role(db, role_id)

    stmt = update(Role).where(Role.id == role_id).values(**values)
    await db.execute(stmt)
    await db.commit()
    return await get_role(db, role_id)


async def delete_role(db: AsyncSession, role_id: str) -> bool:
    role = await db.execute(select(Role).where(Role.id == role_id))
    if not role.scalar_one_or_none():
        return False

    # 删除关联的用户角色和权限
    await db.execute(delete(UserRole).where(UserRole.role_id == role_id))
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    await db.execute(delete(Role).where(Role.id == role_id))
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Role permissions
# ---------------------------------------------------------------------------

async def set_role_permissions(db: AsyncSession, role_id: str, permission_codes: list[str]) -> list[RolePermission]:
    # 删除旧权限
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))

    # 插入新权限
    perms = [
        RolePermission(role_id=role_id, permission_code=code)
        for code in permission_codes
    ]
    if perms:
        db.add_all(perms)

    await db.commit()

    result = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Department CRUD
# ---------------------------------------------------------------------------

async def get_department(db: AsyncSession, dept_id: str) -> Department | None:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    return result.scalar_one_or_none()


async def create_department(
    db: AsyncSession,
    parent_id: str | None,
    name: str,
    leader_id: str = "",
    sort_order: int = 0,
) -> Department:
    dept = Department(
        parent_id=parent_id,
        name=name,
        leader_id=leader_id,
        sort_order=sort_order,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


async def update_department(db: AsyncSession, dept_id: str, **kwargs) -> Department | None:
    values = {k: v for k, v in kwargs.items() if v is not None}
    if not values:
        return await get_department(db, dept_id)

    stmt = update(Department).where(Department.id == dept_id).values(**values)
    await db.execute(stmt)
    await db.commit()
    return await get_department(db, dept_id)


async def delete_department(db: AsyncSession, dept_id: str) -> bool:
    dept = await db.execute(select(Department).where(Department.id == dept_id))
    if not dept.scalar_one_or_none():
        return False

    await db.execute(delete(Department).where(Department.id == dept_id))
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Self-service password change
# ---------------------------------------------------------------------------

async def change_password(db: AsyncSession, user_id: str, old_password: str, new_password: str) -> None:
    """验证旧密码并更新为新密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")

    if not verify_password(old_password, user.password_hash):
        raise ValueError("当前密码不正确")

    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(password_hash=hash_password(new_password))
    )
    await db.execute(stmt)
    await db.commit()


# ---------------------------------------------------------------------------
# Self-service profile update
# ---------------------------------------------------------------------------

async def update_profile(db: AsyncSession, user_id: str, display_name: str | None = None, email: str | None = None) -> User | None:
    """用户修改自己的 display_name 和 email"""
    values = {}
    if display_name is not None:
        values["display_name"] = display_name
    if email is not None:
        values["email"] = email

    if not values:
        return await get_user(db, user_id)

    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()
    return await get_user(db, user_id)