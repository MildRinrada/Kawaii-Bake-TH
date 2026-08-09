"""Business logic for recipe categories.

Categories are curated by staff through the Django admin in Phase 2; the API
exposes reads only. These functions exist so that a future admin API has a
service layer to call rather than reaching for the repository.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.recipe_categories.exceptions import CategoryNotFoundError
from apps.recipe_categories.models import RecipeCategory
from apps.recipe_categories.selectors import category_selector


def list_active_categories() -> QuerySet[RecipeCategory]:
    """Return active categories with their published recipe counts.

    Returns:
        A lazy queryset of categories annotated with ``recipe_count``.
    """
    return category_selector.list_categories()


def get_category(*, slug: str) -> RecipeCategory:
    """Fetch one category by slug.

    Args:
        slug: The category slug.

    Returns:
        The category.

    Raises:
        CategoryNotFoundError: If no category has that slug.
    """
    category = category_selector.get_by_slug(slug=slug)
    if category is None:
        raise CategoryNotFoundError
    return category
