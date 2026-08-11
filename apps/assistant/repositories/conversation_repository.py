"""Write operations for conversations, messages and usage logs.

Messages and usage logs get an ``add``/``log`` only - append-only tables
have no update or delete path, so none exists here to misuse.
"""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.assistant.constants import AUTO_TITLE_LENGTH
from apps.assistant.models import AIUsageLog, AssistantConversation, AssistantMessage


def create_conversation(
    *,
    user_id: int,
    language: str,
    context_type: str,
    prompt_version: str,
    title: str = "",
    recipe_id: int | None = None,
    lesson_id: int | None = None,
    course_id: int | None = None,
) -> AssistantConversation:
    """Create a conversation row.

    Args:
        user_id: Primary key of the owner.
        language: A value of :class:`AssistantLanguage`.
        context_type: A value of :class:`ContextType`.
        prompt_version: The active template version being stamped.
        title: Optional initial title.
        recipe_id: Target recipe, when ``context_type`` is ``recipe``.
        lesson_id: Target lesson, when ``context_type`` is ``lesson``.
        course_id: Target course, when ``context_type`` is ``course``.

    Returns:
        The saved conversation.
    """
    return AssistantConversation.objects.create(
        user_id=user_id,
        language=language,
        context_type=context_type,
        prompt_version=prompt_version,
        title=title,
        recipe_id=recipe_id,
        lesson_id=lesson_id,
        course_id=course_id,
    )


def add_message(
    *,
    conversation: AssistantConversation,
    role: str,
    content: str,
    provider: str = "",
    model_name: str = "",
    token_input: int | None = None,
    token_output: int | None = None,
) -> AssistantMessage:
    """Append one message to a conversation.

    Also touches the conversation's ``updated_at`` so "most recently active"
    ordering works without counting messages.

    Args:
        conversation: The owning conversation.
        role: ``user`` or ``assistant`` (``system`` is never stored).
        content: The message text, UTF-8 (Thai and emoji included).
        provider: Provider name, for assistant turns.
        model_name: Concrete model identifier, for assistant turns.
        token_input: Prompt-side token count, if known.
        token_output: Completion-side token count, if known.

    Returns:
        The saved message.
    """
    message = AssistantMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
        provider=provider,
        model_name=model_name,
        token_input=token_input,
        token_output=token_output,
    )
    AssistantConversation.objects.filter(pk=conversation.pk).update(
        updated_at=timezone.now()
    )
    return message


def set_title_if_empty(*, conversation: AssistantConversation, title: str) -> None:
    """Stamp an auto-title from the first user message, once.

    A conditional UPDATE (``title=""`` in the WHERE) - the stamp-once shape
    used for ``published_at`` and ``completed_at`` - so a concurrent send
    cannot overwrite a title that already exists.

    Args:
        conversation: The conversation to title.
        title: Candidate title; truncated to the auto-title length.
    """
    AssistantConversation.objects.filter(pk=conversation.pk, title="").update(
        title=title[:AUTO_TITLE_LENGTH]
    )


def log_usage(
    *,
    user_id: int,
    provider: str,
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
    estimated_cost: Decimal | None = None,
) -> AIUsageLog:
    """Append one provider call to the usage ledger.

    Args:
        user_id: Primary key of the calling user.
        provider: Provider name.
        model_name: Concrete model identifier.
        input_tokens: Prompt-side token count (``None`` becomes 0).
        output_tokens: Completion-side token count (``None`` becomes 0).
        estimated_cost: Optional cost estimate; unknown stays ``NULL``.

    Returns:
        The saved log row.
    """
    return AIUsageLog.objects.create(
        user_id=user_id,
        provider=provider,
        model_name=model_name,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        estimated_cost=estimated_cost,
    )
