"""AI transport enum."""

from __future__ import annotations

from enum import StrEnum


class AITransport(StrEnum):
    """How to invoke the AI provider."""

    API = "api"
    CLI = "cli"


class AIProvider(StrEnum):
    """Supported AI providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CURSOR = "cursor"
