"""Shared CLI subprocess transport."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any, cast

from app.ai.exceptions import (
    AIAuthenticationError,
    AINotAvailableError,
    AIProviderError,
)


class CliTransport(ABC):
    """Base subprocess runner for CLI-backed AI providers."""

    def __init__(
        self,
        *,
        binary_path: str,
        binary_name: str,
        install_hint: str,
        api_key_env: str | None = None,
    ) -> None:
        """Store CLI binary metadata for subprocess execution."""
        self._binary_path = binary_path
        self._binary_name = binary_name
        self._install_hint = install_hint
        self._api_key_env = api_key_env

    @staticmethod
    def find_binary(name: str) -> str | None:
        """Return path to binary on PATH."""
        return shutil.which(name)

    def run(
        self,
        cmd: list[str],
        *,
        input_text: str | None = None,
        timeout: float,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute CLI command."""
        env = os.environ.copy()
        if self._api_key_env and os.environ.get(self._api_key_env):
            env[self._api_key_env] = os.environ[self._api_key_env]
        try:
            return subprocess.run(  # nosec B603 - argv list from trusted provider wrappers, no shell
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired as exc:
            raise AIProviderError(
                f"{self._binary_name} CLI timed out after {timeout:.0f}s",
            ) from exc
        except FileNotFoundError as exc:
            raise AINotAvailableError(
                f"{self._binary_name} not found. {self._install_hint}",
            ) from exc

    def check_exit_code(
        self,
        result: subprocess.CompletedProcess[str],
        *,
        auth_patterns: tuple[str, ...] = ("authentication", "login", "unauthorized"),
        auth_hint: str = "",
    ) -> None:
        """Map non-zero exit codes to AI exceptions."""
        if result.returncode == 0:
            return
        stderr = (result.stderr or "").lower()
        if any(p in stderr for p in auth_patterns):
            raise AIAuthenticationError(
                f"{self._binary_name} auth failed. {auth_hint}".strip(),
            )
        raise AIProviderError(
            f"{self._binary_name} failed ({result.returncode}): {result.stderr[:500]}",
        )

    @staticmethod
    def extract_json_object(text: str) -> dict[str, Any]:
        """Extract JSON object from noisy stdout."""
        text = text.strip()
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return cast(dict[str, Any], json.loads(match.group(0)))
        msg = "Could not extract JSON from CLI output"
        raise AIProviderError(msg)

    @abstractmethod
    def parse_stdout(self, stdout: str) -> str:
        """Parse provider-specific stdout envelope."""
        ...
