"""Test data builders for the favorites domain."""

from __future__ import annotations

from typing import Any

from apps.favorites.models import Favorite


def create_favorite(*, user: Any, recipe: Any = None, course: Any = None) -> Favorite:
    """Create a favorite directly at the model layer."""
    return Favorite.objects.create(user=user, recipe=recipe, course=course)
