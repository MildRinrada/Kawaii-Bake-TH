"""Write-side database access for recipe categories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.recipe_categories.models import RecipeCategory


def create_category(
    *,
    name: str,
    slug: str,
    description: str = "",
    icon: str = "",
    display_order: int = 0,
) -> RecipeCategory:
    """Create a category.

    Args:
        name: Display name.
        slug: URL-safe identifier.
        description: Optional short description.
        icon: Optional frontend icon key.
        display_order: Sort weight; lower sorts first.

    Returns:
        The created category.
    """
    return RecipeCategory.objects.create(
        name=name,
        slug=slug,
        description=description,
        icon=icon,
        display_order=display_order,
    )


def update_category(
    *, category: RecipeCategory, changes: Mapping[str, Any]
) -> RecipeCategory:
    """Apply changes to a category in a single UPDATE.

    Args:
        category: The category to update.
        changes: Field name to new value.

    Returns:
        The updated category.
    """
    if not changes:
        return category

    for field, value in changes.items():
        setattr(category, field, value)
    category.save(update_fields=[*changes.keys(), "updated_at"])
    return category
