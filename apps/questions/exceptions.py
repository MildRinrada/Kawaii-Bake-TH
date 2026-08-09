"""Domain exceptions for the question bank."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class QuestionNotFoundError(DomainError):
    """Raised when a question is absent, or present but not the viewer's.

    404 in both cases — the bank is a private authoring surface, and a 403
    would confirm someone else's question id exists.
    """

    code = "not_found"
    status_code = 404
    message = "Question not found."


class QuestionFrozenError(DomainError):
    """Raised when mutating content of a question frozen for history.

    A frozen question has been answered in at least one quiz attempt; editing
    its text, type or choices would silently rewrite what students were graded
    against. Duplicate the question instead (versioning via ``supersedes`` is
    the prepared future path). ``explanation`` and ``tags`` stay editable.
    """

    code = "question_frozen"
    status_code = 409
    message = (
        "This question has recorded attempts and its content is frozen. "
        "Duplicate it to make changes."
    )


class QuestionInUseError(DomainError):
    """Raised when deleting a question that a quiz still references."""

    code = "question_in_use"
    status_code = 409
    message = "This question is used by a quiz and cannot be deleted."


class InvalidQuestionChoicesError(DomainError):
    """Raised when a question's answer choices break the rules for its type.

    Carries every problem in ``details`` so the author fixes them in one pass.
    """

    code = "invalid_choices"
    status_code = 400
    message = "The answer choices are not valid for this question type."
