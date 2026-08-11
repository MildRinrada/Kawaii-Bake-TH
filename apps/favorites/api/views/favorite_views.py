"""Favorite endpoints: per-target toggles and the caller's list."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.courses.api.serializers import CourseListItemSerializer
from apps.courses.selectors import course_selector
from apps.favorites.api.serializers import (
    FavoriteItemSerializer,
    FavoriteListQuerySerializer,
)
from apps.favorites.constants import FavoriteTargetKind
from apps.favorites.models import Favorite
from apps.favorites.selectors import favorite_selector
from apps.favorites.services import favorite_service
from apps.recipes.api.serializers import RecipeListItemSerializer
from apps.recipes.selectors import recipe_selector


class _TargetFavoriteView(ServiceAPIView):
    """Toggle one target on or off the caller's favorites."""

    permission_classes = (IsAuthenticated,)
    target_kind = ""

    @extend_schema(request=None, responses={201: None, 200: None}, tags=["favorites"])
    def post(self, request: Request, slug: str) -> Response:
        """Favorite the target. Idempotent: 201 first, 200 after."""
        _favorite, created = favorite_service.favorite(
            user_id=request.user.id, kind=self.target_kind, slug=slug
        )
        return Response(
            {"favorited": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["favorites"])
    def delete(self, request: Request, slug: str) -> Response:
        """Unfavorite the target. Idempotent."""
        favorite_service.unfavorite(
            user_id=request.user.id, kind=self.target_kind, slug=slug
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeFavoriteView(_TargetFavoriteView):
    """Favorite toggle for one recipe."""

    target_kind = FavoriteTargetKind.RECIPE


class CourseFavoriteView(_TargetFavoriteView):
    """Favorite toggle for one course."""

    target_kind = FavoriteTargetKind.COURSE


class MyFavoritesView(PaginatedServiceAPIView):
    """The caller's favorites with target cards embedded."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[FavoriteListQuerySerializer],
        responses={200: FavoriteItemSerializer(many=True)},
        tags=["favorites"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of favorites, newest first, visible targets only.

        Pagination runs on the favorites queryset (already visibility-filtered
        via the content apps' prefix Q builders); the page's target cards are
        then batch-fetched through each app's own card selector  the same
        two-step embed the lesson detail uses, so cards carry their full
        prefetches without joining them through the favorites table.
        """
        query = FavoriteListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        queryset = favorite_selector.list_favorites(
            user_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            kind=query.validated_data.get("type", ""),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        context = {
            **self.get_serializer_context(),
            **self._card_maps(request, page or []),
        }
        data = FavoriteItemSerializer(page, many=True, context=context).data
        return self.paginator.get_paginated_response(data)

    def _card_maps(
        self, request: Request, page: list[Favorite]
    ) -> dict[str, dict[int, Any]]:
        """Batch-fetch and serialize the page's target cards."""
        recipe_ids = [f.recipe_id for f in page if f.recipe_id]
        course_ids = [f.course_id for f in page if f.course_id]
        card_context = self.get_serializer_context()

        recipe_cards: dict[int, Any] = {}
        if recipe_ids:
            recipes = recipe_selector.list_viewable_by_ids(
                ids=recipe_ids,
                viewer_id=request.user.id,
                viewer_is_staff=request.user.is_staff,
            )
            recipe_cards = {
                recipe.pk: RecipeListItemSerializer(
                    recipe, context=card_context
                ).data
                for recipe in recipes
            }

        course_cards: dict[int, Any] = {}
        if course_ids:
            courses = course_selector.list_viewable_by_ids(
                ids=course_ids,
                viewer_id=request.user.id,
                viewer_is_staff=request.user.is_staff,
            )
            course_cards = {
                course.pk: CourseListItemSerializer(
                    course, context=card_context
                ).data
                for course in courses
            }

        return {"recipe_cards": recipe_cards, "course_cards": course_cards}
