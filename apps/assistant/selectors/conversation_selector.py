"""Read-side queries for conversations and messages.

Every conversation read filters by owner: there is deliberately no way to
address another user's conversation, so "not yours" and "does not exist"
are indistinguishable at the API (the same 404).
"""

from __future__ import annotations

from django.db.models import QuerySet

from ai.schemas import AIMessage
from apps.assistant.constants import HISTORY_WINDOW, MessageRole
from apps.assistant.models import AssistantConversation, AssistantMessage


def get_owned_conversation(
    *, conversation_id: int, user_id: int
) -> AssistantConversation | None:
    """Fetch one conversation, restricted to its owner.

    Args:
        conversation_id: Primary key of the conversation.
        user_id: Primary key of the caller.

    Returns:
        The conversation, or ``None`` when absent or not the caller's.
    """
    return AssistantConversation.objects.filter(
        pk=conversation_id, user_id=user_id
    ).first()


def list_for_user(*, user_id: int) -> QuerySet[AssistantConversation]:
    """List the caller's conversations, most recently active first.

    Returns a lazy queryset; the paginator slices it at the API edge.

    Args:
        user_id: Primary key of the caller.

    Returns:
        An unevaluated queryset.
    """
    return AssistantConversation.objects.filter(user_id=user_id)


def list_messages(*, conversation_id: int) -> QuerySet[AssistantMessage]:
    """List a conversation's transcript in chronological order.

    Ownership was already checked by :func:`get_owned_conversation`; this
    filters by conversation only.

    Args:
        conversation_id: Primary key of the conversation.

    Returns:
        An unevaluated queryset ordered oldest-first.
    """
    return AssistantMessage.objects.filter(conversation_id=conversation_id)


def recent_history(*, conversation_id: int) -> list[AIMessage]:
    """Return the provider-facing replay window, oldest-first.

    The last :data:`HISTORY_WINDOW` stored turns as plain ``AIMessage``
    values - the model never crosses into the ``ai`` package. Only ``user``
    and ``assistant`` roles exist in storage; the system prompt is rebuilt
    fresh by the service.

    Args:
        conversation_id: Primary key of the conversation.

    Returns:
        The recent turns as provider-boundary values.
    """
    rows = list(
        AssistantMessage.objects.filter(
            conversation_id=conversation_id,
            role__in=(MessageRole.USER, MessageRole.ASSISTANT),
        )
        .order_by("-created_at", "-id")
        .values("role", "content")[:HISTORY_WINDOW]
    )
    return [AIMessage(role=row["role"], content=row["content"]) for row in reversed(rows)]
