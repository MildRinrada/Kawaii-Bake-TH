"""Business logic for recipes.

Services take primitives and return domain objects. They never touch
``request``, never render, and never query the ORM directly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction

from apps.recipe_categories.selectors import category_selector
from apps.recipes.exceptions import (
    InvalidCategoryError,
    RecipeNotVisibleError,
    SlugImmutableError,
    SlugTakenError,
)
from apps.recipes.models import Recipe
from apps.recipes.permissions.recipe_permissions import (
    can_delete_recipe,
    can_edit_recipe,
)
from apps.recipes.repositories import (
    ingredient_repository,
    nutrition_repository,
    recipe_repository,
    step_repository,
)
from apps.recipes.selectors import recipe_selector
from apps.recipes.services import nutrition_service
from apps.recipes.utils import build_slug_base
from apps.recipes.validators import (
    ingredient_validator,
    recipe_validator,
    step_validator,
)

# Fields a client may set through create or update.
#
# `status` is deliberately ABSENT: publishing must run the completeness checks
# in `publish_service`, and letting `status` through to a plain `setattr` here
# would route every publish around them.
#
# `visibility` IS editable, because it is a plain field with no precondition —
# a recipe may be made private at any moment, in any state.
RECIPE_EDITABLE_FIELDS = frozenset(
    {
        "title",
        "summary",
        "description",
        "difficulty",
        "visibility",
        "prep_minutes",
        "cook_minutes",
        "servings",
        "cover_image",
    }
)


def _resolve_category_ids(*, slugs: Sequence[str]) -> list[int]:
    """Translate category slugs into primary keys.

    Args:
        slugs: Requested category slugs.

    Returns:
        The matching primary keys.

    Raises:
        InvalidCategoryError: If any slug is unknown or inactive.
    """
    if not slugs:
        return []

    resolved = category_selector.resolve_slugs(slugs=slugs)
    missing = [slug for slug in slugs if slug not in resolved]
    if missing:
        # The category app returns what it found; naming the difference an
        # error is this app's decision, so this app raises its own exception.
        raise InvalidCategoryError(details={"category_slugs": sorted(missing)})
    return [resolved[slug] for slug in slugs]


def _core_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the editable recipe columns from a payload."""
    return {key: value for key, value in data.items() if key in RECIPE_EDITABLE_FIELDS}


def create_recipe(*, author_id: int, data: Mapping[str, Any]) -> Recipe:
    """Create a recipe with its ingredients, steps and nutrition.

    Args:
        author_id: Primary key of the author.
        data: Validated payload.

    Returns:
        The created recipe, re-read through the detail selector.

    Raises:
        InvalidCategoryError: If a category slug is unknown.
        django.core.exceptions.ValidationError: If a domain rule fails.
    """
    recipe_validator.validate_core(data)
    ingredients = list(data.get("ingredients") or [])
    steps = list(data.get("steps") or [])
    ingredient_validator.validate_lines(ingredients)
    step_validator.validate_steps(steps)

    category_ids = _resolve_category_ids(slugs=data.get("category_slugs") or [])

    fields = _core_fields(data)
    fields["total_minutes"] = (data.get("prep_minutes") or 0) + (
        data.get("cook_minutes") or 0
    )

    with transaction.atomic():
        recipe = recipe_repository.create_recipe(
            author_id=author_id,
            slug_base=build_slug_base(data["title"]),
            **fields,
        )
        recipe_repository.set_categories(recipe=recipe, category_ids=category_ids)
        ingredient_repository.replace_ingredients(recipe=recipe, lines=ingredients)
        step_repository.replace_steps(recipe=recipe, steps=steps)
        if data.get("nutrition"):
            nutrition_service.set_nutrition(recipe=recipe, values=data["nutrition"])

    # Re-read so the response carries the same prefetched shape a later GET
    # would return. Serialising the freshly built instance would issue a query
    # per relation, and could return a subtly different payload.
    return _require_detail(slug=recipe.slug, viewer_id=author_id)


def update_recipe(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False, data: Mapping[str, Any]
) -> Recipe:
    """Apply a partial update to a recipe.

    Absent keys are left unchanged. A supplied ``ingredients`` or ``steps`` array
    **replaces** that collection wholesale.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload.

    Returns:
        The updated recipe, re-read through the detail selector.

    Raises:
        RecipeNotVisibleError: If the recipe is absent or the caller may not edit it.
        SlugImmutableError: If the slug of a published recipe would change.
        InvalidCategoryError: If a category slug is unknown.
    """
    recipe = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    recipe_validator.validate_core(data)

    if "slug" in data and data["slug"] != recipe.slug:
        if recipe.slug_is_frozen and not viewer_is_staff:
            raise SlugImmutableError
        if recipe_selector.slug_exists(slug=data["slug"], exclude_pk=recipe.pk):
            raise SlugTakenError(details={"slug": ["Already in use."]})

    ingredients = data.get("ingredients")
    steps = data.get("steps")
    if ingredients is not None:
        ingredient_validator.validate_lines(list(ingredients))
    if steps is not None:
        step_validator.validate_steps(list(steps))

    category_ids: list[int] | None = None
    if "category_slugs" in data:
        category_ids = _resolve_category_ids(slugs=data["category_slugs"])

    changes = _core_fields(data)
    if "slug" in data:
        changes["slug"] = data["slug"]
    if "prep_minutes" in data or "cook_minutes" in data:
        prep = data.get("prep_minutes", recipe.prep_minutes)
        cook = data.get("cook_minutes", recipe.cook_minutes)
        changes["total_minutes"] = prep + cook

    with transaction.atomic():
        recipe_repository.update_recipe(recipe=recipe, changes=changes)
        if category_ids is not None:
            recipe_repository.set_categories(recipe=recipe, category_ids=category_ids)
        if ingredients is not None:
            ingredient_repository.replace_ingredients(
                recipe=recipe, lines=list(ingredients)
            )
        if steps is not None:
            step_repository.replace_steps(recipe=recipe, steps=list(steps))
        if "nutrition" in data:
            if data["nutrition"] is None:
                nutrition_repository.clear_nutrition(recipe=recipe)
            else:
                nutrition_service.set_nutrition(recipe=recipe, values=data["nutrition"])

    return _require_detail(
        slug=changes.get("slug", recipe.slug),
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    )


def delete_recipe(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> None:
    """Permanently delete a recipe.

    Archiving is the reversible option and is a separate, explicit action;
    overloading DELETE with soft-delete semantics would surprise callers.

    Stored files are removed explicitly, because Django deletes no files when a
    row is deleted — every recipe deleted without this would orphan its cover
    and gallery images in storage forever.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        RecipeNotVisibleError: If the recipe is absent or the caller may not delete it.
    """
    recipe = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if not can_delete_recipe(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError

    files = [recipe.cover_image] if recipe.cover_image else []
    files += [image.image for image in recipe.images.all() if image.image]
    files += [step.image for step in recipe.steps.all() if step.image]

    recipe_repository.delete_recipe(recipe=recipe)

    for stored in files:
        stored.delete(save=False)


def get_recipe(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Recipe:
    """Fetch a recipe for display.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The recipe.

    Raises:
        RecipeNotVisibleError: If it does not exist or is not visible.
    """
    return _require_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def _require_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Recipe:
    """Fetch a recipe or raise the 404 domain error."""
    recipe = recipe_selector.get_recipe_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None:
        raise RecipeNotVisibleError
    return recipe


def _require_editable(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Recipe:
    """Fetch a recipe the caller is allowed to modify.

    "Not found" and "not yours" both raise the same 404, so the endpoint cannot
    be used to discover which slugs exist.
    """
    recipe = recipe_selector.get_editable_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None:
        raise RecipeNotVisibleError
    if not can_edit_recipe(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError
    return recipe
