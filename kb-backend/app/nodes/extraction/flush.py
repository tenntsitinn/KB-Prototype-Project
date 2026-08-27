"""flush 节点：窗口聚合的 topic 批量执行「向量匹配 → 分层决策 → LLM 重写 → 落库」

决策规则（topic 与已有知识点 title 的向量相似度）:
  score >  TOPIC_MATCH_THRESHOLD      自动合并：重写融合进已有知识点
  TOPIC_CANDIDATE_THRESHOLD < score   新建并记录合并候选（candidate_merge_json），人工审核
  score <= TOPIC_CANDIDATE_THRESHOLD  直接新建
所有落库结果 status='pending_review'。
"""
import json
import logging
import re

from openai import AsyncOpenAI
from sqlalchemy import select, update as sqla_update

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.graphs.point_extraction_graph import PointExtractionState
from app.models.education import KnowledgePoint
from app.models.knowledge_unit import KnowledgeUnit
from app.prompts.point_prompts import POINT_REWRITE_PROMPT
from app.services.topic_store import insert_topic_vectors, search_topic
from app.services.vectorizer import embed_texts

logger = logging.getLogger(__name__)

_llm_clients: dict[str, AsyncOpenAI] = {}

_INVALID_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')


class InsufficientBalanceError(Exception):
    pass


def _get_llm_client(api_key: str, base_url: str) -> AsyncOpenAI:
    cache_key = f"{base_url}::{api_key}"
    if cache_key not in _llm_clients:
        _llm_clients[cache_key] = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _llm_clients[cache_key]


def _parse_json_obj(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {}
    body = raw[start:end + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        sanitized = _INVALID_ESCAPE_RE.sub(r"\\\\", body)
        try:
            data = json.loads(sanitized)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


async def rewrite_point_content(topic: str, old_content: str, delta: str, api_key: str, base_url: str, model: str) -> str:
    """LLM 融合重写知识点内容；失败时回退为原文拼接"""
    prompt = POINT_REWRITE_PROMPT.format(
        topic=topic, old_content=old_content or "（无）", delta=delta,
    )
    try:
        client = _get_llm_client(api_key, base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = _parse_json_obj(raw)
        content = str(data.get("content", "")).strip()
        if content:
            return content
    except Exception as e:
        if "402" in str(e) or "Insufficient Balance" in str(e):
            raise InsufficientBalanceError(str(e))
        logger.warning("知识点重写 LLM 调用失败，回退原文拼接: %s", e)
    return "\n\n".join(x for x in (old_content.strip(), delta.strip()) if x)


def _merge_source_refs(existing_json: str, unit_id: str, chunk_indices: list[int]) -> str:
    refs = json.loads(existing_json) if existing_json else []
    if not isinstance(refs, list):
        refs = []
    for ref in refs:
        if isinstance(ref, dict) and ref.get("unit_id") == unit_id:
            merged = set(ref.get("chunk_indices", [])) | set(chunk_indices)
            ref["chunk_indices"] = sorted(merged)
            return json.dumps(refs, ensure_ascii=False)
    refs.append({"unit_id": unit_id, "chunk_indices": sorted(set(chunk_indices))})
    return json.dumps(refs, ensure_ascii=False)


async def node_flush(state: PointExtractionState) -> dict:
    unit_id = state["unit_id"]
    acc = state.get("topic_acc") or {}
    stats = dict(state.get("stats") or {})

    entries = [e for e in acc.values() if e["raw_delta"].strip()]
    if not entries:
        return {"topic_acc": {}, "since_flush": 0, "stage": "flush"}

    # 批量向量化所有 topic（一次 embed 调用，避免逐个触发限速间隔）
    topics = [e["topic"] for e in entries]
    embeddings = await embed_texts(topics)
    if not embeddings:
        logger.warning("flush: topic 向量化为空，跳过本窗口 %d 个 topic", len(entries))
        return {"topic_acc": {}, "since_flush": 0, "stage": "flush"}

    async with AsyncSessionLocal() as db:
        # 决策需要排除 rejected 的知识点
        matches_by_topic: dict[str, list[dict]] = {}
        point_ids_needed: set[str] = set()
        for entry, emb in zip(entries, embeddings):
            matches = await search_topic(emb, limit=5)
            matches_by_topic[entry["topic"]] = matches
            point_ids_needed.update(m["point_id"] for m in matches)

        point_status: dict[str, str] = {}
        if point_ids_needed:
            result = await db.execute(
                select(KnowledgePoint.id, KnowledgePoint.status).where(KnowledgePoint.id.in_(point_ids_needed))
            )
            point_status = {r[0]: r[1] for r in result.all()}

        # 只保留可参与决策的匹配（rejected 已拒绝；delete_pending 删除待处理，均不可作为合并目标）
        for topic, matches in matches_by_topic.items():
            matches_by_topic[topic] = [
                m for m in matches
                if point_status.get(m["point_id"]) not in ("rejected", "delete_pending")
            ]

        unit = await db.get(KnowledgeUnit, unit_id)
        chapter_id = unit.chapter_id if unit else None

        new_vectors: list[dict] = []

        for entry, emb in zip(entries, embeddings):
            topic = entry["topic"]
            delta = entry["raw_delta"]
            matches = matches_by_topic.get(topic, [])
            best = matches[0] if matches else None
            best_score = best["score"] if best else 0.0

            if best and best_score > settings.TOPIC_MATCH_THRESHOLD:
                # 自动合并：重写融合进已有知识点
                existing = await db.get(KnowledgePoint, best["point_id"])
                old_content = (existing.content or existing.summary or "") if existing else ""
                new_content = await rewrite_point_content(
                    topic, old_content, delta,
                    state["api_key"], state["base_url"], state["model"],
                )
                if existing:
                    await db.execute(
                        sqla_update(KnowledgePoint).where(KnowledgePoint.id == existing.id).values(
                            content=new_content,
                            summary=new_content[:200],
                            status="pending_review",
                            source_refs_json=_merge_source_refs(
                                existing.source_refs_json, unit_id, entry["chunk_indices"]
                            ),
                        )
                    )
                    stats["auto_merged"] = stats.get("auto_merged", 0) + 1
                    logger.info("自动合并: topic=%s -> point=%s score=%.3f", topic, existing.id, best_score)

            elif best and best_score > settings.TOPIC_CANDIDATE_THRESHOLD:
                # 新建 + 记录合并候选，人工审核决定是否并入
                new_content = await rewrite_point_content(
                    topic, "", delta,
                    state["api_key"], state["base_url"], state["model"],
                )
                candidates = [
                    {"point_id": m["point_id"], "title": m["title"], "score": round(m["score"], 3)}
                    for m in matches[:2]
                ]
                point = KnowledgePoint(
                    unit_id=unit_id,
                    title=topic,
                    summary=new_content[:200],
                    content=new_content,
                    point_type="concept",
                    source_refs_json=_merge_source_refs("[]", unit_id, entry["chunk_indices"]),
                    candidate_merge_json=json.dumps(candidates, ensure_ascii=False),
                    status="pending_review",
                )
                db.add(point)
                await db.flush()
                new_vectors.append({
                    "point_id": point.id, "title": topic, "unit_id": unit_id,
                    "chapter_id": chapter_id, "embedding": emb,
                })
                stats["candidates"] = stats.get("candidates", 0) + 1
                logger.info("新建候选: topic=%s best_score=%.3f candidates=%s", topic, best_score, [c["title"] for c in candidates])

            else:
                # 全新知识点
                new_content = await rewrite_point_content(
                    topic, "", delta,
                    state["api_key"], state["base_url"], state["model"],
                )
                point = KnowledgePoint(
                    unit_id=unit_id,
                    title=topic,
                    summary=new_content[:200],
                    content=new_content,
                    point_type="concept",
                    source_refs_json=_merge_source_refs("[]", unit_id, entry["chunk_indices"]),
                    status="pending_review",
                )
                db.add(point)
                await db.flush()
                new_vectors.append({
                    "point_id": point.id, "title": topic, "unit_id": unit_id,
                    "chapter_id": chapter_id, "embedding": emb,
                })
                stats["created"] = stats.get("created", 0) + 1
                logger.info("新建知识点: topic=%s", topic)

        await db.commit()

    if new_vectors:
        await insert_topic_vectors(new_vectors)

    logger.info(
        "flush 完成: unit=%s topics=%d (自动合并=%d 候选=%d 新建=%d)",
        unit_id, len(entries), stats.get("auto_merged", 0), stats.get("candidates", 0), stats.get("created", 0),
    )
    return {"topic_acc": {}, "since_flush": 0, "stats": stats, "stage": "flush"}


def route_after_flush(state: PointExtractionState) -> str:
    if state["cursor"] < len(state["chunks"]):
        return "loop"
    return "finalize"
