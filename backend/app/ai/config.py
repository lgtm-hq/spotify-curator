"""AI configuration."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.ai.enums import AIProvider, AITransport


class AIConfig(BaseModel):
    """AI engine configuration."""

    enabled: bool = False
    provider: AIProvider = AIProvider.ANTHROPIC
    transport: AITransport | None = None
    model: str | None = "claude-sonnet-4-20250514"
    fallback_models: list[str] = Field(default_factory=list)
    max_tokens: int = Field(default=4096, ge=1)
    max_retries: int = Field(default=3, ge=0)
    api_timeout: float = Field(default=120.0, ge=1.0)
    max_cost_usd: float | None = Field(default=0.50)
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    retry_backoff_factor: float = 2.0

    @model_validator(mode="after")
    def validate_transport(self) -> AIConfig:
        """Validate transport rules."""
        if self.enabled and self.transport is None:
            msg = "ai.transport is required when ai.enabled is true"
            raise ValueError(msg)
        if self.provider == AIProvider.CURSOR and self.transport == AITransport.API:
            msg = "cursor provider only supports transport: cli"
            raise ValueError(msg)
        return self


def load_ai_config(path: Path | None = None) -> AIConfig:
    """Load AI config from YAML file."""
    config_path = path or Path("config.yaml")
    if not config_path.exists():
        return AIConfig()
    data = yaml.safe_load(config_path.read_text()) or {}
    ai_section = data.get("ai", {})
    return AIConfig.model_validate(ai_section)


def get_provider(
    ai_config: AIConfig,
):
    """Factory for AI provider instances."""
    from app.ai.providers.anthropic import AnthropicProvider
    from app.ai.providers.cursor import CursorProvider
    from app.ai.providers.openai import OpenAIProvider

    if ai_config.provider == AIProvider.ANTHROPIC:
        return AnthropicProvider(
            model=ai_config.model,
            transport=ai_config.transport,
            max_tokens=ai_config.max_tokens,
        )
    if ai_config.provider == AIProvider.OPENAI:
        return OpenAIProvider(
            model=ai_config.model,
            transport=ai_config.transport,
            max_tokens=ai_config.max_tokens,
        )
    if ai_config.provider == AIProvider.CURSOR:
        return CursorProvider(model=ai_config.model, max_tokens=ai_config.max_tokens)
    msg = f"Unknown provider: {ai_config.provider}"
    raise ValueError(msg)
