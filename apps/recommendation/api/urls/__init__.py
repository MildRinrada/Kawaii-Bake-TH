"""Routes mounted at ``/api/v1/recommendations/``."""

from __future__ import annotations

from django.urls import path

from apps.recommendation.api.views import (
    CourseRecommendationsView,
    RecipeRecommendationsView,
)

app_name = "recommendations"

urlpatterns = [
    path("recipes/", RecipeRecommendationsView.as_view(), name="recipes"),
    path("courses/", CourseRecommendationsView.as_view(), name="courses"),
]
