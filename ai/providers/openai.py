"""OpenAI-compatible chat-completions provider.

Uses the standard library only - the ``openai`` package is not a project
dependency yet, and this endpoint shape is also what local runtimes
(Ollama, LM Studio, vLLM) expose, so ``base_url`` makes this the "real
provider" adapter for all of them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

from ai.constants import PROVIDER_OPENAI
from ai.exceptions import AIProviderError, ProviderNotConfiguredError
from ai.providers.base import AIProvider
from ai.schemas import AICompletion, AIMessage

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_TIMEOUT_SECONDS = 30


class OpenAIProvider(AIProvider):
    """Chat completions over the OpenAI wire format."""

    name = PROVIDER_OPENAI

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        """Store the connection settings.

        Args:
            api_key: Bearer token; ``None``/empty means unconfigured.
            model: Model identifier sent with every request.
            base_url: API root, overridable for OpenAI-compatible servers.
        """
        self._api_key = api_key or ""
        self._model = model
        self._base_url = base_url.rstrip("/")

    def generate(
        self,
        *,
        messages: Sequence[AIMessage],
        language: str,
        context: Mapping[str, Any] | None = None,
    ) -> AICompletion:
        """Call the chat-completions endpoint.

        Args:
            messages: The full prompt in order.
            language: Reply language hint (already embedded in the system
                message; unused on the wire).
            context: Unused - context is rendered into the system message.

        Returns:
            The provider's completion with token usage.

        Raises:
            ProviderNotConfiguredError: If no API key is set.
            AIProviderError: On transport or malformed-response failures.
        """
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "OPENAI_API_KEY is not set; use AI_PROVIDER=mock for local work."
            )

        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": m.role, "content": m.content} for m in messages
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("OpenAI returned an unexpected shape.") from exc

        usage = body.get("usage") or {}
        return AICompletion(
            content=content,
            model_name=body.get("model", self._model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
