"""Gallery routes, mounted at ``/api/v1/gallery/``."""

from __future__ import annotations

from django.urls import path

from apps.gallery.api.views.gallery_views import (
    GalleryDetailView,
    GalleryImageCreateView,
    GalleryImageDeleteView,
    GalleryListCreateView,
)
from apps.gallery.api.views.interaction_views import (
    GalleryCommentDeleteView,
    GalleryCommentListCreateView,
    GalleryLikeView,
)

app_name = "gallery"

urlpatterns = [
    path("", GalleryListCreateView.as_view(), name="list"),
    path("<int:post_id>/", GalleryDetailView.as_view(), name="detail"),
    path(
        "<int:post_id>/images/",
        GalleryImageCreateView.as_view(),
        name="image-create",
    ),
    path(
        "<int:post_id>/images/<int:image_id>/",
        GalleryImageDeleteView.as_view(),
        name="image-delete",
    ),
    # Interactions (ADR 0032). `comments/<id>/` is routed before the
    # post-scoped patterns cannot claim it - a comment id is global.
    path("<int:post_id>/like/", GalleryLikeView.as_view(), name="like"),
    path(
        "<int:post_id>/comments/",
        GalleryCommentListCreateView.as_view(),
        name="comment-list",
    ),
    path(
        "comments/<int:comment_id>/",
        GalleryCommentDeleteView.as_view(),
        name="comment-delete",
    ),
]
