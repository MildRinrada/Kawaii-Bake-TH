"""Deterministic offline provider - the development and test default.

No network, no credentials, no randomness: the reply is a pure function of
the prompt, so tests can assert on it and local development needs no API key.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ai.constants import PROVIDER_MOCK, ROLE_USER
from ai.providers.base import AIProvider
from ai.schemas import AICompletion, AIMessage

_REPLY_PREFIX = {
    "th": "(ผู้ช่วยจำลอง) คำถามของคุณคือ",
    "en": "(mock assistant) Your question was",
}

_CONTEXT_NOTE = {
    "th": "อ้างอิงจาก",
    "en": "Based on",
}


class MockAIProvider(AIProvider):
    """Echoes the newest user message back, tagged as a mock reply.

    Echoing (rather than canned text) is what makes the Thai round-trip tests
    meaningful: the exact bytes the user sent must come back through the
    provider boundary, the database and the API response unchanged.
    """

    name = PROVIDER_MOCK

    def generate(
        self,
        *,
        messages: Sequence[AIMessage],
        language: str,
        context: Mapping[str, Any] | None = None,
    ) -> AICompletion:
        """Build the deterministic reply.

        Args:
            messages: The full prompt; the last ``user`` turn is echoed.
            language: ``th`` or ``en`` - selects the reply phrasing.
            context: Optional content context; its title is acknowledged.

        Returns:
            The mock completion with plausible token counts.
        """
        last_user = next(
            (m.content for m in reversed(messages) if m.role == ROLE_USER), ""
        )
        prefix = _REPLY_PREFIX.get(language, _REPLY_PREFIX["en"])
        reply = f"{prefix}: {last_user}"

        title = (context or {}).get("title")
        if title:
            note = _CONTEXT_NOTE.get(language, _CONTEXT_NOTE["en"])
            reply = f"{reply}\n{note}: {title}"

        input_chars = sum(len(m.content) for m in messages)
        return AICompletion(
            content=reply,
            model_name="mock-1",
            # Rough char-based estimate - good enough for usage-log plumbing.
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(reply) // 4),
        )
