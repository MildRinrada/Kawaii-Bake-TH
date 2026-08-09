"""Domain exceptions for the quizzes app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class QuizNotVisibleError(DomainError):
    """Raised when a quiz is absent, or present but hidden from the viewer.

    404 in both cases — a 403 would confirm the slug exists.
    """

    code = "not_found"
    status_code = 404
    message = "Quiz not found."


class QuizSlugImmutableError(DomainError):
    """Raised when changing the slug of an already-published quiz."""

    code = "slug_immutable"
    status_code = 409
    message = (
        "The URL of a published quiz cannot be changed, because existing "
        "links would break."
    )


class QuizSlugTakenError(DomainError):
    """Raised when a requested slug is already used by another quiz."""

    code = "slug_taken"
    status_code = 409
    message = "That URL is already in use by another quiz."


class QuizSlugGenerationError(DomainError):
    """Raised when a unique slug could not be generated."""

    code = "slug_generation_failed"
    status_code = 500
    message = "Could not generate a unique URL for this quiz. Please try again."


class QuizNotPublishableError(DomainError):
    """Raised when a quiz fails the completeness checks required to publish.

    Carries **every** failure in ``details`` so the frontend can render a
    publish checklist.
    """

    code = "quiz_not_publishable"
    status_code = 400
    message = "This quiz is not ready to publish."


class InvalidQuizQuestionError(DomainError):
    """Raised when composing a quiz with unusable question ids.

    "Someone else's question" and "no such question" are the same problem to
    the client — distinguishing them would confirm foreign ids exist.
    """

    code = "invalid_questions"
    status_code = 400
    message = "One or more questions cannot be used in this quiz."


class QuizNotAvailableError(DomainError):
    """Raised when starting a quiz that is not open for attempts."""

    code = "quiz_not_available"
    status_code = 400
    message = "This quiz is not open for attempts."


class QuizHasAttemptsError(DomainError):
    """Raised when deleting a quiz whose attempt history must survive."""

    code = "quiz_has_attempts"
    status_code = 409
    message = "This quiz has recorded attempts and cannot be deleted. Archive it instead."


class AttemptNotFoundError(DomainError):
    """Raised when the viewer has no matching attempt."""

    code = "not_found"
    status_code = 404
    message = "Attempt not found."


class NoOpenAttemptError(DomainError):
    """Raised when submitting without an in-progress attempt."""

    code = "no_open_attempt"
    status_code = 404
    message = "You have no attempt in progress for this quiz. Start one first."


class AttemptAlreadySubmittedError(DomainError):
    """Raised on a second submit of the same attempt.

    Deliberately **not** idempotent, unlike enroll: a second submit may carry
    different answers, and an attempt is graded exactly once.
    """

    code = "attempt_already_submitted"
    status_code = 409
    message = "This attempt has already been submitted."


class InvalidSubmissionError(DomainError):
    """Raised when submitted answers do not match the attempt snapshot.

    Carries the exact diff (unknown/duplicate question ids, invalid choice
    ids) in ``details``.
    """

    code = "invalid_submission"
    status_code = 400
    message = "The submitted answers do not match this attempt."
