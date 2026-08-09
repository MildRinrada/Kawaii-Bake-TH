"""Domain exceptions for the assistant app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ConversationNotFoundError(DomainError):
    """Raised when a conversation is absent or not the caller's.

    "Not yours" and "does not exist" are the same 404 — the ownership rule
    is enforced by the selector, so no endpoint can even address someone
    else's conversation.
    """

    code = "not_found"
    status_code = 404
    message = "Conversation not found."


class ContextNotFoundError(DomainError):
    """Raised when the requested context target is absent or hidden.

    This app's own 404 for a recipe/lesson/course the viewer cannot see —
    a callee (recipes, lessons, courses) never raises for its caller
    (ADR 0008).
    """

    code = "not_found"
    status_code = 404
    message = "Not found."


class ContextAccessDeniedError(DomainError):
    """Raised when the context target exists but its content is gated.

    Mirrors the lessons two-layer rule: the syllabus already made the lesson
    public, so 404 would be a lie — the caller needs the enrollment signal
    to render the "Enroll" CTA.
    """

    code = "enrollment_required"
    status_code = 403
    message = "Enroll in the course to get help with this lesson."


class InvalidContextError(DomainError):
    """Raised when the context ids do not match the declared context type."""

    code = "invalid_context"
    status_code = 400
    message = "Context ids must match the declared context type."


class AssistantUnavailableError(DomainError):
    """Raised when the AI provider fails or is not configured.

    503, not 500: the request was valid and the state is intact — the
    backend is temporarily unable to answer. The user's message is already
    persisted when this is raised (see ADR 0013 on the transaction shape).
    """

    code = "assistant_unavailable"
    status_code = 503
    message = "The assistant is temporarily unavailable. Please try again."
