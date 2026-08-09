"""Recipe category API routes, mounted at ``/api/v1/recipe-categories/``."""

from __future__ import annotations

from django.urls import path

from apps.recipe_categories.api.views.category_views import CategoryListView

app_name = "recipe_categories"

urlpatterns = [
    path("", CategoryListView.as_view(), name="list"),
]
