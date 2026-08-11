"""Gallery endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.gallery.api.serializers import (
    GalleryImageSerializer,
    GalleryImageUploadSerializer,
    GalleryPostCreateSerializer,
    GalleryPostSerializer,
    GalleryPostUpdateSerializer,
)
from apps.gallery.constants import GalleryPostStatus
from apps.gallery.exceptions import GalleryPostNotFoundError
from apps.gallery.selectors import gallery_selector
from apps.gallery.services import gallery_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


class GalleryListCreateView(PaginatedServiceAPIView):
    """The public gallery feed, or a new post."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        responses={200: GalleryPostSerializer(many=True)}, tags=["gallery"]
    )
    def get(self, request: Request) -> Response:
        """Return a page of visible posts, newest first.

        Filters: ``recipe_id``, ``course_id``, ``category`` (slug),
        ``author`` (username), ``status``. The status filter intersects
        the visibility rule, so it can never widen what a viewer sees -
        it exists for the staff moderation queue and the owner's own
        hidden-posts view.
        """
        viewer_id, viewer_is_staff = _viewer(request)
        params = request.query_params
        requested_status = params.get("status") or None
        if requested_status not in GalleryPostStatus.values:
            requested_status = None
        queryset = gallery_selector.list_posts(
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
            recipe_id=_int_or_none(params.get("recipe_id")),
            course_id=_int_or_none(params.get("course_id")),
            category_slug=params.get("category") or None,
            author_username=params.get("author") or None,
            post_status=requested_status,
        )
        return self.paginated_response(queryset, GalleryPostSerializer)

    @extend_schema(
        request=GalleryPostCreateSerializer,
        responses={201: GalleryPostSerializer},
        tags=["gallery"],
    )
    def post(self, request: Request) -> Response:
        """Create the caller's post."""
        serializer = GalleryPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = gallery_service.create_post(
            author_id=request.user.id, data=serializer.validated_data
        )
        return Response(
            GalleryPostSerializer(post, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class GalleryDetailView(ServiceAPIView):
    """Read, edit or delete one post."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for mutation."""
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: GalleryPostSerializer}, tags=["gallery"])
    def get(self, request: Request, post_id: int) -> Response:
        """Return one post under the same rule as the list."""
        viewer_id, viewer_is_staff = _viewer(request)
        post = gallery_selector.get_post(
            post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        if post is None:
            raise GalleryPostNotFoundError
        return Response(
            GalleryPostSerializer(post, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=GalleryPostUpdateSerializer,
        responses={200: GalleryPostSerializer},
        tags=["gallery"],
    )
    def patch(self, request: Request, post_id: int) -> Response:
        """Edit caption/status/references, optionally reorder images."""
        serializer = GalleryPostUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = gallery_service.update_post(
            post_id=post_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            GalleryPostSerializer(post, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["gallery"])
    def delete(self, request: Request, post_id: int) -> Response:
        """Hard-delete the post; its media files go with it."""
        gallery_service.delete_post(
            post_id=post_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class GalleryImageCreateView(ServiceAPIView):
    """Upload one image to a post."""

    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request=GalleryImageUploadSerializer,
        responses={201: GalleryImageSerializer},
        tags=["gallery"],
    )
    def post(self, request: Request, post_id: int) -> Response:
        """Attach one validated image to the caller's post."""
        serializer = GalleryImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = gallery_service.add_image(
            post_id=post_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            image=serializer.validated_data["image"],
        )
        return Response(
            GalleryImageSerializer(image, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class GalleryImageDeleteView(ServiceAPIView):
    """Delete one image from a post."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None}, tags=["gallery"])
    def delete(self, request: Request, post_id: int, image_id: int) -> Response:
        """Remove the image row and its stored file."""
        gallery_service.remove_image(
            post_id=post_id,
            image_id=image_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _int_or_none(raw: str | None) -> int | None:
    """Parse an optional positive-int query parameter, ignoring junk."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
