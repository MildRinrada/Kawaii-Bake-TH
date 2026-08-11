"""Ingredient substitution lookup for one recipe."""

from __future__ import annotations

from dataclasses import dataclass

from apps.common.utils.text import normalize_ingredient_name
from apps.recipes.selectors import ingredient_selector
from apps.recommendation.exceptions import RecipeNotFoundError
from apps.recommendation.rules import substitution_rules
from apps.recommendation.rules.substitution_rules import SubstitutionOption


@dataclass(frozen=True)
class IngredientSubstitution:
    """One recipe ingredient with its substitution candidates."""

    ingredient: str
    normalized: str
    substitutions: tuple[SubstitutionOption, ...]


def for_recipe(
    *,
    slug: str,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    ingredient: str = "",
) -> list[IngredientSubstitution]:
    """Substitution candidates for a recipe's ingredients.

    Scoped to the recipe on purpose: the endpoint answers "what can I swap
    *in this recipe*", so an ingredient the recipe does not contain yields
    an empty list  a correct answer, not an error. An ingredient the
    registry does not know yields the line with zero candidates: an honest
    empty, never a guess (ADR 0018 §12).

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        ingredient: Optional free-text filter; normalised with the same rule
            ``recipes`` stores, so matching is exact, not fuzzy.

    Returns:
        One entry per distinct ingredient, in the recipe's display order.

    Raises:
        RecipeNotFoundError: If the recipe is absent or hidden from this
            viewer  indistinguishable, as everywhere else.
    """
    lines = ingredient_selector.lines_for_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if lines is None:
        raise RecipeNotFoundError

    if ingredient:
        # Canonical-key comparison, not raw equality: asking for "butter"
        # must find the recipe's "เนย" line  both fold to one rule key.
        wanted = substitution_rules.canonical_key(
            normalize_ingredient_name(ingredient)
        )
        lines = [
            line
            for line in lines
            if substitution_rules.canonical_key(line.normalized_name) == wanted
        ]

    seen: set[str] = set()
    results: list[IngredientSubstitution] = []
    for line in lines:
        if line.normalized_name in seen:
            continue
        seen.add(line.normalized_name)
        results.append(
            IngredientSubstitution(
                ingredient=line.name,
                normalized=line.normalized_name,
                substitutions=substitution_rules.lookup(line.normalized_name),
            )
        )
    return results
