"""Favorites serializers  public API."""

from __future__ import annotations

from apps.favorites.api.serializers.favorite_serializers import (
    FavoriteItemSerializer,
    FavoriteListQuerySerializer,
)

__all__ = ["FavoriteItemSerializer", "FavoriteListQuerySerializer"]
