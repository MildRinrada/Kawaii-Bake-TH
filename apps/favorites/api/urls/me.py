"""The favorites list, nested under ``/api/v1/users/``  mounted by config.

``me`` is in ``RESERVED_USERNAMES``, and this two-segment pattern cannot
collide with the users app's single-segment ``<username>/`` route.
"""

from __future__ import annotations

from django.urls import path

from apps.favorites.api.views.favorite_views import MyFavoritesView

app_name = "my_favorites"

urlpatterns = [
    path("me/favorites/", MyFavoritesView.as_view(), name="list"),
]
