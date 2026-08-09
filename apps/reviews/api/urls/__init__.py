"""Standalone review routes, mounted at ``/api/v1/reviews/``."""

from __future__ import annotations

from django.urls import path

from apps.reviews.api.views.review_views import ReviewDetailView

app_name = "reviews"

urlpatterns = [
    path("<int:review_id>/", ReviewDetailView.as_view(), name="detail"),
]
