"""JSON response parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_JSON_FENCE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class CliSchemaRequest:
    """Native CLI schema request."""

    schema: dict[str, Any]
    schema_name: str | None = None


def strip_json_fences(*, content: str) -> str:
    """Strip markdown JSON fences."""
    stripped = content.strip()
    match = _JSON_FENCE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def load_json_object(*, content: str) -> dict[str, Any]:
    """Parse JSON object from model output."""
    text = strip_json_fences(content=content)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        msg = "JSON response must be an object"
        raise ValueError(msg)
    return payload
