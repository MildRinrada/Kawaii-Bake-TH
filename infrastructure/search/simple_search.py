"""Portable substring search.

Works identically on PostgreSQL and SQLite, so it is the default and is fully
exercised by the test suite. It cannot rank, and it cannot use an index for a
leading wildcard  acceptable at current scale, and the seam exists precisely so
this can be swapped without touching a selector.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet


class SimpleSearchBackend:
    """Case-insensitive substring match across title and summary."""

    search_fields = ("title", "summary")

    def apply(self, queryset: QuerySet, *, term: str) -> QuerySet:
        """Narrow ``queryset`` to rows containing ``term``.

        Args:
            queryset: The queryset to filter.
            term: The raw search term.

        Returns:
            The filtered queryset, unchanged when ``term`` is blank.
        """
        term = term.strip()
        if not term:
            return queryset

        condition = Q()
        for field in self.search_fields:
            condition |= Q(**{f"{field}__icontains": term})
        return queryset.filter(condition)

    def rank_ordering(self) -> tuple[str, ...]:
        """Return no ordering: substring matching produces no relevance score."""
        return ()
