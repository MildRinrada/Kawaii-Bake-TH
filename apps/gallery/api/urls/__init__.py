"""Gallery routes, mounted at ``/api/v1/gallery/``."""

from __future__ import annotations

from django.urls import path

from apps.gallery.api.views.gallery_views import (
    GalleryDetailView,
    GalleryImageCreateView,
    GalleryImageDeleteView,
    GalleryListCreateView,
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
]
