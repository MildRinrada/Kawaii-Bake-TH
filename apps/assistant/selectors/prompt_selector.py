"""Read-side queries for prompt templates."""

from __future__ import annotations

from apps.assistant.models import PromptTemplate


def get_active_template(*, name: str, language: str) -> PromptTemplate | None:
    """Fetch the active template for new conversations.

    The partial unique constraint guarantees at most one row matches.

    Args:
        name: Template name (a :class:`ContextType` value).
        language: A :class:`AssistantLanguage` value.

    Returns:
        The active template, or ``None`` when none is active.
    """
    return PromptTemplate.objects.filter(
        name=name, language=language, is_active=True
    ).first()


def get_template(
    *, name: str, language: str, version: str
) -> PromptTemplate | None:
    """Fetch the exact template version a conversation was stamped with.

    Args:
        name: Template name (a :class:`ContextType` value).
        language: A :class:`AssistantLanguage` value.
        version: The stamped ``prompt_version``.

    Returns:
        The template, or ``None`` when that version does not exist.
    """
    return PromptTemplate.objects.filter(
        name=name, language=language, version=version
    ).first()
