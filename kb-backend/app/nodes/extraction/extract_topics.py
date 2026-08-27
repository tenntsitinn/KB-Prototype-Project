"""提取节点：LLM 从当前 chunk 提取 topic（一对多），聚合进窗口累加器"""
import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings
from app.graphs.point_extraction_graph import PointExtractionState
from app.prompts.point_prompts import POINT_EXTRACT_PROMPT

logger = logging.getLogger(__name__)

_llm_clients: dict[str, AsyncOpenAI] = {}


def _get_llm_client(api_key: str, base_url: str) -> AsyncOpenAI:
    cache_key = f"{base_url}::{api_key}"
    if cache_key not in _llm_clients:
        _llm_clients[cache_key] = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _llm_clients[cache_key]


_INVALID_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')


def _parse_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return []
    body = raw[start:end + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        # LLM 偶发输出非法转义（如 LaTeX \alpha、Windows 路径），转义孤立反斜杠后重试
        sanitized = _INVALID_ESCAPE_RE.sub(r"\\\\", body)
        try:
            data = json.loads(sanitized)
        except json.JSONDecodeError:
            logger.warning("chunk 提取结果 JSON 解析失败，跳过该片段: %s", body[:120])
            return []
    return data if isinstance(data, list) else []


class InsufficientBalanceError(Exception):
    pass


async def extract_topics_from_chunk(chunk_text: str, api_key: str, base_url: str, model: str) -> list[dict]:
    """LLM 提取单个 chunk 的知识点，返回 [{topic, description}]"""
    client = _get_llm_client(api_key, base_url)
    prompt = POINT_EXTRACT_PROMPT.format(chunk_text=chunk_text)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048,
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        if "402" in str(e) or "Insufficient Balance" in str(e):
            raise InsufficientBalanceError(str(e))
        logger.warning("知识点提取 LLM 调用失败: %s", e)
        return []

    topics: list[dict] = []
    for item in _parse_json_array(raw):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()[:256]
        desc = str(item.get("description", "")).strip()
        if topic and desc:
            topics.append({"topic": topic, "description": desc})
    return topics


def _normalize_topic(topic: str) -> str:
    return " ".join(topic.split())


async def node_extract_topics(state: PointExtractionState) -> dict:
    chunks = state["chunks"]
    cursor = state["cursor"]
    chunk = chunks[cursor]

    extractions = await extract_topics_from_chunk(
        chunk["chunk_text"],
        state["api_key"], state["base_url"], state["model"],
    )

    # 聚合进窗口累加器：同一 topic 的多段 delta 先在组内拼接
    acc = dict(state.get("topic_acc") or {})
    for ext in extractions:
        key = _normalize_topic(ext["topic"])
        if not key:
            continue
        if key in acc:
            acc[key]["raw_delta"] += "\n\n" + ext["description"]
            acc[key]["chunk_indices"].append(chunk["chunk_index"])
        else:
            acc[key] = {
                "topic": key,
                "raw_delta": ext["description"],
                "chunk_indices": [chunk["chunk_index"]],
            }

    return {
        "topic_acc": acc,
        "cursor": cursor + 1,
        "since_flush": state.get("since_flush", 0) + 1,
        "stage": "extract",
    }


def route_after_extract(state: PointExtractionState) -> str:
    has_more = state["cursor"] < len(state["chunks"])
    interval_reached = state.get("since_flush", 0) >= settings.POINT_REWRITE_INTERVAL
    if has_more and not interval_reached:
        return "loop"
    return "flush"
