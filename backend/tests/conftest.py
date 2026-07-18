"""Shared backend test configuration."""

from __future__ import annotations

import os

os.environ.setdefault(
    "SECRET_KEY",
    "x" * 32,
)
