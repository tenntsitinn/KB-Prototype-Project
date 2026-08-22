"""清理 Milvus 中已删除知识单元的向量"""
from pymilvus import MilvusClient

MILVUS_HOST = "119.45.115.152"
MILVUS_PORT = 19530
COLLECTION = "knowledge_units"

client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

# 列出所有 unit_id
results = client.query(
    collection_name=COLLECTION,
    filter="unit_id != ''",
    output_fields=["unit_id"],
    limit=1000,
)

unit_ids = set(r["unit_id"] for r in results)
print(f"Milvus 中现有 unit_id: {unit_ids}")

# 查询 PostgreSQL 中存在的 unit_id
import asyncpg, asyncio

async def get_active_ids():
    conn = await asyncpg.connect(
        f"postgresql://kb_user:kb_pass@{MILVUS_HOST}:5432/knowledge_base"
    )
    rows = await conn.fetch(
        "SELECT id FROM knowledge_units WHERE status != 'deleted'"
    )
    await conn.close()
    return {r["id"] for r in rows}

active_ids = asyncio.run(get_active_ids())
print(f"PostgreSQL 中活跃 unit_id: {active_ids}")

# 找出需要清理的
to_delete = unit_ids - active_ids
print(f"需要清理的 unit_id: {to_delete}")

for uid in to_delete:
    try:
        client.delete(
            collection_name=COLLECTION,
            filter=f'unit_id == "{uid}"',
        )
        print(f"  已清理: {uid}")
    except Exception as e:
        print(f"  清理失败: {uid}, {e}")

print("清理完成")