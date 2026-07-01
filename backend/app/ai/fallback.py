"""Model fallback chain."""

from __future__ import annotations

import threading

from app.ai.exceptions import AIAuthenticationError, AIProviderError, AIRateLimitError
from app.ai.json_response import CliSchemaRequest
from app.ai.providers.base import BaseAIProvider
from app.ai.providers.response import AIResponse

_model_lock = threading.Lock()


def complete_with_fallback(
    provider: BaseAIProvider,
    prompt: str,
    *,
    fallback_models: list[str] | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
    timeout: float = 60.0,
    repo_root: str | None = None,
    use_one_shot: bool = False,
    cli_schema: CliSchemaRequest | None = None,
) -> AIResponse:
    """Call provider.complete with model fallback."""
    models = [None] + (fallback_models or [])
    last_error: Exception | None = None
    with _model_lock:
        original = provider.model_name
    try:
        for model in models:
            try:
                with _model_lock:
                    if model is not None:
                        provider.model_name = model
                    return provider.complete(
                        prompt,
                        system=system,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        repo_root=repo_root,
                        use_one_shot=use_one_shot,
                        cli_schema=cli_schema,
                    )
            except AIAuthenticationError:
                raise
            except (AIProviderError, AIRateLimitError) as exc:
                last_error = exc
    finally:
        with _model_lock:
            provider.model_name = original
    if isinstance(last_error, Exception):
        raise last_error
    raise AIProviderError("Fallback chain exhausted")
