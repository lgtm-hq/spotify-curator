"""Unified AI invocation."""

from __future__ import annotations

from app.ai.budget import CostBudget
from app.ai.fallback import complete_with_fallback
from app.ai.json_response import CliSchemaRequest
from app.ai.providers.response import AIResponse
from app.ai.retry import with_retry


def call_ai(
    *,
    provider,
    ai_config,
    user_prompt: str,
    system_prompt: str | None,
    budget: CostBudget | None,
    max_tokens: int | None = None,
    repo_root: str | None = None,
    use_one_shot: bool = False,
    cli_schema: CliSchemaRequest | None = None,
) -> AIResponse:
    """Retry, fallback, and budget tracking for all AI products."""
    tokens = max_tokens if max_tokens is not None else ai_config.max_tokens

    @with_retry(
        max_retries=ai_config.max_retries,
        base_delay=ai_config.retry_base_delay,
        max_delay=ai_config.retry_max_delay,
        backoff_factor=ai_config.retry_backoff_factor,
    )
    def _call() -> AIResponse:
        return complete_with_fallback(
            provider,
            user_prompt,
            fallback_models=list(ai_config.fallback_models),
            system=system_prompt,
            max_tokens=tokens,
            timeout=ai_config.api_timeout,
            repo_root=repo_root,
            use_one_shot=use_one_shot,
            cli_schema=cli_schema,
        )

    if budget is not None:
        budget.check()
    response = _call()
    if budget is not None:
        budget.record(response.cost_estimate)
        budget.check()
    return response
