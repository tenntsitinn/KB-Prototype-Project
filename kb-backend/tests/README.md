# Backend tests

The test suite is split by execution cost and dependency boundary.

## Setup

Install application and test dependencies in the backend virtual environment:

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

No API key, Docker service, GPU, MinIO, Milvus, or external model is required for the default suite. Tests reject non-loopback network connections unless they are explicitly marked `external_api`.

## Test layers

- `tests/unit`: fast isolated tests for parsers, services, authentication, permissions, and Fake providers.
- `tests/integration`: temporary SQLite-backed business tests and import/RAG pipeline tests using Fake external services.
- `tests/e2e`: reserved for full deployed-system workflows.
- `tests/fakes`: reusable Embedding, LLM, Rerank, MinIO, and Milvus substitutes.
- `tests/fixtures/documents`: versioned sample documents used by parsers.

## Commands

```powershell
# Unit tests only
.\\.venv\\Scripts\\python.exe -m pytest tests/unit -q

# Integration tests only
.\\.venv\\Scripts\\python.exe -m pytest tests/integration -q

# Default complete offline suite
.\\.venv\\Scripts\\python.exe -m pytest -q

# One test layer with verbose output
.\\.venv\\Scripts\\python.exe -m pytest tests/integration -v
```

## Markers

- `integration`: spans multiple application layers or a local test database.
- `e2e`: exercises a deployed application workflow.
- `ocr`: requires OCR runtime dependencies or models.
- `gpu`: requires a supported GPU runtime.
- `external_api`: permits real network access and may incur cost.

Run opt-in tests explicitly, for example:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -m external_api
```

Never add `external_api` to ordinary unit or integration tests. Prefer fixtures from `tests/fakes`.

## Database isolation

The `db_session` fixture uses a temporary SQLite database. Every test runs in an outer connection transaction with `rollback_only` join mode. Application services may call `commit()`, but the fixture rolls back the outer transaction at teardown, so rows cannot leak into another test.

