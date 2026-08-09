"""Read-side queries for recipes.

Every entry point starts from a visibility ``Q``; user filters are applied
afterwards and can only narrow the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from django.db.models import Case, IntegerField, Prefetch, QuerySet, Value, When

from apps.recipe_categories.selectors import category_selector
from apps.recipes.constants import (
    DIFFICULTY_RANK,
    ORDERING_MAP,
    Ordering,
    RecipeScope,
)
from apps.recipes.models import Recipe, RecipeImage, RecipeIngredient, RecipeStep
from apps.recipes.selectors.recipe_filters import RecipeListFilters
from apps.recipes.selectors.recipe_visibility import (
    visible_detail_q,
    visible_in_list_q,
)
from apps.recipes.utils import normalize_ingredient_name
from infrastructure.search import get_search_backend


@dataclass(frozen=True)
class RecipeRef:
    """A recipe reference safe to hand across the app boundary.

    The mirror of ``CourseRef`` (ADR 0009): identity for FK writes, the author
    for owner checks, and the state pair — never the model. Added in Phase 5
    for the reviews/favorites target resolution.
    """

    id: int
    slug: str
    title: str
    author_id: int
    status: str
    visibility: str


def get_recipe_ref(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> RecipeRef | None:
    """Fetch a recipe reference for another app.

    Part of the public cross-app API. Returns ``None`` when the recipe is
    absent **or** hidden from this viewer; the caller raises its own domain
    error for that case — never this app's.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A :class:`RecipeRef`, or ``None``.
    """
    row = (
        Recipe.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .values("id", "slug", "title", "author_id", "status", "visibility")
        .first()
    )
    return RecipeRef(**row) if row else None


def _base_list_queryset() -> QuerySet[Recipe]:
    """Return the queryset shape shared by every listing.

    ``defer`` rather than ``only``: ``only`` is an allow-list, so a field
    someone forgets to include costs one extra query **per row**, which
    ``select_related`` does not prevent and which reads like a serializer bug.
    ``defer`` is a deny-list, so a newly added field costs nothing.
    """
    return (
        Recipe.objects.select_related("author", "author__profile")
        .prefetch_related(
            Prefetch("categories", queryset=category_selector.ref_queryset())
        )
        .defer("description")
    )


def _apply_ordering(queryset: QuerySet[Recipe], *, ordering: str) -> QuerySet[Recipe]:
    """Apply an allow-listed ordering to ``queryset``.

    Args:
        queryset: The queryset to order.
        ordering: A value of :class:`Ordering`.

    Returns:
        The ordered queryset.
    """
    if ordering == Ordering.DIFFICULTY:
        queryset = queryset.annotate(
            difficulty_rank=Case(
                *[
                    When(difficulty=value, then=Value(rank))
                    for value, rank in DIFFICULTY_RANK.items()
                ],
                default=Value(max(DIFFICULTY_RANK.values()) + 1),
                output_field=IntegerField(),
            )
        )

    return queryset.order_by(*ORDERING_MAP[ordering])


def _apply_filters(
    queryset: QuerySet[Recipe], *, filters: RecipeListFilters
) -> QuerySet[Recipe]:
    """Apply user-supplied narrowing options.

    Args:
        queryset: The already visibility-restricted queryset.
        filters: The parsed query parameters.

    Returns:
        The narrowed queryset.
    """
    if filters.category_slugs:
        # `.distinct()` is required: a multi-value join on a many-to-many
        # duplicates a recipe once per matching category.
        queryset = queryset.filter(
            categories__slug__in=filters.category_slugs
        ).distinct()

    if filters.difficulty:
        queryset = queryset.filter(difficulty__in=filters.difficulty)

    if filters.max_total_minutes is not None:
        queryset = queryset.filter(total_minutes__lte=filters.max_total_minutes)

    if filters.author_username:
        queryset = queryset.filter(author__username__iexact=filters.author_username)

    if filters.ingredient:
        # Indexed equality on the normalised column, not a leading-wildcard LIKE.
        queryset = queryset.filter(
            ingredients__normalized_name=normalize_ingredient_name(filters.ingredient)
        ).distinct()

    return queryset


def list_recipes(
    *,
    filters: RecipeListFilters,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Recipe]:
    """Build the recipe listing queryset for a viewer.

    Returns a **lazy** queryset: the ORM executes at the API edge, once the
    paginator has applied its slice.

    Args:
        filters: Parsed, validated query parameters.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        An unevaluated queryset of visible recipes.
    """
    queryset = _base_list_queryset().filter(
        visible_in_list_q(
            viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, scope=filters.scope
        )
    )
    queryset = _apply_filters(queryset, filters=filters)

    ordering = filters.ordering

    if filters.search:
        backend = get_search_backend()
        queryset = backend.apply(queryset, term=filters.search)
        if ordering == Ordering.RELEVANCE:
            rank = backend.rank_ordering()
            if rank:
                return queryset.order_by(*rank, *ORDERING_MAP[Ordering.NEWEST])

    # A backend that cannot rank, or a relevance request with no search term,
    # falls back to newest — never to arbitrary database order.
    if ordering == Ordering.RELEVANCE:
        ordering = Ordering.NEWEST
    return _apply_ordering(queryset, ordering=ordering)


def get_recipe_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Recipe | None:
    """Fetch one recipe with everything the detail payload needs.

    Child ordering is declared inside each ``Prefetch`` so there is exactly one
    place it is defined.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The recipe, or ``None`` when it does not exist or is not visible. The
        caller must not distinguish those two cases to the client.
    """
    return (
        Recipe.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .select_related("author", "author__profile", "nutrition")
        .prefetch_related(
            Prefetch("categories", queryset=category_selector.ref_queryset()),
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.order_by("group", "position", "id"),
            ),
            Prefetch("steps", queryset=RecipeStep.objects.order_by("position", "id")),
            Prefetch("images", queryset=RecipeImage.objects.order_by("position", "id")),
        )
        .first()
    )


def get_editable_recipe(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Recipe | None:
    """Fetch a recipe for a write operation, restricted to what the viewer can open.

    Write permission is decided separately, by ``permissions/``. This only
    ensures a caller cannot even name a recipe they are not allowed to see.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The recipe, or ``None``.
    """
    return (
        Recipe.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .first()
    )


def list_by_ids(
    *,
    ids: Sequence[int],
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Recipe]:
    """Fetch specific recipes, preserving the caller's ordering.

    Exists for the future recommendation engine. Without it, that engine would
    reach for ``Recipe.objects.filter(id__in=...)`` and quietly recommend other
    people's drafts and private recipes — this applies the same visibility rule
    as every other read path.

    Args:
        ids: Recipe primary keys, in the order they should be returned.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A queryset ordered to match ``ids``.
    """
    if not ids:
        return Recipe.objects.none()

    ordering = Case(
        *[When(pk=pk, then=Value(index)) for index, pk in enumerate(ids)],
        default=Value(len(ids)),
        output_field=IntegerField(),
    )
    return (
        _base_list_queryset()
        .filter(
            visible_in_list_q(
                viewer_id=viewer_id,
                viewer_is_staff=viewer_is_staff,
                scope=RecipeScope.PUBLIC,
            )
        )
        .filter(pk__in=ids)
        .annotate(requested_order=ordering)
        .order_by("requested_order")
    )


def list_viewable_by_ids(
    *,
    ids: Sequence[int],
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Recipe]:
    """Fetch specific recipes under the **detail** visibility rule.

    Unlike :func:`list_by_ids` (listing rule — public only), this returns
    everything the viewer could open directly: unlisted recipes and their own
    drafts included. Exists for embed/card fetches whose ids were already
    gathered under the detail rule (the favorites list), so the two filters
    agree and a bookmarked unlisted recipe does not vanish from its owner's
    favorites.

    Args:
        ids: Recipe primary keys.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A queryset with the card prefetches applied.
    """
    if not ids:
        return Recipe.objects.none()
    return (
        _base_list_queryset()
        .filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(pk__in=ids)
    )


def get_viewable_by_id(
    *, recipe_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Recipe | None:
    """Fetch one recipe by id under the **detail** visibility rule.

    The pk-addressed mirror of :func:`get_recipe_detail`, added in Phase 7
    for the assistant's context loading — which stores ids, not slugs, and
    needs ingredients and steps. Hidden and absent are the same ``None``.

    Args:
        recipe_id: Primary key of the recipe.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The recipe with ingredients and steps loaded, or ``None``.
    """
    return (
        Recipe.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(pk=recipe_id)
        .prefetch_related(
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.order_by("group", "position", "id"),
            ),
            Prefetch("steps", queryset=RecipeStep.objects.order_by("position", "id")),
        )
        .first()
    )


@dataclass(frozen=True)
class RecipeCandidateFact:
    """The scoring-relevant facts of one publicly listed recipe.

    Part of the public cross-app API (Phase 12). A plain fact row, not the
    model: the recommendation app scores against these and never touches
    ``Recipe``. Everything here already appears on the public card, so
    nothing can leak through it.
    """

    id: int
    author_id: int
    difficulty: str
    published_at: object
    category_slugs: tuple[str, ...]


def public_candidate_facts(*, limit: int) -> list[RecipeCandidateFact]:
    """Facts of the newest publicly listed recipes, for recommendation.

    Applies the **anonymous public listing** rule on purpose — stricter than
    any viewer-specific rule. A recommendation feed must never surface
    unlisted or private content even to viewers who could open it directly,
    so eligibility is decided by the same Q every public list uses, with no
    viewer at all.

    Args:
        limit: Maximum number of candidates, newest first.

    Returns:
        Fact rows, newest first. Two queries regardless of ``limit``.
    """
    rows = list(
        Recipe.objects.filter(visible_in_list_q())
        .order_by("-published_at", "-created_at", "-id")
        .values("id", "author_id", "difficulty", "published_at")[:limit]
    )
    slug_map = category_slugs_for_recipes(ids=[row["id"] for row in rows])
    return [
        RecipeCandidateFact(
            id=row["id"],
            author_id=row["author_id"],
            difficulty=row["difficulty"],
            published_at=row["published_at"],
            category_slugs=slug_map.get(row["id"], ()),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class RecipeSignalFact:
    """Author and categories of a recipe the user has interacted with.

    Part of the public cross-app API (Phase 12). Deliberately **not**
    visibility-filtered: these describe the caller's own history (their
    favorites, their reviews) and are consumed as aggregate interest
    evidence only — never serialized. A favorited recipe that later went
    private still shaped the user's taste.
    """

    author_id: int
    category_slugs: tuple[str, ...]


def signal_facts(*, ids: Sequence[int]) -> dict[int, RecipeSignalFact]:
    """Author and category facts for specific recipes, in one query.

    Args:
        ids: Recipe primary keys from the caller's own interaction history.

    Returns:
        Mapping of recipe id to its fact (absent ids are dropped).
    """
    if not ids:
        return {}
    slugs: dict[int, list[str]] = {}
    authors: dict[int, int] = {}
    for recipe_id, author_id, slug in (
        Recipe.objects.filter(pk__in=ids)
        .values_list("id", "author_id", "categories__slug")
        .order_by("id", "categories__slug")
    ):
        authors[recipe_id] = author_id
        if slug is not None:
            slugs.setdefault(recipe_id, []).append(slug)
    return {
        recipe_id: RecipeSignalFact(
            author_id=author_id, category_slugs=tuple(slugs.get(recipe_id, ()))
        )
        for recipe_id, author_id in authors.items()
    }


def category_slugs_for_recipes(*, ids: Sequence[int]) -> dict[int, tuple[str, ...]]:
    """Category slugs per recipe, in one query.

    Args:
        ids: Recipe primary keys.

    Returns:
        Mapping of recipe id to its sorted category slugs (absent = none).
    """
    if not ids:
        return {}
    grouped: dict[int, list[str]] = {}
    for recipe_id, slug in (
        Recipe.objects.filter(pk__in=ids)
        .exclude(categories__isnull=True)
        .values_list("id", "categories__slug")
        .order_by("id", "categories__slug")
    ):
        grouped.setdefault(recipe_id, []).append(slug)
    return {recipe_id: tuple(slugs) for recipe_id, slugs in grouped.items()}


def slug_exists(*, slug: str, exclude_pk: int | None = None) -> bool:
    """Whether a slug is already taken.

    Args:
        slug: The candidate slug.
        exclude_pk: A recipe to ignore, used when validating an update.

    Returns:
        ``True`` if the slug is in use.
    """
    queryset = Recipe.objects.filter(slug__iexact=slug.strip())
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def count_visible(
    *, viewer_id: int | None = None, viewer_is_staff: bool = False, scope: str = RecipeScope.PUBLIC
) -> int:
    """Count recipes visible to a viewer.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        scope: One of :class:`RecipeScope`.

    Returns:
        The number of visible recipes.
    """
    return Recipe.objects.filter(
        visible_in_list_q(
            viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, scope=scope
        )
    ).count()
