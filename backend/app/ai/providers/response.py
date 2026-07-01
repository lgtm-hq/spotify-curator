"""AI provider response types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AIResponse:
    """Response from an AI provider."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    provider: str = ""
