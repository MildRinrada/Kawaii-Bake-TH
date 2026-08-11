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
    is_active: bool = True,
    image: Any = None,
) -> RecipeCategory:
    """Create a category.

    Args:
        name: Display name.
        slug: URL-safe identifier.
        description: Optional short description.
        icon: Optional frontend icon key.
        display_order: Sort weight; lower sorts first.
        is_active: Whether the category appears in listings.
        image: Optional uploaded tile photo.

    Returns:
        The created category.
    """
    return RecipeCategory.objects.create(
        name=name,
        slug=slug,
        description=description,
        icon=icon,
        display_order=display_order,
        is_active=is_active,
        image=image or "",
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

    # Replacing or clearing the tile photo must not leak the old file:
    # Django never deletes stored files on its own.
    old_image = None
    if "image" in changes and category.image:
        old_image = category.image

    for field, value in changes.items():
        setattr(category, field, value)
    category.save(update_fields=[*changes.keys(), "updated_at"])

    if old_image is not None:
        old_image.delete(save=False)
    return category


def delete_category(*, category: RecipeCategory) -> None:
    """Delete a category and its stored tile photo.

    Recipe and course assignments are many-to-many rows, so deleting the
    category only clears the associations - it never deletes content.

    Args:
        category: The category to delete.
    """
    stored = category.image
    category.delete()
    if stored:
        stored.delete(save=False)
