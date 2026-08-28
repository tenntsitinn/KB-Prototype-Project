import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.system import (
    SystemLLMConfigRequest,
    get_system_llm_config,
    update_system_llm_config,
)
from app.config import settings
from app.core.llm_config import (
    resolve_system_llm_config,
    resolve_user_llm_config,
)
from app.core.security import decrypt_value, encrypt_value
from app.models.system_config import SystemConfig
from app.models.user import User


async def _add_superuser(db_session, username: str = "sys-admin") -> User:
    user = User(id=f"uid-{username}", username=username, password_hash="x", is_superuser=True)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_system_config_db_value_overrides_env(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "env-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://env.example.com")
    monkeypatch.setattr(settings, "LLM_MODEL", "env-model")

    db_session.add_all([
        SystemConfig(key="llm_api_key", value=encrypt_value("db-key-12345")),
        SystemConfig(key="llm_base_url", value="https://db.example.com"),
        SystemConfig(key="llm_model", value="db-model"),
    ])
    await db_session.commit()

    api_key, base_url, model = await resolve_system_llm_config(db_session)

    assert (api_key, base_url, model) == ("db-key-12345", "https://db.example.com", "db-model")


@pytest.mark.asyncio
async def test_system_config_falls_back_to_env_when_no_rows(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "env-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://env.example.com")
    monkeypatch.setattr(settings, "LLM_MODEL", "env-model")

    api_key, base_url, model = await resolve_system_llm_config(db_session)

    assert (api_key, base_url, model) == ("env-key", "https://env.example.com", "env-model")


@pytest.mark.asyncio
async def test_system_config_partial_rows_use_env_for_missing_fields(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "env-key")
    monkeypatch.setattr(settings, "LLM_MODEL", "env-model")
    db_session.add(SystemConfig(key="llm_api_key", value=encrypt_value("db-only-key")))
    await db_session.commit()

    api_key, base_url, model = await resolve_system_llm_config(db_session)

    assert api_key == "db-only-key"
    assert base_url == settings.LLM_BASE_URL
    assert model == "env-model"


@pytest.mark.asyncio
async def test_resolve_user_llm_config_superuser_uses_system_config(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    admin = await _add_superuser(db_session)
    db_session.add(SystemConfig(key="llm_api_key", value=encrypt_value("db-key-12345")))
    await db_session.commit()

    api_key, _, _ = await resolve_user_llm_config(db_session, admin)

    assert api_key == "db-key-12345"


@pytest.mark.asyncio
async def test_resolve_user_llm_config_byok_user_uses_own_key(db_session):
    user = User(
        id="uid-byok", username="byok", password_hash="x",
        llm_api_key=encrypt_value("sk-byok"), llm_base_url="https://byok.example.com",
        llm_model="byok-model",
    )
    db_session.add(user)
    await db_session.commit()

    api_key, base_url, model = await resolve_user_llm_config(db_session, user)

    assert (api_key, base_url, model) == ("sk-byok", "https://byok.example.com", "byok-model")


@pytest.mark.asyncio
async def test_resolve_user_llm_config_keyless_user_gets_403(db_session):
    user = User(id="uid-keyless", username="keyless", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_user_llm_config(db_session, user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_system_llm_config_reports_env_source(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "env-key")

    resp = await get_system_llm_config(db=db_session)

    assert resp.source == "env"
    assert resp.has_key is True
    assert resp.masked_key == "****"


@pytest.mark.asyncio
async def test_update_then_get_system_llm_config_roundtrip(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_MODEL", "")
    admin = await _add_superuser(db_session)

    resp = await update_system_llm_config(
        SystemLLMConfigRequest(
            api_key="sk-db-global-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        ),
        db=db_session,
        user=admin,
    )
    assert resp.source == "db"
    assert resp.has_key is True
    assert resp.masked_key == "sk-d****-key"
    assert resp.model == "deepseek-chat"

    fetched = await get_system_llm_config(db=db_session)
    assert fetched == resp

    # 密文入库，明文不出现在数据库行中
    row = await db_session.get(SystemConfig, "llm_api_key")
    assert row.value != "sk-db-global-key"
    assert decrypt_value(row.value) == "sk-db-global-key"
    assert row.updated_by == admin.id


@pytest.mark.asyncio
async def test_update_system_llm_config_clear_removes_rows(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    admin = await _add_superuser(db_session, "clear-admin")
    await update_system_llm_config(
        SystemLLMConfigRequest(api_key="sk-temp", base_url="https://api.deepseek.com", model="m"),
        db=db_session, user=admin,
    )

    resp = await update_system_llm_config(
        SystemLLMConfigRequest(api_key="", base_url="", model=""),
        db=db_session, user=admin,
    )

    assert resp.source == "none"
    assert resp.has_key is False
    assert resp.masked_key == ""
    rows = (await db_session.execute(select(SystemConfig))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_update_system_llm_config_requires_base_url(db_session):
    admin = await _add_superuser(db_session, "no-base-admin")

    with pytest.raises(HTTPException) as exc_info:
        await update_system_llm_config(
            SystemLLMConfigRequest(api_key="sk-x", base_url="", model=""),
            db=db_session, user=admin,
        )

    assert exc_info.value.status_code == 400
