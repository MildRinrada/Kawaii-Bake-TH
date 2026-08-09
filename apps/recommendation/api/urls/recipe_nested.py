"""Substitution route nested under ``/api/v1/recipes/`` — mounted by config.

The shared prefix is a config concern, not app coupling (the lessons
precedent, ADR 0009). The two-segment pattern cannot collide with the
recipes app's own routes.
"""

from __future__ import annotations

from django.urls import path

from apps.recommendation.api.views import RecipeSubstitutionsView

app_name = "recipe_substitutions"

urlpatterns = [
    path(
        "<str:slug>/substitutions/",
        RecipeSubstitutionsView.as_view(),
        name="list",
    ),
]
