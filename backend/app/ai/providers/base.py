"""Base AI provider."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from app.ai.enums import AITransport
from app.ai.exceptions import AIAuthenticationError, AINotAvailableError
from app.ai.json_response import CliSchemaRequest
from app.ai.providers.response import AIResponse


class BaseAIProvider(ABC):
    """Abstract AI provider."""

    def __init__(
        self,
        *,
        provider_name: str,
        default_model: str,
        default_api_key_env: str,
        model: str | None = None,
        api_key_env: str | None = None,
        max_tokens: int = 4096,
        transport: AITransport | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._model = model or default_model
        self._api_key_env = api_key_env or default_api_key_env
        self._max_tokens = max_tokens
        self._transport = transport
        self._client = None

    @property
    def name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model

    @model_name.setter
    def model_name(self, value: str) -> None:
        self._model = value

    def is_available(self) -> bool:
        """Check if provider is ready."""
        return bool(os.environ.get(self._api_key_env) or self._client)

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        repo_root: str | None = None,
        use_one_shot: bool = False,
        cli_schema: CliSchemaRequest | None = None,
    ) -> AIResponse:
        """Generate completion."""
        ...
