"""Search seam.

The backend **takes and returns a QuerySet, and never executes it.** An
alternative interface returning a list of matching ids would force a two-query
``IN (...)`` pattern that breaks pagination, cannot compose with the visibility
``Q``, and silently caps results. Returning a lazy QuerySet keeps filtering,
permissions and pagination composable *after* search has been applied.
"""

from __future__ import annotations

from typing import Protocol

from django.db.models import QuerySet


class SearchBackend(Protocol):
    """Applies a free-text search term to a queryset."""

    def apply(self, queryset: QuerySet, *, term: str) -> QuerySet:
        """Return ``queryset`` narrowed to rows matching ``term``."""
        ...

    def rank_ordering(self) -> tuple[str, ...]:
        """Return the ordering that expresses relevance.

        Empty when the backend cannot rank, in which case the caller keeps its
        own default ordering.
        """
        ...
