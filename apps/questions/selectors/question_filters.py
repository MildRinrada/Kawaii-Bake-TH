"""The input contract for bank listings."""

from __future__ import annotations

from dataclasses import dataclass

from apps.questions.constants import QuestionScope


@dataclass(frozen=True)
class QuestionListFilters:
    """User-supplied narrowing options for a bank listing.

    Viewer identity is deliberately absent: it is a separate selector argument,
    so nothing in a query string can influence who the server thinks is asking.
    """

    types: tuple[str, ...] = ()
    difficulty: tuple[str, ...] = ()
    tag_slugs: tuple[str, ...] = ()
    search: str = ""
    scope: str = QuestionScope.MINE
