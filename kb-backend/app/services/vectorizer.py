import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import httpx
import numpy as np
from pymilvus import MilvusClient
from app.config import settings
from app.services.importer.text_chunker import Chunk

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
_milvus_client: MilvusClient | None = None
_embedding_model: "SentenceTransformer | None" = None
_embed_pool: ThreadPoolExecutor | None = None

# 远程 API 参数（仅 EMBEDDING_LOCAL=False 时使用）
EMBED_BATCH_SIZE = 16
EMBED_BATCH_INTERVAL = 3.0

# 本地模型批处理参数
LOCAL_BATCH_SIZE = 64


def _get_or_load_model() -> "SentenceTransformer":
    global _embedding_model, _embed_pool
    if _embedding_model is None:
        import os as _os
        _os.environ.setdefault("HF_HUB_OFFLINE", "1")
        _os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        from sentence_transformers import SentenceTransformer
        model_dir = settings.EMBEDDING_MODEL_DIR
        model_name = settings.EMBEDDING_MODEL
        logger.info("加载本地 embedding 模型: %s (cache: %s)", model_name, model_dir)
        try:
            _embedding_model = SentenceTransformer(model_name, cache_folder=model_dir, local_files_only=True)
            logger.info("本地 embedding 模型从缓存加载完成")
        except Exception:
            logger.info("缓存未命中，从网络下载: %s", model_name)
            _embedding_model = SentenceTransformer(model_name, cache_folder=model_dir)
        _embed_pool = ThreadPoolExecutor(max_workers=1)
        logger.info("本地 embedding 模型加载完成, dim=%d", _embedding_model.get_sentence_embedding_dimension())
    return _embedding_model


def _get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        if settings.MILVUS_LITE_DB:
            _milvus_client = MilvusClient(uri=settings.MILVUS_LITE_DB)
        else:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            _milvus_client = MilvusClient(uri=uri)
    return _milvus_client


def _ensure_collection() -> MilvusClient:
    client = _get_milvus_client()
    if not client.has_collection(settings.MILVUS_COLLECTION):
        client.create_collection(
            collection_name=settings.MILVUS_COLLECTION,
            dimension=settings.EMBEDDING_DIM,
            metric_type="COSINE",
            auto_id=True,
            enable_dynamic_field=True,
        )
        client.create_index(
            collection_name=settings.MILVUS_COLLECTION,
            field_name="vector",
            index_params={
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200},
            },
        )
    client.load_collection(settings.MILVUS_COLLECTION)
    return client


def _clean_text(text: str) -> str:
    """清理文本：去控制字符、截断超长"""
    t = text.strip()
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
    if len(t) > 8000:
        t = t[:8000]
    return t


async def embed_texts_local(texts: list[str]) -> list[list[float]]:
    """本地 sentence-transformers 推理，分批处理避免 OOM"""
    model = _get_or_load_model()
    pool = _embed_pool
    loop = asyncio.get_running_loop()

    all_embeddings: list[list[float]] = []
    total = len(texts)
    for i in range(0, total, LOCAL_BATCH_SIZE):
        batch = texts[i:i + LOCAL_BATCH_SIZE]
        logger.info("embed_texts_local batch %d/%d: %d texts", i // LOCAL_BATCH_SIZE + 1, (total + LOCAL_BATCH_SIZE - 1) // LOCAL_BATCH_SIZE, len(batch))
        embeddings = await loop.run_in_executor(
            pool,
            lambda b=batch: model.encode(b, normalize_embeddings=True).tolist(),
        )
        all_embeddings.extend(embeddings)
    return all_embeddings


async def embed_texts_remote(texts: list[str]) -> list[list[float]]:
    """远程 SiliconFlow API 调用"""
    cleaned = [_clean_text(t) for t in texts]
    cleaned = [t for t in cleaned if t]

    if not cleaned:
        logger.warning("embed_texts: 所有文本为空，跳过")
        return []

    url = f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info(
        "embed_texts remote: url=%s, model=%s, total=%d, batch_size=%d",
        url, settings.EMBEDDING_MODEL, len(cleaned), EMBED_BATCH_SIZE,
    )

    all_embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        for i in range(0, len(cleaned), EMBED_BATCH_SIZE):
            batch = cleaned[i:i + EMBED_BATCH_SIZE]
            body = {
                "model": settings.EMBEDDING_MODEL,
                "input": batch,
                "encoding_format": "float",
            }
            logger.info(
                "embed_texts batch %d/%d: %d texts",
                i // EMBED_BATCH_SIZE + 1,
                (len(cleaned) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE,
                len(batch),
            )

            for attempt in range(5):
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    logger.warning("embed_texts 429 rate limit, retry in %ds (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error("embed_texts API error: status=%d, body=%s", resp.status_code, resp.text[:500])
                    raise RuntimeError(f"Embedding API returned {resp.status_code}: {resp.text[:300]}")
                break

            data = resp.json()
            all_embeddings.extend([d["embedding"] for d in data["data"]])
            await asyncio.sleep(EMBED_BATCH_INTERVAL)

    return all_embeddings


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.EMBEDDING_LOCAL:
        return await embed_texts_local(texts)
    return await embed_texts_remote(texts)


# Milvus 插入批次（避免 gRPC 消息超过 64MB 限制）
MILVUS_INSERT_BATCH = 100


def _truncate_utf8(text: str, max_bytes: int = 60000) -> str:
    """按 UTF-8 字节安全截断。Milvus 动态字段上限 65536 字节，
    中文每字 3 字节，按字符截断（如 text[:65000]）实际可达 ~195KB 会超限"""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


async def insert_vectors(unit_id: str, unit_code: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        return
    _ensure_collection()
    client = _get_milvus_client()
    total = len(chunks)
    for i in range(0, total, MILVUS_INSERT_BATCH):
        batch_chunks = chunks[i:i + MILVUS_INSERT_BATCH]
        batch_embeddings = embeddings[i:i + MILVUS_INSERT_BATCH]
        data = [
            {
                "unit_id": unit_id,
                "unit_code": unit_code,
                "chunk_index": c.index,
                "chunk_text": _truncate_utf8(c.text),
                "vector": np.array(e, dtype=np.float32),
            }
            for c, e in zip(batch_chunks, batch_embeddings)
        ]
        logger.info("insert_vectors batch %d/%d: %d rows", i // MILVUS_INSERT_BATCH + 1, (total + MILVUS_INSERT_BATCH - 1) // MILVUS_INSERT_BATCH, len(data))
        client.insert(collection_name=settings.MILVUS_COLLECTION, data=data)


def get_existing_chunk_indexes(unit_id: str) -> set[int]:
    """查询该单元已写入 Milvus 的 chunk 序号（断点续跑依据）"""
    try:
        client = _ensure_collection()
        res = client.query(
            collection_name=settings.MILVUS_COLLECTION,
            filter=f'unit_id == "{unit_id}"',
            output_fields=["chunk_index"],
        )
        return {int(r["chunk_index"]) for r in res}
    except Exception as e:
        logger.warning("get_existing_chunk_indexes failed: %s", e)
        return set()


async def delete_vectors(unit_id: str) -> None:
    _ensure_collection()
    client = _get_milvus_client()
    client.delete(collection_name=settings.MILVUS_COLLECTION, filter=f'unit_id == "{unit_id}"')


async def search_vectors(
    query_embedding: list[float],
    limit: int = 30,
    threshold: float = 0.5,
) -> list[dict]:
    _ensure_collection()
    client = _get_milvus_client()
    results = client.search(
        collection_name=settings.MILVUS_COLLECTION,
        data=[query_embedding],
        limit=limit,
        output_fields=["unit_id", "unit_code", "chunk_index", "chunk_text"],
    )
    if not results or not results[0]:
        return []
    return [
        {
            "unit_id": hit["entity"]["unit_id"],
            "unit_code": hit["entity"]["unit_code"],
            "chunk_index": hit["entity"]["chunk_index"],
            "chunk_text": hit["entity"]["chunk_text"],
            "score": float(hit["distance"]),
        }
        for hit in results[0]
        if hit["distance"] >= threshold
    ]


async def vectorize_and_insert(unit_id: str, unit_code: str, chunks: list[Chunk]) -> None:
    if not chunks:
        return
    valid: list[tuple[Chunk, str]] = [(c, c.text.strip()) for c in chunks if c.text.strip()]
    if not valid:
        return

    # 断点续跑：跳过已写入 Milvus 的 chunk，只补缺的部分
    existing = get_existing_chunk_indexes(unit_id)
    todo = [(c, t) for c, t in valid if c.index not in existing]
    if existing:
        logger.info(
            "vectorize resume: unit=%s total=%d already_done=%d todo=%d",
            unit_id, len(valid), len(valid) - len(todo), len(todo),
        )
    if not todo:
        logger.info("vectorize: unit=%s 所有 chunk 已入库，跳过", unit_id)
        return

    todo_chunks = [c for c, _ in todo]
    todo_texts = [t for _, t in todo]
    logger.info("vectorize: %d chunks, local=%s", len(todo_texts), settings.EMBEDDING_LOCAL)
    embeddings = await embed_texts(todo_texts)
    if not embeddings:
        return
    await insert_vectors(unit_id, unit_code, todo_chunks, embeddings)
