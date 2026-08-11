"""PostgreSQL trigram search.

**Trigram-first, not tsvector-first  because of Thai.**

``to_tsvector`` tokenises on whitespace. Thai is written without inter-word
spaces, so ``to_tsvector('simple', 'ครัวซองต์ไส้ช็อกโกแลต')`` yields a *single*
token covering the whole phrase, and searching ``ช็อกโกแลต`` matches nothing.
Full-text search is therefore close to useless on Thai content, and the failure
is invisible if the test data is English.

``pg_trgm`` compares character trigrams and needs no tokenisation, so it works on
Thai and tolerates typos. ``SearchRank`` is added on top purely for stemming on
the English half of the corpus.

**This module is not exercised by the test suite**  the suite runs on SQLite,
and ``SearchVector`` cannot even be compiled without the PostgreSQL backend. See
``docs/adr/0008-cross-app-model-references.md`` for the accepted trade-off.

Requires the ``pg_trgm`` extension and a GIN index; both are created by a
vendor-guarded migration when this backend is first enabled.
"""

from __future__ import annotations

from django.db.models import QuerySet

TRIGRAM_THRESHOLD = 0.15


class PostgresSearchBackend:
    """Trigram similarity search with a full-text ranking bonus."""

    def apply(self, queryset: QuerySet, *, term: str) -> QuerySet:
        """Narrow and rank ``queryset`` by similarity to ``term``.

        Args:
            queryset: The queryset to filter.
            term: The raw search term.

        Returns:
            The filtered queryset annotated with a ``search_rank`` field.
        """
        term = term.strip()
        if not term:
            return queryset

        # Imported lazily: `django.contrib.postgres` requires psycopg, which is
        # a production-only dependency.
        from django.contrib.postgres.search import (
            SearchQuery,
            SearchRank,
            SearchVector,
            TrigramWordSimilarity,
        )
        from django.db.models.functions import Greatest

        return queryset.annotate(
            search_rank=Greatest(
                TrigramWordSimilarity(term, "title"),
                TrigramWordSimilarity(term, "summary") * 0.4,
                SearchRank(
                    SearchVector("title", weight="A") + SearchVector("summary", weight="B"),
                    SearchQuery(term, search_type="websearch"),
                ),
            )
        ).filter(search_rank__gt=TRIGRAM_THRESHOLD)

    def rank_ordering(self) -> tuple[str, ...]:
        """Order by descending relevance."""
        return ("-search_rank",)
