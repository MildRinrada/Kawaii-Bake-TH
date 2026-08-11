"""Staff-only recommendation-debug endpoints.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.

ADR 0028 amends the ADR 0018 §10 privacy stance for exactly this seam:
the public feed still never carries a score, but an operator answering
"why was this recommended to that user?" may see the ranked list with
its numbers. Raw behavior (what the user favorited, reviewed, enrolled
in) still never crosses this boundary - only scores and reason codes.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.courses.selectors import course_selector
from apps.recipes.selectors import recipe_selector
from apps.recommendation import constants
from apps.recommendation.api.serializers.admin_serializers import (
    EngineConfigSerializer,
    PreviewFilterSerializer,
    PreviewResultSerializer,
)
from apps.recommendation.services import recommendation_service
from apps.users.exceptions import UserNotFoundError
from apps.users.selectors import user_selector

# The preview is a debugging lens, not a feed: the head of the ranking is
# where every real page comes from, so that is all it shows.
PREVIEW_LIMIT = 50


class AdminRecommendationPreviewView(ServiceAPIView):
    """Reproduce one user's ranked feed, scores attached."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("username", str),
            OpenApiParameter("kind", str),
        ],
        responses={200: PreviewResultSerializer},
        tags=["recommendations-admin"],
    )
    def get(self, request: Request) -> Response:
        """Run the live pipeline as the given user and keep the scores.

        Cards are resolved with the *target user* as the viewer, so the
        preview shows exactly what that user's feed would show - a staff
        identity here would quietly widen visibility.

        Raises:
            UserNotFoundError: If no account has that username.
        """
        filters = PreviewFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        username = filters.validated_data["username"]
        kind = filters.validated_data.get("kind") or "recipes"

        target = user_selector.get_by_username(username=username)
        if target is None:
            raise UserNotFoundError

        ranked = recommendation_service.preview_scored(
            kind=kind, target_user_id=target.id
        )[:PREVIEW_LIMIT]
        ids = [item.id for item in ranked]
        if kind == "courses":
            rows = course_selector.list_viewable_by_ids(
                ids=ids, viewer_id=target.id, viewer_is_staff=False
            )
        else:
            rows = recipe_selector.list_by_ids(
                ids=ids, viewer_id=target.id, viewer_is_staff=False
            )
        cards = {row.id: row for row in rows}

        items = [
            {
                "rank": index + 1,
                "target_id": item.id,
                "slug": getattr(cards.get(item.id), "slug", None),
                "title": getattr(cards.get(item.id), "title", None),
                "score": round(item.score, 3),
                "reasons": list(item.reasons),
                "primary_category": item.primary_category,
            }
            for index, item in enumerate(ranked)
        ]
        return Response(
            {
                "username": target.username,
                "kind": kind,
                "count": len(items),
                "items": items,
            },
            status=status.HTTP_200_OK,
        )


class AdminRecommendationConfigView(ServiceAPIView):
    """The engine's tunable weights, for interpreting preview scores."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: EngineConfigSerializer}, tags=["recommendations-admin"]
    )
    def get(self, request: Request) -> Response:
        """Return the scoring constants as they are deployed."""
        return Response(
            {
                "candidate_pool_size": constants.CANDIDATE_POOL_SIZE,
                "positive_review_min_rating": (
                    constants.POSITIVE_REVIEW_MIN_RATING
                ),
                "w_category_match": constants.W_CATEGORY_MATCH,
                "category_score_cap": constants.CATEGORY_SCORE_CAP,
                "w_author_affinity": constants.W_AUTHOR_AFFINITY,
                "w_rating_average": constants.W_RATING_AVERAGE,
                "w_rating_count": constants.W_RATING_COUNT,
                "rating_count_cap": constants.RATING_COUNT_CAP,
                "w_favorite_count": constants.W_FAVORITE_COUNT,
                "favorite_count_cap": constants.FAVORITE_COUNT_CAP,
                "w_recency": constants.W_RECENCY,
                "recency_window_days": constants.RECENCY_WINDOW_DAYS,
                "w_difficulty_fit": constants.W_DIFFICULTY_FIT,
                "diversity_penalty": constants.DIVERSITY_PENALTY,
                "highly_rated_min_average": constants.HIGHLY_RATED_MIN_AVERAGE,
                "highly_rated_min_count": constants.HIGHLY_RATED_MIN_COUNT,
                "popular_min_favorites": constants.POPULAR_MIN_FAVORITES,
            },
            status=status.HTTP_200_OK,
        )
