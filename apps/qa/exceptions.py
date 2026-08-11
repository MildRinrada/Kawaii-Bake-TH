"""Domain exceptions for the Q&A app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ThreadNotFoundError(DomainError):
    """Raised when a thread is absent, deleted, or hidden from this viewer."""

    code = "not_found"
    status_code = 404
    message = "Question not found."


class ThreadTargetNotFoundError(DomainError):
    """Raised when the recipe/course being asked about is absent or hidden.

    This app's own 404 (ADR 0008)  a callee never raises for its caller.
    """

    code = "not_found"
    status_code = 404
    message = "Not found."


class AnswerNotFoundError(DomainError):
    """Raised when an answer is absent or not addressable by the viewer."""

    code = "not_found"
    status_code = 404
    message = "Answer not found."


class ThreadNotActiveError(DomainError):
    """Raised when answering/accepting on a thread that is not active.

    Reached only by viewers who can *see* the thread (its author, staff),
    so 409  the state conflict family  not a lying 404.
    """

    code = "thread_not_active"
    status_code = 409
    message = "This question is not open for answers."


class InvalidAcceptError(DomainError):
    """Raised when the accepted answer does not belong to the thread."""

    code = "invalid_accept"
    status_code = 400
    message = "The answer does not belong to this question."


class ModerationNotAllowedError(DomainError):
    """Raised when a non-staff caller tries to change a thread's status."""

    code = "permission_denied"
    status_code = 403
    message = "Only moderators can change a question's status."
