"""Review routes nested under ``/api/v1/recipes/``  mounted by config.

The shared prefix is a config concern, not app coupling (the lessons
precedent, ADR 0009). These two-segment patterns cannot collide with the
recipes app's own routes.
"""

from __future__ import annotations

from django.urls import path

from apps.reviews.api.views.review_views import (
    RecipeRatingView,
    RecipeReviewListCreateView,
)

app_name = "recipe_reviews"

urlpatterns = [
    path(
        "<str:slug>/reviews/",
        RecipeReviewListCreateView.as_view(),
        name="list",
    ),
    path("<str:slug>/rating/", RecipeRatingView.as_view(), name="rating"),
]
