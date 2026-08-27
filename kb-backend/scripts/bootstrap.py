"""幂等初始化运行所需的角色、权限、标签和可选管理员账号。"""

import asyncio
import os

from app.core.database import AsyncSessionLocal
from app.services.tag_service import seed_tags
from app.services.user_service import cleanup_unknown_permissions, seed_roles, seed_users


async def bootstrap() -> None:
    async with AsyncSessionLocal() as db:
        await seed_roles(db)
        await cleanup_unknown_permissions(db)
        await seed_tags(db)

        initial_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        if initial_password:
            await seed_users(db, initial_password)
            print("Bootstrap complete; initial admin is ready.")
        else:
            print("Bootstrap complete; admin creation skipped (INITIAL_ADMIN_PASSWORD is unset).")


if __name__ == "__main__":
    asyncio.run(bootstrap())
