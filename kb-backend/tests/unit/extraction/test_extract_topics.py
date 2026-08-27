"""知识点提取 extract 节点测试：LLM 输出解析与窗口累加器。"""
import pytest

from app.nodes.extraction.extract_topics import (
    _parse_json_array,
    node_extract_topics,
    route_after_extract,
)
from tests.fakes import FakeLLM


pytestmark = pytest.mark.integration


def test_parse_json_array_plain():
    assert _parse_json_array('[{"topic": "a", "description": "b"}]') == [
        {"topic": "a", "description": "b"}
    ]


def test_parse_json_array_strips_code_fence():
    raw = '```json\n[{"topic": "a", "description": "b"}]\n```'
    assert len(_parse_json_array(raw)) == 1


def test_parse_json_array_recovers_invalid_escape():
    # LaTeX 风格孤立反斜杠，首次 json.loads 失败后应转义重试成功
    raw = r'[{"topic": "alpha", "description": "\alpha 波"}]'
    assert _parse_json_array(raw) == [{"topic": "alpha", "description": r"\alpha 波"}]


def test_parse_json_array_garbage_returns_empty():
    assert _parse_json_array("no json here at all") == []
    assert _parse_json_array("```json\nbroken\n```") == []


@pytest.mark.asyncio
async def test_node_accumulates_same_topic_across_chunks(monkeypatch):
    fake_llm = FakeLLM(responses=[
        '[{"topic": "Lang Graph", "description": "第一段"}]',
        '[{"topic": "Lang  Graph", "description": "第二段"}, {"topic": "RAG", "description": "检索"}]',
    ])
    monkeypatch.setattr(
        "app.nodes.extraction.extract_topics._get_llm_client", lambda api_key, base_url: fake_llm
    )

    state = {
        "chunks": [
            {"chunk_index": 0, "chunk_text": "c0"},
            {"chunk_index": 1, "chunk_text": "c1"},
        ],
        "cursor": 0,
        "since_flush": 0,
        "topic_acc": {},
        "api_key": "k", "base_url": "u", "model": "m",
    }

    state.update(await node_extract_topics(state))
    state.update(await node_extract_topics(state))

    # "Lang Graph" 与 "Lang  Graph" 空白归一化后同名，delta 拼接，chunk_indices 累积
    acc = state["topic_acc"]
    assert set(acc.keys()) == {"Lang Graph", "RAG"}
    assert acc["Lang Graph"]["raw_delta"] == "第一段\n\n第二段"
    assert acc["Lang Graph"]["chunk_indices"] == [0, 1]
    assert state["cursor"] == 2
    assert state["since_flush"] == 2
    assert len(fake_llm.calls) == 2


@pytest.mark.asyncio
async def test_node_filters_invalid_items(monkeypatch):
    fake_llm = FakeLLM(default_response='[{"topic": "", "description": "x"}, {"topic": "ok", "description": "y"}, "junk", {"topic": "no-desc"}]')
    monkeypatch.setattr(
        "app.nodes.extraction.extract_topics._get_llm_client", lambda api_key, base_url: fake_llm
    )

    state = {"chunks": [{"chunk_index": 0, "chunk_text": "c0"}], "cursor": 0, "since_flush": 0,
             "topic_acc": {}, "api_key": "k", "base_url": "u", "model": "m"}

    state.update(await node_extract_topics(state))

    assert list(state["topic_acc"].keys()) == ["ok"]


def test_route_loops_until_interval_or_end(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "POINT_REWRITE_INTERVAL", 3)

    assert route_after_extract({"cursor": 1, "chunks": [0, 0, 0], "since_flush": 1}) == "loop"
    # 到达 flush 间隔
    assert route_after_extract({"cursor": 1, "chunks": [0, 0, 0], "since_flush": 3}) == "flush"
    # chunk 处理完
    assert route_after_extract({"cursor": 3, "chunks": [0, 0, 0], "since_flush": 1}) == "flush"
