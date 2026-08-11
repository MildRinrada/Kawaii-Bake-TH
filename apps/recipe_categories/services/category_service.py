"""Business logic for recipe categories.

Public reads plus the staff-only curation operations behind
``/api/v1/admin/recipe-categories/``. Authorisation (``IsAdminUser``) is the
view's job; these functions enforce the domain rules so any future caller
(management command, import) gets the same guarantees.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.db.models import QuerySet
from django.utils.text import slugify

from apps.recipe_categories.exceptions import (
    CategoryNotFoundError,
    DuplicateCategorySlugError,
)
from apps.recipe_categories.models import RecipeCategory
from apps.recipe_categories.repositories import category_repository
from apps.recipe_categories.selectors import category_selector
from apps.recipe_categories.validators.category_validator import (
    validate_category_image,
)

logger = logging.getLogger(__name__)

CATEGORY_EDITABLE_FIELDS = frozenset(
    {"name", "slug", "description", "icon", "display_order", "is_active", "image"}
)


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


def list_all_categories() -> QuerySet[RecipeCategory]:
    """Return every category, inactive included, for the admin surface.

    Returns:
        A lazy queryset annotated with ``recipe_count``.
    """
    return category_selector.list_categories(include_inactive=True)


def _require_category(category_id: int) -> RecipeCategory:
    category = category_selector.get_by_id(category_id=category_id)
    if category is None:
        raise CategoryNotFoundError
    return category


def _require_free_slug(slug: str, *, exclude_id: int | None = None) -> None:
    existing = category_selector.get_by_slug(slug=slug)
    if existing is not None and existing.id != exclude_id:
        raise DuplicateCategorySlugError


def create_category(
    *, actor_id: int, name: str, slug: str = "", **fields: Any
) -> RecipeCategory:
    """Create a category on behalf of a staff member.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        name: Display name.
        slug: URL identifier; derived from the name when omitted.
        **fields: Optional ``description``, ``icon``, ``display_order``,
            ``is_active``, ``image``.

    Returns:
        The created category, annotated with ``recipe_count``.

    Raises:
        DuplicateCategorySlugError: If the slug is already taken.
        django.core.exceptions.ValidationError: If the image is invalid.
    """
    cleaned_slug = (slug or "").strip() or slugify(name, allow_unicode=True)
    _require_free_slug(cleaned_slug)

    image = fields.get("image")
    if image:
        validate_category_image(image)

    category = category_repository.create_category(
        name=name.strip(),
        slug=cleaned_slug,
        description=fields.get("description", ""),
        icon=fields.get("icon", ""),
        display_order=fields.get("display_order", 0),
        is_active=fields.get("is_active", True),
        image=image,
    )
    logger.info(
        "category created", extra={"category_id": category.id, "actor_id": actor_id}
    )
    return _require_category(category.id)


def update_category(
    *, actor_id: int, category_id: int, changes: Mapping[str, Any]
) -> RecipeCategory:
    """Validate and apply changes to a category.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        category_id: The category to update.
        changes: Submitted field values; unknown keys are ignored.

    Returns:
        The updated category, annotated with ``recipe_count``.

    Raises:
        CategoryNotFoundError: If the category does not exist.
        DuplicateCategorySlugError: If a rename collides with another slug.
        django.core.exceptions.ValidationError: If the image is invalid.
    """
    category = _require_category(category_id)
    accepted = dict(
        (k, v) for k, v in changes.items() if k in CATEGORY_EDITABLE_FIELDS
    )

    if "name" in accepted:
        accepted["name"] = accepted["name"].strip()
    if "slug" in accepted:
        accepted["slug"] = accepted["slug"].strip()
        _require_free_slug(accepted["slug"], exclude_id=category.id)

    # An explicit null on the image means "remove it"; the column is NOT
    # NULL, so the empty string is what an unset FileField holds.
    if "image" in accepted:
        if accepted["image"] is None:
            accepted["image"] = ""
        else:
            validate_category_image(accepted["image"])

    category_repository.update_category(category=category, changes=accepted)
    logger.info(
        "category updated",
        extra={
            "category_id": category.id,
            "actor_id": actor_id,
            "fields": sorted(accepted.keys()),
        },
    )
    return _require_category(category.id)


def delete_category(*, actor_id: int, category_id: int) -> None:
    """Delete a category.

    Assignments to recipes and courses are join rows and vanish with the
    category; the content itself is untouched.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        category_id: The category to delete.

    Raises:
        CategoryNotFoundError: If the category does not exist.
    """
    category = _require_category(category_id)
    category_repository.delete_category(category=category)
    logger.info(
        "category deleted",
        extra={"category_id": category_id, "actor_id": actor_id},
    )
