"""Gallery interaction endpoints: likes and comments (ADR 0032)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.gallery.api.serializers import (
    GalleryCommentCreateSerializer,
    GalleryCommentSerializer,
    GalleryLikeResultSerializer,
)
from apps.gallery.exceptions import GalleryPostNotFoundError
from apps.gallery.selectors import gallery_selector
from apps.gallery.services import interaction_service


class GalleryLikeView(ServiceAPIView):
    """Like or unlike one post."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None, responses={200: GalleryLikeResultSerializer}, tags=["gallery"]
    )
    def post(self, request: Request, post_id: int) -> Response:
        """Like the post (idempotent - liking twice stays one like)."""
        interaction_service.like_post(
            post_id=post_id,
            user_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            {"liked": True, "like_count": gallery_selector.like_count(post_id=post_id)},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: GalleryLikeResultSerializer}, tags=["gallery"]
    )
    def delete(self, request: Request, post_id: int) -> Response:
        """Remove the caller's like (idempotent)."""
        interaction_service.unlike_post(
            post_id=post_id,
            user_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            {
                "liked": False,
                "like_count": gallery_selector.like_count(post_id=post_id),
            },
            status=status.HTTP_200_OK,
        )


class GalleryCommentListCreateView(PaginatedServiceAPIView):
    """Read a post's comments, or add one."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for commenting only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        responses={200: GalleryCommentSerializer(many=True)}, tags=["gallery"]
    )
    def get(self, request: Request, post_id: int) -> Response:
        """Return the post's comments, oldest first.

        The post's own visibility gates the list: a hidden post 404s
        here rather than returning an empty page, so a stranger cannot
        confirm that a hidden post exists.
        """
        viewer_id = request.user.id if request.user.is_authenticated else None
        viewer_is_staff = (
            request.user.is_staff if request.user.is_authenticated else False
        )
        post = gallery_selector.get_post(
            post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        if post is None:
            raise GalleryPostNotFoundError
        return self.paginated_response(
            gallery_selector.list_comments(post_id=post_id), GalleryCommentSerializer
        )

    @extend_schema(
        request=GalleryCommentCreateSerializer,
        responses={201: GalleryCommentSerializer},
        tags=["gallery"],
    )
    def post(self, request: Request, post_id: int) -> Response:
        """Add the caller's comment and notify the post's author."""
        serializer = GalleryCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = interaction_service.add_comment(
            post_id=post_id,
            author_id=request.user.id,
            body=serializer.validated_data["body"],
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            GalleryCommentSerializer(
                comment, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class GalleryCommentDeleteView(ServiceAPIView):
    """Remove one comment."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None}, tags=["gallery"])
    def delete(self, request: Request, comment_id: int) -> Response:
        """Delete a comment as its author, the post's owner, or staff."""
        interaction_service.delete_comment(
            comment_id=comment_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
