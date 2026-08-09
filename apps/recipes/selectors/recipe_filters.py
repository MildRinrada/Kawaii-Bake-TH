"""The input contract for recipe listings."""

from __future__ import annotations

from dataclasses import dataclass

from apps.recipes.constants import Ordering, RecipeScope


@dataclass(frozen=True)
class RecipeListFilters:
    """User-supplied narrowing options for a recipe listing.

    Viewer identity is deliberately **absent** from this dataclass. It is passed
    to the selector as a separate argument, so nothing a client can put in a
    query string is able to influence who the server thinks is asking.
    """

    search: str = ""
    category_slugs: tuple[str, ...] = ()
    difficulty: tuple[str, ...] = ()
    author_username: str = ""
    max_total_minutes: int | None = None
    ordering: str = Ordering.NEWEST
    scope: str = RecipeScope.PUBLIC
    ingredient: str = ""
