"""Shared fixtures and safety guards for the test suite."""

from __future__ import annotations

import socket

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.knowledge_unit import Base
import app.models  # noqa: F401  # 注册全部模型，确保 Base.metadata.create_all 覆盖所有表
from tests.fakes import FakeEmbedding, FakeLLM, FakeMilvus, FakeMinIO, FakeRerank


class UnexpectedNetworkCall(RuntimeError):
    """Raised when a test without external_api permission opens a socket."""


@pytest.fixture(autouse=True)
def block_external_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Deny real network access unless a test explicitly opts in."""
    if request.node.get_closest_marker("external_api"):
        yield
        return

    original_create_connection = socket.create_connection
    original_socket_connect = socket.socket.connect

    def is_loopback(address) -> bool:
        if isinstance(address, tuple) and address:
            return address[0] in {"127.0.0.1", "::1", "localhost"}
        return False

    def blocked_create_connection(address, *args, **kwargs):
        if is_loopback(address):
            return original_create_connection(address, *args, **kwargs)
        raise UnexpectedNetworkCall(
            "Real network access is disabled in tests. Use a Fake provider or mark the test external_api."
        )

    def blocked_socket_connect(sock, address):
        if is_loopback(address):
            return original_socket_connect(sock, address)
        raise UnexpectedNetworkCall(
            "Real network access is disabled in tests. Use a Fake provider or mark the test external_api."
        )

    monkeypatch.setattr(socket, "create_connection", blocked_create_connection)
    monkeypatch.setattr(socket.socket, "connect", blocked_socket_connect)
    yield


@pytest.fixture
def fake_embedding() -> FakeEmbedding:
    return FakeEmbedding()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_rerank() -> FakeRerank:
    return FakeRerank()


@pytest.fixture
def fake_minio() -> FakeMinIO:
    return FakeMinIO()


@pytest.fixture
def fake_milvus() -> FakeMilvus:
    return FakeMilvus()


@pytest_asyncio.fixture(scope="session")
async def test_engine(tmp_path_factory):
    """Create one lightweight database for the test session."""
    database_path = tmp_path_factory.mktemp("database") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Run each test inside an outer transaction that is always rolled back.

    ``join_transaction_mode=rollback_only`` allows application services to
    call ``commit()`` without propagating it to the outer test transaction.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="rollback_only",
        )
        async with factory() as session:
            yield session
        await transaction.rollback()
