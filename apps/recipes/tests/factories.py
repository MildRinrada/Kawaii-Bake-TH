"""Test data builders for the recipe domain.

Thai strings appear here from the first commit on purpose. ``slugify`` without
``allow_unicode``, Django's ``<slug:>`` URL converter and PostgreSQL full-text
tokenisation all fail on Thai, and all three failures are invisible when the
fixtures are English.
"""

from __future__ import annotations

from itertools import count
from typing import Any

from apps.recipe_categories.models import RecipeCategory
from apps.recipes.constants import Difficulty, RecipeStatus, RecipeVisibility
from apps.recipes.models import Recipe, RecipeImage, RecipeIngredient, RecipeStep
from apps.recipes.utils import normalize_ingredient_name

# Real Thai bakery vocabulary — croissant, chocolate, macaron, wheat flour.
THAI_TITLE = "ครัวซองต์ไส้ช็อกโกแลต"
THAI_SEARCH_TERM = "ช็อกโกแลต"
THAI_INGREDIENT = "แป้งสาลีอเนกประสงค์"

_sequence = count(1)


def create_category(*, slug: str | None = None, **extra: Any) -> RecipeCategory:
    """Get or create a category.

    ``get_or_create`` rather than ``create``: migration ``0002`` seeds the real
    taxonomy (``cake``, ``bread``, …) into every test database, so a test asking
    for one of those slugs must reuse the seeded row rather than collide with it.
    """
    index = next(_sequence)
    category, _ = RecipeCategory.objects.get_or_create(
        slug=slug or f"category-{index}",
        defaults={"name": extra.pop("name", f"Category {index}"), **extra},
    )
    return category


def create_recipe(
    *,
    author: Any,
    title: str | None = None,
    slug: str | None = None,
    status: str = RecipeStatus.DRAFT,
    visibility: str = RecipeVisibility.PUBLIC,
    categories: list[RecipeCategory] | None = None,
    with_ingredients: bool = False,
    with_steps: bool = False,
    **extra: Any,
) -> Recipe:
    """Create a recipe in a given state.

    Args:
        author: The owning user.
        title: Recipe title; generated when omitted.
        slug: Explicit slug; derived from the sequence when omitted.
        status: A :class:`RecipeStatus` value.
        visibility: A :class:`RecipeVisibility` value.
        categories: Categories to assign.
        with_ingredients: Whether to add one ingredient line.
        with_steps: Whether to add one step.
        **extra: Additional model field values.

    Returns:
        The created recipe.
    """
    index = next(_sequence)
    prep = extra.pop("prep_minutes", 10)
    cook = extra.pop("cook_minutes", 20)

    recipe = Recipe.objects.create(
        author=author,
        title=title or f"Recipe {index}",
        slug=slug or f"recipe-{index}",
        summary=extra.pop("summary", "A tasty bake."),
        difficulty=extra.pop("difficulty", Difficulty.EASY),
        prep_minutes=prep,
        cook_minutes=cook,
        total_minutes=prep + cook,
        servings=extra.pop("servings", 4),
        status=status,
        visibility=visibility,
        published_at=extra.pop("published_at", None),
        **extra,
    )

    if categories:
        recipe.categories.set(categories)
    if with_ingredients:
        add_ingredient(recipe=recipe)
    if with_steps:
        add_step(recipe=recipe)
    return recipe


def create_published_recipe(**kwargs: Any) -> Recipe:
    """Create a published, publicly visible recipe."""
    from django.utils import timezone

    kwargs.setdefault("status", RecipeStatus.PUBLISHED)
    kwargs.setdefault("visibility", RecipeVisibility.PUBLIC)
    kwargs.setdefault("published_at", timezone.now())
    return create_recipe(**kwargs)


def add_ingredient(*, recipe: Recipe, name: str = "Butter", **extra: Any) -> RecipeIngredient:
    """Add one ingredient line to a recipe."""
    return RecipeIngredient.objects.create(
        recipe=recipe,
        name=name,
        normalized_name=normalize_ingredient_name(name),
        quantity=extra.pop("quantity", 100),
        unit=extra.pop("unit", "g"),
        position=extra.pop("position", 1),
        **extra,
    )


def add_step(*, recipe: Recipe, body: str = "Mix everything.", **extra: Any) -> RecipeStep:
    """Add one step to a recipe."""
    return RecipeStep.objects.create(
        recipe=recipe, body=body, position=extra.pop("position", 1), **extra
    )


def add_image(*, recipe: Recipe, **extra: Any) -> RecipeImage:
    """Add one gallery image row to a recipe."""
    return RecipeImage.objects.create(
        recipe=recipe,
        image=extra.pop("image", "recipes/gallery/test.jpg"),
        position=extra.pop("position", 1),
        **extra,
    )


def make_publishable(recipe: Recipe, *, category: RecipeCategory | None = None) -> Recipe:
    """Give a recipe everything ``assert_publishable`` requires."""
    add_ingredient(recipe=recipe)
    add_step(recipe=recipe)
    recipe.categories.set([category or create_category()])
    recipe.cover_image = "recipes/covers/test.jpg"
    recipe.save(update_fields=["cover_image"])
    return recipe
