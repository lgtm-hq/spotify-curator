"""Transport-aware AI setup checks."""

from __future__ import annotations

import os
import shutil

from app.ai.config import AIConfig
from app.ai.enums import AITransport


def run_doctor(ai_config: AIConfig) -> list[dict[str, str]]:
    """Run AI doctor checks and return status messages."""
    checks: list[dict[str, str]] = []
    if not ai_config.enabled:
        checks.append({"level": "info", "message": "AI is disabled"})
        return checks

    if ai_config.transport is None:
        checks.append({"level": "error", "message": "ai.transport is required when enabled"})
        return checks

    if ai_config.transport == AITransport.CLI:
        binary_map = {
            "anthropic": "claude",
            "openai": "codex",
            "cursor": "agent",
        }
        binary = binary_map.get(ai_config.provider.value)
        if binary and not shutil.which(binary):
            checks.append({"level": "error", "message": f"{binary} CLI not found on PATH"})
        else:
            checks.append({"level": "ok", "message": f"{binary} CLI found"})
    else:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_var = env_map.get(ai_config.provider.value)
        if env_var and not os.environ.get(env_var):
            checks.append({"level": "error", "message": f"Set {env_var} for API transport"})
        elif env_var:
            checks.append({"level": "ok", "message": f"{env_var} is set"})

    checks.append({"level": "info", "message": f"Provider: {ai_config.provider}, transport: {ai_config.transport}"})
    return checks
