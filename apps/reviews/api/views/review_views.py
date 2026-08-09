"""Review endpoints.

The nested list/create/rating views are generated per target kind from one
pair of classes — the target kind is fixed by the URL route, never by client
input.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.reviews.api.serializers import (
    RatingSummarySerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    ReviewUpdateSerializer,
)
from apps.reviews.constants import ReviewTargetKind
from apps.reviews.selectors import rating_selector, review_selector
from apps.reviews.services import review_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


class _TargetReviewListCreateView(PaginatedServiceAPIView):
    """List a target's active reviews, or add the caller's review."""

    permission_classes = (AllowAny,)
    target_kind = ""

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: ReviewSerializer(many=True)}, tags=["reviews"])
    def get(self, request: Request, slug: str) -> Response:
        """Return a page of active reviews, newest first."""
        viewer_id, viewer_is_staff = _viewer(request)
        target_id = review_service.get_rating_context(
            kind=self.target_kind,
            slug=slug,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
        )
        if self.target_kind == ReviewTargetKind.RECIPE:
            queryset = review_selector.list_for_recipe(recipe_id=target_id)
        else:
            queryset = review_selector.list_for_course(course_id=target_id)
        return self.paginated_response(queryset, ReviewSerializer)

    @extend_schema(
        request=ReviewCreateSerializer,
        responses={201: ReviewSerializer},
        tags=["reviews"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Create the caller's review; one active review per target."""
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = review_service.create_review(
            user_id=request.user.id,
            kind=self.target_kind,
            slug=slug,
            data=serializer.validated_data,
        )
        return Response(
            ReviewSerializer(review, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeReviewListCreateView(_TargetReviewListCreateView):
    """Reviews of one recipe."""

    target_kind = ReviewTargetKind.RECIPE


class CourseReviewListCreateView(_TargetReviewListCreateView):
    """Reviews of one course."""

    target_kind = ReviewTargetKind.COURSE


class _TargetRatingView(ServiceAPIView):
    """Read-only rating statistics for one target."""

    permission_classes = (AllowAny,)
    target_kind = ""

    @extend_schema(responses={200: RatingSummarySerializer}, tags=["reviews"])
    def get(self, request: Request, slug: str) -> Response:
        """Return average, count and star distribution over active reviews."""
        viewer_id, viewer_is_staff = _viewer(request)
        target_id = review_service.get_rating_context(
            kind=self.target_kind,
            slug=slug,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
        )
        if self.target_kind == ReviewTargetKind.RECIPE:
            summary = rating_selector.for_recipe(recipe_id=target_id)
        else:
            summary = rating_selector.for_course(course_id=target_id)
        return Response(
            RatingSummarySerializer(summary).data, status=status.HTTP_200_OK
        )


class RecipeRatingView(_TargetRatingView):
    """Rating summary of one recipe."""

    target_kind = ReviewTargetKind.RECIPE


class CourseRatingView(_TargetRatingView):
    """Rating summary of one course."""

    target_kind = ReviewTargetKind.COURSE


class ReviewDetailView(ServiceAPIView):
    """Edit, moderate or soft-delete one review."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=ReviewUpdateSerializer,
        responses={200: ReviewSerializer},
        tags=["reviews"],
    )
    def patch(self, request: Request, review_id: int) -> Response:
        """Owner edits rating/comment; staff may also change ``status``."""
        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = review_service.update_review(
            review_id=review_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            ReviewSerializer(review, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["reviews"])
    def delete(self, request: Request, review_id: int) -> Response:
        """Soft-delete the review; the author may review again afterwards."""
        review_service.delete_review(
            review_id=review_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
