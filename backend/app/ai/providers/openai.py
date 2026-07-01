"""OpenAI provider (API + Codex CLI)."""

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
    import openai

    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


class _CodexCli(CliTransport):
    def parse_stdout(self, stdout: str) -> str:
        payload = self.extract_json_object(stdout)
        if "output" in payload:
            return str(payload["output"])
        return stdout


class OpenAIProvider(BaseAIProvider):
    """OpenAI API and Codex CLI provider."""

    def __init__(
        self,
        *,
        model: str | None = None,
        transport: AITransport | None = AITransport.API,
        max_tokens: int = 4096,
    ) -> None:
        """Configure OpenAI API or Codex CLI transport."""
        super().__init__(
            provider_name="openai",
            default_model="gpt-4o",
            default_api_key_env="OPENAI_API_KEY",
            model=model,
            max_tokens=max_tokens,
            transport=transport,
        )
        self._cli: _CodexCli | None = None

    def _get_client(self) -> Any:
        if not _HAS_SDK:
            raise AINotAvailableError("openai package not installed")
        if self._client is None:
            self._client = openai.OpenAI()
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
        """Generate a completion via OpenAI API or Codex CLI."""
        if self._transport == AITransport.CLI:
            return self._complete_cli(
                prompt,
                system=system,
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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        choice = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return AIResponse(
            content=choice,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=(input_tokens * 2.5 + output_tokens * 10) / 1_000_000,
            provider="openai",
        )

    def _complete_cli(
        self,
        prompt: str,
        *,
        system: str | None,
        timeout: float,
        repo_root: str | None,
        cli_schema: CliSchemaRequest | None,
    ) -> AIResponse:
        binary = CliTransport.find_binary("codex")
        if not binary:
            raise AINotAvailableError("codex CLI not found on PATH")
        if self._cli is None:
            self._cli = _CodexCli(
                binary_path=binary,
                binary_name="codex",
                install_hint="Install OpenAI Codex CLI",
                api_key_env="OPENAI_API_KEY",
            )
        full_prompt = f"{system}\n\n---\n\n{prompt}" if system else prompt
        cmd = [binary, "exec", "--json"]
        if cli_schema:
            cmd.extend(["--output-schema", json.dumps(cli_schema.schema)])
        cmd.append(full_prompt)
        result = self._cli.run(cmd, timeout=max(timeout, 120.0), cwd=repo_root)
        self._cli.check_exit_code(
            result,
            auth_hint="Run `codex login` or set OPENAI_API_KEY",
        )
        content = self._cli.parse_stdout(result.stdout)
        return AIResponse(content=content, model=self._model, provider="openai")
