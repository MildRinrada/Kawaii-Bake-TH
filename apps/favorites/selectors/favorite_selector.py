"""Read-side queries for favorites."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.courses.selectors import course_visibility
from apps.favorites.constants import FavoriteTargetKind
from apps.favorites.models import Favorite
from apps.recipes.selectors import recipe_visibility


def list_favorites(
    *,
    user_id: int,
    viewer_is_staff: bool = False,
    kind: str = "",
) -> QuerySet[Favorite]:
    """The user's favorites, currently-visible targets only, newest first.

    Composes both content apps' **detail** visibility rules across the join
    via the prefix-parameterised Q builders (ADR 0009 mechanism #2)  one
    rule per app, one implementation, applied here without importing a model.
    A favorited recipe that has since gone private silently leaves the list
    (and returns if it comes back); an archived course a student is enrolled
    in stays, because the courses rule already says so.

    ``distinct()`` because the archived-but-enrolled branch joins enrollments.

    Args:
        user_id: Primary key of the favorites' owner (always the viewer).
        viewer_is_staff: Whether the viewer is a staff member.
        kind: Optional :class:`FavoriteTargetKind` narrowing.

    Returns:
        A lazy queryset for pagination.
    """
    visible_recipe = Q(recipe__isnull=False) & recipe_visibility.visible_detail_q(
        viewer_id=user_id, viewer_is_staff=viewer_is_staff, prefix="recipe__"
    )
    visible_course = Q(course__isnull=False) & course_visibility.visible_detail_q(
        viewer_id=user_id, viewer_is_staff=viewer_is_staff, prefix="course__"
    )

    if kind == FavoriteTargetKind.RECIPE:
        condition = visible_recipe
    elif kind == FavoriteTargetKind.COURSE:
        condition = visible_course
    else:
        condition = visible_recipe | visible_course

    return (
        Favorite.objects.filter(user_id=user_id)
        .filter(condition)
        .distinct()
        .order_by("-created_at", "-id")
    )


def list_all_favorites(*, kind: str = "", search: str = "") -> QuerySet[Favorite]:
    """Every favorite across users, for the ``IsAdminUser``-gated views.

    No visibility filter: staff see the platform as it is, including
    favorites of content that has since gone private - that is exactly
    the drift an operator investigates.

    Args:
        kind: Optional :class:`FavoriteTargetKind` narrowing.
        search: Matches the owner's username or the target's title.

    Returns:
        A lazy queryset for pagination, newest first.
    """
    queryset = Favorite.objects.select_related(
        "user", "user__profile", "recipe", "course"
    )

    if kind == FavoriteTargetKind.RECIPE:
        queryset = queryset.filter(recipe__isnull=False)
    elif kind == FavoriteTargetKind.COURSE:
        queryset = queryset.filter(course__isnull=False)

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(user__username__icontains=cleaned)
            | Q(recipe__title__icontains=cleaned)
            | Q(course__title__icontains=cleaned)
        )

    return queryset.order_by("-created_at", "-id")


def top_favorited_recipes(*, limit: int = 10) -> list[dict[str, object]]:
    """The most-favorited recipes, computed live.

    Args:
        limit: How many rows to return.

    Returns:
        Rows of ``{id, slug, title, count}``, most favorited first.
    """
    rows = (
        Favorite.objects.filter(recipe__isnull=False)
        .values("recipe_id", "recipe__slug", "recipe__title")
        .annotate(total=Count("id"))
        .order_by("-total", "recipe_id")[:limit]
    )
    return [
        {
            "id": row["recipe_id"],
            "slug": row["recipe__slug"],
            "title": row["recipe__title"],
            "count": row["total"],
        }
        for row in rows
    ]


def top_favorited_courses(*, limit: int = 10) -> list[dict[str, object]]:
    """The most-favorited courses, computed live.

    Args:
        limit: How many rows to return.

    Returns:
        Rows of ``{id, slug, title, count}``, most favorited first.
    """
    rows = (
        Favorite.objects.filter(course__isnull=False)
        .values("course_id", "course__slug", "course__title")
        .annotate(total=Count("id"))
        .order_by("-total", "course_id")[:limit]
    )
    return [
        {
            "id": row["course_id"],
            "slug": row["course__slug"],
            "title": row["course__title"],
            "count": row["total"],
        }
        for row in rows
    ]


def is_favorited(
    *, user_id: int, recipe_id: int | None = None, course_id: int | None = None
) -> bool:
    """Whether the user has favorited the given target."""
    return Favorite.objects.filter(
        user_id=user_id, recipe_id=recipe_id, course_id=course_id
    ).exists()


def favorited_recipe_ids(*, user_id: int) -> list[int]:
    """Recipe ids the user has favorited.

    Part of the public cross-app API (Phase 12)  a taste signal for the
    recommendation app. Ids only, no visibility filter: the caller consumes
    them as aggregate evidence about its own user, never as displayable
    content.

    Args:
        user_id: Primary key of the user.

    Returns:
        The favorited recipe ids.
    """
    return list(
        Favorite.objects.filter(user_id=user_id, recipe__isnull=False).values_list(
            "recipe_id", flat=True
        )
    )


def favorited_course_ids(*, user_id: int) -> list[int]:
    """Course ids the user has favorited.

    Part of the public cross-app API (Phase 12)  see
    :func:`favorited_recipe_ids`.

    Args:
        user_id: Primary key of the user.

    Returns:
        The favorited course ids.
    """
    return list(
        Favorite.objects.filter(user_id=user_id, course__isnull=False).values_list(
            "course_id", flat=True
        )
    )


def favorite_counts_for_recipes(*, ids: list[int]) -> dict[int, int]:
    """How many users favorited each recipe, in one query.

    Part of the public cross-app API (Phase 12)  the popularity fact
    behind recommendation scoring. Computed live, never stored: the
    no-counters rule (Database.md) applies to consumers too.

    Args:
        ids: Recipe primary keys.

    Returns:
        Mapping of recipe id to favorite count (absent = zero).
    """
    if not ids:
        return {}
    rows = (
        Favorite.objects.filter(recipe_id__in=ids)
        .values("recipe_id")
        .annotate(total=Count("id"))
    )
    return {row["recipe_id"]: row["total"] for row in rows}


def favorite_counts_for_courses(*, ids: list[int]) -> dict[int, int]:
    """How many users favorited each course, in one query.

    Part of the public cross-app API (Phase 12)  see
    :func:`favorite_counts_for_recipes`.

    Args:
        ids: Course primary keys.

    Returns:
        Mapping of course id to favorite count (absent = zero).
    """
    if not ids:
        return {}
    rows = (
        Favorite.objects.filter(course_id__in=ids)
        .values("course_id")
        .annotate(total=Count("id"))
    )
    return {row["course_id"]: row["total"] for row in rows}
