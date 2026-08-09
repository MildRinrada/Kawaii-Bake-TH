"""The provider interface every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from ai.schemas import AICompletion, AIMessage


class AIProvider(ABC):
    """One AI backend (mock, OpenAI, a local model, …).

    The assistant app depends on this interface only; concrete classes are
    resolved by name through :mod:`ai.factory`, so swapping backends is a
    settings change, never a code change.
    """

    name: str = ""

    @abstractmethod
    def generate(
        self,
        *,
        messages: Sequence[AIMessage],
        language: str,
        context: Mapping[str, Any] | None = None,
    ) -> AICompletion:
        """Produce the assistant's next turn.

        Args:
            messages: Full prompt — the system message first, then history,
                ending with the newest user message.
            language: ``th`` or ``en``; the reply should be in this language.
            context: Optional structured content context (already rendered
                into the system message by the caller; passed for providers
                that can use it natively).

        Returns:
            The completion with token accounting.

        Raises:
            ai.exceptions.AIProviderError: On any generation failure.
        """
