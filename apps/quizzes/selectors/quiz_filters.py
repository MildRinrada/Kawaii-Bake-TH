"""The input contract for quiz listings."""

from __future__ import annotations

from dataclasses import dataclass

from apps.quizzes.constants import QuizOrdering, QuizScope


@dataclass(frozen=True)
class QuizListFilters:
    """User-supplied narrowing options for a quiz listing.

    Viewer identity is deliberately absent: it is a separate selector argument,
    so nothing in a query string can influence who the server thinks is asking.
    """

    owner_username: str = ""
    ordering: str = QuizOrdering.NEWEST
    scope: str = QuizScope.PUBLIC
