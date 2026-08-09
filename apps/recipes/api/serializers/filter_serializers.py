"""Query-parameter parsing for recipe listings.

Query strings are validated exactly like request bodies. Using
:class:`StrictSerializer` means ``?catgeory=cake`` fails with a 400 instead of
silently returning everything — the misleading-200 bug that class exists to
prevent.

Repeated parameters are **not** supported: in a ``QueryDict``,
``.get()`` returns only the last occurrence. Comma-separated values are the one
supported form, which is also cleaner in the generated OpenAPI schema.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import (
    CommaSeparatedCharField,
    CommaSeparatedChoiceField,
    StrictSerializer,
)
from apps.recipes.constants import (
    MAX_CATEGORIES_PER_RECIPE,
    SEARCH_TERM_MAX_LENGTH,
    Difficulty,
    Ordering,
    RecipeScope,
)

# CommaSeparatedCharField / CommaSeparatedChoiceField moved to
# `apps.common.api.serializers` when the courses app needed them too.


class RecipeListQuerySerializer(StrictSerializer):
    """Validates the query string of a recipe listing.

    ``page`` and ``page_size`` must be declared even though the paginator reads
    them from the request directly — otherwise the strict check would reject
    them as unknown parameters.

    Note the deliberate asymmetry with recipe *writes*: an unknown category slug
    here yields an empty page rather than a 400, because categories are dynamic
    data and a bookmarked filter URL must not break when staff rename one.
    Assigning an unknown category to a recipe *is* a 400.
    """

    search = serializers.CharField(
        required=False, allow_blank=True, max_length=SEARCH_TERM_MAX_LENGTH
    )
    category = CommaSeparatedCharField(
        required=False, allow_blank=True, max_items=MAX_CATEGORIES_PER_RECIPE
    )
    difficulty = CommaSeparatedChoiceField(
        required=False, allow_blank=True, choices=Difficulty.choices
    )
    author = serializers.CharField(required=False, allow_blank=True, max_length=30)
    ingredient = serializers.CharField(required=False, allow_blank=True, max_length=120)
    max_total_minutes = serializers.IntegerField(required=False, min_value=1)
    ordering = serializers.ChoiceField(choices=Ordering.choices, required=False)
    scope = serializers.ChoiceField(choices=RecipeScope.choices, required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)


class RecipeSearchQuerySerializer(RecipeListQuerySerializer):
    """Validates the query string of the dedicated search endpoint.

    ``q`` is required here, and ordering defaults to relevance.
    """

    q = serializers.CharField(max_length=SEARCH_TERM_MAX_LENGTH)
