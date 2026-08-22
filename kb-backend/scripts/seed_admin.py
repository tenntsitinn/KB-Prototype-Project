"""
种子脚本：创建系统管理员账号（admin / admin123）
在 AutoDL 服务器上运行：python scripts/seed_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.user import User, Role, UserRole
from app.core.security import hash_password
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def seed_admin():
    async with AsyncSessionLocal() as db:
        # 检查是否已存在
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("admin 用户已存在，跳过创建")
            return

        # 创建管理员用户
        user = User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="系统管理员",
            is_superuser=True,
        )
        db.add(user)
        await db.flush()

        # 分配 system_admin 角色
        result = await db.execute(select(Role).where(Role.role_code == "system_admin"))
        role = result.scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

        await db.commit()
        print("系统管理员创建成功！")
        print(f"  ID: {user.id}")
        print(f"  用户名: admin")
        print(f"  密码: admin123")
        print(f"  超级用户: True")
        if role:
            print(f"  角色: system_admin")

        # 验证
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.username == "admin")
        )
        u = result.scalar_one()
        print(f"\n验证 roles: {[ur.role.role_code for ur in u.roles]}")

asyncio.run(seed_admin())