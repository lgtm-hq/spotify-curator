"""Cursor agent CLI provider."""

from __future__ import annotations

import json

from app.ai.exceptions import AINotAvailableError
from app.ai.json_response import CliSchemaRequest
from app.ai.providers.base import BaseAIProvider
from app.ai.providers.cli_transport import CliTransport
from app.ai.providers.response import AIResponse


class _AgentCli(CliTransport):
    def parse_stdout(self, stdout: str) -> str:
        payload = self.extract_json_object(stdout)
        return str(payload.get("result", stdout))


class CursorProvider(BaseAIProvider):
    """Cursor agent CLI provider (CLI only)."""

    def __init__(self, *, model: str | None = None, max_tokens: int = 4096) -> None:
        super().__init__(
            provider_name="cursor",
            default_model=model or "composer-2.5-fast",
            default_api_key_env="CURSOR_API_KEY",
            model=model,
            max_tokens=max_tokens,
        )
        self._cli: _AgentCli | None = None
        self._session_id: str | None = None

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
        binary = CliTransport.find_binary("agent")
        if not binary:
            raise AINotAvailableError("agent CLI not found. Run Cursor CLI setup.")
        if self._cli is None:
            self._cli = _AgentCli(
                binary_path=binary,
                binary_name="agent",
                install_hint="Install Cursor agent CLI",
                api_key_env="CURSOR_API_KEY",
            )
        full_prompt = f"{system}\n\n---\n\n{prompt}" if system else prompt
        cmd = [
            binary,
            "--print",
            "--output-format",
            "json",
            "--trust",
            "--mode",
            "ask",
            "--model",
            self._model,
        ]
        if repo_root:
            cmd.extend(["--workspace", repo_root])
        if self._session_id and not use_one_shot:
            cmd.extend(["--resume", self._session_id])
        result = self._cli.run(
            cmd,
            input_text=full_prompt,
            timeout=max(timeout, 600.0),
            cwd=repo_root,
        )
        self._cli.check_exit_code(result, auth_hint="Run `agent login` or set CURSOR_API_KEY")
        payload = self._cli.extract_json_object(result.stdout)
        if payload.get("session_id"):
            self._session_id = str(payload["session_id"])
        content = str(payload.get("result", ""))
        return AIResponse(content=content, model=self._model, provider="cursor")
