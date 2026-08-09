"""Business logic for conversations: create and address."""

from __future__ import annotations

import logging

from apps.assistant.constants import ContextType
from apps.assistant.exceptions import (
    AssistantUnavailableError,
    ConversationNotFoundError,
    InvalidContextError,
)
from apps.assistant.models import AssistantConversation
from apps.assistant.repositories import conversation_repository
from apps.assistant.selectors import conversation_selector, prompt_selector
from apps.assistant.services import context_service

logger = logging.getLogger("kawaiibake.assistant")

_CONTEXT_ID_FIELDS = {
    ContextType.RECIPE: "recipe_id",
    ContextType.LESSON: "lesson_id",
    ContextType.COURSE: "course_id",
}


def create_conversation(
    *,
    user_id: int,
    viewer_is_staff: bool = False,
    language: str,
    context_type: str,
    recipe_id: int | None = None,
    lesson_id: int | None = None,
    course_id: int | None = None,
) -> AssistantConversation:
    """Create a conversation, validating its context and stamping the prompt.

    Args:
        user_id: Primary key of the owner.
        viewer_is_staff: Whether the caller is a staff member.
        language: A value of :class:`AssistantLanguage`.
        context_type: A value of :class:`ContextType`.
        recipe_id: Target recipe, for recipe conversations.
        lesson_id: Target lesson, for lesson conversations.
        course_id: Target course, for course conversations.

    Returns:
        The created conversation.

    Raises:
        InvalidContextError: If the ids do not match the context type.
        ContextNotFoundError: If the target is absent or hidden.
        ContextAccessDeniedError: If the lesson content is gated.
        AssistantUnavailableError: If no active prompt template exists.
    """
    _validate_context_shape(
        context_type=context_type,
        recipe_id=recipe_id,
        lesson_id=lesson_id,
        course_id=course_id,
    )
    context_service.validate_for_creation(
        context_type=context_type,
        recipe_id=recipe_id,
        lesson_id=lesson_id,
        course_id=course_id,
        viewer_id=user_id,
        viewer_is_staff=viewer_is_staff,
    )

    template = prompt_selector.get_active_template(
        name=context_type, language=language
    )
    if template is None:
        # A deployment gap, not a client error: templates are seeded by
        # migration, so this only happens if someone deactivated them all.
        logger.error(
            "assistant_no_active_template context=%s language=%s",
            context_type,
            language,
        )
        raise AssistantUnavailableError

    conversation = conversation_repository.create_conversation(
        user_id=user_id,
        language=language,
        context_type=context_type,
        prompt_version=template.version,
        recipe_id=recipe_id,
        lesson_id=lesson_id,
        course_id=course_id,
    )
    logger.info(
        "assistant_conversation_created conversation_id=%s context=%s "
        "language=%s prompt_version=%s by=%s",
        conversation.pk,
        context_type,
        language,
        template.version,
        user_id,
    )
    return conversation


def require_owned_conversation(
    *, conversation_id: int, user_id: int
) -> AssistantConversation:
    """Fetch the caller's conversation or 404.

    Args:
        conversation_id: Primary key of the conversation.
        user_id: Primary key of the caller.

    Returns:
        The conversation.

    Raises:
        ConversationNotFoundError: If absent or not the caller's.
    """
    conversation = conversation_selector.get_owned_conversation(
        conversation_id=conversation_id, user_id=user_id
    )
    if conversation is None:
        raise ConversationNotFoundError
    return conversation


def _validate_context_shape(
    *,
    context_type: str,
    recipe_id: int | None,
    lesson_id: int | None,
    course_id: int | None,
) -> None:
    """Require exactly the id matching the context type, none otherwise."""
    supplied = {
        "recipe_id": recipe_id,
        "lesson_id": lesson_id,
        "course_id": course_id,
    }
    expected_field = _CONTEXT_ID_FIELDS.get(context_type)

    problems: dict[str, list[str]] = {}
    for field, value in supplied.items():
        if field == expected_field:
            if value is None:
                problems[field] = [f"Required for context_type '{context_type}'."]
        elif value is not None:
            problems[field] = [f"Not allowed for context_type '{context_type}'."]
    if problems:
        raise InvalidContextError(details=problems)
