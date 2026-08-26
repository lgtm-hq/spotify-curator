"""Tests for application settings validation."""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_SIGNING_VALUE = "x" * 32


def _build_settings(**values: object) -> Settings:
    """Build settings with the repository env file disabled."""
    settings_type: Any = Settings
    return cast(Settings, settings_type(_env_file=None, **values))


def test_settings_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject startup when SECRET_KEY is missing."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="secret_key"):
        _build_settings()


def test_settings_rejects_placeholder_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject the documented placeholder secret key."""
    monkeypatch.setenv("SECRET_KEY", "change-me-to-a-random-string")

    with pytest.raises(ValidationError, match="deployment-specific"):
        _build_settings()


def test_settings_accepts_explicit_secret_key() -> None:
    """Accept a deployment-provided session signing key."""
    settings = _build_settings(secret_key=VALID_SIGNING_VALUE)

    assert settings.secret_key == VALID_SIGNING_VALUE
