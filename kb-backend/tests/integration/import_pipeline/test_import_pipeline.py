import pytest

from app.models.knowledge_unit import KnowledgeUnit
from app.nodes.importer.chunk import node_chunk
from app.nodes.importer.parse_all import node_parse_all
from app.nodes.importer.validate import node_validate, route_after_validate
from app.nodes.importer.vectorize import node_vectorize
from app.services.importer.file_validator import check_duplicate, compute_md5
from app.tasks.import_task import _async_process_document


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_document_validation_parse_chunk_and_fake_vectorize(tmp_path, monkeypatch, fake_embedding, fake_milvus):
    document = tmp_path / "policy.md"
    document.write_text(
        "# Annual Leave\n\nEmployees receive annual leave based on service years.\n\n"
        "## Application\n\nSubmit the request before taking leave.",
        encoding="utf-8",
    )
    state = {
        "file_path": str(document),
        "filename": document.name,
        "creator_id": "test-user",
        "use_unlimited_ocr": False,
        "unit_id": "unit-import",
        "unit_code": "KB-IMPORT",
    }

    state.update(node_validate(state))
    assert route_after_validate(state) == "direct"
    assert state["stage"] == "validated"

    state.update(node_parse_all(state))
    assert "Annual Leave" in state["merged_text"]
    assert state["stage"] == "parsed"

    state.update(node_chunk(state))
    assert state["chunk_count"] >= 1
    assert state["stage"] == "chunked"

    async def fake_vectorize_and_insert(unit_id, unit_code, chunks):
        embeddings = await fake_embedding.embed_texts([chunk.text for chunk in chunks])
        fake_milvus.create_collection("knowledge")
        fake_milvus.insert(
            "knowledge",
            [
                {
                    "unit_id": unit_id,
                    "unit_code": unit_code,
                    "chunk_index": chunk.index,
                    "chunk_text": chunk.text,
                    "vector": vector,
                }
                for chunk, vector in zip(chunks, embeddings)
            ],
        )

    monkeypatch.setattr("app.nodes.importer.vectorize.vectorize_and_insert", fake_vectorize_and_insert)
    state.update(await node_vectorize(state))

    assert state["stage"] == "vectorized"
    assert len(fake_embedding.calls) == 1
    assert len(fake_milvus.collections["knowledge"]) == state["chunk_count"]


@pytest.mark.asyncio
async def test_duplicate_upload_returns_existing_active_unit(tmp_path, db_session):
    document = tmp_path / "duplicate.txt"
    document.write_text("same document", encoding="utf-8")
    md5_hash = compute_md5(str(document))
    existing = KnowledgeUnit(
        id="existing-unit",
        unit_code="KB-EXISTING",
        title="Existing",
        file_md5=md5_hash,
        status="published",
    )
    db_session.add(existing)
    await db_session.commit()

    duplicate = await check_duplicate(db_session, md5_hash)

    assert duplicate is not None
    assert duplicate.id == existing.id


class RecordingTask:
    def __init__(self):
        self.updates = []

    def update_state(self, **kwargs):
        self.updates.append(kwargs)


@pytest.mark.asyncio
async def test_import_task_reports_validation_failure(tmp_path):
    unsupported = tmp_path / "malware.exe"
    unsupported.write_bytes(b"not a supported document")
    task = RecordingTask()

    result = await _async_process_document(task, str(unsupported), unsupported.name, "test-user")

    assert result["status"] == "failed"
    assert "不支持的文件格式" in result["error"]
    assert task.updates[-1]["state"] == "FAILURE"
    assert task.updates[-1]["meta"]["stage"] == "invalid"
