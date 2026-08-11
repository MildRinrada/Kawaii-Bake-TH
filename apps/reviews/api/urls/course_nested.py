"""Review routes nested under ``/api/v1/courses/``  mounted by config."""

from __future__ import annotations

from django.urls import path

from apps.reviews.api.views.review_views import (
    CourseRatingView,
    CourseReviewListCreateView,
)

app_name = "course_reviews"

urlpatterns = [
    path(
        "<str:slug>/reviews/",
        CourseReviewListCreateView.as_view(),
        name="list",
    ),
    path("<str:slug>/rating/", CourseRatingView.as_view(), name="rating"),
]
