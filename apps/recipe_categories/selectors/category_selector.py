"""Read-side queries for recipe categories.

This module is the **public read API** of this app. Other apps call these
functions and never touch :class:`RecipeCategory` directly  see
``docs/adr/0008-cross-app-model-references.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.db.models import Count, Q, QuerySet

from apps.recipe_categories.models import RecipeCategory

# Fields other apps need when embedding a category reference in their payloads.
REFERENCE_FIELDS = ("id", "name", "slug", "icon")


def ref_queryset() -> QuerySet[RecipeCategory]:
    """Return the narrowed queryset other apps should prefetch with.

    Keeping this here means a consumer never names :class:`RecipeCategory` in
    its own ORM code, and the day categories gain a visibility rule, one
    function fixes every consumer.

    Returns:
        Active categories limited to their reference fields.
    """
    return RecipeCategory.objects.filter(is_active=True).only(*REFERENCE_FIELDS)


def list_categories(*, include_inactive: bool = False) -> QuerySet[RecipeCategory]:
    """List categories with their published recipe counts.

    The count is annotated rather than stored, so it can never drift. It counts
    only publicly visible recipes, so an author's drafts never inflate it.

    Args:
        include_inactive: Whether to include categories hidden from listings.

    Returns:
        Categories annotated with ``recipe_count``.
    """
    queryset = RecipeCategory.objects.all()
    if not include_inactive:
        queryset = queryset.filter(is_active=True)

    return queryset.annotate(
        recipe_count=Count(
            "recipes",
            filter=Q(recipes__status="published", recipes__visibility="public"),
            distinct=True,
        )
    )


def get_by_id(*, category_id: int) -> RecipeCategory | None:
    """Fetch one category by primary key, annotated with ``recipe_count``.

    Args:
        category_id: The category primary key.

    Returns:
        The category, or ``None`` when absent.
    """
    return (
        list_categories(include_inactive=True).filter(id=category_id).first()
    )


def get_by_slug(*, slug: str) -> RecipeCategory | None:
    """Fetch one category by slug.

    Args:
        slug: The category slug.

    Returns:
        The category, or ``None`` when absent.
    """
    return RecipeCategory.objects.filter(slug__iexact=slug.strip()).first()


def resolve_slugs(*, slugs: Sequence[str]) -> dict[str, int]:
    """Map category slugs to primary keys.

    Callers diff the result against what they asked for and raise **their own**
    domain error for the difference. This app must not raise another app's
    exception.

    Args:
        slugs: The slugs to resolve.

    Returns:
        A mapping of found slug to primary key. Unknown slugs are simply absent.
    """
    cleaned = [slug.strip() for slug in slugs if slug and slug.strip()]
    if not cleaned:
        return {}

    rows = RecipeCategory.objects.filter(
        slug__in=cleaned, is_active=True
    ).values_list("slug", "id")
    return dict(rows)
