"""AI exceptions."""

from __future__ import annotations


class AIError(Exception):
    """Base AI error."""


class AIProviderError(AIError):
    """Provider call failed."""


class AIAuthenticationError(AIError):
    """Authentication failed."""


class AIRateLimitError(AIProviderError):
    """Rate limited."""


class AINotAvailableError(AIError):
    """Provider not available."""
