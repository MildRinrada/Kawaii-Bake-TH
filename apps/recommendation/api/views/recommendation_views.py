"""The recommendation feed endpoints."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView
from apps.courses.api.serializers import CourseListItemSerializer
from apps.courses.selectors import course_selector
from apps.recipes.api.serializers import RecipeListItemSerializer
from apps.recipes.selectors import recipe_selector
from apps.recommendation.api.serializers import (
    RecommendationListQuerySerializer,
    RecommendedCourseSerializer,
    RecommendedRecipeSerializer,
)
from apps.recommendation.services import recommendation_service
from apps.recommendation.services.recommendation_service import RecommendationItem


class _RecommendationsView(PaginatedServiceAPIView):
    """Shared shape of both feeds.

    Optional auth, like the content listings themselves: an authenticated
    viewer gets a personalized ranking, an anonymous one the deterministic
    cold-start ranking — same pipeline, same response shape. The service
    ranks the bounded candidate pool; pagination slices the ranked list;
    only the page's cards are then batch-fetched through the content app's
    own selector and serializer (the favorites stitching pattern).
    """

    permission_classes = (AllowAny,)

    def _viewer_id(self, request: Request) -> int | None:
        return request.user.id if request.user.is_authenticated else None

    def _paginate_items(
        self, request: Request, items: list[RecommendationItem]
    ) -> list[RecommendationItem]:
        query = RecommendationListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return self.paginator.paginate_queryset(items, request, view=self) or []


class RecipeRecommendationsView(_RecommendationsView):
    """GET /recommendations/recipes/ — the ranked recipe feed."""

    @extend_schema(
        parameters=[RecommendationListQuerySerializer],
        responses={200: RecommendedRecipeSerializer(many=True)},
        tags=["recommendations"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of recommended recipes with reason codes."""
        viewer_id = self._viewer_id(request)
        items = recommendation_service.recommend_recipes(viewer_id=viewer_id)
        page = self._paginate_items(request, items)

        cards: dict[int, Any] = {}
        if page:
            recipes = recipe_selector.list_by_ids(
                ids=[item.target_id for item in page],
                viewer_id=viewer_id,
                viewer_is_staff=request.user.is_staff,
            )
            cards = {
                recipe.pk: RecipeListItemSerializer(
                    recipe, context=self.get_serializer_context()
                ).data
                for recipe in recipes
            }
        data = RecommendedRecipeSerializer(
            page,
            many=True,
            context={**self.get_serializer_context(), "recipe_cards": cards},
        ).data
        return self.paginator.get_paginated_response(data)


class CourseRecommendationsView(_RecommendationsView):
    """GET /recommendations/courses/ — the ranked course feed."""

    @extend_schema(
        parameters=[RecommendationListQuerySerializer],
        responses={200: RecommendedCourseSerializer(many=True)},
        tags=["recommendations"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of recommended courses with reason codes."""
        viewer_id = self._viewer_id(request)
        items = recommendation_service.recommend_courses(viewer_id=viewer_id)
        page = self._paginate_items(request, items)

        cards: dict[int, Any] = {}
        if page:
            courses = course_selector.list_viewable_by_ids(
                ids=[item.target_id for item in page],
                viewer_id=viewer_id,
                viewer_is_staff=request.user.is_staff,
            )
            cards = {
                course.pk: CourseListItemSerializer(
                    course, context=self.get_serializer_context()
                ).data
                for course in courses
            }
        data = RecommendedCourseSerializer(
            page,
            many=True,
            context={**self.get_serializer_context(), "course_cards": cards},
        ).data
        return self.paginator.get_paginated_response(data)
