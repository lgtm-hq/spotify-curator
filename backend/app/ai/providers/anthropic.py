"""Anthropic provider (API + CLI)."""

from __future__ import annotations

import json
from typing import Any

from app.ai.enums import AITransport
from app.ai.exceptions import AINotAvailableError
from app.ai.json_response import CliSchemaRequest
from app.ai.providers.base import BaseAIProvider
from app.ai.providers.cli_transport import CliTransport
from app.ai.providers.response import AIResponse

try:
    import anthropic

    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


class _ClaudeCli(CliTransport):
    def parse_stdout(self, stdout: str) -> str:
        payload = self.extract_json_object(stdout)
        if "result" in payload:
            return str(payload["result"])
        if "content" in payload:
            return str(payload["content"])
        return stdout


class AnthropicProvider(BaseAIProvider):
    """Anthropic API and Claude CLI provider."""

    def __init__(
        self,
        *,
        model: str | None = None,
        transport: AITransport | None = AITransport.API,
        max_tokens: int = 4096,
    ) -> None:
        """Configure Anthropic API or Claude CLI transport."""
        super().__init__(
            provider_name="anthropic",
            default_model="claude-sonnet-4-20250514",
            default_api_key_env="ANTHROPIC_API_KEY",
            model=model,
            max_tokens=max_tokens,
            transport=transport,
        )
        self._cli: _ClaudeCli | None = None

    def _get_client(self) -> Any:
        if not _HAS_SDK:
            raise AINotAvailableError("anthropic package not installed")
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

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
        """Generate a completion via Anthropic API or Claude CLI."""
        if self._transport == AITransport.CLI:
            return self._complete_cli(
                prompt,
                system=system,
                max_tokens=max_tokens,
                timeout=timeout,
                repo_root=repo_root,
                cli_schema=cli_schema,
            )
        return self._complete_api(
            prompt,
            system=system,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def _complete_api(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        timeout: float,
    ) -> AIResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "timeout": timeout,
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        return AIResponse(
            content=content,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=(input_tokens * 3 + output_tokens * 15) / 1_000_000,
            provider="anthropic",
        )

    def _complete_cli(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        timeout: float,
        repo_root: str | None,
        cli_schema: CliSchemaRequest | None,
    ) -> AIResponse:
        binary = CliTransport.find_binary("claude")
        if not binary:
            raise AINotAvailableError("claude CLI not found on PATH")
        if self._cli is None:
            self._cli = _ClaudeCli(
                binary_path=binary,
                binary_name="claude",
                install_hint="Install Claude Code CLI",
                api_key_env="ANTHROPIC_API_KEY",
            )
        cmd = [
            binary,
            "--bare",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            "dontAsk",
        ]
        if system:
            cmd.extend(["--append-system-prompt", system])
        if cli_schema:
            cmd.extend(["--json-schema", json.dumps(cli_schema.schema)])
        result = self._cli.run(cmd, timeout=max(timeout, 120.0), cwd=repo_root)
        self._cli.check_exit_code(
            result,
            auth_hint="Run `claude login` or set ANTHROPIC_API_KEY",
        )
        content = self._cli.parse_stdout(result.stdout)
        return AIResponse(content=content, model=self._model, provider="anthropic")
