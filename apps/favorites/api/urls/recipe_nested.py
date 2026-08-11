"""Favorite routes nested under ``/api/v1/recipes/``  mounted by config."""

from __future__ import annotations

from django.urls import path

from apps.favorites.api.views.favorite_views import RecipeFavoriteView

app_name = "recipe_favorites"

urlpatterns = [
    path("<str:slug>/favorite/", RecipeFavoriteView.as_view(), name="toggle"),
]
