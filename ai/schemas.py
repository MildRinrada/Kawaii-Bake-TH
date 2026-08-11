"""Data shapes crossing the provider boundary.

Frozen dataclasses, mirroring the cross-app ref pattern (``CourseRef``,
``RecipeRef``): providers receive and return plain values, never Django
models and never DRF serializers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIMessage:
    """One turn of a conversation, as a provider sees it.

    Attributes:
        role: ``system``, ``user`` or ``assistant``.
        content: The text of the turn. UTF-8 throughout - Thai and emoji
            must survive this boundary byte-perfect.
    """

    role: str
    content: str


@dataclass(frozen=True)
class AICompletion:
    """A provider's answer plus the accounting the caller must persist.

    Attributes:
        content: The generated reply.
        model_name: The concrete model that produced it (e.g. ``mock-1``).
        input_tokens: Prompt-side token count, or ``None`` if unknown.
        output_tokens: Completion-side token count, or ``None`` if unknown.
    """

    content: str
    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
