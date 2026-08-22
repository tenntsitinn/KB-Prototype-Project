import socket

import pytest

from tests.conftest import UnexpectedNetworkCall


@pytest.mark.asyncio
async def test_fake_embedding_is_stable(fake_embedding):
    first = await fake_embedding.embed_texts(["same text", "other text"])
    second = await fake_embedding.embed_texts(["same text"])

    assert first[0] == second[0]
    assert first[0] != first[1]
    assert len(first[0]) == fake_embedding.dimension


@pytest.mark.asyncio
async def test_fake_llm_matches_async_openai_shape(fake_llm):
    fake_llm.responses.append("rewritten question")
    response = await fake_llm.chat.completions.create(model="fake", messages=[])

    assert response.choices[0].message.content == "rewritten question"
    assert fake_llm.calls[0]["model"] == "fake"


@pytest.mark.asyncio
async def test_fake_rerank_orders_by_overlap(fake_rerank):
    results = await fake_rerank.rerank("annual leave", ["unrelated", "annual leave policy"], top_n=2)

    assert results[0]["index"] == 1
    assert results[0]["relevance_score"] > results[1]["relevance_score"]


def test_fake_minio_round_trip(fake_minio, tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    source.write_text("content", encoding="utf-8")

    fake_minio.make_bucket("docs")
    fake_minio.fput_object("docs", "unit/source.txt", str(source))
    fake_minio.fget_object("docs", "unit/source.txt", str(target))

    assert target.read_text(encoding="utf-8") == "content"
    assert [item.object_name for item in fake_minio.list_objects("docs", "unit/")] == ["unit/source.txt"]


def test_fake_milvus_insert_search_delete(fake_milvus):
    fake_milvus.create_collection("knowledge")
    fake_milvus.insert(
        "knowledge",
        [
            {"unit_id": "u1", "chunk_text": "first", "vector": [1.0, 0.0]},
            {"unit_id": "u2", "chunk_text": "second", "vector": [0.0, 1.0]},
        ],
    )

    hits = fake_milvus.search("knowledge", [[1.0, 0.0]], limit=1, output_fields=["unit_id", "chunk_text"])
    assert hits[0][0]["entity"]["unit_id"] == "u1"

    fake_milvus.delete("knowledge", 'unit_id == "u1"')
    assert len(fake_milvus.collections["knowledge"]) == 1


def test_real_network_is_blocked_by_default():
    with pytest.raises(UnexpectedNetworkCall, match="Real network access is disabled"):
        socket.create_connection(("example.com", 80))
