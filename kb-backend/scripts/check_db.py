import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'"
        ))
        tables = sorted([r[0] for r in result.fetchall()])
        print("现有表:", tables)

        if "users" in tables:
            r = await db.execute(text("SELECT count(*) FROM users"))
            print("用户数:", r.scalar())
        if "roles" in tables:
            r = await db.execute(text("SELECT count(*) FROM roles"))
            print("角色数:", r.scalar())

asyncio.run(check())