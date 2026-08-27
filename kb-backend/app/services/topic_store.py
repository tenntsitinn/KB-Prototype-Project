"""知识点 topic 向量库：知识点级检索（区别于 chunk 级的 knowledge_units collection）。"""
import logging

import numpy as np
from pymilvus import MilvusClient

from app.config import settings

logger = logging.getLogger(__name__)
_topic_client: MilvusClient | None = None


def _get_client() -> MilvusClient:
    global _topic_client
    if _topic_client is None:
        if settings.MILVUS_LITE_DB:
            _topic_client = MilvusClient(uri=settings.MILVUS_LITE_DB)
        else:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            _topic_client = MilvusClient(uri=uri)
    return _topic_client


def _ensure_collection() -> MilvusClient:
    client = _get_client()
    name = settings.MILVUS_TOPIC_COLLECTION
    if not client.has_collection(name):
        client.create_collection(
            collection_name=name,
            dimension=settings.EMBEDDING_DIM,
            metric_type="COSINE",
            auto_id=True,
            enable_dynamic_field=True,
        )
    client.load_collection(name)
    return client


async def insert_topic_vectors(items: list[dict]) -> None:
    """items: [{point_id, title, unit_id, chapter_id, embedding}]"""
    if not items:
        return
    client = _ensure_collection()
    data = [
        {
            "point_id": it["point_id"],
            "title": it["title"],
            "unit_id": it["unit_id"],
            "chapter_id": it.get("chapter_id") or "",
            "vector": np.array(it["embedding"], dtype=np.float32),
        }
        for it in items
    ]
    client.insert(collection_name=settings.MILVUS_TOPIC_COLLECTION, data=data)


async def search_topic(
    query_embedding: list[float],
    limit: int = 5,
    unit_id: str = "",
    unit_ids: list[str] | None = None,
) -> list[dict]:
    """返回 [{point_id, title, unit_id, score}]，按分数降序。

    unit_ids 非空时限定多个来源文档内匹配（OR）；否则 unit_id 非空时限定单文档；
    都为空时全库匹配。
    """
    client = _ensure_collection()
    search_kwargs: dict = {
        "collection_name": settings.MILVUS_TOPIC_COLLECTION,
        "data": [query_embedding],
        "limit": limit,
        "output_fields": ["point_id", "title", "unit_id"],
    }
    if unit_ids:
        ids = [i for i in unit_ids if i]
        if ids:
            search_kwargs["filter"] = " || ".join(f'unit_id == "{i}"' for i in ids)
        elif unit_id:
            search_kwargs["filter"] = f'unit_id == "{unit_id}"'
    elif unit_id:
        search_kwargs["filter"] = f'unit_id == "{unit_id}"'
    results = client.search(**search_kwargs)
    if not results or not results[0]:
        return []
    return [
        {
            "point_id": hit["entity"]["point_id"],
            "title": hit["entity"]["title"],
            "unit_id": hit["entity"]["unit_id"],
            "score": float(hit["distance"]),
        }
        for hit in results[0]
    ]


async def delete_topic_vectors_by_point(point_id: str) -> None:
    try:
        client = _ensure_collection()
        client.delete(
            collection_name=settings.MILVUS_TOPIC_COLLECTION,
            filter=f'point_id == "{point_id}"',
        )
    except Exception as e:
        logger.warning("delete_topic_vectors_by_point failed: point_id=%s err=%s", point_id, e)


async def delete_topic_vectors_by_unit(unit_id: str) -> None:
    try:
        client = _ensure_collection()
        client.delete(
            collection_name=settings.MILVUS_TOPIC_COLLECTION,
            filter=f'unit_id == "{unit_id}"',
        )
    except Exception as e:
        logger.warning("delete_topic_vectors_by_unit failed: unit_id=%s err=%s", unit_id, e)
