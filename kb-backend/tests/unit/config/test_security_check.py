"""Tests for production security validation in app.config."""

import pytest

from app.config import Settings, _check_production_security, _DEFAULT_JWT_SECRET, _DEFAULT_MINIO_KEY


def _make_settings(**overrides) -> Settings:
    base = {
        "APP_ENV": "production",
        "JWT_SECRET_KEY": "a-very-secure-production-secret-key-32+bytes",
        "MINIO_SECRET_KEY": "prod-minio-secret-not-default",
    }
    base.update(overrides)
    return Settings(**base)


class TestProductionSecurityCheck:
    def test_development_mode_skips_all_checks(self):
        s = Settings(APP_ENV="development")
        assert _check_production_security(s) == []

    def test_production_with_default_jwt_key_fails(self):
        s = _make_settings(JWT_SECRET_KEY=_DEFAULT_JWT_SECRET)
        failures = _check_production_security(s)
        assert any("JWT_SECRET_KEY is still the default" in f for f in failures)

    def test_production_with_short_jwt_key_fails(self):
        s = _make_settings(JWT_SECRET_KEY="short")
        failures = _check_production_security(s)
        assert any("at least 32 bytes" in f for f in failures)

    def test_production_with_default_minio_key_fails(self):
        s = _make_settings(MINIO_SECRET_KEY=_DEFAULT_MINIO_KEY)
        failures = _check_production_security(s)
        assert any("MINIO_SECRET_KEY is still the default" in f for f in failures)

    def test_production_with_all_secure_keys_passes(self):
        s = _make_settings()
        assert _check_production_security(s) == []
