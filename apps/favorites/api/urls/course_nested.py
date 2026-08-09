"""Favorite routes nested under ``/api/v1/courses/`` — mounted by config."""

from __future__ import annotations

from django.urls import path

from apps.favorites.api.views.favorite_views import CourseFavoriteView

app_name = "course_favorites"

urlpatterns = [
    path("<str:slug>/favorite/", CourseFavoriteView.as_view(), name="toggle"),
]
